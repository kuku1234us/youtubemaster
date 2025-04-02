"""
Download manager for handling multiple YouTube downloads.
"""
import os
import threading
import time
from typing import Dict, List, Optional, Any, Tuple
from queue import Queue

from PyQt6.QtCore import QObject, pyqtSignal, QThread, QMutex, QUrl, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

from youtubemaster.utils.logger import Logger
from youtubemaster.models.SiteModel import SiteModel

class DownloadThread(QThread):
    """Thread for processing a single download."""
    
    # Define signals
    progress_signal = pyqtSignal(str, float, str)  # url, progress percent, status text
    complete_signal = pyqtSignal(str, str, str)  # url, output_dir, filename
    error_signal = pyqtSignal(str, str)  # url, error message
    log_signal = pyqtSignal(str)  # log message
    processing_signal = pyqtSignal(str, str)  # url, status message
    
    def __init__(self, url, format_options, output_dir, parent=None):
        """Initialize the download thread."""
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
            import os
            import time
            import re
            
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
            # This replaces the need for PhantomJS
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
                # Set a timeout handler to ensure we don't get stuck
                def timeout_handler():
                    self.progress_signal.emit(self.url, 0, "Still processing, please wait...")
                
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
                
                # Get the smallest thumbnail from the available options
                thumbnails = info.get('thumbnails', [])
                thumbnail_url = None
                if thumbnails:
                    # Sort thumbnails by size (width*height) and get the smallest one
                    sorted_thumbnails = sorted(
                        [t for t in thumbnails if t.get('url') and t.get('width') and t.get('height')],
                        key=lambda t: t.get('width', 0) * t.get('height', 0)
                    )
                    if sorted_thumbnails:
                        thumbnail_url = sorted_thumbnails[0].get('url')
                    else:
                        # Fallback to default thumbnail
                        thumbnail_url = info.get('thumbnail')
                else:
                    # Fallback to default thumbnail
                    thumbnail_url = info.get('thumbnail')
                
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


class DownloadManager(QObject):
    """Manager for handling multiple YouTube downloads."""
    
    # Define signals
    queue_updated = pyqtSignal()
    download_started = pyqtSignal(str, str, QPixmap)  # url, title, thumbnail
    download_progress = pyqtSignal(str, float, str)  # url, progress percentage, status text
    download_complete = pyqtSignal(str, str, str)  # url, output_dir, filename
    download_error = pyqtSignal(str, str)  # url, error message
    log_message = pyqtSignal(str)  # log message
    
    def __init__(self, parent=None):
        """Initialize the download manager."""
        super().__init__(parent)
        
        # Download queue and metadata storage
        self._queue = []  # URLs waiting to be downloaded
        self._active = {}  # {url: thread} for active downloads
        self._completed = []  # URLs of completed downloads
        self._errors = []  # URLs of downloads with errors
        self._metadata = {}  # {url: {title, status, progress, thumbnail, etc.}}
        
        # Configuration
        self._max_concurrent = 2
        
        # Mutex for thread safety
        self._mutex = QMutex()
        
        # Logger
        self.logger = Logger()
    
    def get_max_concurrent(self):
        """Get the maximum number of concurrent downloads."""
        return self._max_concurrent
    
    def set_max_concurrent(self, value):
        """Set the maximum number of concurrent downloads."""
        self._max_concurrent = max(1, min(5, value))  # Constrain between 1-5
        self._process_queue()  # Start new downloads if possible
    
    def add_download(self, url, format_options=None, output_dir=None):
        """
        Add a URL to the download queue.
        
        Args:
            url (str): The URL to download
            format_options (dict or str): Format options for yt-dlp
            output_dir (str): The output directory for downloaded files
        
        Returns:
            bool: True if added, False if already in queue
        """
        clean_url = SiteModel.get_clean_url(url)
        
        print(f"DEBUG: add_download called with URL: {url}, clean_url: {clean_url}")
        print(f"DEBUG: Format options received: {format_options}")
        
        self._mutex.lock()
        is_new = False
        try:
            # Check if already in queue
            if (clean_url in self._queue or 
                clean_url in self._active or 
                clean_url in self._completed or
                clean_url in self._errors):
                print(f"DEBUG: URL already in queue: {clean_url}")
                return False
            
            # Add to queue
            self._queue.append(clean_url)
            print(f"DEBUG: Added to queue: {clean_url}")
            is_new = True
            
            # Initialize metadata
            self._metadata[clean_url] = {
                'url': clean_url,
                'title': f"Loading...",
                'status': 'Queued',
                'progress': 0,
                'thumbnail': None,
                'format_options': format_options or 'best',
                'output_dir': output_dir or os.path.expanduser('~/Downloads')
            }
            
            print(f"DEBUG: Metadata initialized with format_options: {self._metadata[clean_url]['format_options']}")
        finally:
            self._mutex.unlock()
        
        if is_new:
            # Emit signal
            self.queue_updated.emit()
            
            # Update log
            self.log_message.emit(f"Added to queue: {clean_url}")
            
            # Fetch metadata in background thread
            # Always fetch metadata for all URLs, even ones that were from the protocol handler
            # This ensures we get proper titles for Chrome extension URLs
            print(f"DEBUG: Starting quick metadata fetch for: {clean_url}")
            self._fetch_quick_metadata_threaded(clean_url)
            
            # Process queue (will start download if slots available)
            self._process_queue()
            
            return True
        
        return False
    
    def _fetch_quick_metadata_threaded(self, url):
        """
        Start a thread to quickly fetch basic metadata without blocking the UI.
        This is a lightweight alternative to the full _fetch_metadata method.
        """
        class QuickMetadataThread(QThread):
            # Define signals for thread-safe communication
            metadata_ready = pyqtSignal(str, str, QPixmap)
            log_message = pyqtSignal(str)
            
            def __init__(self, url, format_options=None, parent=None):
                super().__init__(parent)
                self.url = url
                self.format_options = format_options or {}
                
            def run(self):
                try:
                    # Extract video ID using SiteModel
                    video_id = SiteModel.extract_video_id(self.url)
                    
                    if not video_id:
                        # If we can't extract a video ID, just return
                        return
                    
                    # Try to get title and thumbnail using SiteModel with retries
                    max_retries = 3
                    retry_count = 0
                    title, pixmap = None, None
                    
                    while retry_count < max_retries and not title:
                        try:
                            title, pixmap = SiteModel.get_video_metadata(self.url)
                            if not title:
                                retry_count += 1
                                if retry_count < max_retries:
                                    import time
                                    time.sleep(2)  # Wait before retrying
                                    continue
                                else:
                                    # Use a generic title with the platform detected after max retries
                                    site = SiteModel.detect_site(self.url)
                                    title = f"Loading: {site} video"
                        except Exception:
                            retry_count += 1
                            if retry_count < max_retries:
                                import time
                                time.sleep(2)  # Wait before retrying
                            else:
                                # Use a generic title after max retries
                                site = SiteModel.detect_site(self.url)
                                title = f"Loading: {site} video"
                    
                    if not title:
                        # Use a generic title with the platform detected
                        site = SiteModel.detect_site(self.url)
                        title = f"Loading: {site} video"
                    
                    if pixmap:
                        # Scale the pixmap before sending it
                        scaled_pixmap = pixmap.scaled(
                            160, 90,
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        
                        # Center-crop if too big
                        if scaled_pixmap.width() > 160 or scaled_pixmap.height() > 90:
                            x = (scaled_pixmap.width() - 160) // 2 if scaled_pixmap.width() > 160 else 0
                            y = (scaled_pixmap.height() - 90) // 2 if scaled_pixmap.height() > 90 else 0
                            scaled_pixmap = scaled_pixmap.copy(int(x), int(y), 160, 90)
                        
                        # Emit signal with metadata
                        self.metadata_ready.emit(self.url, title, scaled_pixmap)
                        self.log_message.emit(f"Loaded quick metadata for {self.url}")
                    else:
                        # Always emit signal with title even if no thumbnail
                        # This ensures the title gets updated in the UI
                        self.metadata_ready.emit(self.url, title, QPixmap())
                        self.log_message.emit(f"Loaded title metadata for {self.url} (no thumbnail)")
                
                except Exception as e:
                    # Log the error but don't fail - metadata isn't critical
                    print(f"DEBUG: Error in quick metadata thread: {str(e)}")
                    # We don't return anything here - the download will continue regardless
                    
                    # Still emit a signal with a generic title so the UI can show something
                    site = SiteModel.detect_site(self.url)
                    title = f"Loading: {site} video {video_id}" if video_id else f"Loading: {site} video"
                    self.metadata_ready.emit(self.url, title, QPixmap())
        
        # Get the format options for the URL
        format_options = None
        if url in self._metadata and 'format_options' in self._metadata[url]:
            format_options = self._metadata[url]['format_options']
        
        # Create and configure the thread
        thread = QuickMetadataThread(url, format_options, self)
        
        # Connect signals
        thread.metadata_ready.connect(self._on_quick_metadata_ready)
        thread.log_message.connect(self.log_message)
        
        # Store thread reference to prevent garbage collection
        if not hasattr(self, '_quick_metadata_threads'):
            self._quick_metadata_threads = {}
        self._quick_metadata_threads[url] = thread
        
        # Start the thread
        thread.start()
    
    def _on_quick_metadata_ready(self, url, title, pixmap):
        """Handle completion of quick metadata fetch."""
        print(f"DEBUG: Quick metadata ready for {url}: title={title}, has thumbnail={not pixmap.isNull()}")
        self.log_message.emit(f"Video metadata received: URL={url}, Title=\"{title}\"")
        
        # Update metadata
        self._mutex.lock()
        try:
            if url in self._metadata:
                # Only update title if it's better than the loading placeholder
                # or if the current title is a placeholder
                current_title = self._metadata[url].get('title', '')
                if (title and not title.startswith("Loading:") or 
                    current_title.startswith("Loading")):
                    print(f"DEBUG: Updating title for {url} from '{current_title}' to '{title}'")
                    self._metadata[url]['title'] = title
                    self.log_message.emit(f"Title updated from '{current_title}' to '{title}'")
                else:
                    self.log_message.emit(f"NOT updating title (keeping '{current_title}' instead of '{title}')")
                
                # Update thumbnail if we have one
                if not pixmap.isNull():
                    self._metadata[url]['thumbnail'] = pixmap
                
                # Get metadata values to use outside the lock
                meta_title = self._metadata[url]['title']
                meta_thumbnail = self._metadata[url]['thumbnail']
        finally:
            self._mutex.unlock()
        
        # Emit signal to update UI (outside the lock)
        self.log_message.emit(f"Sending UI update signal with title: \"{meta_title}\"")
        self.download_started.emit(url, meta_title, meta_thumbnail or QPixmap())
        
        # Debug log that we emitted the signal
        print(f"DEBUG: Emitted download_started signal for {url} with title '{meta_title}'")
        
        # Clean up thread
        if hasattr(self, '_quick_metadata_threads') and url in self._quick_metadata_threads:
            thread = self._quick_metadata_threads[url]
            if not thread.isRunning():
                thread.deleteLater()
                del self._quick_metadata_threads[url]
    
    def _fetch_quick_metadata(self, url):
        """
        DEPRECATED: Use _fetch_quick_metadata_threaded instead.
        This synchronous version is kept for backward compatibility.
        """
        # Start threaded version instead
        self._fetch_quick_metadata_threaded(url)
    
    def cancel_download(self, url):
        """Cancel a download or remove a completed download."""
        # Prepare variables to store what we need outside the lock
        thread_to_cancel = None
        url_to_cancel = url
        need_queue_update = False
        need_process_queue = False
        metadata_removed = False
        output_dir = None
        video_title = None
        
        # Lock only to access and modify internal data structures
        self._mutex.lock()
        try:
            print(f"DEBUG: Cancelling download for URL: {url}")
            
            # Check if download is active
            if url in self._active:
                thread_to_cancel = self._active.pop(url)
                need_process_queue = True
                need_queue_update = True
                
                # Store output directory and title for potential temp file cleanup
                if url in self._metadata:
                    self._metadata[url]['status'] = 'Cancelled'
                    output_dir = self._metadata[url].get('output_dir')
                    video_title = self._metadata[url].get('title')
            
            # Check if download is queued
            elif url in self._queue:
                self._queue.remove(url)
                need_queue_update = True
                
                # Remove metadata
                if url in self._metadata:
                    del self._metadata[url]
                    metadata_removed = True
            
            # Check if it's in the error list
            elif url in self._errors:
                self._errors.remove(url)
                need_queue_update = True
                
                # Remove metadata
                if url in self._metadata:
                    del self._metadata[url]
                    metadata_removed = True
                
                print(f"DEBUG: Removed error item: {url}")
            
            # Check if it's a completed download
            elif url in self._completed:
                self._completed.remove(url)
                need_queue_update = True
                
                # Remove metadata
                if url in self._metadata:
                    del self._metadata[url]
                    metadata_removed = True
                
                print(f"DEBUG: Removed completed download: {url}")
            
            # Check if it's in metadata but not tracked elsewhere
            elif url in self._metadata:
                # Just remove from metadata, it's completed
                print(f"DEBUG: Removing metadata for URL: {url}")
                del self._metadata[url]
                metadata_removed = True
                need_queue_update = True
            else:
                print(f"DEBUG: URL not found in any collection: {url}")
        finally:
            self._mutex.unlock()
        
        # Now perform operations that may take time or emit signals
        # without holding the lock
        if thread_to_cancel is not None:
            # Signal cancellation
            thread_to_cancel.cancel()
            
            # Wait for thread to finish, but with timeout to avoid UI freeze
            # Increased from 1 second to 3 seconds for more graceful shutdown
            if not thread_to_cancel.wait(3000):  # 3 second timeout
                # Thread didn't finish in time, just force termination
                thread_to_cancel.terminate()
                thread_to_cancel.wait()
            
            # Perform cleanup of temporary files if we had to force termination
            if output_dir and video_title:
                self._cleanup_temp_files(output_dir, video_title)
        
            print(f"DEBUG: Thread cancelled: {url_to_cancel}")
        
        # Emit signals outside the lock
        if not metadata_removed:
            self.log_message.emit(f"Cancelled download: {url_to_cancel}")
        else:
            self.log_message.emit(f"Removed from queue: {url_to_cancel}")
        
        # Update UI
        if need_queue_update:
            self.queue_updated.emit()
            # Process queue to start new downloads (without holding the lock)
            self._process_queue()
    
    def _cleanup_temp_files(self, output_dir, video_title):
        """Clean up temporary files after a forced termination."""
        try:
            import os
            import glob
            import re
            
            # Log that we're attempting cleanup
            self.log_message.emit(f"Cleaning up temporary files in {output_dir}")
            
            # Sanitize the video title for use in filename pattern matching
            # Remove characters that would interfere with glob patterns
            safe_title = re.sub(r'[^\w\s-]', '', video_title)
            
            # Different patterns to look for:
            # 1. Files with format ID suffixes: filename.f140.m4a, filename.f137.mp4, etc.
            # 2. Temporary .part files: filename.f140.m4a.part
            # 3. Temporary yt-dlp files: filename.f140.m4a.ytdl
            
            patterns = [
                os.path.join(output_dir, f"{safe_title}*.*.part"),
                os.path.join(output_dir, f"{safe_title}*.*.ytdl"),
                os.path.join(output_dir, f"{safe_title}*.f*.m4a"),
                os.path.join(output_dir, f"{safe_title}*.f*.mp4"),
                os.path.join(output_dir, f"{safe_title}*.f*.webm"),
            ]
            
            # Find and remove matching files
            removed_count = 0
            for pattern in patterns:
                for file_path in glob.glob(pattern):
                    try:
                        os.remove(file_path)
                        removed_count += 1
                        self.log_message.emit(f"Removed temporary file: {os.path.basename(file_path)}")
                    except Exception as e:
                        self.log_message.emit(f"Error removing file {file_path}: {str(e)}")
            
            if removed_count > 0:
                self.log_message.emit(f"Cleaned up {removed_count} temporary files")
            else:
                self.log_message.emit("No temporary files found to clean up")
            
        except Exception as e:
            self.log_message.emit(f"Error during temporary file cleanup: {str(e)}")
    
    def get_all_urls(self):
        """Get all URLs in the queue, active downloads, completed downloads, and error downloads."""
        self._mutex.lock()
        try:
            # Make a copy of the lists to avoid thread safety issues
            return list(self._queue) + list(self._active.keys()) + list(self._completed) + list(self._errors)
        finally:
            self._mutex.unlock()
    
    def get_status(self, url):
        """Get the status of a download."""
        if url in self._metadata:
            return self._metadata[url]['status']
        return None
    
    def get_progress(self, url):
        """Get the progress percentage of a download."""
        if url in self._metadata:
            return self._metadata[url]['progress']
        return 0
    
    def get_title(self, url):
        """Get the title of a video."""
        if url in self._metadata:
            return self._metadata[url]['title']
        return None
    
    def get_thumbnail(self, url):
        """Get the thumbnail for a video."""
        if url in self._metadata:
            return self._metadata[url]['thumbnail']
        return None
    
    def get_output_path(self, url):
        """Get the output directory for a completed download."""
        if url in self._metadata:
            return self._metadata[url].get('output_dir')
        return None
    
    def get_output_filename(self, url):
        """Get the filename of a completed download."""
        if url in self._metadata:
            return self._metadata[url].get('filename')
        return None
    
    def _process_queue(self):
        """Process the download queue and start new downloads if possible."""
        # Create a copy of the queue to avoid holding the lock during signal emissions
        urls_to_process = []
        metadata_to_fetch = []
        
        self._mutex.lock()
        try:
            # Check if we can start more downloads
            available_slots = self._max_concurrent - len(self._active)
            urls_to_start = min(available_slots, len(self._queue))
            
            # Store URLs that need UI updates
            urls_to_update = []
            
            for _ in range(urls_to_start):
                # Get next URL from queue
                url = self._queue.pop(0)
                
                # Get metadata
                metadata = self._metadata[url]
                format_options = metadata['format_options']
                output_dir = metadata['output_dir']
                
                urls_to_process.append((url, format_options, output_dir))
                metadata_to_fetch.append((url, format_options, output_dir))
                
                # Update metadata
                metadata['status'] = 'Starting'
                metadata['stats'] = 'Initializing...'
                
                # Store URLs that need UI updates
                urls_to_update.append(url)
                
                # Add to active downloads (but don't start thread yet)
                self._active[url] = None  # Will be replaced with thread
        finally:
            self._mutex.unlock()
        
        # Now emit progress signals for status updates
        for url in urls_to_update:
            # This will update the UI with the "Initializing..." message
            self.download_progress.emit(url, 0, "Initializing...")
        
        # Now process without holding the lock
        for url, format_options, output_dir in urls_to_process:
            # Create and start download thread
            thread = DownloadThread(url, format_options, output_dir)
            
            # Connect signals
            thread.progress_signal.connect(self._on_progress)
            thread.complete_signal.connect(self._on_complete)
            thread.error_signal.connect(self._on_error)
            thread.log_signal.connect(self.log_message)
            thread.processing_signal.connect(
                lambda url, message: self._on_processing(url, message)
            )
            
            # Start thread
            thread.start()
            
            # Update active downloads with thread
            self._mutex.lock()
            try:
                if url in self._active:
                    self._active[url] = thread
            finally:
                self._mutex.unlock()
            
            # Log and emit signals
            self.log_message.emit(f"Starting download: {url}")
        
        # Emit queue updated signal
        if urls_to_process:
            self.queue_updated.emit()
        
        # Fetch metadata for new downloads
        for url, format_options, output_dir in metadata_to_fetch:
            self._fetch_metadata(url, format_options, output_dir)
    
    def _fetch_metadata(self, url, format_options, output_dir):
        """Fetch metadata for a video in a separate thread."""
        # Create a QThread instead of a standard Python thread
        class MetadataThread(QThread):
            # Define signals that will be emitted safely to the main thread
            finished = pyqtSignal(str, str, QPixmap)
            error = pyqtSignal(str, str)
            log = pyqtSignal(str)
            
            def __init__(self, url, format_options=None, parent=None):
                super().__init__(parent)
                self.url = url
                self.format_options = format_options or {}
                print(f"DEBUG: MetadataThread created for URL: {self.url}")
                
            def run(self):
                try:
                    print(f"DEBUG: MetadataThread started for URL: {self.url}")
                    
                    # First check if we can get metadata directly via SiteModel
                    site = SiteModel.detect_site(self.url)
                    
                    if site != SiteModel.SITE_UNKNOWN:
                        # Get metadata directly from the appropriate platform model
                        self.log.emit(f"Fetching {site} metadata for: {self.url}")
                        title, pixmap = SiteModel.get_video_metadata(self.url)
                        
                        if title and pixmap:
                            print(f"DEBUG: Got {site} metadata: {title}")
                            self.finished.emit(self.url, title, pixmap)
                            return
                        elif title:
                            # We have title but no thumbnail, continue with yt-dlp to get thumbnail
                            print(f"DEBUG: Got {site} title only: {title}")
                            # Continue to yt-dlp flow but with title already known
                    
                    # For cases where direct API fails or for unsupported sites, use yt-dlp
                    from yt_dlp import YoutubeDL
                    
                    # Configure yt-dlp options
                    ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                    }
                    
                    # Add cookies options if present
                    if 'cookies' in self.format_options:
                        try:
                            cookie_file = self.format_options['cookies']
                            if os.path.exists(cookie_file):
                                ydl_opts['cookies'] = cookie_file
                                self.log.emit(f"Using cookies from file: {cookie_file}")
                            else:
                                self.log.emit(f"Warning: Cookie file not found: {cookie_file}")
                        except Exception as e:
                            self.log.emit(f"Error setting cookie file: {str(e)}")
                    
                    # Add cookies from browser if present (as fallback)
                    elif 'cookies_from_browser' in self.format_options:
                        try:
                            browser = self.format_options['cookies_from_browser']
                            ydl_opts['cookies_from_browser'] = browser
                            self.log.emit(f"Using cookies from {browser} browser")
                            
                            # Add debug info about closing the browser
                            if 'firefox' in browser.lower():
                                self.log.emit("Note: If Firefox is running, try closing it and retrying if cookie extraction fails")
                        except Exception as e:
                            error_msg = f"Error setting up browser cookies: {str(e)}"
                            self.log.emit(error_msg)
                            # We don't want to abort the download if cookie setup fails
                            # it will just try without cookies
                    
                    print(f"DEBUG: About to extract info for URL: {self.url}")
                    
                    # Extract info
                    with YoutubeDL(ydl_opts) as ydl:
                        self.log.emit(f"Fetching metadata for: {self.url}")
                        print(f"DEBUG: Starting extract_info for URL: {self.url}")
                        info = ydl.extract_info(self.url, download=False)
                        print(f"DEBUG: Finished extract_info for URL: {self.url}")
                        
                        title = info.get('title', 'Unknown Title')
                        
                        # Get the smallest thumbnail from the available options
                        thumbnails = info.get('thumbnails', [])
                        thumbnail_url = None
                        if thumbnails:
                            # Sort thumbnails by size (width*height) and get the smallest one
                            sorted_thumbnails = sorted(
                                [t for t in thumbnails if t.get('url') and t.get('width') and t.get('height')],
                                key=lambda t: t.get('width', 0) * t.get('height', 0)
                            )
                            if sorted_thumbnails:
                                thumbnail_url = sorted_thumbnails[0].get('url')
                            else:
                                # Fallback to default thumbnail
                                thumbnail_url = info.get('thumbnail')
                        else:
                            # Fallback to default thumbnail
                            thumbnail_url = info.get('thumbnail')
                        
                        print(f"DEBUG: Got title: {title} and thumbnail URL: {bool(thumbnail_url)}")
                        
                        # Try to download thumbnail using Qt's network capabilities
                        # This avoids the PIL dependency
                        if thumbnail_url:
                            try:
                                print(f"DEBUG: Downloading thumbnail from: {thumbnail_url}")
                                from PyQt6.QtCore import QUrl, QTimer
                                from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
                                from PyQt6.QtCore import QByteArray, QEventLoop
                                
                                # Create network manager
                                manager = QNetworkAccessManager()
                                
                                # Create request
                                request = QNetworkRequest(QUrl(thumbnail_url))
                                
                                # Set timeout for the request (30 seconds for slow connections)
                                request.setAttribute(QNetworkRequest.Attribute.CacheLoadControlAttribute, 
                                                  QNetworkRequest.CacheLoadControl.PreferNetwork)
                                
                                # Create event loop to wait for reply
                                loop = QEventLoop()
                                
                                # Create timeout timer
                                timeout_timer = QTimer()
                                timeout_timer.setSingleShot(True)
                                timeout_timer.timeout.connect(loop.quit)
                                
                                # Send request
                                reply = manager.get(request)
                                
                                # Connect signals
                                reply.finished.connect(loop.quit)
                                
                                # Start timeout timer (30 seconds)
                                timeout_timer.start(30000)
                                
                                # Wait for reply or timeout
                                loop.exec()
                                
                                # Check if we timed out
                                if timeout_timer.isActive():
                                    # Timer is still active, so we didn't time out
                                    timeout_timer.stop()
                                    
                                    if reply.error() == QNetworkReply.NetworkError.NoError:
                                        # Read data
                                        data = reply.readAll()
                                        
                                        # Create pixmap from data
                                        pixmap = QPixmap()
                                        pixmap.loadFromData(data)
                                        
                                        print(f"DEBUG: QPixmap loaded with size: {pixmap.width()}x{pixmap.height()}")
                                        
                                        # Emit signal with the results
                                        print(f"DEBUG: About to emit finished signal for URL: {self.url}")
                                        self.finished.emit(self.url, title, pixmap)
                                        print(f"DEBUG: Emitted finished signal for URL: {self.url}")
                                        return
                                    else:
                                        print(f"DEBUG: Network error: {reply.errorString()}")
                                else:
                                    # We timed out
                                    print(f"DEBUG: Thumbnail download timed out")
                                    reply.abort()
                            except Exception as e:
                                error_msg = f"Failed to load thumbnail: {str(e)}"
                                print(f"DEBUG: {error_msg}")
                                self.log.emit(error_msg)
                        
                        # If we got here, we either have no thumbnail URL or failed to load it
                        print(f"DEBUG: No thumbnail, emitting with empty QPixmap for URL: {self.url}")
                        self.finished.emit(self.url, title, QPixmap())
                        print(f"DEBUG: Emitted signal with empty QPixmap for URL: {self.url}")
                
                except Exception as e:
                    error_msg = f"Failed to fetch metadata: {str(e)}"
                    print(f"DEBUG ERROR: {error_msg}")
                    self.error.emit(self.url, error_msg)
                    print(f"DEBUG: Emitted error signal for URL: {self.url}")
        
        # Create and start the QThread
        metadata_thread = MetadataThread(url, format_options, self)
        
        # Connect signals to slots in the main thread
        metadata_thread.finished.connect(
            lambda url, title, pixmap: self._handle_metadata_finished(url, title, pixmap)
        )
        metadata_thread.error.connect(
            lambda url, error: self._handle_metadata_error(url, error)
        )
        metadata_thread.log.connect(self.log_message.emit)
        
        # Need to store reference to prevent garbage collection
        if not hasattr(self, '_metadata_threads'):
            self._metadata_threads = {}
        self._metadata_threads[url] = metadata_thread
        
        # Start the thread
        metadata_thread.start()

    def _handle_metadata_finished(self, url, title, pixmap):
        """Handle metadata fetch completion in the main thread."""
        print(f"DEBUG: _handle_metadata_finished called for URL: {url}")
        
        self._mutex.lock()
        try:
            if url in self._metadata:
                print(f"DEBUG: Updating metadata for URL: {url}")
                self._metadata[url]['title'] = title
                self._metadata[url]['thumbnail'] = pixmap
                print(f"DEBUG: About to emit download_started for URL: {url}")
                self.download_started.emit(url, title, pixmap)
                print(f"DEBUG: Emitted download_started for URL: {url}")
        finally:
            self._mutex.unlock()

    def _handle_metadata_error(self, url, error_message):
        """Handle metadata fetch error in the main thread."""
        self.log_message.emit(error_message)
        self._mutex.lock()
        try:
            if url in self._metadata:
                self.download_started.emit(url, "Unknown Title", QPixmap())
            # Clean up the thread
            if url in self._metadata_threads:
                self._metadata_threads[url].deleteLater()
                del self._metadata_threads[url]
        finally:
            self._mutex.unlock()
    
    def _on_progress(self, url, progress, status_text):
        """Handle progress updates from download threads."""
        if url in self._metadata:
            self._metadata[url]['progress'] = progress
            self._metadata[url]['stats'] = status_text
            self.download_progress.emit(url, progress, status_text)
    
    def _on_complete(self, url, output_dir, filename):
        """Handle download completion."""
        # Important diagnostic information for thumbnail click functionality
        print(f"Download complete - URL: {url}")
        print(f"Output directory: {output_dir}")
        print(f"Filename: {filename}")
        
        if not output_dir or not os.path.isdir(output_dir):
            print(f"WARNING: Output directory is invalid or does not exist: {output_dir}")
        
        if filename:
            # Check if the file actually exists
            filepath = os.path.join(output_dir, filename) if output_dir else None
            if filepath and os.path.exists(filepath):
                print(f"Confirmed file exists at: {filepath}")
            else:
                print(f"WARNING: File does not exist at expected path: {filepath}")
        
        self._mutex.lock()
        need_process_queue = False
        
        try:
            # Remove from active downloads
            if url in self._active:
                thread_to_cancel = self._active.pop(url)
                need_process_queue = True
            
            # Add to completed downloads
            if url not in self._completed:
                self._completed.append(url)
                
            # Update metadata
            if url in self._metadata:
                self._metadata[url]['status'] = 'Complete'
                self._metadata[url]['progress'] = 100
                # Store the output directory and filename in metadata
                self._metadata[url]['output_dir'] = output_dir
                self._metadata[url]['filename'] = filename
                print(f"Updated metadata with output_dir={output_dir}, filename={filename}")
                
        finally:
            self._mutex.unlock()
            
        # Emit signals
        self.download_complete.emit(url, output_dir, filename)
        self.queue_updated.emit()
        self.log_message.emit(f"Download completed: {url}")
        
        # Process queue if needed
        if need_process_queue:
            self._process_queue()
    
    def _on_error(self, url, error_message):
        """Handle download errors."""
        print(f"DEBUG: _on_error called for URL: {url} with message: {error_message}")
        
        thread = None
        need_process_queue = False
        
        self._mutex.lock()
        
        try:
            # Remove from active downloads
            if url in self._active:
                thread = self._active.pop(url)
                need_process_queue = True
                
                # Move to error list instead of removing completely
                if url not in self._errors:
                    self._errors.append(url)
                
                # Update metadata
                if url in self._metadata:
                    self._metadata[url]['status'] = 'Error'
                    self._metadata[url]['stats'] = error_message
                    self._metadata[url]['dismissable'] = True  # Mark as dismissable
                
                # Log the error
                print(f"DEBUG: Download error updated in metadata: {error_message}")
        finally:
            self._mutex.unlock()
        
        # Now emit signals outside the lock
        self.log_message.emit(f"Download error: {error_message}")
        self.download_error.emit(url, error_message)
        
        # Clean up thread if needed
        if thread:
            # Ensure the thread is disconnected
            try:
                thread.progress_signal.disconnect()
                thread.complete_signal.disconnect()
                thread.error_signal.disconnect()
                thread.log_signal.disconnect()
                thread.processing_signal.disconnect()
            except Exception:
                # Ignore disconnection errors
                pass
            
            thread.wait(1000)  # Wait up to 1 second for thread to finish
            thread.deleteLater()
            
            print(f"DEBUG: Thread cleanup completed for URL: {url}")
        
        # Update UI
        self.queue_updated.emit()
        
        # Process queue to start new downloads if there's room
        if need_process_queue:
            self._process_queue()
    
    def _on_processing(self, url, message):
        """Handle processing started signal from download thread."""
        if url in self._metadata:
            self._metadata[url]['stats'] = message
            self.download_progress.emit(url, 0, message)
    
    def dismiss_error(self, url):
        """Dismiss an error item from the queue."""
        self._mutex.lock()
        try:
            # Remove from error list
            if url in self._errors:
                self._errors.remove(url)
                
            # Remove metadata
            if url in self._metadata:
                del self._metadata[url]
            
            print(f"DEBUG: Dismissed error for URL: {url}")
        finally:
            self._mutex.unlock()
        
        # Update UI
        self.queue_updated.emit()
        self.log_message.emit(f"Dismissed error for: {url}") 