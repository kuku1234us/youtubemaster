"""
Download queue component for displaying current downloads.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel, 
    QSizePolicy, QHBoxLayout, QSpinBox, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize

from youtubemaster.ui.FlowLayout import FlowLayout
from youtubemaster.models.DownloadManager import DownloadManager
from youtubemaster.ui.YoutubeProgress import YoutubeProgress

class DownloadQueue(QScrollArea):
    """
    A component that displays a queue of YouTube downloads with thumbnails and progress.
    """
    
    def __init__(self, download_manager):
        """Initialize the download queue."""
        super().__init__()
        
        # Store reference to download manager
        self.download_manager = download_manager
        
        # Configure the scroll area
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create container widget and layout
        self.container = QWidget()
        self.container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Create header layout
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 5)
        
        # Queue label
        queue_label = QLabel("Download Queue")
        queue_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(queue_label)
        
        # Concurrent downloads control
        concurrent_layout = QHBoxLayout()
        concurrent_label = QLabel("Max Concurrent:")
        concurrent_layout.addWidget(concurrent_label)
        
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setMinimum(1)
        self.concurrent_spin.setMaximum(5)
        self.concurrent_spin.setValue(self.download_manager.get_max_concurrent())
        self.concurrent_spin.valueChanged.connect(self.download_manager.set_max_concurrent)
        concurrent_layout.addWidget(self.concurrent_spin)
        
        header_layout.addLayout(concurrent_layout)
        
        # Add Clear Completed button
        self.clear_completed_button = QPushButton("Clear Completed")
        self.clear_completed_button.clicked.connect(self.clear_completed_downloads)
        header_layout.addWidget(self.clear_completed_button)
        
        header_layout.addStretch()
        
        # Use FlowLayout for the downloads grid
        self.flow_layout = FlowLayout()
        self.flow_layout.setSpacing(10)  # Add some space between items
        
        # Main layout to contain header and flow layout
        main_layout = QVBoxLayout(self.container)
        main_layout.addLayout(header_layout)
        main_layout.addLayout(self.flow_layout)
        main_layout.addStretch()  # Add stretch at the end to push everything to the top
        
        # Set the container as the widget for the scroll area
        self.setWidget(self.container)
        
        # Connect signals from download manager
        self.download_manager.queue_updated.connect(self.update_queue)
        self.download_manager.download_started.connect(self.on_download_started)
        self.download_manager.download_progress.connect(self.on_download_progress)
        self.download_manager.download_complete.connect(self.on_download_complete)
        self.download_manager.download_error.connect(self.on_download_error)
        
        # Create a dictionary to track progress components
        self.progress_components = {}
        
        # Initial queue update
        self.update_queue()
    
    def _create_cancel_handler(self, url):
        """Create a function that captures the URL parameter correctly."""
        return lambda: self.on_cancel_clicked(url)
    
    def update_queue(self):
        """Update the display of the download queue."""
        print("DEBUG: DownloadQueue.update_queue called")  # Debug log
        
        # Clear existing progress components that are no longer in the queue
        urls_in_queue = set(self.download_manager.get_all_urls())
        urls_to_remove = set(self.progress_components.keys()) - urls_in_queue
        
        print(f"DEBUG: URLs in queue: {len(urls_in_queue)}, URLs to remove: {len(urls_to_remove)}")  # Debug log
        
        for url in urls_to_remove:
            if url in self.progress_components:
                component = self.progress_components.pop(url)
                # Remove from layout and delete
                print(f"DEBUG: Removing component for URL: {url}")  # Debug log
                self.flow_layout.removeWidget(component)
                component.deleteLater()
        
        # Add new items to the queue
        for url in urls_in_queue:
            if url not in self.progress_components:
                print(f"DEBUG: Adding progress component for URL: {url}")  # Debug log
                
                # Get download status
                status = self.download_manager.get_status(url)
                progress = self.download_manager.get_progress(url)
                title = self.download_manager.get_title(url) or "Loading..."
                thumbnail = self.download_manager.get_thumbnail(url)
                
                print(f"DEBUG: Status: {status}, Title: {title}, Has thumbnail: {thumbnail is not None}")  # Debug log
                
                # Create progress component
                progress_component = YoutubeProgress(url, title)
                progress_component.set_progress(progress)
                progress_component.set_status(status)
                
                if thumbnail:
                    print(f"DEBUG: Setting thumbnail for URL: {url}")  # Debug log
                    progress_component.set_thumbnail(thumbnail)
                
                # Connect the cancel signal with explicit URL capture
                progress_component.cancel_requested.connect(
                    self._create_cancel_handler(url)
                )
                
                # Add to layout and dictionary
                print(f"DEBUG: Adding component to layout for URL: {url}")  # Debug log
                self.flow_layout.addWidget(progress_component)
                self.progress_components[url] = progress_component
        
        print("DEBUG: DownloadQueue.update_queue finished")  # Debug log
    
    def on_download_started(self, url, title, thumbnail):
        """Handle download started signal."""
        if url in self.progress_components:
            component = self.progress_components[url]
            component.set_title(title or "Downloading...")
            component.set_status("Starting")  # This will trigger the overlay
            component.set_progress(0)
            
            if thumbnail:
                component.set_thumbnail(thumbnail)
    
    def on_download_progress(self, url, progress, status_text):
        """Handle download progress signal."""
        if url in self.progress_components:
            component = self.progress_components[url]
            component.set_progress(progress)
            if status_text:
                component.set_stats(status_text)
    
    def on_download_complete(self, url):
        """Handle download completion signal."""
        if url in self.progress_components:
            component = self.progress_components[url]
            component.set_progress(100)
            component.set_status("Complete")
            component.set_stats("Download completed")
    
    def on_download_error(self, url, error_message):
        """Handle download error signal."""
        if url in self.progress_components:
            component = self.progress_components[url]
            component.set_status("Error")
            component.set_stats(error_message)
    
    def on_cancel_clicked(self, url):
        """Handle cancel button click with explicit URL parameter."""
        print(f"DEBUG: Cancel requested for URL: {url}")
        try:
            # Process the URL to ensure it's valid
            if url and isinstance(url, str):
                self.download_manager.cancel_download(url)
            else:
                print(f"DEBUG: Invalid URL for cancellation: {url}")
        except Exception as e:
            print(f"DEBUG: Error cancelling download: {e}")
    
    def clear_completed_downloads(self):
        """Clear all completed downloads from the queue."""
        urls_to_remove = []
        
        # Find all completed downloads
        for url, component in self.progress_components.items():
            if component.status == "Complete":
                urls_to_remove.append(url)
        
        # Cancel each download (which removes it from the UI)
        for url in urls_to_remove:
            self.download_manager.cancel_download(url) 