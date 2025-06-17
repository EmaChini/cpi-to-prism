def collect_tasks_with_impacts(node, tasks=None):
    """Recursively collect all tasks with their impacts from the CPI dictionary.
    
    Args:
        node (dict): Current node in the CPI dictionary
        tasks (list, optional): List to accumulate tasks. Defaults to None.
        
    Returns:
        list: List of tuples containing (task_id, impacts_dict)
    """
    if tasks is None:
        tasks = []
        
    if node['type'] == 'task' and 'impacts' in node:
        tasks.append((node['id'], node.get('impacts', {})))
        
    # Recursive traversal based on node type
    if node['type'] == 'sequence':
        collect_tasks_with_impacts(node['head'], tasks)
        collect_tasks_with_impacts(node['tail'], tasks)
    elif node['type'] == 'parallel':
        collect_tasks_with_impacts(node['first_split'], tasks)
        collect_tasks_with_impacts(node['second_split'], tasks)
    elif node['type'] in ['choice', 'nature']:
        collect_tasks_with_impacts(node['true'], tasks)
        collect_tasks_with_impacts(node['false'], tasks)
        
    return tasks

def generate_rewards(root_dict):
    """Generate rewards sections for the MDP model.
    
    Args:
        root_dict (dict): The root CPI dictionary containing the process structure
        
    Returns:
        str: The rewards sections as a string
    """

    # Collect all tasks with their impacts
    tasks_with_impacts = collect_tasks_with_impacts(root_dict)
    
    # Get unique impact names across all tasks
    all_impacts = set()
    for _, impacts in tasks_with_impacts:
        all_impacts.update(impacts.keys())
    
    # Generate rewards sections for each impact
    rewards_sections = []
    root_id = root_dict['id']
        
    for impact_name in sorted(all_impacts):
        rewards_lines = [f'rewards "{impact_name}"']
        
        # Add reward for each task that has this impact
        for task_id, impacts in tasks_with_impacts:
            if impact_name in impacts:
                impact_value = impacts[impact_name]
                # Format with just task state condition and running_to_complete action
                rewards_lines.append(f'    [running_to_completed_{root_dict["type"]}{root_id}] state{task_id}!=0 & state{task_id}!=1 : {impact_value};')
        
        rewards_lines.append('endrewards\n')
        rewards_sections.append('\n'.join(rewards_lines))
    
    return '\n'.join(rewards_sections)

def integrate_rewards_to_mdp(mdp_content, rewards_content):
    """Integrate rewards sections into the MDP model content.
    
    Args:
        mdp_content (str): Existing MDP model content
        rewards_content (str): Generated rewards sections
        
    Returns:
        str: Complete MDP model with rewards sections
    """
    # Add a blank line before rewards if needed
    if not mdp_content.endswith('\n\n'):
        if mdp_content.endswith('\n'):
            rewards_content = '\n' + rewards_content
        else:
            rewards_content = '\n\n' + rewards_content
            
    return mdp_content + rewards_content