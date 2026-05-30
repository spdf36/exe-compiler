import os
import json
import random
import piexif
import csv
from PIL import Image

def get_random_time():
    """Generates a random time between 09:00:00 and 17:59:59"""
    h = random.randint(9, 17)
    m = random.randint(0, 59)
    s = random.randint(0, 59)
    return f"{h:02d}:{m:02d}:{s:02d}"

def get_random_night_time():
    """Generates a random time between 18:30:00 and 22:30:00 (6:30 PM to 10:30 PM)"""
    start_sec = 18 * 3600 + 30 * 60
    end_sec = 22 * 3600 + 30 * 60
    random_sec = random.randint(start_sec, end_sec)
    
    h = random_sec // 3600
    m = (random_sec % 3600) // 60
    s = random_sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def find_image_file(folder_path, filename):
    """Searches recursively for a file in the given directory (case-insensitive)"""
    if not os.path.isdir(folder_path):
        return None
    for root, _, files in os.walk(folder_path):
        for f in files:
            if f.lower() == filename.lower():
                return os.path.join(root, f)
    return None

def update_exif_date(filepath, new_date_str):
    """Updates the Date Taken (DateTimeOriginal) EXIF metadata of the image"""
    date_part = new_date_str.split('T')[0].replace('-', ':')
    time_part = get_random_time()
    exif_datetime_str = f"{date_part} {time_part}"
    exif_datetime_bytes = exif_datetime_str.encode('utf-8')

    try:
        if filepath.lower().endswith(('.jpg', '.jpeg')):
            try:
                exif_dict = piexif.load(filepath)
            except Exception:
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "Interop": {}, "1st": {}}

            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = exif_datetime_bytes
            exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = exif_datetime_bytes
            exif_dict["0th"][piexif.ImageIFD.DateTime] = exif_datetime_bytes

            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, filepath)
            
        elif filepath.lower().endswith('.png'):
            with Image.open(filepath) as img:
                exif = img.getexif()
                exif[36867] = exif_datetime_str
                exif[36868] = exif_datetime_str
                exif[306] = exif_datetime_str
                img.save(filepath, exif=exif)
                
        print(f"  [+] Day Time Updated: {os.path.basename(filepath)} -> {exif_datetime_str}")
    except Exception as e:
        print(f"  [!] Failed to update {os.path.basename(filepath)}: {e}")

def update_exif_night_time(filepath):
    """Reads existing EXIF date, keeps it, and only randomizes the time to night hours."""
    new_time_str = get_random_night_time()
    
    try:
        if filepath.lower().endswith(('.jpg', '.jpeg')):
            exif_dict = piexif.load(filepath)
            
            existing_datetime_bytes = exif_dict["Exif"].get(piexif.ExifIFD.DateTimeOriginal)
            if existing_datetime_bytes:
                existing_datetime_str = existing_datetime_bytes.decode('utf-8')
                date_part = existing_datetime_str.split(' ')[0]
            else:
                print(f"  [!] No existing EXIF date found in {os.path.basename(filepath)}. Skipping.")
                return
            
            new_datetime_str = f"{date_part} {new_time_str}"
            exif_datetime_bytes = new_datetime_str.encode('utf-8')
            
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = exif_datetime_bytes
            exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = exif_datetime_bytes
            exif_dict["0th"][piexif.ImageIFD.DateTime] = exif_datetime_bytes
            
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, filepath)
            print(f"  [+] Night Time Updated: {os.path.basename(filepath)} -> {new_datetime_str}")
            
        elif filepath.lower().endswith('.png'):
            with Image.open(filepath) as img:
                exif = img.getexif()
                existing_datetime_str = exif.get(36867)
                
                if existing_datetime_str:
                    date_part = existing_datetime_str.split(' ')[0]
                else:
                    print(f"  [!] No existing EXIF date found in {os.path.basename(filepath)}. Skipping.")
                    return
                    
                new_datetime_str = f"{date_part} {new_time_str}"
                exif[36867] = new_datetime_str
                exif[36868] = new_datetime_str
                exif[306] = new_datetime_str
                img.save(filepath, exif=exif)
                print(f"  [+] Night Time Updated: {os.path.basename(filepath)} -> {new_datetime_str}")
                
    except Exception as e:
        print(f"  [!] Failed to update night time for {os.path.basename(filepath)}: {e}")

def main():
    print("=============================================")
    print("      Image EXIF Date Randomizer Tool        ")
    print("=============================================\n")
    
    # --- PHASE 1: DAYTIME PROCESSING ---
    base_dir = input("Enter the path to the main input folder: ").strip().strip('"\'')
    
    if not os.path.isdir(base_dir):
        print(f"\n[Error] The directory '{base_dir}' does not exist.")
        input("\nPress Enter to close...")
        return

    for item in os.listdir(base_dir):
        batch_folder = os.path.join(base_dir, item)
        
        if os.path.isdir(batch_folder):
            metadata_path = os.path.join(batch_folder, "metadata.json")
            
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

                for filename, date_str in historic_dates.items():
                    # Safely search inside the specific batch folder
                    img_path = find_image_file(batch_folder, filename)
                    if img_path:
                        update_exif_date(img_path, date_str)
                    else:
                        print(f"  [!] File not found: {filename} in {item}")

    print("\n=============================================")
    print("      Day Time Processing Complete!          ")
    print("=============================================\n")

    # --- PHASE 2: NIGHTTIME PROCESSING ---
    process_night = input("Do you have a CSV file for night time pictures? (y/n): ").strip().lower()
    
    if process_night == 'y':
        csv_path = input("Enter the path to the CSV file: ").strip().strip('"\'')
        
        if os.path.isfile(csv_path):
            print("\nProcessing night time pictures from CSV...")
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row: 
                        continue
                    
                    rel_path = row[0].strip()
                    if not rel_path: 
                        continue
                    
                    # Normalize slashes and split
                    rel_path_clean = rel_path.replace('\\', '/')
                    parts = rel_path_clean.split('/')
                    filename = parts[-1]
                    
                    # Extract the P-folder (e.g., P00013) from the CSV path
                    p_folder = next((part for part in parts if part.upper().startswith('P0') and len(part) >= 4), None)
                    
                    img_path = None
                    
                    # If we found the P-folder in the CSV path, search ONLY inside that specific folder
                    if p_folder:
                        specific_batch_folder = os.path.join(base_dir, p_folder)
                        img_path = find_image_file(specific_batch_folder, filename)
                    
                    # If all else fails, try a global search in the base dir
                    if not img_path:
                        img_path = find_image_file(base_dir, filename)

                    # Update if found
                    if img_path and os.path.isfile(img_path):
                        update_exif_night_time(img_path)
                    else:
                        print(f"  [!] Night file not found in directory: {rel_path}")
        else:
            print(f"\n[Error] The CSV file '{csv_path}' does not exist.")

    print("\n=============================================")
    print("Process completely finished!")
    input("Press Enter to close...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        input("\nPress Enter to close...")
