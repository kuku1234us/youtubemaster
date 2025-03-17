#!/usr/bin/env python3
"""
Run script for YouTubeMaster application
"""
import os
import sys

# Add src directory to Python path
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
sys.path.insert(0, src_dir)

# Now we can import from youtubemaster
from youtubemaster.main import main

if __name__ == "__main__":
    main() 