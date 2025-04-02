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
from youtubemaster.utils.config import config

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

        # Replace subtitle label and input with toggle button
        self.btn_subtitles = ToggleButton("Subtitles")
        self.btn_subtitles.setChecked(config.get('subtitles.enabled', True))  # Default is on
        self.btn_subtitles.setToolTip("Enable/disable subtitle download")
        self.btn_subtitles.clicked.connect(self.on_subtitles_toggled)
        format_layout.addWidget(self.btn_subtitles)
        
        # Add cookie toggle button
        self.btn_cookies = ToggleButton("Cookies")
        self.btn_cookies.setChecked(config.get('cookies.enabled', False))  # Default is off
        self.btn_cookies.setToolTip("Use Firefox cookies to bypass YouTube bot verification")
        self.btn_cookies.clicked.connect(self.on_cookies_toggled)
        format_layout.addWidget(self.btn_cookies)
        
        # Add language selection combo box
        self.subtitle_lang_combo = QComboBox()
        self.subtitle_lang_combo.setFixedWidth(120)  # Increased from 70 to 120 pixels
        self.subtitle_lang_combo.setEditable(True)  # Allow custom language codes
        self.subtitle_lang_combo.setToolTip("Select subtitle language (e.g., 'en' for English, 'zh' for Chinese)")
        
        # Make the dropdown menu wider
        self.subtitle_lang_combo.view().setMinimumWidth(200)  # Make dropdown wider than the combo box
        
        # Add common language options
        language_options = [
            ("en", "English"),
            ("zh", "中文"),
            ("ja", "日本語"),
            ("es", "Español"),
            ("fr", "Français"),
            ("de", "Deutsch"),
            ("ko", "한국어"),
            ("ru", "Русский"),
            ("pt", "Português"),
            ("ar", "العربية"),
            ("hi", "हिन्दी"),
            ("all", "All Languages")
        ]
        
        # Populate the combo box with native language names but store language codes
        for code, name in language_options:
            # Store the name as display text and code as hidden data
            self.subtitle_lang_combo.addItem(name, code)
        
        # Set current value from config
        current_lang = config.get('subtitles.language', 'en')
        index = self.subtitle_lang_combo.findData(current_lang)
        if index >= 0:
            self.subtitle_lang_combo.setCurrentIndex(index)
        else:
            # If not found in predefined list, add it as custom option
            self.subtitle_lang_combo.addItem(current_lang, current_lang)
            self.subtitle_lang_combo.setCurrentText(current_lang)
        
        # Connect signal to save changes
        self.subtitle_lang_combo.currentTextChanged.connect(self.on_subtitle_lang_changed)
        format_layout.addWidget(self.subtitle_lang_combo)
        
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
            print("DEBUG: Audio button selected, turning off M4A by default")
            self.btn_m4a.setChecked(False)
        
        # Debug log button states
        print(f"DEBUG: Button states - 1080p: {self.btn_1080p.isChecked()}, 720p: {self.btn_720p.isChecked()}, 480p: {self.btn_480p.isChecked()}, Audio: {self.btn_audio.isChecked()}")
        
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
        elif self.btn_audio.isChecked():
            resolution = None  # Audio only
        else:
            print("DEBUG: No resolution button is checked, defaulting to audio only")
            resolution = None
        
        # Get subtitles setting
        subtitle_enabled = self.btn_subtitles.isChecked()
        
        # Get cookies setting
        cookies_enabled = self.btn_cookies.isChecked()
        
        # Get the selected language code
        subtitle_lang = None
        if subtitle_enabled:
            # Get the language code from the combobox's data rather than text
            index = self.subtitle_lang_combo.currentIndex()
            if index >= 0:
                subtitle_lang = self.subtitle_lang_combo.itemData(index)
                
                # Special handling for Chinese to include simplified, traditional, and Hong Kong variants
                if subtitle_lang == 'zh':
                    subtitle_lang = ['zh-CN', 'zh-TW', 'zh-HK']
                    print(f"DEBUG: Selected Chinese subtitles, downloading variants: {subtitle_lang}")
            else:
                # Fallback to text if it's a custom entry
                subtitle_lang = self.subtitle_lang_combo.currentText().strip()
        
        # Log the options being used
        print(f"DEBUG: Generating format options with resolution={resolution}, https={self.btn_https.isChecked()}, m4a={self.btn_m4a.isChecked()}, subtitle_lang={subtitle_lang}, cookies={cookies_enabled}")
        
        # Use YtDlpModel to generate the format options
        options = YtDlpModel.generate_format_string(
            resolution=resolution,
            use_https=self.btn_https.isChecked(),
            use_m4a=self.btn_m4a.isChecked(),
            subtitle_lang=subtitle_lang,
            use_cookies=cookies_enabled
        )
        
        # Log the generated format options
        print(f"DEBUG: Generated format options: {options}")
        
        return options

    def set_format_audio_only(self):
        """Set format selection to audio only"""
        # Uncheck all resolution buttons
        self.btn_1080p.setChecked(False)
        self.btn_720p.setChecked(False)
        self.btn_480p.setChecked(False)
        
        # Check audio button
        self.btn_audio.setChecked(True)
        
        # Update format string
        self.update_format()

    def set_format_video_720p(self):
        """Set format selection to 720p video"""
        # Uncheck all other resolution buttons
        self.btn_1080p.setChecked(False)
        self.btn_480p.setChecked(False)
        self.btn_audio.setChecked(False)
        
        # Check 720p button
        self.btn_720p.setChecked(True)
        
        # Update format string
        self.update_format()

    def on_subtitle_lang_changed(self, text):
        """Handle subtitle language changes and save to config."""
        # Get the language code from the data associated with the current selection
        index = self.subtitle_lang_combo.currentIndex()
        if index >= 0:
            code = self.subtitle_lang_combo.itemData(index)
        else:
            # For custom text entries, use the text as the code
            code = text.strip()
        
        config.set('subtitles.language', code)
        self.update_format()

    def on_subtitles_toggled(self):
        """Handle subtitles toggle and save to config."""
        config.set('subtitles.enabled', self.btn_subtitles.isChecked())
        self.update_format()

    def on_cookies_toggled(self):
        """Handle cookies toggle and save to config."""
        config.set('cookies.enabled', self.btn_cookies.isChecked())
        self.update_format()