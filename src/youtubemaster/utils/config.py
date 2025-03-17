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
        # Check in current directory
        if os.path.exists("config.yaml"):
            return Path("config.yaml")
            
        # Check in the app directory
        app_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent.parent
        config_in_app = app_dir / "config.yaml"
        if config_in_app.exists():
            return config_in_app
            
        # Check in user config directory
        user_config_dir = Path.home() / ".youtubemaster"
        if not user_config_dir.exists():
            user_config_dir.mkdir(exist_ok=True)
            
        user_config = user_config_dir / "config.yaml"
        if user_config.exists():
            return user_config
            
        # If no config file found, create default in app directory
        return app_dir / "config.yaml"
    
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
            # Ensure directory exists
            self._config_path.parent.mkdir(exist_ok=True)
            
            with open(self._config_path, 'w') as file:
                yaml.dump(self._config, file)
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