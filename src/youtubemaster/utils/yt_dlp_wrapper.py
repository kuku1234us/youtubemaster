"""
yt-dlp wrapper - Utilities for interacting with the system-installed yt-dlp executable.
"""

import os
import subprocess
import shutil
from typing import Optional, List, Dict, Callable, Any


class YtDlpWrapper:
    """Wrapper for the yt-dlp executable."""
    
    def __init__(self, path: Optional[str] = None):
        """
        Initialize the yt-dlp wrapper.
        
        Args:
            path: Optional path to the yt-dlp executable. If None, the wrapper
                 will search in common locations.
        """
        self.yt_dlp_path = path or self._find_yt_dlp()
        self.ffmpeg_path = self._find_ffmpeg()
        
    def _find_yt_dlp(self) -> str:
        """
        Find the yt-dlp executable on the system.
        
        Returns:
            The path to the yt-dlp executable.
            
        Raises:
            FileNotFoundError: If yt-dlp cannot be found.
        """
        # Check common locations
        common_paths = [
            r"C:\windows\system32\yt-dlp.exe",
            os.path.join(os.environ.get("APPDATA", ""), "yt-dlp", "yt-dlp.exe"),
            os.path.join(os.path.expanduser("~"), "yt-dlp", "yt-dlp.exe")
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
                
        # Check PATH
        yt_dlp_path = shutil.which("yt-dlp")
        if yt_dlp_path:
            return yt_dlp_path
            
        raise FileNotFoundError(
            "yt-dlp executable not found. Please make sure it's installed and available in your PATH."
        )
        
    def _find_ffmpeg(self) -> Optional[str]:
        """
        Find the ffmpeg executable on the system.
        
        Returns:
            The path to the ffmpeg executable, or None if not found.
        """
        # Check PATH
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            return ffmpeg_path
            
        # Check common locations
        common_paths = [
            r"C:\windows\system32\ffmpeg.exe",
            r"C:\ffmpeg\bin\ffmpeg.exe",
            os.path.join(os.environ.get("APPDATA", ""), "ffmpeg", "bin", "ffmpeg.exe")
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
                
        return None
        
    def get_version(self) -> str:
        """
        Get the version of yt-dlp.
        
        Returns:
            The version string.
        """
        result = subprocess.run(
            [self.yt_dlp_path, "--version"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        return result.stdout.strip()
        
    def execute(self, 
                url: str, 
                output_template: str = "%(title)s.%(ext)s", 
                format_code: Optional[str] = None,
                options: Optional[Dict[str, Any]] = None,
                progress_callback: Optional[Callable[[str], None]] = None) -> subprocess.CompletedProcess:
        """
        Execute yt-dlp with the given parameters.
        
        Args:
            url: The URL to download.
            output_template: The output filename template.
            format_code: The format code to download.
            options: Additional options to pass to yt-dlp.
            progress_callback: Optional callback function to track progress.
            
        Returns:
            The completed process object.
        """
        cmd = [self.yt_dlp_path]
        
        # Add output template
        cmd.extend(["--output", output_template])
        
        # Add format if specified
        if format_code:
            cmd.extend(["--format", format_code])
            
        # Add ffmpeg path if found
        if self.ffmpeg_path:
            cmd.extend(["--ffmpeg-location", self.ffmpeg_path])
            
        # Add custom progress format for parsing
        cmd.extend([
            "--progress-template", 
            "[yt-dlp],%(progress._percent_str)s,%(progress._eta_str)s,%(progress.downloaded_bytes)s,%(progress.total_bytes)s,%(progress.speed)s,%(progress.eta)s"
        ])
            
        # Add any additional options
        if options:
            for key, value in options.items():
                if value is True:
                    # Flag without value
                    cmd.append(f"--{key}")
                elif value is not False:  # Skip False values
                    cmd.extend([f"--{key}", str(value)])
                    
        # Add the URL
        cmd.append(url)
        
        # Execute the command
        if progress_callback:
            # Use real-time output processing with callback
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1  # Line buffered
            )
            
            # Process output lines
            for line in iter(process.stdout.readline, ''):
                if progress_callback:
                    progress_callback(line.strip())
                    
            process.wait()
            return subprocess.CompletedProcess(cmd, process.returncode, "", "")
        else:
            # Simple execution without progress tracking
            return subprocess.run(cmd, capture_output=True, text=True)
            
    def get_formats(self, url: str) -> List[Dict[str, str]]:
        """
        Get available formats for a URL.
        
        Args:
            url: The URL to check.
            
        Returns:
            A list of available formats with their details.
        """
        result = subprocess.run(
            [self.yt_dlp_path, "-F", url],
            capture_output=True,
            text=True
        )
        
        formats = []
        lines = result.stdout.strip().split('\n')
        
        # Skip header lines
        for line in lines:
            if line.startswith('ID') or line.startswith('-'):
                continue
                
            # Parse format lines
            try:
                parts = line.split()
                if len(parts) >= 3:
                    format_id = parts[0]
                    extension = parts[1]
                    
                    # Handle format description (may contain spaces)
                    resolution = parts[2]
                    note = ' '.join(parts[3:]) if len(parts) > 3 else ''
                    
                    formats.append({
                        'format_id': format_id,
                        'extension': extension,
                        'resolution': resolution,
                        'note': note,
                        'full_line': line
                    })
            except Exception:
                # Skip lines that don't parse correctly
                pass
                
        return formats

    def extract_video_info(self, url: str) -> Dict[str, Any]:
        """
        Extract video information from a URL.
        
        Args:
            url: The URL to extract information from.
            
        Returns:
            A dictionary containing video information.
        """
        result = subprocess.run(
            [self.yt_dlp_path, "--dump-json", url],
            capture_output=True,
            text=True
        )
        
        import json
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"error": "Failed to parse video information"} 