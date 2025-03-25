"""
YouTubeMaster - Main entry point
"""
import os
import sys
import urllib.parse

# Add parent directory to path to allow direct imports
if not getattr(sys, 'frozen', False):
    # Not frozen, in development - add path for module imports
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtCore import QObject, pyqtSignal

from youtubemaster.ui.main_window import MainWindow, ThemeManager

# Define a custom signal for receiving URLs
class SingleInstanceListener(QObject):
    url_received = pyqtSignal(str, str)  # url, format_type

    def __init__(self):
        super().__init__()
        
# Define APPLICATION_ID for single instance check
APPLICATION_ID = "YouTubeMaster-SingleInstance"

def main():
    """Main entry point for the application."""
    # Create the Qt Application
    app = QApplication(sys.argv)
    
    # Set app name and organization for settings
    app.setApplicationName("YouTubeMaster")
    app.setOrganizationName("YouTubeMaster")
    
    # Check if launched with URL argument
    url_to_download = None
    format_type = "video"  # Default format type
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        # Handle protocol handler format
        if arg.startswith('youtubemaster://'):
            protocol_path = arg.replace('youtubemaster://', '')
            
            # Check if it's the new format with format type
            if protocol_path.startswith('video/') or protocol_path.startswith('audio/'):
                format_type, url_part = protocol_path.split('/', 1)
                url_to_download = urllib.parse.unquote(url_part)
            else:
                # Legacy format - treat as video
                url_to_download = urllib.parse.unquote(protocol_path)
                format_type = "video"
                
            print(f"Received protocol URL: {url_to_download} with format {format_type}")
        # Handle direct URL
        else:
            url_to_download = arg
    
    # Try to connect to an existing instance
    socket = QLocalSocket()
    socket.connectToServer(APPLICATION_ID)
    
    # If connection succeeds, send URL and exit
    if socket.waitForConnected(500):
        # Connected to existing instance
        print("Another instance is already running, sending URL and exiting.")
        
        # If we have a URL, send it to the existing instance
        if url_to_download:
            # Send both URL and format type
            message = f"{format_type}|{url_to_download}"
            socket.write(message.encode())
            socket.flush()
            socket.waitForBytesWritten(1000)
        
        socket.close()
        return 0  # Exit this instance
    
    # No existing instance found, start a new one
    # Create a local server to listen for new instances
    server = QLocalServer()
    server.removeServer(APPLICATION_ID)  # Clean up any previous server
    server.listen(APPLICATION_ID)
    
    # Create a listener for new URLs
    listener = SingleInstanceListener()
    
    # Connect the server's new connection signal to handle new instances
    def handle_connection():
        socket = server.nextPendingConnection()
        if socket.waitForReadyRead(1000):
            data = socket.readAll().data().decode()
            if data:
                print(f"Received data from another instance: {data}")
                # Parse format type and URL
                if '|' in data:
                    format_type, url = data.split('|', 1)
                    # Clean any protocol URLs before passing to the application
                    if url.startswith('youtubemaster://'):
                        protocol_path = url.replace('youtubemaster://', '')
                        
                        # Check if it's the new format with format type embedded in protocol
                        if protocol_path.startswith('video/') or protocol_path.startswith('audio/'):
                            _, url_part = protocol_path.split('/', 1)
                            url = urllib.parse.unquote(url_part)
                        else:
                            # Legacy format - just the URL
                            url = urllib.parse.unquote(protocol_path)
                    
                    # Emit signal with the URL and format type
                    listener.url_received.emit(url, format_type)
                else:
                    # Legacy format - assume video
                    url = data
                    # Clean any protocol URLs
                    if url.startswith('youtubemaster://'):
                        url = urllib.parse.unquote(url.replace('youtubemaster://', ''))
                    
                    listener.url_received.emit(url, "video")
        socket.close()
    
    server.newConnection.connect(handle_connection)
    
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
    
    # Connect the URL received signal to the auto_add_download method
    listener.url_received.connect(main_window.auto_add_download)
    
    # If URL was passed, add it to the download queue automatically
    if url_to_download:
        main_window.auto_add_download(url_to_download, format_type)
    
    main_window.show()
    
    # Start the event loop
    return app.exec()

if __name__ == "__main__":
    sys.exit(main()) 