import os
import subprocess
from pathlib import Path
import logging

# הגדרת לוגים כדי לראות מה קורה בזמן אמת
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# נתיב למאגר הסרטונים שלך
BACKGROUNDS_DIR = Path(r"C:\Projects\ShortsGeneratorBetter\backend_v2\assets\backgrounds")

def apply_secret_sauce(video_path: Path):
    """
    מיישם את הלוגיקה המדויקת מה-BackgroundManager המקורי:
    נורמליזציה מלאה, setsar=1, ו-CFR (קצב פריימים קבוע).
    """
    temp_output = video_path.with_suffix(f".fixed{video_path.suffix}")
    
    # הפילטרים שהפכו את הסרטונים שלך ל"חסיני גליצ'ים" בגרסה היציבה:
    # 1. scale ו-crop ל-1080x1920
    # 2. setsar=1 להבטחת פיקסלים ריבועיים (מונע עיוותים בחיבור)
    # 3. fps=30 קבוע (מונע כפילויות כתוביות)
    filter_complex = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,setsar=1,fps=fps=30"
    )

    cmd = [
        'ffmpeg', '-y',
        '-i', str(video_path),
        '-vf', filter_complex,
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '20', # איכות גבוהה מאוד
        '-pix_fmt', 'yuv420p', # תאימות מקסימלית
        '-r', '30', # כפייה של 30FPS ברמת הקודק
        '-c:a', 'aac',
        '-b:a', '128k',
        '-ar', '44100',
        '-movflags', '+faststart',
        str(temp_output)
    ]

    try:
        logger.info(f"Applying Secret Sauce to: {video_path.name}")
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        # אם הצלחנו, מחליפים את הקובץ המקורי
        video_path.unlink()
        temp_output.rename(video_path)
        logger.info(f"Successfully repaired and optimized: {video_path.name}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to fix {video_path.name}: {e.stderr}")
        if temp_output.exists():
            temp_output.unlink()
        return False

def main():
    if not BACKGROUNDS_DIR.exists():
        logger.error(f"Directory not found: {BACKGROUNDS_DIR}")
        return

    video_files = []
    for ext in ['.mp4', '.mov', '.avi', '.mkv']:
        video_files.extend(list(BACKGROUNDS_DIR.rglob(f"*{ext}")))

    logger.info(f"Found {len(video_files)} videos to process.")

    successful = 0
    failed = 0

    for video_file in video_files:
        if apply_secret_sauce(video_file):
            successful += 1
        else:
            failed += 1

    logger.info(f"Finished! Processed: {successful}, Failed: {failed}")

if __name__ == "__main__":
    main()