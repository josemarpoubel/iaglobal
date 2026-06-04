"""Helper functions for common operations."""

from typing import Any, Dict, List
import json

def format_output(data: Any, pretty: bool = True) -> str:
    """Format output as JSON string."""
    if pretty:
        return json.dumps(data, indent=2)
    return json.dumps(data)

def parse_input(data: str) -> Any:
    """Parse input as JSON."""
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return data

def merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
    """Recursively merge two dictionaries."""
    result = dict1.copy()
    for key, value in dict2.items():
        if isinstance(value, dict):
            result[key] = merge_dicts(result.get(key, {}), value)
        else:
            result[key] = value
    return result
