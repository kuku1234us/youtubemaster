import os
import sys

# When using PyInstaller with --onefile and --windowed, this ensures
# the 'youtubemaster' module can be imported correctly
def patch_path():
    # This ensures that 'import youtubemaster' works whether running from the source
    # tree or from the PyInstaller-built exe
    if getattr(sys, 'frozen', False):
        # Running from the PyInstaller bundle
        base_dir = sys._MEIPASS
    else:
        # Running from the source code
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'src'))
    
    # Add the base directory to the path if not already there
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    
    # Also try adding the parent of youtubemaster
    youtubemaster_path = os.path.join(base_dir, 'youtubemaster')
    parent_dir = os.path.dirname(youtubemaster_path)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

# Call this function when this hook is imported
patch_path() 