"""
Video Input component for YouTube Master application.
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
    QPushButton, QButtonGroup, QLabel, QComboBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor

from youtubemaster.models.YoutubeModel import YoutubeModel
from youtubemaster.models.Yt_DlpModel import YtDlpModel
from youtubemaster.models.ThemeManager import ThemeManager
from youtubemaster.models.SiteModel import SiteModel

class ToggleButton(QPushButton):
    """Custom toggle button that can be toggled on/off with clear visual state."""
    
    def __init__(self, text, parent=None, exclusive=False):
        """Initialize the toggle button."""
        super().__init__(text, parent)
        self.setCheckable(True)
        self._exclusive = exclusive
        self.setMinimumWidth(50)  # Reduced from 70 to 50
        
        # Apply stylesheet for toggle states with smaller dimensions
        self.setStyleSheet(ThemeManager.get_toggle_button_style())
        
        # Set a fixed height to make buttons shorter
        self.setFixedHeight(22)  # This will make them shorter
    
    def toggle(self):
        """Toggle the button state."""
        if self._exclusive or not self.isChecked():
            self.setChecked(not self.isChecked())
        # For exclusive buttons, we don't allow unchecking by clicking again
        # For non-exclusive buttons, we allow toggling on and off

class VideoInput(QWidget):
    """
    Video input component with URL entry and format selection.
    
    Emits:
        format_changed: When the selected format changes
        enter_pressed: When Enter is pressed in the URL field
        add_clicked: When the Add button is clicked
    """
    
    format_changed = pyqtSignal(dict)
    enter_pressed = pyqtSignal()
    add_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        """Initialize the video input component."""
        super().__init__(parent)
        
        # Initialize layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Create URL input row with Add button
        url_row = QHBoxLayout()
        
        # URL input
        url_label = QLabel("Video URL:")
        url_row.addWidget(url_label)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter YouTube or Bilibili URL or Video ID...")
        self.url_input.returnPressed.connect(self.on_enter_pressed)
        url_row.addWidget(self.url_input)
        
        # Add button (moved from main window)
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.on_add_clicked)
        self.add_button.setFixedWidth(80)  # Set a fixed width
        url_row.addWidget(self.add_button)
        
        self.layout.addLayout(url_row)
        
        # Create format selection row
        self.create_format_row()
        
        # Initial format update
        self.update_format()
    
    def create_format_row(self):
        """Create the format selection row."""
        format_layout = QHBoxLayout()
        format_layout.setSpacing(5)  # Reduced from 10 to 5
        
        # Create resolution buttons
        self.resolution_group = QButtonGroup(self)
        self.resolution_group.setExclusive(False)  # We'll handle exclusivity manually
        
        self.btn_1080p = ToggleButton("1080p", exclusive=True)
        self.btn_720p = ToggleButton("720p", exclusive=True)
        self.btn_480p = ToggleButton("480p", exclusive=True)
        self.btn_audio = ToggleButton("Audio", exclusive=True)
        
        # Set 720p as default
        self.btn_720p.setChecked(True)
        
        # Add buttons to layout and group
        format_layout.addWidget(self.btn_1080p)
        format_layout.addWidget(self.btn_720p)
        format_layout.addWidget(self.btn_480p)
        format_layout.addWidget(self.btn_audio)
        
        self.resolution_group.addButton(self.btn_1080p)
        self.resolution_group.addButton(self.btn_720p)
        self.resolution_group.addButton(self.btn_480p)
        self.resolution_group.addButton(self.btn_audio)
        
        # Create option toggles
        self.btn_https = ToggleButton("HTTPS")
        self.btn_https.setChecked(True)  # Default is on
        format_layout.addWidget(self.btn_https)
        
        self.btn_m4a = ToggleButton("M4A")
        self.btn_m4a.setChecked(True)  # Default is on
        format_layout.addWidget(self.btn_m4a)
        
        # Add stretch to push everything to the left
        format_layout.addStretch()
        
        # Connect signals
        self.btn_1080p.clicked.connect(self.on_resolution_clicked)
        self.btn_720p.clicked.connect(self.on_resolution_clicked)
        self.btn_480p.clicked.connect(self.on_resolution_clicked)
        self.btn_audio.clicked.connect(self.on_resolution_clicked)
        self.btn_https.clicked.connect(self.update_format)
        self.btn_m4a.clicked.connect(self.update_format)
        
        self.layout.addLayout(format_layout)
    
    def on_resolution_clicked(self):
        """Handle resolution button clicks - ensure one is always selected."""
        sender = self.sender()
        
        # Ensure one resolution is always selected
        if not sender.isChecked():
            sender.setChecked(True)
            return
        
        # Uncheck all other resolution buttons
        for button in self.resolution_group.buttons():
            if button != sender:
                button.setChecked(False)
        
        # If audio is selected, turn off m4a (user can turn it back on)
        if sender == self.btn_audio:
            self.btn_m4a.setChecked(False)
        
        self.update_format()
    
    def update_format(self):
        """Update the format selection based on button states and emit signal."""
        # Get format options from YtDlpModel
        format_dict = self.get_format_options()
        
        # Emit the format changed signal
        self.format_changed.emit(format_dict)
    
    def on_enter_pressed(self):
        """Handle enter key in URL field."""
        self.enter_pressed.emit()
    
    def on_add_clicked(self):
        """Handle Add button click."""
        self.add_clicked.emit()
    
    def get_url(self):
        """Get the entered URL and clean it from unnecessary parameters."""
        url = self.url_input.text().strip()
        
        # Use SiteModel to clean the URL based on detected platform
        return SiteModel.get_clean_url(url)
    
    def set_url(self, url):
        """Set the URL input text."""
        self.url_input.setText(url)
        self.url_input.selectAll()
    
    def get_format_options(self):
        """Get the selected format options using YtDlpModel."""
        # Determine selected resolution
        resolution = None
        if self.btn_1080p.isChecked():
            resolution = 1080
        elif self.btn_720p.isChecked():
            resolution = 720
        elif self.btn_480p.isChecked():
            resolution = 480
        # Audio only if none of the above are checked
        
        # Use YtDlpModel to generate the format options
        return YtDlpModel.generate_format_string(
            resolution=resolution,
            use_https=self.btn_https.isChecked(),
            use_m4a=self.btn_m4a.isChecked()
        )