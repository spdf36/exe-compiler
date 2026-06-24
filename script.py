import os
import shutil
import subprocess
from pathlib import Path
from tqdm import tqdm

SUPPORTED_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.m4v'}

def check_dependencies():
    """Ensure ffmpeg and exiftool are installed and accessible."""
    missing = []
    if not shutil.which('ffmpeg'):
        missing.append("FFmpeg")
    if not shutil.which('exiftool'):
        missing.append("ExifTool")
    
    if missing:
        print(f"❌ Error: Missing dependencies: {', '.join(missing)}")
        print("Please install them and ensure they are added to your system PATH.")
        exit(1)

def process_video(file_path):
    """Mutes, universally encodes to bulletproof H.264 MP4, and removes metadata."""
    file_path = Path(file_path)
    original_ext = file_path.suffix.lower()
    
    new_file_path = file_path.with_suffix('.mp4')
    temp_output = file_path.with_name(f".temp_{file_path.stem}.mp4")

    try:
        # Step 1 & 2: Mute (-an) and Convert to universally compatible mp4
        ffmpeg_cmd = [
            'ffmpeg', 
            '-y',                   
            '-i', str(file_path),   
            '-c:v', 'libx264',      # The definitive standard video codec for MP4
            '-preset', 'slow',      # Prioritizes file size and quality over processing speed
            '-crf', '18',           # Visually lossless quality
            '-pix_fmt', 'yuv420p',  # Forces standard color space (fixes black screen issues on Windows/Web)
            '-an',                  # Remove audio
            str(temp_output)        
        ]
        
        subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # Step 3: Remove Metadata using ExifTool
        exiftool_cmd = [
            'exiftool', 
            '-all=',                
            '-overwrite_original',  
            str(temp_output)
        ]
        
        subprocess.run(exiftool_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # Step 4: Cleanup and replace original
        if original_ext != '.mp4':
            file_path.unlink()
        elif file_path.exists() and file_path != temp_output:
            file_path.unlink()

        temp_output.rename(new_file_path)
        return True, ""

    except subprocess.CalledProcessError as e:
        if temp_output.exists():
            temp_output.unlink()
        return False, f"Failed to process {file_path.name}: {e}"
    except Exception as e:
        if temp_output.exists():
            temp_output.unlink()
        return False, str(e)

def main():
    print("🎬 Ultimate Video Processing Tool (Mute, Universal MP4, Strip Metadata)")
    print("-" * 70)
    
    check_dependencies()

    input_folder = input("📂 Enter the folder path to process: ").strip()
    
    if input_folder.startswith('"') and input_folder.endswith('"'):
        input_folder = input_folder[1:-1]
    elif input_folder.startswith("'") and input_folder.endswith("'"):
        input_folder = input_folder[1:-1]

    folder_path = Path(input_folder)

    if not folder_path.is_dir():
        print("❌ Error: The provided path is not a valid directory.")
        return

    print("\n🔍 Scanning folder for video files...")
    video_files = []
    for ext in SUPPORTED_EXTENSIONS:
        video_files.extend(folder_path.rglob(f"*{ext}"))
        video_files.extend(folder_path.rglob(f"*{ext.upper()}"))

    video_files = list(set(video_files))

    if not video_files:
        print("⚠️ No supported video files found in the specified folder.")
        return

    print(f"✅ Found {len(video_files)} video file(s). Starting processing...\n")
    print("⏳ Note: High-quality encoding enabled. This will take time.\n")

    successful = 0
    errors = []

    for video_file in tqdm(video_files, desc="Processing Videos", unit="file"):
        success, error_msg = process_video(video_file)
        if success:
            successful += 1
        else:
            errors.append(error_msg)

    print("\n" + "=" * 70)
    print("🎉 Processing Complete!")
    print(f"✅ Successfully processed: {successful}/{len(video_files)} files.")
    
    if errors:
        print(f"❌ Errors encountered ({len(errors)}):")
        for err in errors:
            print(f"   - {err}")

if __name__ == "__main__":
    main()
