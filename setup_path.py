"""
Setup script for YouTube Summary project
"""
import os
import sys

def setup_path():
    """Add the project root to Python path"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = current_dir
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

# Call setup when module is imported
setup_path()
