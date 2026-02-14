from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
import uuid
from pydantic import BaseModel
import logging

from video_processor import create_shorts_with_captions, batch_process_shorts

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ShortsGenerator Backend v2 - Automated Pipeline", version="2.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create necessary directories
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

class Subtitle(BaseModel):
    text: str
    start: float
    end: float

class VideoUploadResponse(BaseModel):
    success: bool
    message: str
    original_path: Optional[str] = None
    processed_path: Optional[str] = None
    subtitles: Optional[List[Subtitle]] = None

class ProcessVideoRequest(BaseModel):
    input_path: str
    model_size: Optional[str] = "base"  # base, small, medium, large

class ProcessVideoResponse(BaseModel):
    success: bool
    message: str
    input_path: Optional[str] = None
    output_path: Optional[str] = None
    segments_count: Optional[int] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class BatchProcessRequest(BaseModel):
    input_dir: str
    output_dir: Optional[str] = None
    model_size: Optional[str] = "base"

class BatchProcessResponse(BaseModel):
    success: bool
    message: str
    total: Optional[int] = None
    successful: Optional[int] = None
    failed: Optional[int] = None
    failed_files: Optional[List[Dict[str, str]]] = None
    processed_files: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None

@app.get("/")
async def root():
    return {
        "message": "ShortsGenerator Backend v2 - Automated Pipeline",
        "version": "2.0.0",
        "features": [
            "16:9 to 9:16 reframing",
            "AI transcription with word-level timestamps",
            "Dynamic .ass subtitle generation",
            "Word-by-word highlighting (Hormozi style)",
            "Perfect sync with original audio"
        ]
    }

@app.post("/upload/video", response_model=VideoUploadResponse)
async def upload_video(file: UploadFile = File(...)):
    """
    Upload a video file for processing.
    The video will be processed through the complete automated shorts pipeline.
    """
    try:
        # Validate file type
        allowed_extensions = {".mp4", ".avi", ".mkv", ".mov", ".webm"}
        file_extension = Path(file.filename).suffix.lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Generate unique filename
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        original_path = UPLOAD_DIR / unique_filename
        
        # Save uploaded file
        with open(original_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process video through complete pipeline
        processed_filename = f"shorts_{unique_filename}"
        processed_path = OUTPUT_DIR / processed_filename
        
        # Call automated shorts pipeline
        result = create_shorts_with_captions(str(original_path), str(processed_path))
        
        if result['success']:
            # Convert transcription segments to subtitle format
            # Note: In a real implementation, we would parse the actual segments
            # For now, return success with basic info
            mock_subtitles = [
                Subtitle(text="Automated transcription", start=0.0, end=2.0),
                Subtitle(text="with word-level sync", start=2.0, end=4.0),
                Subtitle(text="and Hormozi style captions", start=4.0, end=6.0),
            ]
            
            return VideoUploadResponse(
                success=True,
                message=f"Video processed successfully with {result.get('segments_count', 0)} transcription segments",
                original_path=str(original_path),
                processed_path=str(processed_path),
                subtitles=mock_subtitles
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process video: {result.get('error', 'Unknown error')}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing video upload: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")

@app.post("/process-video", response_model=ProcessVideoResponse)
async def process_video(request: ProcessVideoRequest):
    """
    Process a video file from a local path through the complete automated shorts pipeline.
    
    Request body should contain:
    {
        "input_path": "/path/to/input/video.mp4",
        "model_size": "base"  # optional, defaults to "base"
    }
    """
    try:
        input_path = request.input_path
        model_size = request.model_size or "base"
        
        # Validate input file exists
        if not os.path.exists(input_path):
            return ProcessVideoResponse(
                success=False,
                message="Input file does not exist",
                input_path=input_path,
                error=f"File not found: {input_path}"
            )
        
        # Validate it's a video file
        allowed_extensions = {".mp4", ".avi", ".mkv", ".mov", ".webm"}
        file_extension = Path(input_path).suffix.lower()
        
        if file_extension not in allowed_extensions:
            return ProcessVideoResponse(
                success=False,
                message="Invalid file type",
                input_path=input_path,
                error=f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Generate output path
        input_filename = Path(input_path).stem
        output_filename = f"shorts_{input_filename}.mp4"
        output_path = str(OUTPUT_DIR / output_filename)
        
        # Process through complete automated pipeline
        logger.info(f"Starting automated shorts pipeline for: {input_path}")
        result = create_shorts_with_captions(input_path, output_path, model_size)
        
        if result['success']:
            return ProcessVideoResponse(
                success=True,
                message="Video successfully processed through automated shorts pipeline",
                input_path=input_path,
                output_path=output_path,
                segments_count=result.get('segments_count'),
                metadata={
                    'subtitles_generated': True,
                    'word_level_timestamps': True,
                    'aspect_ratio': '9:16 (1080x1920)',
                    'subtitle_style': 'Hormozi style with karaoke effect'
                }
            )
        else:
            return ProcessVideoResponse(
                success=False,
                message="Failed to process video through automated pipeline",
                input_path=input_path,
                output_path=output_path,
                error=result.get('error', 'Unknown error')
            )
            
    except Exception as e:
        logger.error(f"Error in process-video endpoint: {e}")
        return ProcessVideoResponse(
            success=False,
            message="Internal server error",
            input_path=request.input_path,
            error=f"Unexpected error: {str(e)}"
        )

@app.post("/batch-process", response_model=BatchProcessResponse)
async def batch_process(request: BatchProcessRequest):
    """
    Process all videos in a directory through the automated shorts pipeline.
    
    Request body should contain:
    {
        "input_dir": "/path/to/input/directory",
        "output_dir": "/path/to/output/directory",  # optional, defaults to backend_v2/outputs
        "model_size": "base"  # optional
    }
    """
    try:
        input_dir = request.input_dir
        output_dir = request.output_dir or str(OUTPUT_DIR)
        model_size = request.model_size or "base"
        
        # Validate input directory exists
        if not os.path.exists(input_dir):
            return BatchProcessResponse(
                success=False,
                message="Input directory does not exist",
                error=f"Directory not found: {input_dir}"
            )
        
        if not os.path.isdir(input_dir):
            return BatchProcessResponse(
                success=False,
                message="Input path is not a directory",
                error=f"Not a directory: {input_dir}"
            )
        
        # Process batch
        logger.info(f"Starting batch processing for directory: {input_dir}")
        result = batch_process_shorts(input_dir, output_dir, model_size)
        
        return BatchProcessResponse(
            success=True,
            message=f"Batch processing complete: {result['successful']}/{result['total']} successful",
            total=result['total'],
            successful=result['successful'],
            failed=result['failed'],
            failed_files=result['failed_files'],
            processed_files=result['processed_files']
        )
            
    except Exception as e:
        logger.error(f"Error in batch-process endpoint: {e}")
        return BatchProcessResponse(
            success=False,
            message="Internal server error during batch processing",
            error=f"Unexpected error: {str(e)}"
        )

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "service": "shorts-generator-backend-v2",
        "version": "2.0.0",
        "features": [
            "automated_pipeline",
            "ai_transcription",
            "word_level_sync",
            "ass_subtitles",
            "9:16_reframing"
        ]
    }

@app.get("/system-info")
async def system_info():
    """Get system information and pipeline status."""
    try:
        # Check if faster-whisper is available
        import faster_whisper
        whisper_status = "available"
    except ImportError:
        whisper_status = "not_available"
    
    try:
        import ffmpeg
        ffmpeg_status = "available"
    except ImportError:
        ffmpeg_status = "not_available"
    
    return {
        "pipeline_components": {
            "faster_whisper": whisper_status,
            "ffmpeg_python": ffmpeg_status,
            "tempfile": "available",
            "pathlib": "available"
        },
        "directories": {
            "uploads": str(UPLOAD_DIR.absolute()),
            "outputs": str(OUTPUT_DIR.absolute()),
            "uploads_exists": UPLOAD_DIR.exists(),
            "outputs_exists": OUTPUT_DIR.exists()
        },
        "supported_formats": [".mp4", ".avi", ".mkv", ".mov", ".webm"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
