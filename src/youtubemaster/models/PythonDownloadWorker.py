"""
Worker class for processing downloads using the yt-dlp Python package.
"""
import os
import time
import re
from PyQt6.QtCore import QThread, pyqtSignal
from youtubemaster.utils.logger import Logger

class PythonDownloadWorker(QThread):
    """Thread for processing a single download using the yt-dlp Python package."""
    
    # Define signals (same as the original DownloadThread)
    progress_signal = pyqtSignal(str, float, str)  # url, progress percent, status text
    complete_signal = pyqtSignal(str, str, str)    # url, output_dir, filename
    error_signal = pyqtSignal(str, str)            # url, error message
    log_signal = pyqtSignal(str)                   # log message
    processing_signal = pyqtSignal(str, str)       # url, status message
    
    def __init__(self, url, format_options, output_dir, parent=None):
        """
        Initialize the download worker.
        
        Args:
            url (str): The URL to download from
            format_options (dict): Options dictionary for yt-dlp (format, cookies, etc.)
            output_dir (str): Directory where downloaded files will be saved
            parent (QObject, optional): Parent QObject for proper memory management
        """
        super().__init__(parent)
        self.url = url
        self.format_options = format_options
        self.output_dir = output_dir
        self.cancelled = False
        self.logger = Logger()
        self.downloaded_filename = None  # Will store the filename of the downloaded file
    
    def run(self):
        """Run the download process."""
        try:
            from yt_dlp import YoutubeDL
            from yt_dlp.utils import DownloadError
            
            self.log_signal.emit(f"Starting download for: {self.url}")
            
            # Track files before download
            files_before = set(os.listdir(self.output_dir))
            
            # Progress hook for yt-dlp
            def progress_hook(d):
                if self.cancelled:
                    raise Exception("Download cancelled by user")
                
                if d['status'] == 'downloading':
                    # Calculate progress percentage
                    downloaded_bytes = d.get('downloaded_bytes', 0)
                    total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    
                    if total_bytes > 0:
                        percentage = (downloaded_bytes / total_bytes) * 100
                        speed = d.get('_speed_str', 'N/A')
                        eta = d.get('_eta_str', 'N/A')
                        status_text = f"Downloading: {percentage:.1f}% at {speed}, ETA: {eta}"
                        self.progress_signal.emit(self.url, percentage, status_text)
                    else:
                        # Emit a progress signal even when total bytes is unknown
                        status_text = f"Downloading: {downloaded_bytes / 1024:.1f} KB at {d.get('_speed_str', 'N/A')}"
                        # Use a small percentage to show some progress
                        self.progress_signal.emit(self.url, 1, status_text)
                
                elif d['status'] == 'finished':
                    self.log_signal.emit(f"Finished downloading part of {self.url}")
                    # Store the filename of the downloaded file
                    if 'filename' in d:
                        self.downloaded_filename = os.path.basename(d['filename'])
                        self.log_signal.emit(f"File: {self.downloaded_filename}")
                
                # Check for error status
                elif d['status'] == 'error':
                    error_msg = d.get('error', 'An error occurred during download')
                    self.error_signal.emit(self.url, f"Download error: {error_msg}")
                    raise Exception(f"Download error: {error_msg}")
            
            # Signal that processing is starting
            self.processing_signal.emit(self.url, "Processing started...")
            
            # Configure yt-dlp options with extended timeouts for slow connections
            ydl_opts = {
                'format': self.format_options.get('format'),
                'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
                'progress_hooks': [progress_hook],
                'quiet': False,
                'no_warnings': False,
                'no_color': True,
                'no_mtime': True,  # Don't use the media timestamp
                # Extended timeout settings for slow connections
                'socket_timeout': 120,  # 2 minutes socket timeout (default is 20s)
                'retries': 10,          # Retry up to 10 times (default is 3)
                'fragment_retries': 10, # Retry fragments up to 10 times
                'extractor_retries': 5, # Retry information extraction 5 times
                'file_access_retries': 5, # Number of times to retry on file access error
                'skip_unavailable_fragments': True, # Skip unavailable fragments
                'abort_on_unavailable_fragment': False, # Don't abort on unavailable fragments
                'ignoreerrors': False,  # Don't ignore errors, but retry multiple times
                'external_downloader_args': ['--connect-timeout', '120'], # For external downloaders
            }
            
            # Add format_sort if it exists in options
            if 'format_sort' in self.format_options:
                ydl_opts['format_sort'] = self.format_options['format_sort']
                
            # Add merge_output_format if it exists
            if 'merge_output_format' in self.format_options:
                ydl_opts['merge_output_format'] = self.format_options['merge_output_format']
                
            # Add subtitle options if present
            if 'writesubtitles' in self.format_options:
                ydl_opts['writesubtitles'] = self.format_options['writesubtitles']
            
            if 'writeautomaticsub' in self.format_options:
                ydl_opts['writeautomaticsub'] = self.format_options['writeautomaticsub']
                
            if 'subtitleslangs' in self.format_options:
                ydl_opts['subtitleslangs'] = self.format_options['subtitleslangs']
                
            if 'subtitlesformat' in self.format_options:
                ydl_opts['subtitlesformat'] = self.format_options['subtitlesformat']
                
            if 'embedsubtitles' in self.format_options:
                ydl_opts['embedsubtitles'] = self.format_options['embedsubtitles']
                
            if 'postprocessors' in self.format_options:
                ydl_opts['postprocessors'] = self.format_options['postprocessors']
            
            # Add extractor-specific arguments for more reliable format extraction
            ydl_opts['extractor_args'] = self.format_options.get('extractor_args', {})
            if 'youtube' not in ydl_opts['extractor_args']:
                ydl_opts['extractor_args']['youtube'] = {
                    # No specific client player requirements
                }
            
            # Add cookies options if present
            if 'cookies' in self.format_options:
                try:
                    cookie_file = self.format_options['cookies']
                    if os.path.exists(cookie_file):
                        ydl_opts['cookies'] = cookie_file
                        self.log_signal.emit(f"Using cookies from file: {cookie_file}")
                    else:
                        self.log_signal.emit(f"Warning: Cookie file not found: {cookie_file}")
                except Exception as e:
                    self.log_signal.emit(f"Error setting cookie file: {str(e)}")
            
            # Add cookies from browser if present (as fallback)
            elif 'cookies_from_browser' in self.format_options:
                try:
                    browser = self.format_options['cookies_from_browser']
                    ydl_opts['cookies_from_browser'] = browser
                    self.log_signal.emit(f"Using cookies from {browser} browser")
                    
                    # Add debug info about closing the browser
                    if 'firefox' in browser.lower():
                        self.log_signal.emit("Note: If Firefox is running, try closing it and retrying if cookie extraction fails")
                except Exception as e:
                    error_msg = f"Error setting up browser cookies: {str(e)}"
                    self.log_signal.emit(error_msg)
                    # We don't want to abort the download if cookie setup fails
                    # it will just try without cookies
            
            # Extract info first to get title and thumbnail
            with YoutubeDL(ydl_opts) as ydl:
                info = None
                max_retries = 3
                retry_count = 0
                
                while retry_count < max_retries and not info:
                    try:
                        info = ydl.extract_info(self.url, download=False)
                    except Exception as e:
                        retry_count += 1
                        if retry_count >= max_retries:
                            raise
                        self.progress_signal.emit(self.url, 0, f"Retrying metadata extraction ({retry_count}/{max_retries})...")
                        time.sleep(2)  # Wait before retrying
                
                title = info.get('title', 'Unknown Title')
                
                # Start the actual download
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        ydl.download([self.url])
                        break  # Success, exit the retry loop
                    except DownloadError as e:
                        error_message = str(e)
                        self.log_signal.emit(f"Download error encountered: {error_message}")
                        
                        # Check if it's a timeout or connection error
                        if "urlopen error timed out" in error_message or "urlopen error" in error_message:
                            retry_count += 1
                            if retry_count >= max_retries:
                                raise
                            self.progress_signal.emit(self.url, 0, f"Connection timed out, retrying ({retry_count}/{max_retries})...")
                            time.sleep(5)  # Wait before retrying
                        # Check for HTTP 403 Forbidden error
                        elif "HTTP Error 403: Forbidden" in error_message:
                            # This is likely a YouTube restriction or rate limiting
                            error_msg = "Access forbidden (HTTP 403). YouTube may be limiting downloads or restricting this video."
                            self.error_signal.emit(self.url, error_msg)
                            return  # Exit thread gracefully
                        # Check for regional restrictions
                        elif "This video is not available in your country" in error_message:
                            error_msg = "Video unavailable in your region due to geographical restrictions."
                            self.error_signal.emit(self.url, error_msg)
                            return  # Exit thread gracefully
                        # Check for private videos
                        elif "Private video" in error_message or "Sign in to confirm your age" in error_message:
                            error_msg = "This video is private, age-restricted, or requires sign-in."
                            self.error_signal.emit(self.url, error_msg)
                            return  # Exit thread gracefully
                        # Check for other HTTP errors
                        elif re.search(r"HTTP Error \d+", error_message):
                            match = re.search(r"HTTP Error (\d+)", error_message)
                            code = match.group(1) if match else "unknown"
                            error_msg = f"Server returned HTTP error {code}. Please try again later."
                            self.error_signal.emit(self.url, error_msg)
                            return  # Exit thread gracefully
                        else:
                            # Not a timeout error, re-raise
                            raise
            
            # Find new files after download
            files_after = set(os.listdir(self.output_dir))
            new_files = files_after - files_before
            
            # If we didn't capture the filename during download, try to determine it from new files
            if not self.downloaded_filename and len(new_files) == 1:
                # If only one file was created, it must be our download
                self.downloaded_filename = list(new_files)[0]
                self.log_signal.emit(f"Identified download as: {self.downloaded_filename}")
            elif not self.downloaded_filename and len(new_files) > 1:
                # More complex - multiple files were created
                # Look for the most likely media file types
                media_extensions = ['.mp4', '.webm', '.mkv', '.mp3', '.m4a', '.opus']
                media_files = [f for f in new_files if any(f.lower().endswith(ext) for ext in media_extensions)]
                
                if len(media_files) == 1:
                    self.downloaded_filename = media_files[0]
                    self.log_signal.emit(f"Identified media file as: {self.downloaded_filename}")
                elif len(media_files) > 1:
                    # Use the largest file as the main download
                    largest_file = max(
                        [(f, os.path.getsize(os.path.join(self.output_dir, f))) for f in media_files],
                        key=lambda x: x[1]
                    )[0]
                    self.downloaded_filename = largest_file
                    self.log_signal.emit(f"Selected largest media file as: {self.downloaded_filename}")
            
            # Update modification time of the final files
            current_time = time.time()
            for filename in new_files:
                filepath = os.path.join(self.output_dir, filename)
                if os.path.isfile(filepath):
                    try:
                        # Set both access time and modification time to current time
                        os.utime(filepath, (current_time, current_time))
                    except Exception as e:
                        self.log_signal.emit(f"Failed to update timestamp: {str(e)}")
            
            # Signal completion with output directory and filename
            self.complete_signal.emit(self.url, self.output_dir, self.downloaded_filename)
            
        except DownloadError as e:
            error_message = str(e)
            # Make error messages more user-friendly
            if "YouTube said:" in error_message:
                # Extract the actual YouTube error message
                youtube_msg = re.search(r"YouTube said: (.*?)(\n|$)", error_message)
                if youtube_msg:
                    error_message = f"YouTube error: {youtube_msg.group(1)}"
                
            self.error_signal.emit(self.url, f"Download error: {error_message}")
        except Exception as e:
            error_message = str(e)
            self.error_signal.emit(self.url, f"Error: {error_message}")
    
    def cancel(self):
        """Cancel the download."""
        self.cancelled = True 