import os
import subprocess
import json
import logging
from pathlib import Path
from config.settings import settings

# הגדרת לוגים
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def get_video_info(file_path):
    """שואב נתוני מטא-דאטה מהסרטון כדי לבדוק אם הוא כבר אופטימלי."""
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', str(file_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        video_stream = next(s for s in data['streams'] if s['codec_type'] == 'video')
        
        width = int(video_stream.get('width', 0))
        height = int(video_stream.get('height', 0))
        
        fps_str = video_stream.get('avg_frame_rate', '30/1')
        num, den = map(int, fps_str.split('/'))
        fps = num / den if den != 0 else 30.0
        
        return width, height, fps
    except Exception as e:
        logger.error(f"Could not probe {file_path}: {e}")
        return None, None, None

def optimize_video(input_path, output_path):
    """מבצע המרה לפורמט Shorts תקני (1080x1920, 30FPS)."""
    # חישוב פילטר ה-Crop בדומה ללוגיקה ב-BackgroundManager
    filter_complex = (
        f"crop='ih*9/16:ih:(iw-ow)/2:0',scale=1080:1920,setsar=1,fps=fps=30"
    )
    
    cmd = [
        'ffmpeg', '-y', '-i', str(input_path),
        '-filter_complex', filter_complex,
        '-c:v', 'libx264', '-preset', 'slow', '-crf', '20',
        '-pix_fmt', 'yuv420p', '-c:a', 'copy', str(output_path)
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error for {input_path}: {e.stderr.decode()}")
        return False

def run_optimization():
    bg_dir = Path(settings.BACKGROUNDS_DIR).absolute()
    logger.info(f"Starting background optimization in: {bg_dir}")

    # סריקה של כל סוגי הקבצים המותרים
    for ext in settings.ALLOWED_EXTENSIONS:
        for video_path in bg_dir.rglob(f"*{ext}"):
            # מניעת עיבוד של קבצים זמניים
            if ".temp" in video_path.name or "_optimized" in video_path.name:
                continue

            width, height, fps = get_video_info(video_path)
            
            # בדיקה אם הקובץ כבר בפורמט הנכון (1080x1920, 30FPS)
            if width == 1080 and height == 1920 and abs(fps - 30) < 0.1:
                logger.info(f"SKIPPING: {video_path.name} is already optimized.")
                continue

            logger.info(f"OPTIMIZING: {video_path.name} ({width}x{height}, {fps} FPS)")
            
            temp_output = video_path.with_suffix(f".optimized{video_path.suffix}")
            
            if optimize_video(video_path, temp_output):
                # החלפת הקובץ המקורי בקובץ המותאם
                video_path.unlink() # מחיקת המקורי
                temp_output.rename(video_path) # שינוי שם המותאם לשם המקורי
                logger.info(f"SUCCESS: {video_path.name} optimized.")
            else:
                logger.error(f"FAILED: Could not optimize {video_path.name}.")

if __name__ == "__main__":
    run_optimization()