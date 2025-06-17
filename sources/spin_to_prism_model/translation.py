import graphviz
from typing import Dict, List, Tuple, Union
from dataclasses import dataclass
from enum import Enum

class TransitionType(Enum):
    SINGLE = "single"
    TASK = "task"
    CHOICE = "choice"
    NATURE = "nature"
    PARALLEL_SPLIT = "parallel_split"
    PARALLEL_MERGE = "parallel_merge"

@dataclass
class Place:
    name: str
    duration: int
    is_initial: bool = False
    
@dataclass
class Transition:
    name: str
    type: TransitionType
    input_places: List[str]
    output_places: List[str]
    probability: float = 1.0  # For nature transitions
    impact_vector: List[float] = None  # For task transitions
    
    def __post_init__(self):
        if self.impact_vector is None:
            self.impact_vector = []

class SPINtoPRISM:
    def __init__(self):
        self.places: Dict[str, Place] = {}
        self.transitions: List[Transition] = []
        self.initial_place: str = None
        
    def add_place(self, name: str, duration: int, is_initial: bool = False):
        """Add a place to the SPIN model"""
        self.places[name] = Place(name, duration, is_initial)
        if is_initial:
            self.initial_place = name
            
    def add_transition(self, name: str, type_: TransitionType, 
                      input_places: List[str], output_places: List[str],
                      probability: float = 1.0, impact_vector: List[float] = None):
        """Add a transition to the SPIN model"""
        self.transitions.append(Transition(
            name, type_, input_places, output_places, 
            probability, impact_vector or []
        ))
        
    def get_sorted_places(self) -> List[str]:
        """Get places sorted lexicographically"""
        return sorted(self.places.keys())
        
    def get_sorted_transitions(self) -> List[Transition]:
        """Get transitions sorted lexicographically by name"""
        return sorted(self.transitions, key=lambda t: t.name)
        
    def generate_prism_variables(self) -> str:
        """Generate PRISM global variables for places"""
        lines = ["mdp \n"]
        lines.append("// Global variables for places")
        
        # Manager stage variable first
        lines.append("global STAGE : [0..5] init 0;")
        lines.append("")
        
        # All place_value variables
        lines.append("// Place value variables")
        for place_name in self.get_sorted_places():
            place = self.places[place_name]
            init_value = 0 if place.is_initial else -1
            lines.append(f"global {place_name}_value : [-1..{place.duration}] init {init_value};")
        
        lines.append("")
        
        # All place_updated variables
        lines.append("// Place updated variables")
        for place_name in self.get_sorted_places():
            lines.append(f"global {place_name}_updated : [0..1] init 0;")
            
        return "\n".join(lines)
    
    def generate_reward_structures(self) -> str:
        """Generate PRISM reward structures for impacts"""
        lines = []
        impact_dims = self.get_impact_dimensions()
        
        if impact_dims == 0:
            return ""
        
        # Create reward structure for each impact dimension
        for i in range(impact_dims):
            lines.append(f'rewards "impact_{i}"')
            
            # Add rewards for each task transition that has impacts
            for transition in self.transitions:
                if (transition.type == TransitionType.TASK and 
                    transition.impact_vector and 
                    i < len(transition.impact_vector) and 
                    transition.impact_vector[i] != 0):
                    
                    # Reward is given when the task fires (using action label)
                    lines.append(f'  [fire_{transition.name}] true : {transition.impact_vector[i]};')
            
            lines.append("endrewards")
            lines.append("")
        
        return "\n".join(lines)

    def get_impact_dimensions(self) -> int:
        """Get the number of impact dimensions from transitions"""
        max_dims = 0
        for transition in self.transitions:
            if transition.impact_vector:
                max_dims = max(max_dims, len(transition.impact_vector))
        return max_dims

    def generate_manager_module(self) -> str:
        """Generate the manager module"""
        lines = ["module manager"]
        
        # Stage transitions
        lines.append("  // Stage 0 -> 3: Can do step")
        lines.append("  [] STAGE=0 & psi_step -> (STAGE'=3);")
        
        lines.append("  // Stage 0 -> 2: Terminated")
        lines.append("  [] STAGE=0 & !psi_step & psi_noone_idle & !psi_atleastone_active -> (STAGE'=2);")
        
        lines.append("  // Stage 0 -> 4: Fire transitions (FIXED: added psi_noone_idle)")
        lines.append("  [] STAGE=0 & !psi_step & psi_noone_idle & psi_atleastone_active -> (STAGE'=4);")
        
        # Stage 3: Update places
        for place_name in self.get_sorted_places():
            place = self.places[place_name]
            lines.append(f"  // Update {place_name}")
            lines.append(f"  [] STAGE=3 & step_updated_{place_name} & {place_name}_value=-1 -> ({place_name}_updated'=1);")
            lines.append(f"  [] STAGE=3 & step_updated_{place_name} & {place_name}_value>=0 & {place_name}_value<{place.duration} -> ({place_name}_value'={place_name}_value+1) & ({place_name}_updated'=1);")
            lines.append(f"  [] STAGE=3 & step_updated_{place_name} & {place_name}_value={place.duration} -> ({place_name}_updated'=1);")
            
        lines.append("  // Stage 3 -> 1: All updated")
        lines.append("  [] STAGE=3 & psi_all_step_updated -> (STAGE'=1);")
        
        # Stage 1: Reset updated flags
        for place_name in self.get_sorted_places():
            lines.append(f"  [] STAGE=1 & step_not_updated_{place_name} -> ({place_name}_updated'=0);")
            
        lines.append("  // Stage 1 -> 0: All reset")
        lines.append("  [] STAGE=1 & psi_all_step_not_updated -> (STAGE'=0);")
        
        # Stage 4 -> 5: All non-nature transitions processed
        # Check if nature is present
        natures_exists = False
        for transition in self.transitions:
            if transition.type == TransitionType.NATURE:
                natures_exists = True
                break

        if natures_exists:
            lines.append("  [] STAGE=4 & psi_all_idle_but_nature -> (STAGE'=5);")
            lines.append("  [] STAGE=5 & psi_all_idle_nature -> (STAGE'=0);")
        else:
            lines.append("  [] STAGE=4 & psi_all_idle_but_nature -> (STAGE'=0);")

        lines.append("endmodule")
        return "\n".join(lines)
    
    def generate_transition_modules(self) -> str:
        """Generate modules for transitions"""
        lines = []
        
        for transition in self.get_sorted_transitions():
            lines.append(f"module {transition.name}")
            lines.append(f"  {transition.name}_state : [-1..1] init 0;")
            
            # Stage 0: Determine if transition should be activated or deactivated
            lines.append(f"  // Stage 0: Activation check")
            
            # Build condition for all incoming places meeting their duration
            duration_conditions = []
            for p_in in transition.input_places:
                place = self.places[p_in]
                duration_conditions.append(f"{p_in}_value >= {place.duration}")
            
            all_duration_met = " & ".join(duration_conditions)
            
            # Rule 1: LABEL HERE for TASK transitions (decision to fire)
            if transition.type == TransitionType.TASK:
                action_label = f"[fire_{transition.name}]"
            else:
                action_label = "[]"
            
            lines.append(f"  {action_label} STAGE=0 & psi_idle_{transition.name} & ({all_duration_met}) -> ({transition.name}_state'=1);")
            
            # Rule 2: NO LABEL - just deactivation  
            lines.append(f"  [] STAGE=0 & psi_idle_{transition.name} & !({all_duration_met}) -> ({transition.name}_state'=-1);")
            
            if transition.type != TransitionType.NATURE:
                # Non-nature transitions (Stage 4) - NO LABELS, just mechanical execution
                lines.append(f"  // Stage 4: Non-nature transition firing")
                lines.append(f"  [] STAGE=4 & psi_first_but_nature_not_idle_{transition.name} & {transition.name}_state=-1 -> ({transition.name}_state'=0);")
                
                # Fire transition based on type - NO LABELS (mechanical execution)
                if transition.type == TransitionType.SINGLE or transition.type == TransitionType.TASK:
                    p_in = transition.input_places[0]
                    p_out = transition.output_places[0]
                    lines.append(f"  [] STAGE=4 & psi_first_but_nature_not_idle_{transition.name} & {transition.name}_state=1 -> ({transition.name}_state'=0) & ({p_in}_value'=-1) & ({p_out}_value'=0);")
                    
                elif transition.type == TransitionType.PARALLEL_SPLIT:
                    p_in = transition.input_places[0]
                    p_out1, p_out2 = transition.output_places
                    lines.append(f"  [] STAGE=4 & psi_first_but_nature_not_idle_{transition.name} & {transition.name}_state=1 -> ({transition.name}_state'=0) & ({p_in}_value'=-1) & ({p_out1}_value'=0) & ({p_out2}_value'=0);")
                    
                elif transition.type == TransitionType.PARALLEL_MERGE:
                    p_in1, p_in2 = transition.input_places
                    p_out = transition.output_places[0]
                    lines.append(f"  [] STAGE=4 & psi_first_but_nature_not_idle_{transition.name} & {transition.name}_state=1 -> ({transition.name}_state'=0) & ({p_in1}_value'=-1) & ({p_in2}_value'=-1) & ({p_out}_value'=0);")
                    
                elif transition.type == TransitionType.CHOICE:
                    p_in = transition.input_places[0]
                    p_true, p_false = transition.output_places
                    lines.append(f"  [] STAGE=4 & psi_first_but_nature_not_idle_{transition.name} & {transition.name}_state=1 -> ({transition.name}_state'=0) & ({p_in}_value'=-1) & ({p_true}_value'=0);")
                    lines.append(f"  [] STAGE=4 & psi_first_but_nature_not_idle_{transition.name} & {transition.name}_state=1 -> ({transition.name}_state'=0) & ({p_in}_value'=-1) & ({p_false}_value'=0);")
                    
            else:
                # Nature transitions (Stage 5) - NO LABELS
                lines.append(f"  // Stage 5: Nature transition firing")
                lines.append(f"  [] STAGE=5 & psi_first_nature_not_idle_{transition.name} & {transition.name}_state=-1 -> ({transition.name}_state'=0);")
                
                # Fire nature transition with probability - NO LABEL
                p_in = transition.input_places[0]
                p_true, p_false = transition.output_places
                prob = transition.probability
                lines.append(f"  [] STAGE=5 & psi_first_nature_not_idle_{transition.name} & {transition.name}_state=1 -> {prob}: ({transition.name}_state'=0) & ({p_true}_value'=0) & ({p_in}_value'=-1) + {1-prob}: ({transition.name}_state'=0) & ({p_false}_value'=0) & ({p_in}_value'=-1);")
            
            lines.append("endmodule")
            lines.append("")
            
        return "\n".join(lines)
        
    def generate_formulas(self) -> str:
        """Generate PRISM formulas and labels"""
        lines = ["// Formulas"]
        
        # is_active formulas for each transition
        for transition in self.get_sorted_transitions():
            conditions = []
            for p_in in transition.input_places:
                place = self.places[p_in]
                conditions.append(f"({p_in}_value >= {place.duration})")
            lines.append(f"formula is_active_{transition.name} = {' & '.join(conditions)};")
        
        # psi_at_least_one_remaining_duration: at least one place has a token but hasn't met its duration
        remaining_duration_conditions = []
        for place_name in self.get_sorted_places():
            place = self.places[place_name]
            remaining_duration_conditions.append(f"({place_name}_value >= 0 & {place_name}_value < {place.duration})")
        lines.append(f"formula psi_at_least_one_remaining_duration = {' | '.join(remaining_duration_conditions)};")
        
        # psi_step formula (MODIFIED): no transitions active AND at least one place can advance
        not_active_conditions = [f"!is_active_{t.name}" for t in self.get_sorted_transitions()]
        lines.append(f"formula psi_step = ({' & '.join(not_active_conditions)}) & psi_at_least_one_remaining_duration;")
        
        # Step update formulas for places
        for i, place_name in enumerate(self.get_sorted_places()):
            if i == 0:
                lines.append(f"formula step_updated_{place_name} = {place_name}_updated=0;")
            else:
                prev_conditions = [f"{p}_updated=1" for p in self.get_sorted_places()[:i]]
                lines.append(f"formula step_updated_{place_name} = {place_name}_updated=0 & {' & '.join(prev_conditions)};")
                
        # All step updated formula
        all_updated = [f"{p}_updated=1" for p in self.get_sorted_places()]
        lines.append(f"formula psi_all_step_updated = {' & '.join(all_updated)};")
        
        # Step not updated formulas
        for i, place_name in enumerate(self.get_sorted_places()):
            if i == 0:
                lines.append(f"formula step_not_updated_{place_name} = {place_name}_updated=1;")
            else:
                prev_conditions = [f"{p}_updated=0" for p in self.get_sorted_places()[:i]]
                lines.append(f"formula step_not_updated_{place_name} = {place_name}_updated=1 & {' & '.join(prev_conditions)};")
                
        # All step not updated formula
        all_not_updated = [f"{p}_updated=0" for p in self.get_sorted_places()]
        lines.append(f"formula psi_all_step_not_updated = {' & '.join(all_not_updated)};")
        
        # FIXED: Generate psi_idle formulas with proper ordering (psi_first_idle pattern)
        all_transitions = self.get_sorted_transitions()
        for i, transition in enumerate(all_transitions):
            if i == 0:
                lines.append(f"formula psi_idle_{transition.name} = !psi_step & {transition.name}_state=0;")
            else:
                prev_conditions = [f"{t.name}_state!=0" for t in all_transitions[:i]]
                lines.append(f"formula psi_idle_{transition.name} = !psi_step & {transition.name}_state=0 & {' & '.join(prev_conditions)};")
        
        # Transition ordering formulas
        non_nature_transitions = [t for t in self.get_sorted_transitions() if t.type != TransitionType.NATURE]
        nature_transitions = [t for t in self.get_sorted_transitions() if t.type == TransitionType.NATURE]
        
        # Ordering formulas for non-nature transitions        
        for i, transition in enumerate(non_nature_transitions):
            if i == 0:
                lines.append(f"formula psi_first_but_nature_not_idle_{transition.name} = {transition.name}_state!=0;")
            else:
                prev_conditions = [f"{t.name}_state=0" for t in non_nature_transitions[:i]]
                lines.append(f"formula psi_first_but_nature_not_idle_{transition.name} = {transition.name}_state!=0 & {' & '.join(prev_conditions)};")
                
        # Ordering formulas for nature transitions
        for i, transition in enumerate(nature_transitions):
            if i == 0:
                lines.append(f"formula psi_first_nature_not_idle_{transition.name} = {transition.name}_state!=0;")
            else:
                prev_conditions = [f"{t.name}_state=0" for t in nature_transitions[:i]]
                lines.append(f"formula psi_first_nature_not_idle_{transition.name} = {transition.name}_state!=0 & {' & '.join(prev_conditions)};")
        
        # All idle formulas
        if non_nature_transitions:
            all_idle_but_nature = [f"{t.name}_state=0" for t in non_nature_transitions]
            lines.append(f"formula psi_all_idle_but_nature = {' & '.join(all_idle_but_nature)};")
            
        if nature_transitions:
            all_idle_nature = [f"{t.name}_state=0" for t in nature_transitions]
            lines.append(f"formula psi_all_idle_nature = {' & '.join(all_idle_nature)};")
        
        # Other helper formulas
        all_states_not_idle = []
        for transition in self.get_sorted_transitions():
            all_states_not_idle.append(f"{transition.name}_state!=0")
        if all_states_not_idle:
            lines.append(f"formula psi_noone_idle = {' & '.join(all_states_not_idle)};")
            lines.append(f"formula psi_atleastone_active = {' | '.join([f'is_active_{t.name}' for t in self.get_sorted_transitions()])};")
        
        # ADD STATE LABELS
        lines.append("")
        lines.append("// State Labels for Simulator")
        
        # Labels for ALL psi formulas
        lines.append('label "psi_step" = psi_step;')
        lines.append('label "psi_at_least_one_remaining_duration" = psi_at_least_one_remaining_duration;')
        lines.append('label "psi_all_step_updated" = psi_all_step_updated;')
        lines.append('label "psi_all_step_not_updated" = psi_all_step_not_updated;')
        lines.append('label "psi_noone_idle" = psi_noone_idle;')
        lines.append('label "psi_atleastone_active" = psi_atleastone_active;')
        
        # Labels for psi_idle formulas
        for transition in self.get_sorted_transitions():
            lines.append(f'label "psi_idle_{transition.name}" = psi_idle_{transition.name};')
        
        # Labels for psi_first_but_nature_not_idle formulas
        for transition in non_nature_transitions:
            lines.append(f'label "psi_first_but_nature_not_idle_{transition.name}" = psi_first_but_nature_not_idle_{transition.name};')
        
        # Labels for psi_first_nature_not_idle formulas  
        for transition in nature_transitions:
            lines.append(f'label "psi_first_nature_not_idle_{transition.name}" = psi_first_nature_not_idle_{transition.name};')
        
        # Labels for psi_all_idle formulas
        if non_nature_transitions:
            lines.append('label "psi_all_idle_but_nature" = psi_all_idle_but_nature;')
        if nature_transitions:
            lines.append('label "psi_all_idle_nature" = psi_all_idle_nature;')
        
        # Labels for step_updated formulas
        for place_name in self.get_sorted_places():
            lines.append(f'label "step_updated_{place_name}" = step_updated_{place_name};')
            lines.append(f'label "step_not_updated_{place_name}" = step_not_updated_{place_name};')
        
        # Labels for is_active formulas
        for transition in self.get_sorted_transitions():
            lines.append(f'label "is_active_{transition.name}" = is_active_{transition.name};')
        
        # Labels for stages
        lines.append('label "stage_0" = STAGE=0;')
        lines.append('label "stage_1" = STAGE=1;')
        lines.append('label "stage_2" = STAGE=2;')
        lines.append('label "stage_3" = STAGE=3;')
        lines.append('label "stage_4" = STAGE=4;')
        lines.append('label "stage_5" = STAGE=5;')
        
        # Labels for transition states
        for transition in self.get_sorted_transitions():
            lines.append(f'label "state_{transition.name}_ready" = {transition.name}_state=1;')
            lines.append(f'label "state_{transition.name}_disabled" = {transition.name}_state=-1;')
            lines.append(f'label "state_{transition.name}_idle" = {transition.name}_state=0;')
        
        # Labels for place states
        for place_name in self.get_sorted_places():
            place = self.places[place_name]
            lines.append(f'label "place_{place_name}_empty" = {place_name}_value=-1;')
            lines.append(f'label "place_{place_name}_has_token" = {place_name}_value>=0;')
            lines.append(f'label "place_{place_name}_duration_met" = {place_name}_value>={place.duration};')
            lines.append(f'label "place_{place_name}_can_advance" = {place_name}_value>=0 & {place_name}_value<{place.duration};')
            lines.append(f'label "place_{place_name}_updated" = {place_name}_updated=1;')
        
        return "\n".join(lines)
        
    def generate_prism_model(self) -> str:
        """Generate complete PRISM model"""
        sections = [
            self.generate_prism_variables(),
            "",
            self.generate_formulas(),
            "",
            self.generate_manager_module(),
            "",
            self.generate_transition_modules(),
            "",
            self.generate_reward_structures() 
        ]
        return "\n".join(sections)
        
    def print_model_summary(self):
        """Print a summary of the model"""
        print("=== SPIN to PRISM Translation ===")
        print(f"Places: {len(self.places)}")
        for name, place in sorted(self.places.items()):
            initial_marker = " (INITIAL)" if place.is_initial else ""
            print(f"  {name}: duration={place.duration}{initial_marker}")
            
        print(f"\nTransitions: {len(self.transitions)}")
        for transition in self.get_sorted_transitions():
            print(f"  {transition.name} ({transition.type.value}): {transition.input_places} -> {transition.output_places}")
            if transition.type == TransitionType.NATURE:
                print(f"    Probability: {transition.probability}")
            if transition.impact_vector:
                print(f"    Impact: {transition.impact_vector}")
                
    def visualize_spin(self):
        """Create a Graphviz visualization of the SPIN model"""
        dot = graphviz.Digraph(comment='SPIN Model')
        dot.attr(rankdir='LR')
        
        # Add places
        for name, place in self.places.items():
            shape = 'doublecircle' if place.is_initial else 'circle'
            label = f"{name}\\nd={place.duration}"
            dot.node(name, label, shape=shape)
            
        # Add transitions and connections
        for transition in self.transitions:
            # Create transition node
            if transition.type == TransitionType.NATURE:
                label = f"{transition.name}\\np={transition.probability}"
                color = 'red'
            elif transition.type == TransitionType.CHOICE:
                label = f"{transition.name}\\n(choice)"
                color = 'blue'
            elif transition.type == TransitionType.TASK:
                label = f"{transition.name}\\n{transition.impact_vector}"
                color = 'green'
            else:
                label = transition.name
                color = 'black'
                
            dot.node(f"t_{transition.name}", label, shape='box', color=color)
            
            # Add edges from input places to transition
            for p_in in transition.input_places:
                dot.edge(p_in, f"t_{transition.name}")
                
            # Add edges from transition to output places
            for p_out in transition.output_places:
                dot.edge(f"t_{transition.name}", p_out)
                
        return dot

# Example usage
def create_example_model():
    """Create an example SPIN model for testing"""
    model = SPINtoPRISM()
    
    # Add places
    model.add_place("p0", 1, is_initial=True)
    model.add_place("p1", 2)
    model.add_place("p2", 1)
    model.add_place("p3", 2)
    model.add_place("p4", 1)
    model.add_place("p5", 1)
    
    # Add transitions
    model.add_transition("t_start", TransitionType.TASK, ["p0"], ["p1"], impact_vector=[10, 1])
    model.add_transition("t_split", TransitionType.PARALLEL_SPLIT, ["p1"], ["p2", "p3"])
    model.add_transition("t_choice", TransitionType.CHOICE, ["p2"], ["p4", "p5"])
    model.add_transition("t_nature", TransitionType.NATURE, ["p3"], ["p4", "p5"], probability=0.7)
    
    return model

# Test the implementation
if __name__ == "__main__":
    model = create_example_model()
    #model.print_model_summary()
    #print("\n" + "="*50)
    #print("PRISM MODEL:")
    #print("="*50)
    print(model.generate_prism_model())
    
    # Visualize
    #viz = model.visualize_spin()
    #print(f"\nGraphviz DOT representation:")
    #sprint(viz.source)