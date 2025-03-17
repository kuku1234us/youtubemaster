"""
Download manager for handling multiple YouTube downloads.
"""
import os
import threading
import time
from typing import Dict, List, Optional, Any, Tuple
from queue import Queue

from PyQt6.QtCore import QObject, pyqtSignal, QThread, QMutex
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

from youtubemaster.utils.logger import Logger
from youtubemaster.models.YoutubeModel import YoutubeModel

class DownloadThread(QThread):
    """Thread for processing a single download."""
    
    # Define signals
    progress_signal = pyqtSignal(str, float, str)  # url, progress percent, status text
    complete_signal = pyqtSignal(str)  # url
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
    
    def run(self):
        """Run the download process."""
        try:
            from yt_dlp import YoutubeDL
            from yt_dlp.utils import DownloadError
            import os
            import time
            
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
                
                elif d['status'] == 'finished':
                    self.log_signal.emit(f"Finished downloading part of {self.url}")
            
            # Signal that processing is starting
            self.processing_signal.emit(self.url, "Processing started...")
            
            # Configure yt-dlp options
            ydl_opts = {
                'format': self.format_options.get('format'),
                'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
                'progress_hooks': [progress_hook],
                'quiet': False,
                'no_warnings': False,
                'no_color': True,
                'no_mtime': True,  # Don't use the media timestamp
            }
            
            # Add format_sort if it exists in options
            if 'format_sort' in self.format_options:
                ydl_opts['format_sort'] = self.format_options['format_sort']
            
            # Extract info first to get title and thumbnail
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
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
                ydl.download([self.url])
            
            # Find new files after download
            files_after = set(os.listdir(self.output_dir))
            new_files = files_after - files_before
            
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
            
            # Signal completion
            self.complete_signal.emit(self.url)
            
        except DownloadError as e:
            self.error_signal.emit(self.url, f"Download error: {str(e)}")
        except Exception as e:
            self.error_signal.emit(self.url, f"Error: {str(e)}")
    
    def cancel(self):
        """Cancel the download."""
        self.cancelled = True


class DownloadManager(QObject):
    """Manager for handling multiple YouTube downloads."""
    
    # Define signals
    queue_updated = pyqtSignal()
    download_started = pyqtSignal(str, str, QPixmap)  # url, title, thumbnail
    download_progress = pyqtSignal(str, float, str)  # url, progress percentage, status text
    download_complete = pyqtSignal(str)  # url
    download_error = pyqtSignal(str, str)  # url, error message
    log_message = pyqtSignal(str)  # log message
    
    def __init__(self, parent=None):
        """Initialize the download manager."""
        super().__init__(parent)
        
        # Download queue and metadata storage
        self._queue = []  # URLs waiting to be downloaded
        self._active = {}  # {url: thread} for active downloads
        self._completed = []  # URLs of completed downloads
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
    
    def add_download(self, url, format_options, output_dir):
        """Add a download to the queue."""
        # Lock to ensure thread safety
        self._mutex.lock()
        
        try:
            print(f"DEBUG: Adding download for URL: {url}")
            
            # Check if URL is already in queue or active
            if url in self._queue or url in self._active:
                print(f"DEBUG: URL already in queue: {url}")
                return False
            
            # Add to queue
            self._queue.append(url)
            
            print(f"DEBUG: Added URL to queue: {url}")
            
            # Initialize metadata
            self._metadata[url] = {
                'title': 'Loading...',
                'status': 'Queued',
                'progress': 0,
                'output_dir': output_dir,
                'format_options': format_options,
                'thumbnail': None,
                'stats': ''
            }
            
            print(f"DEBUG: About to release mutex before queue_updated signal")
            
            # Create local copies of data needed for processing
            # so we can release the mutex before emitting signals
            queue_to_process = True
            
        finally:
            self._mutex.unlock()
        
        # Immediately fetch basic metadata using YoutubeModel (faster than yt-dlp)
        self._fetch_quick_metadata(url)
        
        # Emit signal AFTER releasing the mutex
        self.queue_updated.emit()
        self.log_message.emit(f"Added to queue: {url}")
        
        print(f"DEBUG: About to process queue for URL: {url}")
        
        # Process queue to start download if possible
        if queue_to_process:
            self._process_queue()
        
        print(f"DEBUG: Finished adding URL: {url}")
        
        return True
    
    def _fetch_quick_metadata(self, url):
        """Quickly fetch basic metadata without waiting for yt-dlp."""
        # Extract video ID and get thumbnail
        video_id = YoutubeModel.extract_video_id(url)
        if video_id:
            # Try to get title and thumbnail together from YouTube API
            title, pixmap = YoutubeModel.get_video_metadata(url)
            
            if not title:
                title = f"Loading: {video_id}"
            
            if pixmap:
                # Update the thumbnail scaling to fill the frame properly
                from PyQt6.QtCore import Qt  # Need to import Qt
                
                # Scale the pixmap before storing it
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
                
                # Update metadata
                self._mutex.lock()
                try:
                    if url in self._metadata:
                        self._metadata[url]['title'] = title
                        self._metadata[url]['thumbnail'] = scaled_pixmap
                        self.download_started.emit(url, title, scaled_pixmap)
                finally:
                    self._mutex.unlock()
                
                self.log_message.emit(f"Loaded quick metadata for {url}")
    
    def cancel_download(self, url):
        """Cancel a download or remove a completed download."""
        # Prepare variables to store what we need outside the lock
        thread_to_cancel = None
        url_to_cancel = url
        need_queue_update = False
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
        """Get all URLs in the queue, active downloads, and completed downloads."""
        self._mutex.lock()
        try:
            # Make a copy of the lists to avoid thread safety issues
            return list(self._queue) + list(self._active.keys()) + list(self._completed)
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
            
            def __init__(self, url, parent=None):
                super().__init__(parent)
                self.url = url
                print(f"DEBUG: MetadataThread created for URL: {self.url}")
                
            def run(self):
                try:
                    print(f"DEBUG: MetadataThread started for URL: {self.url}")
                    
                    from yt_dlp import YoutubeDL
                    
                    # Configure yt-dlp options
                    ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                    }
                    
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
                                from PyQt6.QtCore import QUrl
                                from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
                                from PyQt6.QtCore import QByteArray, QEventLoop
                                
                                # Create network manager
                                manager = QNetworkAccessManager()
                                
                                # Create request
                                request = QNetworkRequest(QUrl(thumbnail_url))
                                
                                # Create event loop to wait for reply
                                loop = QEventLoop()
                                
                                # Send request
                                reply = manager.get(request)
                                
                                # Connect signals
                                reply.finished.connect(loop.quit)
                                
                                # Wait for reply
                                loop.exec()
                                
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
        metadata_thread = MetadataThread(url, self)
        
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
    
    def _on_complete(self, url):
        """Handle download completion."""
        thread = None
        emit_complete = False
        
        self._mutex.lock()
        try:
            # Remove from active downloads
            if url in self._active:
                thread = self._active.pop(url)
                
                # Add to completed downloads
                if url not in self._completed:
                    self._completed.append(url)
                
                # Update metadata
                if url in self._metadata:
                    self._metadata[url]['status'] = 'Complete'
                    self._metadata[url]['progress'] = 100
                    emit_complete = True

            # Process queue immediately while we hold the lock and know there's a free slot
            process_queue_needed = len(self._active) < self._max_concurrent and self._queue
        finally:
            self._mutex.unlock()
        
        # Do these operations without holding the lock
        if emit_complete:
            # Log and notify
            self.log_message.emit(f"Download completed: {url}")
            self.download_complete.emit(url)
        
        # Clean up thread after emitting signals
        if thread:
            thread.deleteLater()
        
        # Process queue to start new downloads immediately if needed
        if process_queue_needed:
            self._process_queue()
    
    def _on_error(self, url, error_message):
        """Handle download errors."""
        self._mutex.lock()
        
        try:
            # Remove from active downloads
            if url in self._active:
                thread = self._active.pop(url)
                
                # Update metadata
                if url in self._metadata:
                    self._metadata[url]['status'] = 'Error'
                    self._metadata[url]['stats'] = error_message
                
                # Log and notify
                self.log_message.emit(f"Download error: {error_message}")
                self.download_error.emit(url, error_message)
                
                # Process queue to start new downloads
                self._process_queue()
        finally:
            self._mutex.unlock()

    def _on_processing(self, url, message):
        """Handle processing started signal from download thread."""
        if url in self._metadata:
            self._metadata[url]['stats'] = message
            self.download_progress.emit(url, 0, message) 