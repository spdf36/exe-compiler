import os
import shutil
import subprocess
from pathlib import Path
from tqdm import tqdm

# Define the flexible video extensions you want to target
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
    """Mutes, converts (if needed), and removes metadata from a single video."""
    file_path = Path(file_path)
    original_ext = file_path.suffix.lower()
    
    # Define paths
    new_file_path = file_path.with_suffix('.mp4')
    # Use a temporary file to avoid in-place read/write corruption with ffmpeg
    temp_output = file_path.with_name(f".temp_{file_path.stem}.mp4")

    try:
        # Step 1 & 2: Mute (-an) and Convert to mp4 (-c:v copy for blazing speed without re-encoding)
        ffmpeg_cmd = [
            'ffmpeg', 
            '-y',                   # Overwrite output files without asking
            '-i', str(file_path),   # Input file
            '-c:v', 'copy',         # Copy the video codec directly (no quality loss, very fast)
            '-an',                  # Remove audio
            str(temp_output)        # Output temp file
        ]
        
        # Run ffmpeg, suppressing standard output/errors to keep the terminal clean
        subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # Step 3: Remove Metadata using ExifTool
        exiftool_cmd = [
            'exiftool', 
            '-all=',                # Strip all metadata
            '-overwrite_original',  # Overwrite in place (prevents creating *_original backup files)
            str(temp_output)
        ]
        
        subprocess.run(exiftool_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # Step 4: Cleanup and replace original
        if original_ext != '.mp4':
            # If it was a .mov (or other), delete the original file safely
            file_path.unlink()
        elif file_path.exists() and file_path != temp_output:
            # If it was already an .mp4, delete the original so we can replace it
            file_path.unlink()

        # Rename the processed temporary file to the final .mp4 name
        temp_output.rename(new_file_path)
        return True, ""

    except subprocess.CalledProcessError as e:
        # If anything fails, clean up the temp file to prevent clutter
        if temp_output.exists():
            temp_output.unlink()
        return False, f"Failed to process {file_path.name}: {e}"
    except Exception as e:
        if temp_output.exists():
            temp_output.unlink()
        return False, str(e)

def main():
    print("🎬 Video Processing Tool (Mute, Convert to MP4, Strip Metadata)")
    print("-" * 60)
    
    check_dependencies()

    # Get input folder from user
    input_folder = input("📂 Enter the folder path to process: ").strip()
    
    # Strip quotes if the user dragged and dropped the folder into the terminal
    if input_folder.startswith('"') and input_folder.endswith('"'):
        input_folder = input_folder[1:-1]
    elif input_folder.startswith("'") and input_folder.endswith("'"):
        input_folder = input_folder[1:-1]

    folder_path = Path(input_folder)

    if not folder_path.is_dir():
        print("❌ Error: The provided path is not a valid directory.")
        return

    # Find all supported video files recursively
    print("\n🔍 Scanning folder for video files...")
    video_files = []
    for ext in SUPPORTED_EXTENSIONS:
        video_files.extend(folder_path.rglob(f"*{ext}"))
        video_files.extend(folder_path.rglob(f"*{ext.upper()}")) # Catch uppercase extensions

    # Remove duplicates just in case
    video_files = list(set(video_files))

    if not video_files:
        print("⚠️ No supported video files found in the specified folder.")
        return

    print(f"✅ Found {len(video_files)} video file(s). Starting processing...\n")

    # Process files with tqdm progress bar
    successful = 0
    errors = []

    for video_file in tqdm(video_files, desc="Processing Videos", unit="file"):
        success, error_msg = process_video(video_file)
        if success:
            successful += 1
        else:
            errors.append(error_msg)

    # Final Report
    print("\n" + "=" * 60)
    print("🎉 Processing Complete!")
    print(f"✅ Successfully processed: {successful}/{len(video_files)} files.")
    
    if errors:
        print(f"❌ Errors encountered ({len(errors)}):")
        for err in errors:
            print(f"   - {err}")

if __name__ == "__main__":
    main()
