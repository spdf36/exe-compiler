import os
import subprocess
import threading
import concurrent.futures
from pathlib import Path

print_lock = threading.Lock()

def safe_print(message):
    with print_lock:
        print(message)

def get_ffmpeg_args(mode):
    """Returns the FFmpeg arguments based on speed mode, plus aggressive audio/meta removal."""
    
    # THE METADATA NUKE:
    # -an : removes all audio streams
    # -map_metadata -1 : removes all global container metadata
    # -map_metadata:s:v -1 : removes metadata specifically attached to the video stream (like handler names)
    # -map_chapters -1 : removes any embedded chapters or scene markers
    # -fflags +bitexact : prevents FFmpeg from writing its own "Lavf" software signature into the new file
    # -movflags +faststart : optimizes MP4 structure for fast playback
    # -y : overwrites existing files automatically
    base_args = [
        '-an', 
        '-map_metadata', '-1', 
        '-map_metadata:s:v', '-1',
        '-map_chapters', '-1',
        '-fflags', '+bitexact',
        '-movflags', '+faststart', 
        '-y'
    ]
    
    if mode == 'copy':
        # INSTANT: Copies only the video stream, no re-encoding.
        return ['-c:v', 'copy'] + base_args
    elif mode == 'nvidia':
        return ['-c:v', 'h264_nvenc', '-preset', 'fast'] + base_args
    elif mode == 'amd':
        return ['-c:v', 'h264_amf'] + base_args
    elif mode == 'intel':
        return ['-c:v', 'h264_qsv'] + base_args
    elif mode == 'cpu_ultrafast':
        return ['-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23'] + base_args
    else:
        return ['-c:v', 'libx264', '-preset', 'fast', '-crf', '23'] + base_args

def process_single_video(file_path, in_dir, out_dir, default_mode):
    relative_path = file_path.relative_to(in_dir)
    target_path = out_dir / relative_path
    target_path = target_path.with_suffix('.mp4')
    
    # Ensure target subfolder exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # --- SMART DETECTION ---
    # If the file is already an MP4, force 'copy' mode to skip re-encoding.
    # If it's a MOV, use whatever mode you selected at the bottom of the script.
    current_mode = 'copy' if file_path.suffix.lower() == '.mp4' else default_mode

    safe_print(f"Starting [{current_mode} | Deep-Scrub]: {relative_path.name}")
    
    # Construct command
    command = ['ffmpeg', '-i', str(file_path)] + get_ffmpeg_args(current_mode) + [str(target_path)]
    
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        safe_print(f"  -> Finished: {relative_path.name}")
    except subprocess.CalledProcessError:
        safe_print(f"  -> ERROR: Failed to process {relative_path.name}.")
    except FileNotFoundError:
        safe_print("\nCRITICAL ERROR: 'ffmpeg' command not found.")

def process_videos_parallel(input_dir, output_dir, max_workers, mode):
    in_dir = Path(input_dir)
    out_dir = Path(output_dir)

    if not in_dir.exists():
        print(f"Error: Input directory '{input_dir}' not found.")
        return

    # Find both .mov and .mp4 files recursively
    valid_extensions = {'.mov', '.mp4'}
    video_files = [f for f in in_dir.rglob('*') if f.is_file() and f.suffix.lower() in valid_extensions]
    
    if not video_files:
        print("No .mov or .mp4 files found in the input directory.")
        return

    print(f"Found {len(video_files)} video files.")
    print(f"Starting processing (Default Mode: {mode}, Workers: {max_workers})...\n")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_single_video, file_path, in_dir, out_dir, mode) 
            for file_path in video_files
        ]
        concurrent.futures.wait(futures)

    print("\nAll processing complete! Videos are now clean MP4s, deeply scrubbed of metadata, with no audio.")

if __name__ == "__main__":
    # --- SETUP YOUR PATHS HERE ---
    INPUT_FOLDER = input("Enter the input folder path: ").strip('"\'')
    OUTPUT_FOLDER = input("Enter the output folder path: ").strip('"\'')
    
    # --- CHOOSE YOUR SPEED MODE HERE ---
    ENCODING_MODE = 'cpu_ultrafast' 
    MAX_WORKERS = 4 
    
    process_videos_parallel(INPUT_FOLDER, OUTPUT_FOLDER, MAX_WORKERS, ENCODING_MODE)
