def get_parent_info(child_id, root_dict, regions):
    """Find parent and child's position in parent by recursively traversing from root.
    
    Args:
        child_id (int): ID of the child node to find parent for
        root_dict (dict): Root of the CPI dictionary
        regions (dict): Dictionary of all regions indexed by ID
        
    Returns:
        dict: Parent information containing:
            - parent_id: ID of direct parent
            - position: Position in parent ('head', 'tail', 'true', 'false', etc.)
            - choice_info: Information about nearest choice/nature ancestor if any
    """
    def check_node(node, path=None):
        if path is None:
            path = []
            
        path = path + [(node['type'], node['id'])]
        
        if node['type'] == 'sequence':
            if node['head']['id'] == child_id:
                return node['id'], 'head', path
            if node['tail']['id'] == child_id:
                return node['id'], 'tail', path
            result = check_node(node['head'], path)
            if result[0] is not None:
                return result
            return check_node(node['tail'], path)
            
        elif node['type'] == 'parallel':
            if node['first_split']['id'] == child_id:
                return node['id'], 'first', path
            if node['second_split']['id'] == child_id:
                return node['id'], 'second', path
            result = check_node(node['first_split'], path)
            if result[0] is not None:
                return result
            return check_node(node['second_split'], path)
            
        elif node['type'] in ['choice', 'nature']:
            if node['true']['id'] == child_id:
                return node['id'], 'true', path
            if node['false']['id'] == child_id:
                return node['id'], 'false', path
            result = check_node(node['true'], path)
            if result[0] is not None:
                return result
            return check_node(node['false'], path)
            
        elif node['type'] == 'task':
            return None, None, path
            
        return None, None, path
            
    parent_id, position, path = check_node(root_dict)
    
    if parent_id is not None:
        # Find nearest choice/nature ancestor and siblings if any
        choice_info = None
        for node_type, node_id in reversed(path):
            if node_type in ['choice', 'nature']:
                choice_info = {
                    'type': node_type,  # Added to distinguish between choice and nature
                    'id': node_id,
                    'probability': regions[node_id].get('probability') if node_type == 'nature' else None,
                    'true_id': regions[node_id]['true']['id'],
                    'false_id': regions[node_id]['false']['id']
                }
                break
                
        return {
            'parent_id': parent_id,
            'position': position,
            'choice_info': choice_info
        }
        
    return {
        'parent_id': None,
        'position': None,
        'choice_info': None
    }