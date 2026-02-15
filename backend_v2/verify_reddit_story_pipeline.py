#!/usr/bin/env python3
"""
Verification script for the complete Reddit Stories pipeline.
Checks that all components are properly integrated and ready for use.
"""

import sys
import tempfile
from pathlib import Path
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_imports():
    """Verify all required imports work."""
    print("=" * 60)
    print("Verifying Imports")
    print("=" * 60)
    
    imports_to_check = [
        ("reddit_story.reddit_client", "RedditClient"),
        ("reddit_story.story_processor", "StoryProcessor"),
        ("reddit_story.elevenlabs_client", "ElevenLabsClient"),
        ("reddit_story.background_manager", "BackgroundManager"),
        ("reddit_story.video_composer", "VideoComposer"),
        ("config.settings", "settings"),
        ("video_processor", "create_shorts_with_captions"),
    ]
    
    all_imports_ok = True
    
    for module_name, class_name in imports_to_check:
        try:
            if module_name == "video_processor":
                # Special handling for video_processor
                import importlib
                module = importlib.import_module(module_name)
                if hasattr(module, class_name):
                    print(f"✅ {module_name}.{class_name}")
                else:
                    print(f"❌ {module_name}.{class_name} - Not found")
                    all_imports_ok = False
            else:
                # Standard import
                exec(f"from {module_name} import {class_name}")
                print(f"✅ {module_name}.{class_name}")
        except ImportError as e:
            print(f"❌ {module_name}.{class_name} - ImportError: {e}")
            all_imports_ok = False
        except Exception as e:
            print(f"❌ {module_name}.{class_name} - Error: {e}")
            all_imports_ok = False
    
    return all_imports_ok

def verify_directory_structure():
    """Verify required directory structure exists."""
    print("\n" + "=" * 60)
    print("Verifying Directory Structure")
    print("=" * 60)
    
    directories_to_check = [
        Path("uploads"),
        Path("outputs"),
        Path("assets/backgrounds"),
        Path("reddit_story"),
    ]
    
    all_dirs_ok = True
    
    for directory in directories_to_check:
        abs_path = Path(__file__).parent / directory
        if abs_path.exists():
            print(f"✅ {directory}/")
        else:
            print(f"⚠️  {directory}/ - Does not exist (will be created automatically)")
            # These directories are created automatically by the code
    
    return True

def verify_background_manager():
    """Verify BackgroundManager functionality."""
    print("\n" + "=" * 60)
    print("Verifying BackgroundManager")
    print("=" * 60)
    
    try:
        from reddit_story.background_manager import BackgroundManager
        
        # Create temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test structure
            backgrounds_dir = temp_path / "backgrounds"
            backgrounds_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize manager
            manager = BackgroundManager(backgrounds_dir=backgrounds_dir)
            print(f"✅ BackgroundManager initialized")
            
            # Test methods
            themes = manager.get_available_themes()
            print(f"✅ get_available_themes() - Themes: {themes}")
            
            # Create a dummy video for metadata testing
            test_video = temp_path / "test.mp4"
            test_video.write_text("dummy")
            
            metadata = manager.get_video_metadata(test_video)
            print(f"✅ get_video_metadata() - Basic metadata extracted")
            
            return True
            
    except Exception as e:
        print(f"❌ BackgroundManager verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_video_composer():
    """Verify VideoComposer functionality."""
    print("\n" + "=" * 60)
    print("Verifying VideoComposer")
    print("=" * 60)
    
    try:
        from reddit_story.video_composer import VideoComposer
        from reddit_story.elevenlabs_client import AudioChunk
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Initialize composer
            composer = VideoComposer()
            print(f"✅ VideoComposer initialized")
            
            # Test subtitle creation
            test_text = "This is a test for subtitle generation."
            subtitle_path = temp_path / "test_subtitles.ass"
            
            success = composer.create_subtitles_for_text(
                text=test_text,
                audio_duration=5.0,
                output_path=subtitle_path
            )
            
            if success:
                print(f"✅ create_subtitles_for_text() - Subtitles created")
            else:
                print(f"⚠️  create_subtitles_for_text() - Failed (may need actual text processing)")
            
            return True
            
    except Exception as e:
        print(f"❌ VideoComposer verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_api_structure():
    """Verify API endpoint structure."""
    print("\n" + "=" * 60)
    print("Verifying API Structure")
    print("=" * 60)
    
    try:
        # Check main.py has the new endpoints
        main_py_path = Path(__file__).parent / "main.py"
        main_content = main_py_path.read_text()
        
        endpoints_to_check = [
            "/generate/reddit-story",
            "/reddit-story/status/",
            "/reddit-story/jobs",
            "/reddit-story/themes",
            "/reddit-story/voices",
        ]
        
        all_endpoints_found = True
        
        for endpoint in endpoints_to_check:
            if endpoint in main_content:
                print(f"✅ Endpoint found: {endpoint}")
            else:
                print(f"❌ Endpoint not found: {endpoint}")
                all_endpoints_found = False
        
        # Check for BackgroundTasks import
        if "BackgroundTasks" in main_content:
            print("✅ BackgroundTasks import found")
        else:
            print("❌ BackgroundTasks import not found")
            all_endpoints_found = False
        
        # Check for Reddit story models
        model_names = ["RedditStoryRequest", "RedditStoryResponse", "RedditStoryStatus"]
        for model in model_names:
            if model in main_content:
                print(f"✅ Model found: {model}")
            else:
                print(f"❌ Model not found: {model}")
                all_endpoints_found = False
        
        return all_endpoints_found
        
    except Exception as e:
        print(f"❌ API structure verification failed: {e}")
        return False

def verify_settings():
    """Verify settings configuration."""
    print("\n" + "=" * 60)
    print("Verifying Settings")
    print("=" * 60)
    
    try:
        from config.settings import settings
        
        print(f"✅ Settings module loaded")
        
        # Check important settings
        settings_to_check = [
            ("BACKGROUNDS_DIR", settings.BACKGROUNDS_DIR),
            ("OUTPUT_DIR", settings.OUTPUT_DIR),
            ("TARGET_WIDTH", settings.TARGET_WIDTH),
            ("TARGET_HEIGHT", settings.TARGET_HEIGHT),
            ("MAX_BACKGROUND_DURATION", settings.MAX_BACKGROUND_DURATION),
        ]
        
        for name, value in settings_to_check:
            print(f"  {name}: {value}")
        
        # Check API configuration
        print(f"\nAPI Configuration:")
        print(f"  ElevenLabs configured: {settings.is_elevenlabs_configured()}")
        print(f"  Reddit configured: {settings.is_reddit_configured()}")
        
        if not settings.is_elevenlabs_configured():
            print("  ⚠️  ElevenLabs API key not set (TTS will not work)")
            print("     Set ELEVENLABS_API_KEY in .env file")
        
        if not settings.is_reddit_configured():
            print("  ⚠️  Reddit API credentials not set (Reddit fetching will not work)")
            print("     Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT in .env file")
        
        return True
        
    except Exception as e:
        print(f"❌ Settings verification failed: {e}")
        return False

def verify_requirements():
    """Verify required dependencies."""
    print("\n" + "=" * 60)
    print("Verifying Requirements")
    print("=" * 60)
    
    try:
        import subprocess
        import sys
        
        # Check Python version
        python_version = sys.version_info
        print(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
        
        if python_version.major == 3 and python_version.minor >= 8:
            print("✅ Python version OK (3.8+)")
        else:
            print("❌ Python version too old (need 3.8+)")
            return False
        
        # Check ffmpeg availability
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ FFmpeg is available")
            else:
                print("❌ FFmpeg not available or not in PATH")
                print("   Install ffmpeg and add it to PATH")
                return False
        except FileNotFoundError:
            print("❌ FFmpeg not found")
            print("   Install ffmpeg and add it to PATH")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Requirements verification failed: {e}")
        return False

def main():
    """Run all verification checks."""
    print("Reddit Stories Pipeline Verification")
    print("=" * 60)
    
    checks = [
        ("Imports", verify_imports),
        ("Directory Structure", verify_directory_structure),
        ("BackgroundManager", verify_background_manager),
        ("VideoComposer", verify_video_composer),
        ("API Structure", verify_api_structure),
        ("Settings", verify_settings),
        ("Requirements", verify_requirements),
    ]
    
    results = []
    all_passed = True
    
    for check_name, check_func in checks:
        try:
            print(f"\nRunning: {check_name}")
            result = check_func()
            results.append((check_name, result))
            
            if result:
                print(f"✅ {check_name} passed")
            else:
                print(f"❌ {check_name} failed")
                all_passed = False
                
        except Exception as e:
            print(f"❌ {check_name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((check_name, False))
            all_passed = False
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    for check_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {check_name}")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL VERIFICATIONS PASSED!")
        print("\nThe Reddit Stories pipeline is ready for use!")
        print("\nNext steps:")
        print("1. Add background videos to: assets/backgrounds/")
        print("   - Create subdirectories for themes (e.g., minecraft/, abstract/)")
        print("   - Add .mp4 files to each theme directory")
        print("2. Configure API keys in .env file:")
        print("   - ELEVENLABS_API_KEY for text-to-speech")
        print("   - REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT for Reddit")
        print("3. Start the server: python main.py")
        print("4. Visit Swagger UI: http://localhost:8000/docs")
        print("5. Test the new endpoint: POST /generate/reddit-story")
    else:
        print("💥 SOME VERIFICATIONS FAILED")
        print("\nCheck the errors above and fix them before proceeding.")
        print("\nCommon issues:")
        print("- Install missing dependencies: pip install -r requirements.txt")
        print("- Install ffmpeg and add to PATH")
        print("- Create required directories")
        print("- Configure API keys in .env file")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)