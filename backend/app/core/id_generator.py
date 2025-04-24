from typing import Dict, Type
from sqlmodel import SQLModel

# Dictionary to store the last used ID for each model
_last_ids: Dict[Type[SQLModel], int] = {}

def generate_id(model_class: Type[SQLModel], start_from: int = 1) -> int:
    """
    Generate a sequential integer ID for a model.
    
    Args:
        model_class: The SQLModel class to generate ID for
        start_from: The starting number for the sequence
        
    Returns:
        int: The next ID in sequence
    """
    if model_class not in _last_ids:
        _last_ids[model_class] = start_from - 1
    
    _last_ids[model_class] += 1
    return _last_ids[model_class] 