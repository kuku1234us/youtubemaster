"""
YouTube progress component for displaying download progress with thumbnails.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QPushButton, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QFont, QColor, QPalette

from youtubemaster.utils.config import config

class TitleProgressBar(QFrame):
    """A custom progress bar that displays text and fills with a background color."""
    
    def __init__(self, parent=None):
        """Initialize the title progress bar."""
        super().__init__(parent)
        
        # Set fixed height
        self.setFixedHeight(20)
        
        # Set frame properties - explicitly use a border
        self.setFrameShape(QFrame.Shape.Box)
        self.setFrameShadow(QFrame.Shadow.Plain)
        
        # Create a child frame for the progress fill
        self.progress_fill = QFrame(self)
        self.progress_fill.setGeometry(1, 1, 0, self.height() - 2)  # Initial size with border offset
        
        # Set the progress fill with reversed gradient (darker on left, brighter on right)
        self.progress_fill.setStyleSheet("""
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,  /* Direction: left to right */
                stop:0 #00213A,  /* Start with very dark blue */
                stop:1 #007ACC   /* End with bright blue */
            );
        """)
        
        # Create layout for the text
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 0, 5, 0)
        
        # Create label for title
        self.title_label = QLabel("Loading...")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        # Use smaller font for title
        font = self.title_label.font()
        font.setPointSize(7)
        self.title_label.setFont(font)
        
        # Add to layout
        self.layout.addWidget(self.title_label)
        
        # Ensure text appears on top of the progress fill
        self.title_label.raise_()
        
        # Set the border and background
        self.setStyleSheet("""
            TitleProgressBar {
                border: 1px solid #555555;
                background-color: #1E1E1E;
            }
            
            QLabel {
                background-color: transparent;
                color: white;
            }
        """)
        
        # Initialize progress value
        self.progress_value = 0
    
    def set_title(self, title):
        """Set the title text."""
        # Truncate title if too long
        if len(title) > 50:
            title = title[:47] + "..."
        self.title_label.setText(title)
    
    def set_progress(self, value):
        """Set the progress value (0-100)."""
        self.progress_value = max(0, min(100, value))
        
        # Update the progress fill position and size
        # Fill from left to right instead of right to left
        fill_width = int((self.width() - 2) * (self.progress_value / 100.0))
        self.progress_fill.setGeometry(
            1,                  # Start from left edge + 1px border
            1,                  # 1px from top border
            fill_width,         # Width based on progress
            self.height() - 2   # Height with 1px margin top and bottom
        )
    
    def resizeEvent(self, event):
        """Handle resize events to update the progress fill."""
        super().resizeEvent(event)
        # Update the progress fill when the widget is resized
        self.set_progress(self.progress_value)

class YoutubeProgress(QWidget):
    """
    Component displaying YouTube video download progress with thumbnail.
    
    Signals:
        cancel_requested: When the user clicks the cancel button
    """
    
    cancel_requested = pyqtSignal(str)
    
    def __init__(self, url, title=None, parent=None):
        """Initialize the YouTube progress component."""
        super().__init__(parent)
        
        # Store URL
        self.url = url
        
        # Set size policy
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        # Create layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Create thumbnail container with relative positioning for the cancel button
        self.thumbnail_container = QFrame()
        self.thumbnail_container.setFrameShape(QFrame.Shape.NoFrame)
        self.thumbnail_container.setFixedSize(160, 90)  # Half the original size
        
        # Use absolute layout for thumbnail container
        self.thumbnail_container.setLayout(QVBoxLayout())
        self.thumbnail_container.layout().setContentsMargins(0, 0, 0, 0)
        
        # Create thumbnail label
        self.thumbnail = QLabel()
        self.thumbnail.setFixedSize(160, 90)
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setStyleSheet("background-color: #2A2A2A;")
        self.thumbnail_container.layout().addWidget(self.thumbnail)
        
        # Create cancel button as overlay
        self.cancel_button = QPushButton("×")  # Using multiplication sign as X
        self.cancel_button.setFixedSize(20, 20)  # Slightly smaller button
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                border-radius: 10px;
                font-weight: bold;
                font-size: 14px;
                padding: 0px 0px 3px 0px; /* Adjust padding to center the × character */
                text-align: center;
            }
            QPushButton:hover {
                background-color: rgba(255, 0, 0, 0.8);
            }
        """)
        self.cancel_button.clicked.connect(self.on_cancel_clicked)
        
        # Position cancel button at top-right of thumbnail
        self.cancel_button.setParent(self.thumbnail_container)
        self.cancel_button.move(135, 5)  # Adjust position for smaller thumbnail
        
        # Create title progress bar
        self.progress_bar = TitleProgressBar()
        self.progress_bar.setFixedWidth(160)  # Match thumbnail width
        
        if title:
            self.progress_bar.set_title(title)
        
        # Create stats overlay for showing download progress details
        self.stats_overlay = QLabel("Waiting...")
        self.stats_overlay.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self.stats_overlay.setWordWrap(True)
        self.stats_overlay.setStyleSheet("""
            background-color: rgba(0, 0, 0, 0.7);
            color: white;
            padding: 3px;
            border-radius: 2px;
            font-size: 8pt;
        """)
        self.stats_overlay.setParent(self.thumbnail_container)
        self.stats_overlay.move(4, 52)  # Adjust position for smaller thumbnail
        self.stats_overlay.setFixedSize(152, 34)  # Adjust size proportionally
        self.stats_overlay.hide()  # Hide initially until we have stats
        
        # Add widgets to layout
        self.layout.addWidget(self.thumbnail_container)
        self.layout.addWidget(self.progress_bar)
        
        # Initialize stats and status
        self.stats = ""
        self.status = "Queued"
    
    def set_thumbnail(self, pixmap):
        """Set the thumbnail image."""
        if isinstance(pixmap, QPixmap):
            # Scale pixmap to FILL the label (expanding if needed)
            scaled_pixmap = pixmap.scaled(
                160, 90,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,  # Changed from KeepAspectRatio
                Qt.TransformationMode.SmoothTransformation
            )
            
            # If the scaled image is larger than the container, center-crop it
            if scaled_pixmap.width() > 160 or scaled_pixmap.height() > 90:
                x = (scaled_pixmap.width() - 160) / 2 if scaled_pixmap.width() > 160 else 0
                y = (scaled_pixmap.height() - 90) / 2 if scaled_pixmap.height() > 90 else 0
                scaled_pixmap = scaled_pixmap.copy(int(x), int(y), 160, 90)
            
            self.thumbnail.setPixmap(scaled_pixmap)
        elif isinstance(pixmap, str) and os.path.isfile(pixmap):
            # Load from file path
            self.set_thumbnail(QPixmap(pixmap))
        else:
            # Reset thumbnail
            self.thumbnail.clear()
    
    def set_progress(self, progress):
        """Set the progress value (0-100)."""
        self.progress_bar.set_progress(progress)
    
    def set_title(self, title):
        """Set the title text."""
        self.progress_bar.set_title(title)
    
    def set_status(self, status):
        """Set the status text and update the overlay based on status."""
        self.status = status
        
        # Show appropriate overlay message based on status
        if status == "Starting":
            self.set_stats("Processing started...")
        elif status == "Queued":
            self.set_stats("Waiting in queue...")
        elif status == "Complete":
            self.set_stats("Download completed")
        elif status == "Error":
            # Don't override error message if already set
            if not self.stats or not self.stats.startswith("Error"):
                self.set_stats("Error occurred")
    
    def set_stats(self, stats):
        """Set the stats text."""
        self.stats = stats
        if stats:
            self.stats_overlay.setText(stats)
            self.stats_overlay.show()
        else:
            self.stats_overlay.hide()
    
    def on_cancel_clicked(self):
        """Handle cancel button click."""
        self.cancel_requested.emit(self.url)
    
    def sizeHint(self):
        """Return the preferred size for the widget."""
        return QSize(160, 110)  # 160x90 thumbnail + 20 for progress bar (was 120)

    def set_url(self, url):
        """Set the YouTube URL."""
        if not url:
            self.clear()
            return
        
        self.url = url
        # We'll let the DownloadManager handle fetching the thumbnail
    
    def clear(self):
        """Clear the thumbnail and progress."""
        self.thumbnail.clear()
        self.progress_bar.set_progress(0)
        self.stats = ""
        self.stats_overlay.hide()
        self.status = "Queued"
    
    def resizeEvent(self, event):
        """Handle resize events to update progress indicator position."""
        super().resizeEvent(event)
        # Update the progress indicator position when resized
        self.progress_bar.resizeEvent(event)

    def set_url(self, url):
        """Set the YouTube URL."""
        if not url:
            self.clear()
            return
        
        self.url = url
        # We'll let the DownloadManager handle fetching the thumbnail
    
    def clear(self):
        """Clear the thumbnail and progress."""
        self.thumbnail.clear()
        self.progress_bar.set_progress(0)
        self.stats = ""
        self.stats_overlay.hide()
        self.status = "Queued"
    
    def resizeEvent(self, event):
        """Handle resize events to scale the thumbnail."""
        super().resizeEvent(event)
        if hasattr(self, 'base_pixmap') and self.base_pixmap is not None:
            # Re-scale the pixmap when the widget is resized
            scaled_pixmap = self.base_pixmap.scaled(
                self.thumbnail.width(),
                self.thumbnail.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.set_thumbnail(scaled_pixmap) 