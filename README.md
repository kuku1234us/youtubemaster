# YouTubeMaster

A modern GUI frontend for yt-dlp - download YouTube videos and other online media efficiently.

## Features

- Simple and intuitive user interface
- Download videos in various formats and qualities
- Extract audio tracks
- Download subtitles
- Custom download options

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/youtubemaster.git
cd youtubemaster

# Install with Poetry
poetry install

# Run the application
poetry run youtubemaster
```

## Development

This project uses Poetry for dependency management.

### Setup Development Environment

```bash
# Install dependencies including development dependencies
poetry install

# Activate the virtual environment
poetry shell
```

### Building Executable

```bash
# Build Windows executable
poetry run pyinstaller --name=YouTubeMaster --onefile --windowed src/youtubemaster/main.py
```

## License

[MIT License](LICENSE)
