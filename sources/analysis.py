import os
import subprocess
from typing import Dict, Any, Optional, Union
from sources.env import PRISM_PATH


def generate_multi_rewards_requirement(thresholds: Dict[str, float]) -> str:
    """
    Generate a PRISM property for multi-cumulative rewards with thresholds.
    
    Args:
        thresholds: Dictionary mapping impact names to their threshold values
                   e.g. {"cost": 100, "time": 50}
                          
    Returns:
        PRISM property checking multiple reward thresholds
    """
    # Generate individual reward bound expressions
    reward_bounds = [
        f'R{{"impact_{i}"}}<={threshold:0.6f} [C]'
        for i, threshold in enumerate(sorted(thresholds.values()))
    ]
    
    # Combine into multi() property
    return f'multi({", ".join(reward_bounds)})'

def parse_line_value(line: str, prefix: str) -> Optional[str]:
    """Extract value after prefix and colon from line."""
    if line.startswith(prefix):
        try:
            return line.split(':', 1)[1].strip()
        except IndexError:
            return None
    return None

def safe_float_conversion(value: str) -> Optional[float]:
    """Safely convert string to float."""
    try:
        return float(value.split()[0])  # Take first word only
    except (ValueError, IndexError):
        return None

def safe_int_conversion(value: str) -> Optional[int]:
    """Safely convert string to integer."""
    try:
        return int(value.split()[0])  # Take first word only
    except (ValueError, IndexError):
        return None

def parse_states_line(line: str) -> tuple[Optional[int], Optional[int]]:
    """Parse states line to extract total and initial states."""
    try:
        parts = line.split(':', 1)[1].strip()
        if '(' in parts:
            total, initial = parts.split('(')
            return (
                safe_int_conversion(total),
                safe_int_conversion(initial.strip(') '))
            )
    except (ValueError, IndexError):
        pass
    return None, None

def analyze_bounds(model_name: str, thresholds: Dict[str, float]) -> Dict[str, Any]:
    """
    Analyze a model against multi-reward bounds.
    
    Args:
        model_name: Name of the model file (without extension)
        thresholds: Dictionary mapping impact names to threshold values
        
    Returns:
        Analysis results including full PRISM analysis information
    """
    # Ensure models directory exists
    os.makedirs('models', exist_ok=True)
    
    # Define paths
    model_path = os.path.join('models', f'{model_name}.nm')
    pctl_path = os.path.join('models', f'{model_name}.pctl')
    
    # Generate and write PCTL property
    property_str = generate_multi_rewards_requirement(thresholds)
    try:
        with open(pctl_path, 'w') as f:
            f.write(property_str)
    except IOError as e:
        return {
            'error': f"Failed to write PCTL file: {str(e)}",
            'return_code': -1,
            'result': None,
            'model_info': {},
            'timings': {},
            'states_info': {},
            'warnings': [],
            'property': property_str
        }

    print("pctl_path: ", pctl_path)
    print("model_path: ", model_path)
    
    # Run PRISM with the model and property files
    cmd = [
        os.path.abspath(PRISM_PATH) if PRISM_PATH else "prism",
        "-cuddmaxmem",
        "10g",
        "-javamaxmem",
        "2g",
        os.path.abspath(model_path),
        os.path.abspath(pctl_path),
        "-verbose"
    ]
    print(cmd)
    try:
        result = subprocess.run(cmd, 
                              capture_output=True, 
                              text=True, 
                              check=True)
        
        # Parse PRISM output
        prism_output = result.stdout
        model_info: Dict[str, Any] = {}
        timings: Dict[str, Optional[float]] = {}
        states_info: Dict[str, Optional[int]] = {}
        result_value: Optional[bool] = None
        warnings: list[str] = []

        print(f'Prism output:\n{prism_output}')
        
        for line in prism_output.split('\n'):
            line = line.strip()
            
            # Version and basic info
            if value := parse_line_value(line, 'Version:'): 
                model_info['version'] = value
            elif value := parse_line_value(line, 'Type:'): 
                model_info['type'] = value
            elif value := parse_line_value(line, 'Modules:'):
                model_info['modules'] = value.split()
            elif value := parse_line_value(line, 'Variables:'):
                model_info['variables'] = value.split()
                
            # Timing information
            elif 'Time for model construction:' in line:
                if value := parse_line_value(line, 'Time for model construction:'):
                    timings['model_construction'] = safe_float_conversion(value)
            elif 'Time for model checking:' in line:
                if value := parse_line_value(line, 'Time for model checking:'):
                    timings['model_checking'] = safe_float_conversion(value)
                
            # States information
            elif line.startswith('States:'):
                total, initial = parse_states_line(line)
                states_info['total'] = total
                states_info['initial'] = initial
            elif value := parse_line_value(line, 'Transitions:'):
                states_info['transitions'] = safe_int_conversion(value)
            elif value := parse_line_value(line, 'Choices:'):
                states_info['choices'] = safe_int_conversion(value)
                
            # Result
            elif value := parse_line_value(line, 'Result:'):
                result_value = value.lower() == 'true'
                
            # Warnings
            elif line.startswith('Warning:'):
                warnings.append(line.split('Warning:', 1)[1].strip())
        
        # Compile complete results
        analysis_info = {
            'command': ' '.join(cmd),
            'prism_output': prism_output,
            'model_info': model_info,
            'timings': timings,
            'states_info': states_info,
            'property': property_str,
            'result': result_value,
            'warnings': warnings,
            'return_code': result.returncode,
            'error_output': result.stderr if result.stderr else None
        }
        
        return analysis_info
        
    except subprocess.CalledProcessError as e:
        return {
            'command': ' '.join(cmd),
            'error': str(e),
            'prism_output': e.output if hasattr(e, 'output') else None,
            'return_code': e.returncode,
            'error_output': e.stderr if hasattr(e, 'stderr') else None,
            'result': None,
            'model_info': {},
            'timings': {},
            'states_info': {},
            'warnings': [],
            'property': property_str
        }
    except Exception as e:
        return {
            'command': ' '.join(cmd),
            'error': str(e),
            'return_code': -1,
            'result': None,
            'model_info': {},
            'timings': {},
            'states_info': {},
            'warnings': [],
            'property': property_str
        }