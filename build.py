"""
Build script for creating a Windows executable using PyInstaller.
"""

import os
import shutil
import subprocess
import sys

def clean_build_dirs():
    """Remove build artifacts from previous builds."""
    directories = ['build', 'dist']
    for directory in directories:
        if os.path.exists(directory):
            shutil.rmtree(directory)
    
    # Also remove spec files
    for file in os.listdir('.'):
        if file.endswith('.spec'):
            os.remove(file)

def build_executable():
    """Build the executable using PyInstaller."""
    icon_path = os.path.join('src', 'youtubemaster', 'resources', 'icon.ico')
    
    # Basic PyInstaller command
    cmd = [
        'pyinstaller',
        '--name=YouTubeMaster',
        '--onefile',  # Create a single executable
        '--windowed',  # Don't open console window
    ]
    
    # Add icon if it exists
    if os.path.exists(icon_path):
        cmd.append(f'--icon={icon_path}')
    
    cmd.extend([
        '--clean',
        '--noconfirm',
        # Add data files (modify as needed)
        '--add-data', f'{os.path.join("src", "youtubemaster", "resources")}:resources',
    ])
    
    # Add hidden imports for yt-dlp
    cmd.extend(['--hidden-import', 'yt_dlp.utils'])
    cmd.extend(['--hidden-import', 'yt_dlp.options'])
    
    # Main script
    cmd.append(os.path.join('src', 'youtubemaster', 'main.py'))
    
    # Execute PyInstaller
    subprocess.run(cmd)
    
    print("Build completed! Executable is in the 'dist' folder.")

if __name__ == "__main__":
    clean_build_dirs()
    build_executable() 