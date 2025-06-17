import graphviz
from spin_to_prism_model.translation import SPINtoPRISM, TransitionType


class CPIToSPINConverter:
    """
    Converts CPI (Control Process Interface) format to SPIN model format.
    
    Efficient translation following BPMN+CPI pattern:
    - Each region adds at most 2 places (entry and exit)
    - Sequences add no intermediate places (direct connection)
    - Task input places get the task duration, all others have duration 0
    """
    
    def __init__(self):
        self.spin_model = SPINtoPRISM()
        self.place_counter = 0
        self.transition_counter = 0
        
    def get_next_place_name(self, prefix="p"):
        """Generate next place name"""
        name = f"{prefix}{self.place_counter}"
        self.place_counter += 1
        return name
        
    def get_next_transition_name(self, prefix="t"):
        """Generate next transition name"""
        name = f"{prefix}{self.transition_counter}"
        self.transition_counter += 1
        return name
    
    def convert_cpi_to_spin(self, cpi_dict):
        """
        Main conversion function from CPI dictionary to SPIN model.
        """
        # Reset counters
        self.place_counter = 0
        self.transition_counter = 0
        self.spin_model = SPINtoPRISM()
        
        # Create initial place (duration 0)
        start_place = self.get_next_place_name("start")
        self.spin_model.add_place(start_place, duration=0, is_initial=True)
        
        # Create end place (duration 0)
        end_place = self.get_next_place_name("end")
        self.spin_model.add_place(end_place, duration=0)
        
        # Convert the root region
        self._convert_region(cpi_dict, start_place, end_place)
        
        return self.spin_model
    
    def _convert_region(self, region, input_place, output_place):
        """Recursively convert a CPI region to SPIN places and transitions."""
        region_type = region['type']
        
        if region_type == 'task':
            self._convert_task(region, input_place, output_place)
        elif region_type == 'sequence':
            self._convert_sequence(region, input_place, output_place)
        elif region_type == 'parallel':
            self._convert_parallel(region, input_place, output_place)
        elif region_type == 'choice':
            self._convert_choice(region, input_place, output_place)
        elif region_type == 'nature':
            self._convert_nature(region, input_place, output_place)
        elif region_type == 'loop':
            self._convert_loop(region, input_place, output_place)
        else:
            raise ValueError(f"Unknown region type: {region_type}")
    
    def _convert_task(self, task_region, input_place, output_place):
        """Convert a task region to SPIN task transition
        
        Pattern: input_place --[task_transition]--> output_place
        """
        transition_name = self.get_next_transition_name(f"task{task_region['id']}")
        
        # Set the duration on the input place (where time is spent)
        if input_place in self.spin_model.places:
            self.spin_model.places[input_place].duration = task_region['duration']
        else:
            self.spin_model.add_place(input_place, duration=task_region['duration'])
        
        # Extract impact vector
        impacts = task_region.get('impacts', {})
        impact_vector = [impacts[k] for k in sorted(impacts.keys())] if impacts else []
        
        # Create task transition
        self.spin_model.add_transition(
            transition_name,
            TransitionType.TASK,
            [input_place],
            [output_place],
            impact_vector=impact_vector
        )
    
    def _convert_sequence(self, seq_region, input_place, output_place):
        """Convert a sequence region (head then tail)
        
        Pattern: input_place --> head --> intermediate --> tail --> output_place
        Adds 0 places (reuses input/output, creates 1 intermediate)
        """
        # Create only one intermediate place between head and tail
        intermediate_place = self.get_next_place_name(f"seq{seq_region['id']}_mid")
        self.spin_model.add_place(intermediate_place, duration=0)
        
        # Convert head and tail
        self._convert_region(seq_region['head'], input_place, intermediate_place)
        self._convert_region(seq_region['tail'], intermediate_place, output_place)
    
    def _convert_parallel(self, par_region, input_place, output_place):
        """Convert a parallel region (concurrent execution)

        Pattern: input --[split]--> branch1 --[merge]--> output
                                 \\--> branch2 ----/
        Adds 2 places (one for each branch end)
        """
        split_name = self.get_next_transition_name(f"split{par_region['id']}")
        merge_name = self.get_next_transition_name(f"merge{par_region['id']}")
        
        # Create end places for each branch
        first_end = self.get_next_place_name(f"par{par_region['id']}_first_end")
        second_end = self.get_next_place_name(f"par{par_region['id']}_second_end")
        
        self.spin_model.add_place(first_end, duration=0)
        self.spin_model.add_place(second_end, duration=0)
        
        # Create start places for each branch
        first_start = self.get_next_place_name(f"par{par_region['id']}_first_start")
        second_start = self.get_next_place_name(f"par{par_region['id']}_second_start")
        
        self.spin_model.add_place(first_start, duration=0)
        self.spin_model.add_place(second_start, duration=0)
        
        # Split transition
        self.spin_model.add_transition(
            split_name,
            TransitionType.PARALLEL_SPLIT,
            [input_place],
            [first_start, second_start]
        )
        
        # Convert both branches
        self._convert_region(par_region['first_split'], first_start, first_end)
        self._convert_region(par_region['second_split'], second_start, second_end)
        
        # Merge transition
        self.spin_model.add_transition(
            merge_name,
            TransitionType.PARALLEL_MERGE,
            [first_end, second_end],
            [output_place]
        )
    
    def _convert_choice(self, choice_region, input_place, output_place):
        """Convert a choice region (non-deterministic choice)

        Pattern: input --[choice]--> branch1 --[single]--> output
                                 \\--> branch2 --[single]---/
        Adds 2 places (entry for each branch)
        """

        choice_name = self.get_next_transition_name(f"choice{choice_region['id']}")
        
        # Create entry places for each branch
        true_entry = self.get_next_place_name(f"choice{choice_region['id']}_true")
        false_entry = self.get_next_place_name(f"choice{choice_region['id']}_false")
        
        self.spin_model.add_place(true_entry, duration=0)
        self.spin_model.add_place(false_entry, duration=0)
        
        # Choice transition
        self.spin_model.add_transition(
            choice_name,
            TransitionType.CHOICE,
            [input_place],
            [true_entry, false_entry]
        )
        
        # Convert both branches directly to output
        self._convert_region(choice_region['true'], true_entry, output_place)
        self._convert_region(choice_region['false'], false_entry, output_place)
    
    def _convert_nature(self, nature_region, input_place, output_place):
        """Convert a nature region (probabilistic choice)

        Pattern: input --[nature_prob]--> branch1 --[single]--> output
                                     \\--> branch2 --[single]---/
        Adds 2 places (entry for each branch)
        """

        nature_name = self.get_next_transition_name(f"nature{nature_region['id']}")
        
        # Create entry places for each branch
        true_entry = self.get_next_place_name(f"nature{nature_region['id']}_true")
        false_entry = self.get_next_place_name(f"nature{nature_region['id']}_false")
        
        self.spin_model.add_place(true_entry, duration=0)
        self.spin_model.add_place(false_entry, duration=0)
        
        # Nature transition with probability
        self.spin_model.add_transition(
            nature_name,
            TransitionType.NATURE,
            [input_place],
            [true_entry, false_entry],
            probability=nature_region['probability']
        )
        
        # Convert both branches directly to output
        self._convert_region(nature_region['true'], true_entry, output_place)
        self._convert_region(nature_region['false'], false_entry, output_place)
    
    def _convert_loop(self, loop_region, input_place, output_place):
        """Convert a loop region (probabilistic repetition)
        
        Pattern: input --> child_entry --> [child] --> child_exit --> decision
                                                           ^              |
                                                           |    [repeat]  |
                                                           +------<-------+
                                                                          |
                                                                    [exit]|
                                                                          v
                                                                      output
        Adds 2 places (child entry and decision point)
        """
        # Create places for loop structure
        child_entry = self.get_next_place_name(f"loop{loop_region['id']}_child_entry")
        decision_place = self.get_next_place_name(f"loop{loop_region['id']}_decision")
        
        self.spin_model.add_place(child_entry, duration=0)
        self.spin_model.add_place(decision_place, duration=0)
        
        # Initial transition to child (first execution)
        init_trans = self.get_next_transition_name(f"loop{loop_region['id']}_init")
        self.spin_model.add_transition(
            init_trans,
            TransitionType.SINGLE,
            [input_place],
            [child_entry]
        )
        
        # Convert child region to decision point
        self._convert_region(loop_region['child'], child_entry, decision_place)
        
        # Decision transition: repeat or exit
        decision_trans = self.get_next_transition_name(f"loop{loop_region['id']}_decision")
        self.spin_model.add_transition(
            decision_trans,
            TransitionType.NATURE,
            [decision_place],
            [child_entry, output_place],  # repeat or exit
            probability=loop_region['probability']  # probability of repeating
        )




def create_cpi_visualization(cpi_dict):
    """Create a Graphviz visualization of the CPI structure"""
    dot = graphviz.Digraph(comment="CPI Process", format='png')
    dot.attr(rankdir='LR')
    dot.attr('node', fontsize='10', fontname='Arial')
    dot.attr('edge', fontsize='8', fontname='Arial')
    
    def add_cpi_node(region):
        """Recursively add nodes for CPI regions"""
        node_id = f"{region['type']}{region['id']}"
        
        # Customize node appearance based on type
        if region['type'] == 'task':
            impacts_str = ', '.join([f"{k}:{v}" for k,v in region.get('impacts', {}).items()])
            label = f"{node_id}\\ndur:{region['duration']}\\n{impacts_str}"
            dot.node(node_id, label, shape='box', style='filled', color='lightgreen')
        elif region['type'] == 'nature':
            label = f"{node_id}\\np={region['probability']}"
            dot.node(node_id, label, shape='diamond', style='filled', color='lightcoral')
        elif region['type'] == 'choice':
            dot.node(node_id, node_id, shape='diamond', style='filled', color='lightblue')
        elif region['type'] == 'sequence':
            dot.node(node_id, node_id, shape='box', style='filled', color='lightyellow')
        elif region['type'] == 'parallel':
            dot.node(node_id, node_id, shape='box', style='filled', color='lightpink')
        elif region['type'] == 'loop':
            label = f"{node_id}\\nrep_p={region['probability']}"
            dot.node(node_id, label, shape='box', style='filled', color='lightgray')
        else:
            dot.node(node_id, node_id, shape='ellipse')
        
        # Add edges based on region type
        if region['type'] == 'sequence':
            head_id = f"{region['head']['type']}{region['head']['id']}"
            tail_id = f"{region['tail']['type']}{region['tail']['id']}"
            dot.edge(node_id, head_id, label='head')
            dot.edge(node_id, tail_id, label='tail')
            add_cpi_node(region['head'])
            add_cpi_node(region['tail'])
        elif region['type'] == 'parallel':
            first_id = f"{region['first_split']['type']}{region['first_split']['id']}"
            second_id = f"{region['second_split']['type']}{region['second_split']['id']}"
            dot.edge(node_id, first_id, label='first')
            dot.edge(node_id, second_id, label='second')
            add_cpi_node(region['first_split'])
            add_cpi_node(region['second_split'])
        elif region['type'] in ['choice', 'nature']:
            true_id = f"{region['true']['type']}{region['true']['id']}"
            false_id = f"{region['false']['type']}{region['false']['id']}"
            dot.edge(node_id, true_id, label='true')
            dot.edge(node_id, false_id, label='false')
            add_cpi_node(region['true'])
            add_cpi_node(region['false'])
        elif region['type'] == 'loop':
            child_id = f"{region['child']['type']}{region['child']['id']}"
            dot.edge(node_id, child_id, label='child')
            dot.edge(child_id, node_id, label='repeat', style='dashed', color='gray')
            add_cpi_node(region['child'])
    
    add_cpi_node(cpi_dict)
    return dot

def create_spin_visualization(spin_model: SPINtoPRISM):
    """Create a Graphviz visualization of the SPIN model"""
    dot = graphviz.Digraph(comment="SPIN Model", format='png')
    dot.attr(rankdir='LR')
    dot.attr('node', fontsize='10', fontname='Arial')
    dot.attr('edge', fontsize='8', fontname='Arial')
    
    # Add places
    for name, place in spin_model.places.items():
        if place.is_initial:
            shape = 'doublecircle'
            color = 'lightblue'
            style = 'filled'
        else:
            shape = 'circle'
            color = 'lightgray'
            style = 'filled'
            
        label = f"{name}\\nd={place.duration}"
        dot.node(name, label, shape=shape, color=color, style=style)
    
    # Add transitions and connections
    for transition in spin_model.transitions:
        # Create transition node with type-specific styling
        if transition.type.value == 'nature':
            label = f"{transition.name}\\np={transition.probability}"
            color = 'lightcoral'
            style = 'filled'
        elif transition.type.value == 'choice':
            label = f"{transition.name}\\n(choice)"
            color = 'lightblue'
            style = 'filled'
        elif transition.type.value == 'task':
            impact_str = str(transition.impact_vector) if transition.impact_vector else ""
            label = f"{transition.name}\\n{impact_str}"
            color = 'lightgreen'
            style = 'filled'
        elif transition.type.value == 'parallel_split':
            label = f"{transition.name}\\n(||split)"
            color = 'lightyellow'
            style = 'filled'
        elif transition.type.value == 'parallel_merge':
            label = f"{transition.name}\\n(||merge)"
            color = 'lightyellow'
            style = 'filled'
        else:
            label = transition.name
            color = 'white'
            style = 'filled'
            
        t_node = f"t_{transition.name}"
        dot.node(t_node, label, shape='box', color=color, style=style)
        
        # Add edges from input places to transition
        for p_in in transition.input_places:
            dot.edge(p_in, t_node, arrowsize='0.7')
            
        # Add edges from transition to output places
        for p_out in transition.output_places:
            dot.edge(t_node, p_out, arrowsize='0.7')
    
    return dot


def analyze_cpi_structure(region, depth=0):
    """Recursively analyze the CPI structure"""
    indent = "  " * depth
    region_type = region['type']
    region_id = region['id']
    
    print(f"{indent}{region_type}{region_id}")
    
    if region_type == 'task':
        print(f"{indent}  duration: {region['duration']}")
        if 'impacts' in region:
            print(f"{indent}  impacts: {region['impacts']}")
    elif region_type == 'loop':
        print(f"{indent}  repeat_probability: {region['probability']}")
        print(f"{indent}  child:")
        analyze_cpi_structure(region['child'], depth + 2)
    elif region_type == 'sequence':
        print(f"{indent}  head:")
        analyze_cpi_structure(region['head'], depth + 2)
        print(f"{indent}  tail:")
        analyze_cpi_structure(region['tail'], depth + 2)
    elif region_type == 'parallel':
        print(f"{indent}  first_split:")
        analyze_cpi_structure(region['first_split'], depth + 2)
        print(f"{indent}  second_split:")
        analyze_cpi_structure(region['second_split'], depth + 2)
    elif region_type in ['choice', 'nature']:
        if region_type == 'nature':
            print(f"{indent}  probability: {region['probability']}")
        print(f"{indent}  true:")
        analyze_cpi_structure(region['true'], depth + 2)
        print(f"{indent}  false:")
        analyze_cpi_structure(region['false'], depth + 2)


# Count regions in CPI
def count_cpi_regions(region):
    count = 1
    if region['type'] == 'sequence':
        count += count_cpi_regions(region['head'])
        count += count_cpi_regions(region['tail'])
    elif region['type'] == 'parallel':
        count += count_cpi_regions(region['first_split'])
        count += count_cpi_regions(region['second_split'])
    elif region['type'] in ['choice', 'nature']:
        count += count_cpi_regions(region['true'])
        count += count_cpi_regions(region['false'])
    elif region['type'] == 'loop':
        count += count_cpi_regions(region['child'])
    return count

# Count tasks in CPI
def count_cpi_tasks(region):
    count = 1 if region['type'] == 'task' else 0
    if region['type'] == 'sequence':
        count += count_cpi_tasks(region['head'])
        count += count_cpi_tasks(region['tail'])
    elif region['type'] == 'parallel':
        count += count_cpi_tasks(region['first_split'])
        count += count_cpi_tasks(region['second_split'])
    elif region['type'] in ['choice', 'nature']:
        count += count_cpi_tasks(region['true'])
        count += count_cpi_tasks(region['false'])
    elif region['type'] == 'loop':
        count += count_cpi_tasks(region['child'])
    return count


