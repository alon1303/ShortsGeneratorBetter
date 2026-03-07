# Tech Context: ShortsGenerator Automation Pipeline

## Technologies Used

### Core Technologies
- **Python 3.8+**: Primary programming language with async/await support
- **FastAPI**: Web framework for REST API endpoints
- **Uvicorn**: ASGI server for FastAPI
- **Pydantic**: Data validation and settings management
- **Pydantic Settings**: Environment-aware configuration management

### Video & Audio Processing
- **FFmpeg**: Command-line tool for video/audio processing (via ffmpeg-python)
- **faster-whisper**: Faster implementation of OpenAI's Whisper for transcription
- **pysubs2**: Subtitle file generation and manipulation
- **pydub**: Audio processing and manipulation
- **av**: Pythonic binding for FFmpeg libraries

### Text-to-Speech (TTS)
- **Edge TTS**: Free Microsoft Edge TTS engine via edge-tts package
- **ElevenLabs API**: Optional premium TTS (requires API key)
- **TTS Router**: Custom abstraction layer supporting multiple TTS engines

### Content & APIs
- **Reddit Public JSON Endpoints**: No API keys required for story fetching
- **YouTube Data API v3**: Video upload and metadata management
- **Google OAuth2**: Authentication for YouTube API
- **aiohttp**: Asynchronous HTTP client for API requests

### UI & Presentation
- **Playwright**: Headless browser for HTML-to-image title card generation
- **Jinja2**: Templating engine for HTML title cards
- **html2image**: Alternative HTML-to-image conversion
- **CSS/HTML**: Custom styling for Reddit-style title cards

### Data Management
- **JSON**: Configuration and state persistence
- **Pathlib**: Modern file path manipulation
- **asyncio**: Asynchronous I/O operations
- **logging**: Comprehensive logging system

### Development & Testing
- **pytest**: Testing framework
- **pytest-asyncio**: Async test support
- **black**: Code formatting
- **mypy**: Type checking

## Development Setup

### Prerequisites
1. **Python 3.8+** installed and in PATH
2. **FFmpeg** installed and in PATH (required for video processing)
3. **Playwright** browsers installed (`playwright install`)
4. **Git** for version control

### Installation Steps
```powershell
# 1. Navigate to project directory
cd c:\Projects\sg_automation_dev\backend_v2

# 2. Create and activate virtual environment (optional but recommended)
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browsers
playwright install chromium

# 5. Configure environment variables
copy .env.example .env
# Edit .env with your configuration

# 6. Set up YouTube API credentials
# Obtain client_secrets.json from Google Cloud Console
# Place in backend_v2/ directory
```

### Directory Structure
```
sg_automation_dev/
├── .clinerules/                    # Memory bank documentation
├── backend_v2/                     # Main application
│   ├── config/settings.py         # Centralized configuration
│   ├── reddit_story/              # Reddit story processing
│   │   ├── reddit_client.py       # Reddit story fetching
│   │   ├── story_processor.py     # Text splitting and processing
│   │   ├── tts_router.py          # TTS engine abstraction
│   │   ├── video_composer.py      # Video generation and composition
│   │   └── background_manager.py  # Background video management
│   ├── youtube/uploader.py        # YouTube API integration
│   ├── auto_pipeline.py           # End-to-end orchestration
│   ├── main.py                    # FastAPI server
│   └── requirements.txt           # Dependencies
├── cache/                         # Cached TTS audio and images
├── outputs/                       # Generated videos and logs
└── data/                          # Pipeline state and statistics
```

### Environment Variables
Create `.env` file in `backend_v2/` directory:
```env
# Application Settings
DEBUG=false
HOST=0.0.0.0
PORT=8000

# YouTube API (optional for testing)
# ELEVENLABS_API_KEY=your_api_key_here

# Reddit Settings (using public endpoints)
REDDIT_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36

# TTS Engine (edge or elevenlabs)
TTS_ENGINE=edge
DEFAULT_VOICE_ID=en-US-AriaNeural
```

## Technical Constraints

### Platform Constraints
1. **Windows PowerShell**: All terminal commands must use PowerShell syntax
2. **FFmpeg Requirement**: Must be installed and accessible in PATH
3. **YouTube API Quota**: ~10,000 units/day, ~1,600 units per video upload
4. **Video Duration**: Must be under 3 minutes (180 seconds) for YouTube Shorts
5. **Video Resolution**: 1080x1920 vertical format required for Shorts
6. **File Size**: Generated videos can be 50-100MB each

### Performance Constraints
1. **Processing Time**: ~2-5 minutes per story depending on length
2. **Memory Usage**: 500MB-1GB during video processing
3. **Disk Space**: ~50-100MB per generated video
4. **Network Dependencies**: Reddit and YouTube API availability
5. **CPU Usage**: High during FFmpeg video processing

### API Limitations
1. **Reddit Rate Limits**: Public JSON endpoints have implicit rate limits
2. **YouTube Upload Limits**: ~6 uploads/day within API quota
3. **TTS Generation**: Edge TTS free tier has no rate limits
4. **Concurrent Processing**: Single-threaded story processing by design

### Security Constraints
1. **OAuth2 Tokens**: Must be stored securely (token.json)
2. **Client Secrets**: Google Cloud credentials must be protected
3. **Environment Variables**: Sensitive configuration should use .env files
4. **File System**: Generated videos contain user content

## Dependencies

### Production Dependencies (from requirements.txt)
```txt
# Core Framework
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6

# Video Processing
ffmpeg-python==0.2.0
faster-whisper==1.2.1
ctranslate2>=4.0,<5
onnxruntime>=1.14,<2
av>=11

# Configuration & Data
pydantic>=2.12.0
pydantic-settings>=2.12.0
python-dotenv>=1.2.0
filelock>=3.23.0

# Reddit Stories Feature
aiofiles>=23.0.0
html2image>=2.0.3
pysubs2>=1.6.0
edge-tts>=7.0.0

# Title Card Generation
jinja2>=3.1.0
playwright>=1.40.0
pydub>=0.25.1

# YouTube Integration
google-api-python-client>=2.0.0
google-auth-oauthlib>=1.0.0
google-auth-httplib2>=0.1.0
google-auth>=2.0.0
```

### System Dependencies (not in requirements.txt)
1. **FFmpeg**: Must be installed separately (not a Python package)
2. **Playwright Browsers**: Installed via `playwright install`
3. **Python 3.8+**: Modern Python with async features
4. **Windows/Linux/macOS**: Cross-platform but tested on Windows

### Dependency Management
- **Virtual Environments**: Recommended for isolation
- **requirements.txt**: Pinned versions for reproducibility
- **No Docker**: Currently runs directly on host system
- **Manual FFmpeg**: Users must install FFmpeg separately

## Tool Usage Patterns

### Command Line Interface (CLI)
All commands use **PowerShell syntax** on Windows:

```powershell
# Single-cycle pipeline test (no YouTube upload)
python auto_pipeline.py --single-cycle --no-upload

# Continuous operation with 60-minute intervals
python auto_pipeline.py --interval 60

# Custom subreddits and settings
python auto_pipeline.py --subreddits AmItheAsshole tifu --stories 5 --no-upload

# Help and options
python auto_pipeline.py --help
```

### Development Commands
```powershell
# Run FastAPI development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests
python test_imports.py
python test_reddit_client.py
python test_youtube_compatibility.py

# Check dependencies
python -m pip list
```

### Logging & Monitoring
- **Log Location**: `outputs/auto_pipeline.log`
- **Console Output**: Real-time progress and errors
- **Statistics**: `data/pipeline_stats.json`
- **Cycle Results**: `data/pipeline/cycle_*.json`

### Testing Patterns
1. **Unit Tests**: Individual component testing with mocks
2. **Integration Tests**: Full pipeline with `--no-upload` flag
3. **Manual Testing**: Single-cycle operation for validation
4. **Cleanup**: Test files deleted after running tests

## Development Workflow

### Typical Development Session
1. **Start**: Read memory bank files for context
2. **Test**: Run verification tests (`python test_imports.py`)
3. **Develop**: Make changes to execution flow, scheduling, or auto_pipeline.py
4. **Test**: Run single-cycle pipeline with `--no-upload`
5. **Verify**: Check logs and generated videos
6. **Document**: Update memory bank if needed
7. **Cleanup**: Delete test files and outputs

### Code Style & Standards
- **Async-first**: Use asyncio for all I/O operations
- **Type Hints**: Comprehensive type annotations
- **Modular Design**: Clear separation of concerns
- **Error Handling**: Graceful degradation and retry logic
- **Logging**: Comprehensive at INFO level, DEBUG for troubleshooting

### Debugging Patterns
1. **Enable Debug Logging**: Set logging level to DEBUG
2. **Check Logs**: Review `outputs/auto_pipeline.log`
3. **Single Story Mode**: Process one story at a time
4. **No Upload Mode**: Test without YouTube API
5. **Clean Cache**: Clear `cache/` directory if TTS issues

## Deployment Considerations

### Local Development
- **Requirements**: Python 3.8+, FFmpeg, dependencies
- **Setup**: One-time installation of system dependencies
- **Testing**: Local pipeline runs with test videos
- **Monitoring**: Log files and console output

### Production Server
- **Headless Operation**: No GUI required
- **Stable Internet**: Reddit/YouTube API access
- **Sufficient Storage**: ~10GB for videos and cache
- **Monitoring**: Log rotation and disk space monitoring
- **Backup**: Configuration files and credentials

### Scaling Limitations
- **Single Instance**: Designed for single-server operation
- **YouTube Quota**: Primary limiting factor (6 uploads/day)
- **Processing Capacity**: ~3 stories/hour per instance
- **State Management**: JSON files, not distributed

## Common Issues & Solutions

### YouTube Authentication Issues
1. **Problem**: `client_secrets.json` not found
   **Solution**: Obtain from Google Cloud Console and place in `backend_v2/`
2. **Problem**: OAuth2 token expired
   **Solution**: Delete `youtube/token.json` and re-authenticate
3. **Problem**: Quota exceeded
   **Solution**: Wait 24 hours or request quota increase

### Video Processing Issues
1. **Problem**: FFmpeg not found
   **Solution**: Install FFmpeg and ensure it's in PATH
2. **Problem**: Video generation fails
   **Solution**: Check disk space and permissions
3. **Problem**: Memory errors
   **Solution**: Reduce concurrent processing or increase system memory

### Reddit Fetching Issues
1. **Problem**: No stories fetched
   **Solution**: Check internet connection and subreddit names
2. **Problem**: Rate limited
   **Solution**: Add delays between requests
3. **Problem**: NSFW content
   **Solution**: Ensure `EXCLUDE_NSFW=true` in settings

### TTS Issues
1. **Problem**: Audio not generated
   **Solution**: Check Edge TTS installation and network
2. **Problem**: Wrong voice
   **Solution**: Verify voice ID in settings
3. **Problem**: Timing data missing
   **Solution**: Clear cache and regenerate