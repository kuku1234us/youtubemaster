"""
YouTubeMaster - Main entry point
"""
import os
import sys

# Add parent directory to path to allow direct imports
if not getattr(sys, 'frozen', False):
    # Not frozen, in development - add path for module imports
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from youtubemaster.ui.main_window import MainWindow, ThemeManager

def main():
    """Main entry point for the application."""
    # Create the Qt Application
    app = QApplication(sys.argv)
    
    # Set app name and organization for settings
    app.setApplicationName("YouTubeMaster")
    app.setOrganizationName("YouTubeMaster")
    
    # Apply dark theme
    ThemeManager.apply_dark_theme(app)
    
    # Set application icon - using more robust path resolution
    try:
        # Check if we're running from PyInstaller bundle
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
            icon_path = os.path.join(base_path, "assets", "app.ico")
        else:
            # Regular development path
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "app.ico")
            
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            app.setWindowIcon(app_icon)
        else:
            print(f"Warning: Icon not found at {icon_path}")
    except Exception as e:
        print(f"Error setting icon: {str(e)}")
    
    # Create and show main window
    main_window = MainWindow()
    main_window.show()
    
    # Start the event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 