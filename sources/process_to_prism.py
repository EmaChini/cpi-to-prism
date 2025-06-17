from spin_to_prism_model.formula_generators import generate_step_ready_formula, generate_closing_pending_formula, \
    generate_ready_pending_formula, generate_active_ready_pending_formula, generate_active_closing_pending_formula
from spin_to_prism_model.module_generators import generate_module
from spin_to_prism_model.rewards_generators import generate_rewards, integrate_rewards_to_mdp


def cpi_to_mdp(root_dict):
    """
    Convert a CPI (Configurable Process Instance) dictionary to an MDP (Markov Decision Process) model.
    
    Args:
        root_dict (dict): The root CPI dictionary containing the process structure
        
    Returns:
        str: The PRISM model as a string in .nm format
    """
    # Store all regions for formula generation
    regions = {}
    
    def collect_regions(node):
        """Recursively collect all regions from the CPI dictionary."""
        regions[node['id']] = node
        if node['type'] == 'sequence':
            collect_regions(node['head'])
            collect_regions(node['tail'])
        elif node['type'] == 'parallel':
            collect_regions(node['first_split'])
            collect_regions(node['second_split'])
        elif node['type'] in ['choice','nature']:
            collect_regions(node['true'])
            collect_regions(node['false'])
        else:
            raise ValueError(f"Unknown node type: {node['type']}")
    
    collect_regions(root_dict)
    
    # Generate formula definitions
    formulas = ["mdp\n\n// Formula definitions"]
    
    # Add ClosingPending formulas
    for region_id, region in sorted(regions.items()):
        closing_pending = generate_closing_pending_formula(region)
        if closing_pending:
            formulas.append(f"formula ClosingPending_{region['type']}{region_id} = {closing_pending};")
    
    formulas.append("")
    
    # Add ReadyPending formulas for all non-root regions
    non_root_regions = [(rid, r) for rid, r in sorted(regions.items()) if rid != root_dict['id']]
    
    for region_id, region in non_root_regions:
        ready_pending = generate_ready_pending_formula(region, root_dict, regions)
        if ready_pending:
            formulas.append(f"formula ReadyPending_{region['type']}{region_id} = {ready_pending};")
    
    formulas.append("")
    
    # Get lists of regions with ready/closing pending for later use
    ready_pending_regions = [(rid, r) for rid, r in non_root_regions 
                           if generate_ready_pending_formula(r, root_dict, regions)]
    closing_pending_regions = [(rid, r) for rid, r in sorted(regions.items())
                             if generate_closing_pending_formula(r)]
    
    # Add ReadyPendingCleared and ClosingPendingCleared formulas
    ready_pending_terms = [f"!ReadyPending_{r['type']}{rid}" for rid, r in ready_pending_regions]
    closing_pending_terms = [f"!ClosingPending_{r['type']}{rid}" for rid, r in closing_pending_regions]
    
    formulas.append(f"formula ReadyPendingCleared = {' & '.join(ready_pending_terms)};")
    formulas.append(f"formula ClosingPendingCleared = {' & '.join(closing_pending_terms)};")
    formulas.append("")
    
    # Add StepReady formulas for tasks
    for region_id, region in sorted(regions.items()):
        if region['type'] == 'task':
            formula = generate_step_ready_formula(region)
            if formula:
                formulas.append(f"formula StepReady_task{region_id} = {formula};")
    
    formulas.append("")
    
    # Add StepAvailable formula
    step_ready_terms = [f"StepReady_task{region_id}" 
                       for region_id, region in regions.items() 
                       if region['type'] == 'task']
    formulas.append(f"formula StepAvailable = ReadyPendingCleared & ClosingPendingCleared & ({' | '.join(step_ready_terms)});")
    formulas.append("")
    
    # Add ActiveReadyPending formulas
    for region_id, region in ready_pending_regions:
        formula = generate_active_ready_pending_formula(region, root_dict, regions, ready_pending_regions)
        formulas.append(f"formula ActiveReadyPending_{region['type']}{region_id} = {formula};")
    
    formulas.append("")
    
    # Add ActiveClosingPending formulas
    for region_id, region in closing_pending_regions:
        formula = generate_active_closing_pending_formula(region, regions, closing_pending_regions)
        formulas.append(f"formula ActiveClosingPending_{region['type']}{region_id} = {formula};")
    
    formulas.append("")
    
    # Generate module definitions
    modules = []
    for region_id in sorted(regions.keys()):
        region = regions[region_id]
        modules.extend(generate_module(region, root_dict, regions))
        modules.append("")
    
    # Generate labels
    labels = ["\n// Labels for formulas"]
    
    # Labels for ClosingPending
    for region_id, region in sorted(regions.items()):
        closing_pending = generate_closing_pending_formula(region)
        if closing_pending:
            label = f'label "ClosingPending_{region["type"]}{region_id}" = {closing_pending};'
            labels.append(label)
    
    labels.append("")
    
    # Labels for ReadyPending
    for region_id, region in sorted(regions.items()):
        if region_id != root_dict['id']:
            ready_pending = generate_ready_pending_formula(region, root_dict, regions)
            if ready_pending:
                label = f'label "ReadyPending_{region["type"]}{region_id}" = {ready_pending};'
                labels.append(label)
    
    labels.append("")
    
    # Labels for ReadyPendingCleared and ClosingPendingCleared
    labels.append(f'label "ReadyPendingCleared" = {" & ".join(ready_pending_terms)};')
    labels.append(f'label "ClosingPendingCleared" = {" & ".join(closing_pending_terms)};')
    labels.append("")
    
    # Labels for StepReady
    for region_id, region in sorted(regions.items()):
        if region['type'] == 'task':
            step_ready = generate_step_ready_formula(region)
            if step_ready:
                label = f'label "StepReady_task{region_id}" = {step_ready};'
                labels.append(label)
    
    labels.append("")
    
    # Label for StepAvailable
    labels.append(f'label "StepAvailable" = ReadyPendingCleared & ClosingPendingCleared & ({" | ".join(step_ready_terms)});')
    labels.append("")
    
    # Labels for ActiveReadyPending
    for region_id, region in ready_pending_regions:
        formula = generate_active_ready_pending_formula(region, root_dict, regions, ready_pending_regions)
        label = f'label "ActiveReadyPending_{region["type"]}{region_id}" = {formula};'
        labels.append(label)
    
    labels.append("")
    
    # Labels for ActiveClosingPending
    for region_id, region in closing_pending_regions:
        formula = generate_active_closing_pending_formula(region, regions, closing_pending_regions)
        label = f'label "ActiveClosingPending_{region["type"]}{region_id}" = {formula};'
        labels.append(label)
    
    mdp_content = '\n'.join(formulas + modules + labels)

    # Generate and integrate rewards sections
    rewards_content = generate_rewards(root_dict)

    # Combine everything into final output
    return integrate_rewards_to_mdp(mdp_content, rewards_content)

