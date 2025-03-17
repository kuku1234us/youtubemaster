"""
Environment variables loader for YouTubeMaster.

This module loads environment variables from a .env file and makes them
available throughout the application.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

def load_environment():
    """Load environment variables from .env file."""
    # Try to locate .env file
    env_path = Path('.env')
    
    # Check alternative locations if not found
    if not env_path.exists():
        # Check in the parent directory (project root)
        parent_env = Path('..') / '.env'
        if parent_env.exists():
            env_path = parent_env
    
    # Load the .env file if found
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        return True
    
    return False

def get_env(key, default=None):
    """Get environment variable with optional default value."""
    return os.environ.get(key, default)

# Load environment variables when the module is imported
loaded = load_environment() 