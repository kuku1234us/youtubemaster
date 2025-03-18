"""
Bilibili data model for the application.
"""
import re
import requests
from urllib.parse import urlparse
from PyQt6.QtGui import QPixmap

class BilibiliModel:
    """Model for Bilibili data and operations."""
    
    @staticmethod
    def extract_video_id(url):
        """
        Extract BV ID from a Bilibili URL.
        
        Args:
            url (str): The Bilibili URL
            
        Returns:
            str: The BV ID or None if not found
        """
        # Handle direct BV ID input
        if re.match(r'^BV[a-zA-Z0-9]{10}$', url):
            return url
            
        # Parse the URL
        try:
            parsed_url = urlparse(url)
            
            # Extract BV ID from path
            path = parsed_url.path
            match = re.search(r'BV([a-zA-Z0-9]{10})', path)
            if match:
                return f"BV{match.group(1)}"
                
            return None
            
        except Exception as e:
            print(f"Error extracting Bilibili ID: {e}")
            return None
    
    @staticmethod
    def clean_url(url):
        """
        Clean a Bilibili URL to the standard format.
        
        Args:
            url (str): The Bilibili URL or BV ID
            
        Returns:
            str: Normalized URL or original URL if normalization fails
        """
        # Handle direct BV ID input
        if re.match(r'^BV[a-zA-Z0-9]{10}$', url):
            return f"https://www.bilibili.com/video/{url}"
            
        # Extract the BV ID and create a clean URL
        bv_id = BilibiliModel.extract_video_id(url)
        if bv_id:
            return f"https://www.bilibili.com/video/{bv_id}"
            
        # Return original URL if we can't normalize it
        return url
    
    @staticmethod
    def get_video_metadata(url):
        """
        Get title and thumbnail for a Bilibili video.
        
        Args:
            url (str): The Bilibili URL
            
        Returns:
            tuple: (title, pixmap) or ("Unknown Video", None) if not found
        """
        bv_id = BilibiliModel.extract_video_id(url)
        if not bv_id:
            return "Unknown Video", None
        
        # Bilibili API URL for video info
        api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv_id}"
        
        try:
            response = requests.get(api_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if the API returned successfully
                if data.get('code') == 0 and 'data' in data:
                    video_data = data['data']
                    title = video_data.get('title', f"Bilibili: {bv_id}")
                    
                    # Get thumbnail URL
                    thumbnail_url = video_data.get('pic')
                    
                    # Download the thumbnail
                    if thumbnail_url:
                        img_response = requests.get(thumbnail_url)
                        if img_response.status_code == 200:
                            pixmap = QPixmap()
                            pixmap.loadFromData(img_response.content)
                            return title, pixmap
                    
                    return title, None
        
        except Exception as e:
            print(f"Error fetching Bilibili metadata: {e}")
        
        return f"Bilibili: {bv_id}", None
    
    @staticmethod
    def get_thumbnail(url, quality='default'):
        """
        Get thumbnail image from Bilibili video URL.
        
        Args:
            url (str): The Bilibili URL
            quality (str): Quality level (ignored, Bilibili API provides one size)
            
        Returns:
            QPixmap: Thumbnail image or None if not found
        """
        _, pixmap = BilibiliModel.get_video_metadata(url)
        return pixmap