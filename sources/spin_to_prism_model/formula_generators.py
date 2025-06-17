from .parent_info import get_parent_info

def generate_closing_pending_formula(region):
    """Generate ClosingPending formula for a region.
    
    Args:
        region (dict): Region dictionary containing type and ID
        
    Returns:
        str: The ClosingPending formula for this region, or empty string if not applicable
    """
    region_id = region['id']
    if region['type'] == 'task':
        return f"state{region_id}=3 & step{region_id}={region['duration']}"
    elif region['type'] == 'sequence':
        tail_id = region['tail']['id']
        return f"state{region_id}=3 & (state{tail_id}=4 | state{tail_id}=5)"
    elif region['type'] == 'parallel':
        first_id = region['first_split']['id']
        second_id = region['second_split']['id']
        return f"state{region_id}=3 & (state{first_id}=4 | state{first_id}=5) & (state{second_id}=4 | state{second_id}=5)"
    elif region['type'] in ['choice', 'nature']:
        true_id = region['true']['id']
        false_id = region['false']['id']
        return f"state{region_id}=3 & ((state{true_id}=4 | state{true_id}=5) | (state{false_id}=4 | state{false_id}=5))"
    return ""

def generate_ready_pending_formula(region, root_dict, regions):
    """Generate ReadyPending formula for a region.
    
    Args:
        region (dict): Region dictionary containing type and ID
        root_dict (dict): Root of the CPI dictionary
        regions (dict): Dictionary of all regions indexed by ID
        
    Returns:
        str: The ReadyPending formula for this region, or None if root
    """
    region_id = region['id']
    
    if region_id == root_dict['id']:
        return None
        
    parent_info = get_parent_info(region_id, root_dict, regions)
    parent_id = parent_info['parent_id']
    position = parent_info['position']
    
    if parent_id is None:
        raise ValueError(f"Error: non-root region {region_id} has no parent!")
        
    parent = regions[parent_id]
    base_condition = f"state{region_id}=1"
    
    if parent['type'] == 'sequence':
        if position == 'head':
            return f"{base_condition} & state{parent_id}=2"
        else:  # tail
            head_id = parent['head']['id']
            return f"{base_condition} & (state{parent_id}=2 | state{parent_id}=3) & (state{head_id}=4 | state{head_id}=5)"
    elif parent['type'] == 'parallel':
        return f"{base_condition} & (state{parent_id}=2 | state{parent_id}=3)"
    elif parent['type'] in ['choice', 'nature']:
        if position == 'true':
            return f"{base_condition} & (state{parent_id}=2 | state{parent_id}=3)"
        else:  # false
            true_id = parent['true']['id']
            return f"{base_condition} & (state{parent_id}=2 | state{parent_id}=3) & (state{true_id}=0 | state{true_id}=2)"
            
    raise ValueError(f"Unknown parent type: {parent['type']}")

def generate_step_ready_formula(region):
    """Generate StepReady formula for a task region.
    
    Args:
        region (dict): Task region dictionary
        
    Returns:
        str: The StepReady formula for this task, or None if not a task
    """
    if region['type'] != 'task':
        return None
        
    region_id = region['id']
    return f"(state{region_id}=2 | state{region_id}=3) & step{region_id} < {region['duration']}"

def generate_active_ready_pending_formula(region, root_dict, regions, ready_pending_regions):
    """Generate ActiveReadyPending formula for a region.
    
    Args:
        region (dict): Region dictionary
        root_dict (dict): Root of the CPI dictionary
        regions (dict): Dictionary of all regions indexed by ID
        ready_pending_regions (list): List of (id, type) tuples for regions with ReadyPending
        
    Returns:
        str: The ActiveReadyPending formula for this region
    """
    region_id = region['id']
    
    # Get all regions with smaller IDs that have ReadyPending
    prev_terms = [f"!ReadyPending_{regions[prev_id]['type']}{prev_id}" 
                 for prev_id, _ in ready_pending_regions 
                 if prev_id < region_id]
    
    if prev_terms:
        return f"ReadyPending_{region['type']}{region_id} & {' & '.join(prev_terms)}"
    return f"ReadyPending_{region['type']}{region_id}"

def generate_active_closing_pending_formula(region, regions, closing_pending_regions):
    """Generate ActiveClosingPending formula for a region.
    
    Args:
        region (dict): Region dictionary
        regions (dict): Dictionary of all regions indexed by ID
        closing_pending_regions (list): List of (id, type) tuples for regions with ClosingPending
        
    Returns:
        str: The ActiveClosingPending formula for this region
    """
    region_id = region['id']
    
    # Get all regions with smaller IDs that have ClosingPending
    prev_terms = [f"!ClosingPending_{regions[prev_id]['type']}{prev_id}" 
                 for prev_id, _ in closing_pending_regions 
                 if prev_id < region_id]
    
    if prev_terms:
        return f"ReadyPendingCleared & ClosingPending_{region['type']}{region_id} & {' & '.join(prev_terms)}"
    return f"ReadyPendingCleared & ClosingPending_{region['type']}{region_id}"

def generate_step_available_formula(task_regions):
    """Generate StepAvailable formula.
    
    Args:
        task_regions (list): List of task regions
        
    Returns:
        str: The StepAvailable formula
    """
    step_ready_terms = [f"StepReady_task{region['id']}" for region in task_regions]
    return f"ReadyPendingCleared & ClosingPendingCleared & ({' | '.join(step_ready_terms)})"

def generate_ready_pending_cleared_formula(ready_pending_regions, regions):
    """Generate ReadyPendingCleared formula.
    
    Args:
        ready_pending_regions (list): List of regions with ReadyPending
        regions (dict): Dictionary of all regions indexed by ID
        
    Returns:
        str: The ReadyPendingCleared formula
    """
    ready_pending_terms = [f"!ReadyPending_{regions[rid]['type']}{rid}" 
                          for rid, _ in ready_pending_regions]
    return " & ".join(ready_pending_terms)

def generate_closing_pending_cleared_formula(closing_pending_regions, regions):
    """Generate ClosingPendingCleared formula.
    
    Args:
        closing_pending_regions (list): List of regions with ClosingPending
        regions (dict): Dictionary of all regions indexed by ID
        
    Returns:
        str: The ClosingPendingCleared formula
    """
    closing_pending_terms = [f"!ClosingPending_{regions[rid]['type']}{rid}" 
                           for rid, _ in closing_pending_regions]
    return " & ".join(closing_pending_terms)