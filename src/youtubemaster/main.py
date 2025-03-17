"""
YouTubeMaster - Main entry point
"""
import os
import sys
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
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "app.ico")
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
    else:
        print(f"Warning: Icon not found at {icon_path}")
    
    # Create and show main window
    main_window = MainWindow()
    main_window.show()
    
    # Start the event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 