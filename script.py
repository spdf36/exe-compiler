import pandas as pd
import os
import shutil
import cv2
from datetime import datetime
from pathlib import Path
import sys

def get_video_metadata(filepath):
    """Extracts duration, FPS, and resolution from a video file."""
    cap = cv2.VideoCapture(str(filepath))
    if not cap.isOpened():
        return None, None, None
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Handle potential division by zero
    duration_sec = round(frame_count / fps, 2) if fps and fps > 0 else 0.0
    resolution = f"{width}x{height}"
    
    cap.release()
    return duration_sec, round(fps, 2), resolution

def process_video_dataset(input_xlsx, source_folder, output_xlsx, output_base_folder):
    print("\n[1/4] Loading Excel file...")
    try:
        df = pd.read_excel(input_xlsx)
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return
    
    # Clean up column names just in case there are trailing spaces
    df.columns = df.columns.str.strip()
    
    print("[2/4] Scanning source directory for video files (this might take a moment)...")
    source_path = Path(source_folder)
    # Dictionary to quickly find the full path of a file by its name
    file_map = {f.name: f for f in source_path.rglob('*') if f.is_file()}
    print(f"      Found {len(file_map)} total files in source directories.")
    
    # Create the batch directory with today's date
    today_str = datetime.now().strftime("%Y-%m-%d")
    batch_folder_name = f"batch_{today_str}"
    batch_dir = Path(output_base_folder) / batch_folder_name
    
    new_paths = []
    
    print(f"[3/4] Processing files, extracting metadata, and organizing folders...")
    
    # Use standard loops with print updates for a better CLI experience
    total_rows = len(df)
    for index, row in df.iterrows():
        file_name = str(row.get("Video File Name")).strip()
        
        # Display progress
        sys.stdout.write(f"\r      Processing {index + 1}/{total_rows}: {file_name[:30]}...")
        sys.stdout.flush()
        
        # Replace NaNs or empty values with "Unknown" to avoid folder creation errors
        age_group = str(row.get("Age Group", "Unknown_Age")).strip() or "Unknown_Age"
        gender = str(row.get("Gender", "Unknown_Gender")).strip() or "Unknown_Gender"
        skin_tone = str(row.get("Skin Tone", "Unknown_Skin_Tone")).strip() or "Unknown_Skin_Tone"
        participant_id = str(row.get("Global Participant ID", "Unknown_ID")).strip() or "Unknown_ID"
        
        # Check if the file exists in our scanned files
        if file_name in file_map:
            original_file_path = file_map[file_name]
            
            # Construct the new folder structure
            target_dir = batch_dir / age_group / gender / skin_tone / participant_id
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Construct the target file path
            target_file_path = target_dir / file_name
            
            try:
                # Move the file
                shutil.move(str(original_file_path), str(target_file_path))
                
                # Extract Metadata from the video
                duration, fps, resolution = get_video_metadata(target_file_path)
                
                # Update the DataFrame with the extracted data
                df.at[index, "Video Duration (sec)"] = duration
                df.at[index, "FPS"] = fps
                df.at[index, "Video Resolution"] = resolution
                
                # Record the relative path starting from batch_<todays_date>
                relative_path = Path(batch_folder_name) / age_group / gender / skin_tone / participant_id / file_name
                new_paths.append(str(relative_path))
            except Exception as e:
                new_paths.append(f"Error Processing: {e}")
            
        else:
            new_paths.append("File Not Found in Source")
            
    print("\n[4/4] Sorting data and saving to new Excel file...")
    # Add the new path column to the end of the DataFrame
    df["File Path"] = new_paths
    
    # Sort by Global Participant ID
    if "Global Participant ID" in df.columns:
        df.sort_values(by="Global Participant ID", inplace=True)
    
    # Save to the new Output Excel file
    try:
        df.to_excel(output_xlsx, index=False, engine='openpyxl')
        print(f"\nSUCCESS! Process complete. Output saved to: {output_xlsx}")
    except Exception as e:
        print(f"\nERROR: Could not save output Excel file. Is it open in another program? Details: {e}")

# ==========================================
# Terminal/CLI Interactive Execution Setup
# ==========================================
if __name__ == "__main__":
    print("=" * 60)
    print(" " * 15 + "Video Dataset Processor Tool")
    print("=" * 60)
    print("You can type the folder/file paths or drag-and-drop them here.\n")

    # 1. Get Input Excel Path
    while True:
        input_xlsx = input("1. Enter the path to the INPUT Excel file (.xlsx): ").strip()
        # Clean up quotes if user dragged-and-dropped the file into the terminal
        input_xlsx = input_xlsx.strip('"').strip("'") 
        
        if os.path.isfile(input_xlsx) and input_xlsx.lower().endswith('.xlsx'):
            break
        print("   [!] Error: File not found or not an .xlsx file. Please try again.\n")

    # 2. Get Source Video Folder
    while True:
        source_folder = input("2. Enter the path to the SOURCE video folder: ").strip()
        source_folder = source_folder.strip('"').strip("'")
        
        if os.path.isdir(source_folder):
            break
        print("   [!] Error: Directory not found. Please try again.\n")

    # 3. Get Output Base Folder
    while True:
        output_base_folder = input("3. Enter the target folder where files will be MOVED (batch folder will be created here): ").strip()
        output_base_folder = output_base_folder.strip('"').strip("'")
        
        if os.path.isdir(output_base_folder):
            break
        
        # Give user option to create the directory if it doesn't exist
        create_dir = input(f"   Directory '{output_base_folder}' does not exist. Create it? (y/n): ").strip().lower()
        if create_dir == 'y':
            try:
                os.makedirs(output_base_folder, exist_ok=True)
                break
            except Exception as e:
                print(f"   [!] Error creating directory: {e}\n")
        else:
            print("   Please provide a valid directory.\n")

    # 4. Get Output Excel File Name
    output_xlsx = input("4. Enter the desired name/path for the OUTPUT Excel file (e.g., output.xlsx): ").strip()
    output_xlsx = output_xlsx.strip('"').strip("'")
    if not output_xlsx.lower().endswith('.xlsx'):
        output_xlsx += '.xlsx'

    # Run the main processor
    try:
        process_video_dataset(input_xlsx, source_folder, output_xlsx, output_base_folder)
    except KeyboardInterrupt:
        print("\n\nProcess cancelled by user.")
    except Exception as e:
        print(f"\n\nAn unexpected error occurred: {e}")

    print("=" * 60)
    # Crucial for .exe files: Prevents the terminal window from closing instantly upon completion
    input("Press Enter to exit the program...")
