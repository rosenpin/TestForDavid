import os
import shutil
import json
from typing import Dict, Any

def ensure_directory(directory_path: str) -> None:
    """Ensure a directory exists, creating it if necessary."""
    os.makedirs(directory_path, exist_ok=True)

def save_json(data: Dict[str, Any], file_path: str) -> None:
    """Save data as JSON to the specified file path."""
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

def load_json(file_path: str) -> Dict[str, Any]:
    """Load JSON data from the specified file path."""
    with open(file_path, "r") as f:
        return json.load(f)

def copy_file(source_path: str, destination_path: str) -> None:
    """Copy a file from source to destination."""
    with open(source_path, "rb") as src_file, open(destination_path, "wb") as dst_file:
        dst_file.write(src_file.read())

def remove_file(file_path: str) -> None:
    """Remove a file if it exists."""
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Error removing file {file_path}: {str(e)}")

def ensure_serializable(data):
    """Ensure that data is JSON serializable."""
    if isinstance(data, dict):
        return {str(k): ensure_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [ensure_serializable(item) for item in data]
    elif isinstance(data, (str, int, float, bool, type(None))):
        return data
    else:
        # Convert anything else to string
        return str(data) 