"""
Configuration handler for YouTubeMaster.
"""
import os
import sys
from pathlib import Path
from ruamel.yaml import YAML
from youtubemaster.utils.env_loader import get_env

class Config:
    """Configuration handler for the application."""
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the configuration handler."""
        if self._initialized:
            return
            
        self._config = {}
        self._config_path = self._find_config_file()
        self._load_config()
        self._initialized = True
    
    def _find_config_file(self):
        """Find the configuration file in common locations."""
        # First, determine if we're running as frozen app (PyInstaller)
        is_frozen = getattr(sys, 'frozen', False)
        
        # First priority: Check user's config directory (always writable)
        user_config_dir = Path.home() / ".youtubemaster"
        if not user_config_dir.exists():
            user_config_dir.mkdir(exist_ok=True)
            
        user_config = user_config_dir / "config.yaml"
        
        # If user config exists, use it
        if user_config.exists():
            return user_config
            
        # Second priority: Check in AppData/Local (Windows) or .config (Linux)
        if sys.platform == 'win32':
            app_config_dir = Path(os.environ.get('LOCALAPPDATA', '')) / "YouTubeMaster"
        else:
            app_config_dir = Path.home() / ".config" / "youtubemaster"
            
        if not app_config_dir.exists():
            app_config_dir.mkdir(exist_ok=True, parents=True)
            
        app_config = app_config_dir / "config.yaml"
        
        # If App config exists, use it
        if app_config.exists():
            return app_config
        
        # Third priority for development: Check in current directory or app directory
        config_in_cwd = Path("config.yaml")
        if not is_frozen and config_in_cwd.exists():
            return config_in_cwd
            
        app_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent.parent
        config_in_app = app_dir / "src" / "config.yaml"
        if not is_frozen and config_in_app.exists():
            # Load from src dir but save to user dir
            print(f"Found config in {config_in_app}, but will save to {user_config}")
            return config_in_app
        
        # If we get here, no config file was found
        # When running as executable, default to user directory
        if is_frozen:
            print(f"Creating new config in {user_config}")
            return user_config
        else:
            # In development, use cwd
            print(f"Creating new config in {config_in_cwd}")
            return config_in_cwd
    
    def _load_config(self):
        """Load the configuration from file."""
        yaml = YAML(typ='safe')
        try:
            if self._config_path.exists():
                with open(self._config_path, 'r') as file:
                    self._config = yaml.load(file)
            
            # Apply environment variables for non-core settings
            self._apply_env_overrides()
        except Exception as e:
            print(f"Error loading configuration: {e}")
            self._config = self._create_default_config()
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides for certain settings."""
        # List of settings that can be overridden by environment variables
        # Notably excludes 'app_mode' and 'output_directory'
        override_map = {
            'LOG_LEVEL': 'logging.level',
            'LOG_FILE': 'logging.file',
            # Add any other env vars that should override config here
            'YOUTUBE_API_KEY': 'api.youtube_key',
        }
        
        # Apply overrides
        for env_var, config_path in override_map.items():
            env_value = get_env(env_var)
            if env_value is not None:
                self.set(config_path, env_value)
    
    def _create_default_config(self):
        """Create default configuration."""
        # Don't use environment variables for these core settings
        # Use fixed defaults for config.yaml instead
        return {
            "app_mode": "debug",
            "output_directory": "downloads",
            "logging": {
                "level": get_env('LOG_LEVEL', 'INFO'),
                "file": get_env('LOG_FILE', 'app.log')
            },
            "ui": {
                "font": {
                    "family": "Calibri",
                    "size": 10
                },
                "theme": {
                    "dark": {
                        "background": "#1E1E1E",
                        "text": "#FFFFFF",
                        "accent": "#007ACC",
                        "table": {
                            "header": "#2D2D2D",
                            "background": "#252526",
                            "alternate_row": "#2D2D2D",
                            "grid": "#3C3C3C"
                        },
                        "search": {
                            "background": "#2D2D2D",
                            "border": "#3C3C3C",
                            "focus": "#4CAF50"
                        },
                        "button": {
                            "background": "#3C3C3C",
                            "text": "#FFFFFF",
                            "hover": "#505050",
                            "disabled": {
                                "background": "#2A2A2A",
                                "text": "#808080"
                            }
                        },
                        "input": {
                            "background": "#3C3C3C",
                            "text": "#FFFFFF",
                            "border": "#555555"
                        },
                        "splitter": "#2D2D2D",
                        "titlebar": {
                            "background": "#2D2D2D",
                            "text": "#FFFFFF",
                            "button_hover": "#3C3C3C"
                        },
                        "scrollbar": {
                            "background": "#1E1E1E",
                            "handle": "#3C3C3C",
                            "border": "#2D2D2D",
                            "button": "#3C3C3C",
                            "arrow": "#555555"
                        },
                        "border_radius": {
                            "button": "5px",
                            "input": "5px"
                        }
                    }
                }
            }
        }
    
    def _save_config(self):
        """Save the configuration to file."""
        yaml = YAML()
        yaml.indent(mapping=2, sequence=4, offset=2)
        
        try:
            # Determine if we're running as bundled app
            is_frozen = getattr(sys, 'frozen', False)
            
            # If we're frozen or the current path is not writable,
            # save to user directory instead
            save_path = self._config_path
            
            # Check if we can write to the directory
            if is_frozen or not os.access(self._config_path.parent, os.W_OK):
                # Save to user config directory instead
                user_config_dir = Path.home() / ".youtubemaster"
                user_config_dir.mkdir(exist_ok=True)
                save_path = user_config_dir / "config.yaml"
                print(f"Saving config to user directory: {save_path}")
            
            # Ensure directory exists
            save_path.parent.mkdir(exist_ok=True, parents=True)
            
            with open(save_path, 'w') as file:
                yaml.dump(self._config, file)
                
            # If we redirected the save, update config_path for next time
            if save_path != self._config_path:
                self._config_path = save_path
                
        except Exception as e:
            print(f"Error saving configuration: {e}")
    
    def get(self, key, default=None):
        """Get a configuration value by key."""
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key, value):
        """Set a configuration value by key."""
        keys = key.split('.')
        config = self._config
        
        # Navigate to the right level
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
        self._save_config()
    
    @property
    def output_directory(self):
        """Get the output directory."""
        output_dir = self.get('output_directory')
        if not output_dir:
            output_dir = os.path.expanduser("~/Downloads")
        return output_dir
    
    @output_directory.setter
    def output_directory(self, value):
        """Set the output directory."""
        self.set('output_directory', value)

# Global config instance
config = Config() 