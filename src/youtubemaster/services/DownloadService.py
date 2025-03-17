"""
Download service for handling YouTube downloads.
"""
import os
import re
from PyQt6.QtCore import QObject, pyqtSignal

class DownloadService(QObject):
    """Service for handling YouTube download operations."""
    
    # Signals
    log_message = pyqtSignal(str)
    download_progress = pyqtSignal(str, float, str)  # url, percentage, stats
    download_completed = pyqtSignal(str, bool, str)  # url, success, message
    
    def __init__(self):
        """Initialize the download service."""
        super().__init__()
    
    def extract_info(self, url, options=None):
        """Extract information about a YouTube video."""
        from yt_dlp import YoutubeDL
        
        ydl_opts = options or {}
        ydl_opts.update({
            'quiet': True,
            'no_warnings': True,
        })
        
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    
    def list_formats(self, url):
        """List available formats for a YouTube video."""
        try:
            from yt_dlp import YoutubeDL
            import io
            from contextlib import redirect_stdout
            
            # Configure yt-dlp options for listing formats
            ydl_opts = {
                'listformats': True,
                'quiet': False,
                'no_warnings': False,
                'no_color': True
            }
            
            # Capture stdout to get the format listing
            captured_output = io.StringIO()
            
            with redirect_stdout(captured_output):
                # Run yt-dlp to get format info
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.extract_info(url, download=False)
            
            # Return the captured output
            return captured_output.getvalue()
            
        except Exception as e:
            return f"Error listing formats: {str(e)}"
    
    def clean_ansi_codes(self, text):
        """Remove ANSI color codes from text."""
        return re.sub(r'\x1b\[[0-9;]*m', '', text)
    
    def create_download_options(self, format_options, output_dir):
        """Create download options for yt-dlp."""
        ydl_opts = {
            'format': format_options.get('format'),
            'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'no_color': True,
        }
        
        # Add format_sort if present
        if 'format_sort' in format_options:
            ydl_opts['format_sort'] = format_options['format_sort']
            
        # Add merge_output_format if present
        if 'merge_output_format' in format_options:
            ydl_opts['merge_output_format'] = format_options['merge_output_format']
            
        return ydl_opts 