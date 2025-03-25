from youtubemaster.utils.config import config

# ... existing code ...

def run(self):
    """Run the download process."""
    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
        import time
        import os
        import glob
        
        if self.logger:
            self.logger.info(f"Starting download for: {self.url}")
        
        self.progress_signal.emit("Extracting info for: " + self.url)
        
        # Add debug information
        self.progress_signal.emit(f"Python version: {sys.version}")
        self.progress_signal.emit(f"Using format: {self.format_id}")
        self.progress_signal.emit(f"Output directory: {self.output_dir}")
        
        # Keep track of files before download
        files_before = set(os.listdir(self.output_dir))
        
        # Modify the progress hook to capture filenames
        def progress_hook(d):
            if self.cancelled:
                raise Exception("Download cancelled by user")
            
            if d['status'] == 'downloading':
                try:
                    # Use the raw progress data available in the dictionary
                    # Instead of trying to parse the formatted string with ANSI codes
                    percentage = None
                    
                    # Try to calculate percentage directly from bytes
                    downloaded_bytes = d.get('downloaded_bytes', 0)
                    total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    
                    if total_bytes > 0:
                        percentage = (downloaded_bytes / total_bytes) * 100
                        self.percentage_signal.emit(percentage)
                    
                    # Format a clean progress message for the log
                    percent_str = d.get('_percent_str', '0%')
                    speed = d.get('_speed_str', 'N/A')
                    eta = d.get('_eta_str', 'N/A')
                    
                    # Remove ANSI color codes for clean display
                    # ANSI codes follow pattern: ESC[ ... m
                    import re
                    clean_percent = re.sub(r'\x1b\[[0-9;]*m', '', percent_str)
                    clean_speed = re.sub(r'\x1b\[[0-9;]*m', '', speed)
                    clean_eta = re.sub(r'\x1b\[[0-9;]*m', '', eta)
                    
                    # Create a clean, easily parsed progress message
                    progress_msg = f"Downloading: {clean_percent} at {clean_speed}, ETA: {clean_eta}"
                    self.progress_signal.emit(progress_msg)
                    
                except Exception as e:
                    # If there's any error in progress reporting, log it but don't fail
                    if self.logger:
                        self.logger.warning(f"Progress reporting error: {str(e)}")
            
            elif d['status'] == 'finished':
                filename = d.get('filename', '')
                if filename and os.path.exists(filename):
                    self.progress_signal.emit(f"Finished downloading {filename}")
        
        # Get format options
        format_options = self.format_id if isinstance(self.format_id, dict) else {"format": self.format_id}
        
        # Configure yt-dlp options
        ydl_opts = {
            'format': format_options.get('format'),
            'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
            'progress_hooks': [progress_hook],
            'quiet': False,
            'no_warnings': False,
            'no_color': True,
            'no_mtime': True,  # Don't use the media timestamp
        }
        
        # Add format_sort only if it exists in format_options
        if 'format_sort' in format_options:
            ydl_opts['format_sort'] = format_options['format_sort']
            
        # If merge_output_format is set, add it to ydl_opts
        if 'merge_output_format' in format_options:
            ydl_opts['merge_output_format'] = format_options['merge_output_format']
            
        # Add subtitle options if present in format_options
        if 'writesubtitles' in format_options:
            ydl_opts['writesubtitles'] = format_options['writesubtitles']
        
        if 'writeautomaticsub' in format_options:
            ydl_opts['writeautomaticsub'] = format_options['writeautomaticsub']
            
        if 'subtitleslangs' in format_options:
            ydl_opts['subtitleslangs'] = format_options['subtitleslangs']
            
        if 'subtitlesformat' in format_options:
            ydl_opts['subtitlesformat'] = format_options['subtitlesformat']
            
        if 'embedsubtitles' in format_options:
            ydl_opts['embedsubtitles'] = format_options['embedsubtitles']
            
        if 'postprocessors' in format_options:
            ydl_opts['postprocessors'] = format_options['postprocessors']
        
        # First extract video info
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(self.url, download=False)
            self.progress_signal.emit(f"Found video: {info.get('title', 'Unknown title')}")
            # ... rest of the code ... 

class AnalyzeThread(QThread):
    """Worker thread for analyzing video formats."""
    
    # Signals for updates
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, url):
        """Initialize the analyze thread."""
        super().__init__()
        self.url = url
        # Initialize logger
        try:
            self.logger = Logger()
            from youtubemaster.utils.config import config
            self.logger.setup_logger(config)
        except Exception as e:
            print(f"Could not initialize logger: {e}")
            self.logger = None
    
    def run(self):
        """Run the analysis process."""
        try:
            from yt_dlp import YoutubeDL
            from yt_dlp.utils import DownloadError
            import io
            from contextlib import redirect_stdout
            
            if self.logger:
                self.logger.info(f"Analyzing formats for: {self.url}")
            
            self.progress_signal.emit(f"Analyzing URL: {self.url}")
            
            # Configure yt-dlp options for listing formats
            ydl_opts = {
                'listformats': True,
                'quiet': False,
                'no_warnings': False,
                'no_color': True,
                # Add more flexible format options for analysis
                'extractor_args': {
                    'youtube': {
                        'formats': 'all',  # Allow all formats
                        'player_skip': ['js', 'configs']  # Skip potentially problematic extraction steps
                    }
                },
                # Don't check formats before downloading
                'check_formats': False
            }
            
            # Capture stdout to get the format listing
            captured_output = io.StringIO()
            
            with redirect_stdout(captured_output):
                # Run yt-dlp to get format info
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.extract_info(self.url, download=False)
            
            # Get the captured output and send it to the UI
            output = captured_output.getvalue()
            
            # Split the output by lines and emit each line to show progress
            for line in output.split('\n'):
                if line.strip():  # Only emit non-empty lines
                    self.progress_signal.emit(line)
            
            self.finished_signal.emit(True, "Analysis completed")
            
        except DownloadError as e:
            error_msg = str(e)
            if self.logger:
                self.logger.error(f"Analysis error: {error_msg}")
            self.progress_signal.emit(f"Error: {error_msg}")
            
            # Try again with even more permissive options if there was an error
            try:
                self.progress_signal.emit("Retrying analysis with more permissive options...")
                
                # Configure more permissive yt-dlp options
                ydl_opts = {
                    'listformats': True,
                    'quiet': False,
                    'no_warnings': False,
                    'no_color': True,
                    'extractor_args': {
                        'youtube': {
                            'formats': 'all',
                            'player_skip': ['js', 'configs', 'webpage']
                        }
                    },
                    'check_formats': False
                }
                
                # Capture stdout again
                captured_output = io.StringIO()
                
                with redirect_stdout(captured_output):
                    with YoutubeDL(ydl_opts) as ydl:
                        ydl.extract_info(self.url, download=False)
                
                # Process output
                output = captured_output.getvalue()
                for line in output.split('\n'):
                    if line.strip():
                        self.progress_signal.emit(line)
                
                self.finished_signal.emit(True, "Analysis completed on second attempt")
                return
                
            except Exception as retry_error:
                # If retry also fails, report the original error
                self.finished_signal.emit(False, f"Analysis failed: {error_msg}")
                
        except Exception as e:
            error_msg = str(e)
            if self.logger:
                self.logger.error(f"Error during analysis: {error_msg}")
            self.progress_signal.emit(f"Error: {error_msg}")
            self.finished_signal.emit(False, f"Error: {error_msg}") 