"""
Theme Manager for YouTube Master application.
Centralizes all theme related configuration and styling.
"""
from youtubemaster.utils.config import config

class ThemeManager:
    """
    Manages UI themes and styling for the application.
    Provides methods to get colors and styles from the configuration.
    """
    
    @staticmethod
    def get_accent_color():
        """Get the accent color from config."""
        return config.get('ui.theme.dark.accent', '#007ACC')
    
    @staticmethod
    def get_background_color():
        """Get the background color for buttons."""
        return config.get('ui.theme.dark.button.background', '#3C3C3C')
    
    @staticmethod
    def get_hover_color():
        """Get the hover color for buttons."""
        return config.get('ui.theme.dark.button.hover', '#505050')
    
    @staticmethod
    def get_text_color():
        """Get the text color for buttons."""
        return config.get('ui.theme.dark.button.text', '#FFFFFF')
    
    @staticmethod
    def get_toggle_button_style():
        """Get the complete stylesheet for toggle buttons."""
        accent_color = ThemeManager.get_accent_color()
        background_color = ThemeManager.get_background_color()
        hover_color = ThemeManager.get_hover_color()
        text_color = ThemeManager.get_text_color()
        
        return f"""
            QPushButton {{
                background-color: {background_color};
                color: {text_color};
                border: 1px solid #555555;
                padding: 3px;
                border-radius: 4px;
                font-size: 10px;
            }}
            
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            
            QPushButton:checked {{
                background-color: {accent_color};
                border: 1px solid {accent_color};
                color: white;
            }}
            
            QPushButton:checked:hover {{
                background-color: {accent_color};
                border: 1px solid white;
            }}
        """ 