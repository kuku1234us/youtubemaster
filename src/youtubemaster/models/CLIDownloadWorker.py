"""
Worker class for processing downloads using the yt-dlp CLI.
"""
import os
import time
import re
import subprocess
import json
import shlex
import sys
import tempfile
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from youtubemaster.utils.logger import Logger

class CLIDownloadWorker(QThread):
    """Thread for processing a single download using the yt-dlp command line interface."""
    
    # Define signals (same as the PythonDownloadWorker for API compatibility)
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
        self.process = None
    
    def run(self):
        """Run the download process."""
        try:
            self.log_signal.emit(f"Starting CLI download for: {self.url}")
            
            # Track files before download
            files_before = set(os.listdir(self.output_dir))
            
            # Signal that processing is starting
            self.processing_signal.emit(self.url, "Processing started...")
            
            # Build the yt-dlp command
            cmd = self._build_ytdlp_command()
            
            # Log the command (with sensitive info like cookies redacted)
            safe_cmd = self._get_safe_command_string(cmd)
            self.log_signal.emit(f"Executing yt-dlp command (see debug terminal for details)")
            # Print the command to debug terminal rather than GUI log
            print(f"DEBUG: Executing command: {safe_cmd}")
            
            # Create a temporary file for progress output
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as progress_file:
                progress_file_path = progress_file.name
            
            # Set up process
            self.process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )
            
            # Initialize variables to track progress
            current_percentage = 0
            downloading_started = False
            
            # Process output in real-time
            for line in iter(self.process.stdout.readline, ''):
                if self.cancelled:
                    self.process.terminate()
                    raise Exception("Download cancelled by user")
                
                # Filter progress lines from debug terminal output
                is_progress_line = False
                # Filter out video/audio download progress lines
                if '[download]' in line and '%' in line and any(x in line for x in ['MiB at', 'KiB at', 'B/s']):
                    is_progress_line = True
                # Filter out subtitle download progress lines
                elif '[download]' in line and any(x in line for x in ['KiB at', 'MiB at', 'B/s']) and line.strip().startswith('[download]'):
                    is_progress_line = True
                # Filter intermediate progress like '1.00KiB at 57.75KiB/s'
                elif line.strip().startswith('[download]') and any(x in line for x in ['KiB at', 'MiB at', 'B/s']):
                    is_progress_line = True
                
                # Only print non-progress lines to debug terminal
                if not is_progress_line:
                    print(line.strip())
                
                # Try to parse progress information
                if '[download]' in line:
                    # Check if the download has started
                    if 'Destination:' in line:
                        downloading_started = True
                        output_file = line.split('Destination: ')[1].strip()
                        # Still send this important info to GUI log
                        self.log_signal.emit(f"Downloading to: {output_file}")
                        self.downloaded_filename = os.path.basename(output_file)
                    
                    # Parse download progress
                    elif downloading_started and '%' in line:
                        # Extract percentage
                        match = re.search(r'(\d+\.\d+)%', line)
                        if match:
                            try:
                                percentage = float(match.group(1))
                                current_percentage = percentage
                                
                                # Extract speed and ETA
                                speed_match = re.search(r'at\s+([^\s]+)', line)
                                eta_match = re.search(r'ETA\s+([^\s]+)', line)
                                
                                speed = speed_match.group(1) if speed_match else "unknown"
                                eta = eta_match.group(1) if eta_match else "unknown"
                                
                                status_text = f"Downloading: {percentage:.1f}% at {speed}, ETA: {eta}"
                                
                                # Emit progress update
                                self.progress_signal.emit(self.url, percentage, status_text)
                            except Exception as e:
                                print(f"DEBUG: Error parsing progress: {str(e)}")
                
                # Check for completion message
                elif line.strip().startswith('[ffmpeg]') and 'Merging formats into' in line:
                    match = re.search(r'Merging formats into "(.*?)"', line)
                    if match:
                        self.downloaded_filename = os.path.basename(match.group(1))
                        self.log_signal.emit(f"Final output file: {self.downloaded_filename}")
                
                # Check for errors in real-time
                if 'ERROR:' in line:
                    error_msg = line.strip()
                    self.log_signal.emit(f"Error detected: {error_msg}")
                    # Don't exit here, continue processing to capture more info
            
            # Process any stderr output
            stderr_output = self.process.stderr.read()
            if stderr_output:
                print(f"DEBUG: Standard error output: {stderr_output}")
                # Report critical errors to the GUI log
                if "ERROR:" in stderr_output:
                    for line in stderr_output.splitlines():
                        if "ERROR:" in line:
                            self.log_signal.emit(f"Error: {line.strip()}")
            
            # Wait for the process to complete
            return_code = self.process.wait()
            
            # Check if the process completed successfully
            if return_code != 0 and not self.cancelled:
                error_msg = f"yt-dlp process exited with code {return_code}"
                print(f"DEBUG: {error_msg}")
                
                # Try to extract a more specific error message from stderr output
                if stderr_output:
                    error_lines = stderr_output.splitlines()
                    for line in reversed(error_lines):
                        if 'ERROR:' in line:
                            error_msg = line.strip()
                            break
                
                self.error_signal.emit(self.url, error_msg)
                return
            
            # Find new files after download
            files_after = set(os.listdir(self.output_dir))
            new_files = files_after - files_before
            
            # Identify the main media file
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
            
            # Clean up subtitle files if subtitles were embedded
            if isinstance(self.format_options, dict) and self.format_options.get('embedsubtitles', False) and self.downloaded_filename:
                # Get the base filename without extension
                base_filename = os.path.splitext(self.downloaded_filename)[0]
                
                # Find and delete subtitle files (.vtt, .srt, etc.)
                subtitle_extensions = ['.vtt', '.srt', '.ttml', '.sbv', '.ass', '.ssa']
                for filename in new_files:
                    file_path = os.path.join(self.output_dir, filename)
                    if (any(filename.endswith(ext) for ext in subtitle_extensions) or 
                        '.en.' in filename or  # Common subtitle file naming pattern
                        any(f'.{lang}.' in filename for lang in ['en', 'es', 'fr', 'de', 'zh', 'ja'])):
                        
                        try:
                            # Make sure it's not our main media file
                            if filename != self.downloaded_filename:
                                os.remove(file_path)
                                self.log_signal.emit(f"Cleaned up subtitle file: {filename}")
                        except Exception as e:
                            self.log_signal.emit(f"Failed to remove subtitle file {filename}: {str(e)}")
            
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
            
        except Exception as e:
            error_message = str(e)
            self.error_signal.emit(self.url, f"Error: {error_message}")
    
    def _build_ytdlp_command(self):
        """Build the yt-dlp command with all necessary options."""
        cmd = ["yt-dlp"]
        
        # Add the format option
        if isinstance(self.format_options, dict) and 'format' in self.format_options:
            cmd.extend(["--format", self.format_options['format']])
        elif isinstance(self.format_options, str):
            cmd.extend(["--format", self.format_options])
        else:
            cmd.extend(["--format", "best"])
        
        # Set output template
        output_template = os.path.join(self.output_dir, '%(title)s.%(ext)s')
        cmd.extend(["--output", output_template])
        
        # Add format sorting if specified
        if isinstance(self.format_options, dict) and 'format_sort' in self.format_options:
            format_sort = self.format_options['format_sort']
            if isinstance(format_sort, list):
                format_sort = ','.join(format_sort)
            cmd.extend(["--format-sort", format_sort])
        
        # Add merge format if specified
        if isinstance(self.format_options, dict) and 'merge_output_format' in self.format_options:
            cmd.extend(["--merge-output-format", self.format_options['merge_output_format']])
        
        # Add subtitle options if specified
        if isinstance(self.format_options, dict):
            if self.format_options.get('writesubtitles', False):
                cmd.append("--write-subs")
            
            if self.format_options.get('writeautomaticsub', False):
                cmd.append("--write-auto-subs")
            
            if 'subtitleslangs' in self.format_options:
                langs = self.format_options['subtitleslangs']
                if isinstance(langs, list):
                    langs = ','.join(langs)
                cmd.extend(["--sub-langs", langs])
            
            if 'subtitlesformat' in self.format_options:
                cmd.extend(["--sub-format", self.format_options['subtitlesformat']])
            
            if self.format_options.get('embedsubtitles', False):
                cmd.append("--embed-subs")
        
        # Handle cookies option
        # For CLI mode, always use --cookies-from-browser firefox when cookies are enabled
        cookies_enabled = False
        if isinstance(self.format_options, dict):
            # Check if cookies are enabled directly
            if self.format_options.get('cookies') or self.format_options.get('cookies_from_browser'):
                cookies_enabled = True
            # Or if this is set from the Cookies toggle in the UI
            elif 'use_cookies' in self.format_options and self.format_options['use_cookies']:
                cookies_enabled = True
                
        if cookies_enabled:
            cmd.extend(["--cookies-from-browser", "firefox"])
            self.log_signal.emit("Using cookies from Firefox browser")
            # Important note about browser usage
            self.log_signal.emit("Note: Please ensure Firefox is closed and you're logged into YouTube in Firefox")
            # Also print to debug terminal
            print("DEBUG: Using cookies from Firefox browser")
        
        # Add network timeout options
        cmd.extend([
            "--socket-timeout", "120",
            "--retries", "10",
            "--fragment-retries", "10",
            "--extractor-retries", "5",
            "--file-access-retries", "5"
        ])
        
        # Add options to skip unavailable fragments but not abort on them
        cmd.append("--skip-unavailable-fragments")
        
        # Add other useful flags
        cmd.extend([
            "--no-mtime",        # Don't use the media timestamp
            "--progress"         # Show progress bar
        ])
        
        # Finally add the URL
        cmd.append(self.url)
        
        return cmd
    
    def _get_safe_command_string(self, cmd):
        """Create a safe version of the command for logging (redact sensitive info)."""
        safe_cmd = cmd.copy()
        
        # Redact cookies
        if "--cookies" in safe_cmd:
            cookie_index = safe_cmd.index("--cookies")
            if cookie_index + 1 < len(safe_cmd):
                safe_cmd[cookie_index + 1] = "[REDACTED]"
        
        # Redact cookies-from-browser
        if "--cookies-from-browser" in safe_cmd:
            browser_index = safe_cmd.index("--cookies-from-browser")
            if browser_index + 1 < len(safe_cmd):
                # Keep browser name but redact any profile path
                browser_info = safe_cmd[browser_index + 1]
                if os.path.sep in browser_info:
                    safe_cmd[browser_index + 1] = browser_info.split(os.path.sep)[0] + os.path.sep + "[REDACTED]"
        
        return ' '.join(shlex.quote(arg) for arg in safe_cmd)
    
    def cancel(self):
        """Cancel the download."""
        self.cancelled = True
        if self.process:
            try:
                self.process.terminate()
                # Give it a moment to terminate gracefully
                time.sleep(0.5)
                if self.process.poll() is None:
                    # Force kill if still running
                    self.process.kill()
            except Exception as e:
                self.log_signal.emit(f"Error terminating process: {str(e)}")
                # Try to ensure process is killed
                try:
                    self.process.kill()
                except:
                    pass 