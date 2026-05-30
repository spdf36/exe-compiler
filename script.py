import os
import json
import random
import piexif
from PIL import Image

def get_random_time():
    """Generates a random time between 09:00:00 and 17:59:59"""
    h = random.randint(9, 17)
    m = random.randint(0, 59)
    s = random.randint(0, 59)
    return f"{h:02d}:{m:02d}:{s:02d}"

def find_image_file(folder_path, filename):
    """Searches recursively for a file in the given directory (case-insensitive)"""
    for root, _, files in os.walk(folder_path):
        for f in files:
            if f.lower() == filename.lower():
                return os.path.join(root, f)
    return None

def update_exif_date(filepath, new_date_str):
    """Updates the Date Taken (DateTimeOriginal) EXIF metadata of the image"""
    # EXIF dates are formatted with colons: YYYY:MM:DD HH:MM:SS
    date_part = new_date_str.split('T')[0].replace('-', ':')
    time_part = get_random_time()
    exif_datetime_str = f"{date_part} {time_part}"
    
    # piexif requires bytes
    exif_datetime_bytes = exif_datetime_str.encode('utf-8')

    try:
        if filepath.lower().endswith(('.jpg', '.jpeg')):
            try:
                exif_dict = piexif.load(filepath)
            except Exception:
                # If no EXIF data exists, create a blank dictionary structure
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}}

            # Update standard EXIF date fields
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = exif_datetime_bytes
            exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = exif_datetime_bytes
            exif_dict["0th"][piexif.ImageIFD.DateTime] = exif_datetime_bytes

            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, filepath)
            
        elif filepath.lower().endswith('.png'):
            # PNGs require Pillow to update EXIF chunks safely
            with Image.open(filepath) as img:
                exif = img.getexif()
                exif[36867] = exif_datetime_str  # DateTimeOriginal
                exif[36868] = exif_datetime_str  # DateTimeDigitized
                exif[306] = exif_datetime_str    # DateTime
                img.save(filepath, exif=exif)
                
        print(f"  [+] Updated: {os.path.basename(filepath)} -> {exif_datetime_str}")
    except Exception as e:
        print(f"  [!] Failed to update {os.path.basename(filepath)}: {e}")

def main():
    print("=============================================")
    print("      Image EXIF Date Randomizer Tool        ")
    print("=============================================\n")
    
    # 1. Take folder input from the user (stripping quotes if they dragged and dropped the folder)
    base_dir = input("Enter the path to the main input folder: ").strip().strip('"\'')
    
    if not os.path.isdir(base_dir):
        print(f"\n[Error] The directory '{base_dir}' does not exist.")
        input("\nPress Enter to close...")
        return

    # 2. Iterate through the subdirectories (P00032, P00033, etc.)
    for item in os.listdir(base_dir):
        batch_folder = os.path.join(base_dir, item)
        
        if os.path.isdir(batch_folder):
            metadata_path = os.path.join(batch_folder, "metadata.json")
            
            # 3. Check if metadata.json exists in this batch
            if os.path.isfile(metadata_path):
                print(f"\nProcessing batch: {item}")
                
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    try:
                        metadata = json.load(f)
                    except json.JSONDecodeError:
                        print(f"  [!] Failed to parse metadata.json in {item}")
                        continue
                
                historic_dates = metadata.get("historic_capture_dates", {})
                
                if not historic_dates:
                    print("  [-] No 'historic_capture_dates' found in metadata.json. Skipping.")
                    continue

                # 4. Process each image listed in the JSON
                for filename, date_str in historic_dates.items():
                    # We search for the file recursively inside the P batch folder to locate it
                    # no matter if it's in /Historical/ or another subdirectory.
                    img_path = find_image_file(batch_folder, filename)
                    
                    if img_path:
                        update_exif_date(img_path, date_str)
                    else:
                        print(f"  [!] File not found: {filename}")

    print("\n=============================================")
    print("Process complete!")
    input("Press Enter to close...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        input("\nPress Enter to close...")
