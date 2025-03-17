"""
yt-dlp model Encapsulates logic that deals with yt-dlp
"""

class YtDlpModel:
    """
    Model for yt-dlp operations and format string generation.
    This class encapsulates all the logic related to creating format strings
    for the yt-dlp command line tool.
    """

    @staticmethod
    def generate_format_string(resolution=None, use_https=True, use_m4a=True):
        """
        Generate the yt-dlp format string based on the provided parameters.
        
        Args:
            resolution (int, optional): Video resolution (1080, 720, 480, None for audio only)
            use_https (bool): Whether to prefer HTTPS protocol
            use_m4a (bool): Whether to prefer M4A/MP4 formats
            
        Returns:
            dict: Dictionary with format options for yt-dlp
        """
        format_options = {}
        
        if resolution:
            # Video format
            format_str = f"bestvideo[height<={resolution}]"
            if use_https:
                format_str += "[protocol=https]"
            if use_m4a:
                format_str += "[ext=mp4]"
            
            # Audio format
            audio_str = "bestaudio"
            if use_https:
                audio_str += "[protocol=https]"
            if use_m4a:
                audio_str += "[ext=m4a]"
            
            # Fall back options
            fallback = f"best[height<={resolution}]"
            if use_https:
                fallback += "[protocol=https]"
            if use_m4a and resolution:
                fallback += "[ext=mp4]"
            
            # Complete format string
            format_str = f"{format_str}+{audio_str}/{fallback}/best"
            format_options["format"] = format_str
            
            # Force MP4 output if m4a is selected
            if use_m4a:
                format_options["merge_output_format"] = "mp4"
        else:
            # Audio only format
            format_str = "bestaudio"
            if use_https:
                format_str += "[protocol=https]"
            if use_m4a:
                format_str += "[ext=m4a]"
                format_options["merge_output_format"] = "m4a"
            else:
                format_str += "/best"
            
            format_options["format"] = format_str
        
        return format_options
    
    @staticmethod
    def get_video_formats(video_url):
        """
        Get available formats for a video URL.
        This would call yt-dlp to list available formats.
        
        Not implemented yet - placeholder for future functionality.
        """
        # This would use subprocess to call yt-dlp -F video_url
        # and parse the results
        pass
    
    @staticmethod
    def generate_download_options(format_options, output_path=None, output_template=None):
        """
        Generate full download options for yt-dlp.
        
        Args:
            format_options (dict): Format options from generate_format_string
            output_path (str, optional): Output directory path
            output_template (str, optional): Output filename template
            
        Returns:
            dict: Complete options dictionary for yt-dlp
        """
        options = format_options.copy()
        
        if output_path:
            options["paths"] = {"home": output_path}
            
        if output_template:
            options["outtmpl"] = {"default": output_template}
            
        return options 