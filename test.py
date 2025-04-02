import subprocess
import sys
import time

def run_ytdlp_test():
    # Test URL
    url = "https://www.youtube.com/watch?v=0ahIpX6H2Fw"
    
    # Format string matching our Yt_DlpModel logic for 1080p without AV1 codec
    format_str = "bestvideo[height<=1080][vcodec!*=av01]+bestaudio[ext=m4a]/best[height<=1080][vcodec!*=av01]"
    
    # Construct the yt-dlp command
    cmd = [
        "yt-dlp",
        "--format", format_str,
        "--verbose",  # Show detailed output
        "--progress",  # Show download progress
        "--cookies-from-browser", "firefox",  # Use Firefox cookies for authentication
        url
    ]
    
    print(f"Running command: {' '.join(cmd)}\n")
    print("=" * 80)
    
    try:
        # Run the command and stream output in real-time
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Stream the output in real-time
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
                sys.stdout.flush()  # Force flush to show output immediately
        
        # Get return code
        return_code = process.poll()
        print("=" * 80)
        print(f"\nProcess finished with return code: {return_code}")
        
    except subprocess.CalledProcessError as e:
        print(f"Error running yt-dlp: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    run_ytdlp_test() 