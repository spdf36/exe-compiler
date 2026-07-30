import sys
import os
import shutil
import subprocess
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QTextEdit, 
                             QFileDialog, QLabel)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# --- CORE LOGIC HELPER ---
def get_bin_path(exe_name):
    """Finds ffmpeg/ffprobe in a local 'bin' folder first, then system PATH."""
    exe_with_ext = f"{exe_name}.exe" if os.name == 'nt' else exe_name
    
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent
        
    local_bin = base_dir / "bin" / exe_with_ext
    if local_bin.exists():
        return str(local_bin)
        
    sys_path = shutil.which(exe_name)
    if sys_path:
        return sys_path
        
    raise FileNotFoundError(f"{exe_name} missing! Please place it in the 'bin/' or system PATH.")

def detect_qsv_support():
    """
    Detects if Intel Quick Sync Video (QSV) hardware encoding actually works 
    by attempting to encode a 0.1 second blank video in the background.
    """
    try:
        cmd = [
            get_bin_path("ffmpeg"),
            "-v", "error",            
            "-f", "lavfi",            
            "-i", "color=c=black:s=256x256:d=0.1", 
            "-c:v", "h264_qsv",       
            "-f", "null",             
            "-"                       
        ]
        
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        result = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo)
        return result.returncode == 0
    except Exception:
        return False

def default_worker_count(use_gpu):
    if use_gpu:
        return 1 
    cores = os.cpu_count() or 4
    return max(1, cores // 2)

def find_mov_files(root_path):
    """Recursively finds all .mov files, ensuring no duplicates on Windows."""
    seen_paths = set()
    unique_files = []
    
    # Search for both extensions but deduplicate by absolute path
    for ext in ("*.mov", "*.MOV"):
        for path_obj in Path(root_path).rglob(ext):
            # Normalize path for Windows case-insensitivity
            abs_path = str(path_obj.resolve()).lower()
            if abs_path not in seen_paths:
                seen_paths.add(abs_path)
                unique_files.append(path_obj)
                
    return unique_files

def verify_mp4(filepath):
    return filepath.exists() and filepath.stat().st_size > 0

def build_cmd(src, dst, use_gpu, threads_per_job):
    cmd = [
        get_bin_path("ffmpeg"),
        "-y",                 
        "-noautorotate",      
        "-i", str(src),       
        "-map_metadata", "-1", # Strips all global metadata
    ]
    
    if use_gpu:
        cmd.extend(["-c:v", "h264_qsv", "-preset", "medium"])
    else:
        cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "23"])
        
    cmd.extend([
        "-an", # Completely removes the audio track (mutes the video)
        "-threads", str(threads_per_job),
        str(dst)
    ])
    
    return cmd

def convert_file(src, use_gpu, threads_per_job):
    """Executes the FFmpeg conversion for a single file."""
    dst = src.with_suffix('.mp4')
    cmd = build_cmd(src, dst, use_gpu, threads_per_job)
    cmd_str = " ".join(cmd)
    
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        result = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo)
        
        if result.returncode == 0 and verify_mp4(dst):
            return (src, dst, True, "Successfully converted.")
        else:
            if dst.exists():
                dst.unlink()
            
            err_msg = f"COMMAND RAN:\n{cmd_str}\n\nFFMPEG ERROR OUTPUT:\n{result.stderr.strip()}"
            return (src, dst, False, err_msg)
            
    except Exception as e:
        return (src, dst, False, f"Python Exception: {str(e)}")


# --- THREAD FOR BACKGROUND PROCESSING ---
class ConversionWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, root_path):
        super().__init__()
        self.root_path = Path(root_path)

    def log(self, text):
        self.log_signal.emit(text)

    def run(self):
        try:
            self.log("--- MOV to MP4 In-Place Converter ---")
            
            use_gpu = detect_qsv_support() 
            self.log(f"Intel Quick Sync: {'Supported & Active' if use_gpu else 'Not Supported (Safely falling back to CPU)'}")

            workers = default_worker_count(use_gpu)
            cores = os.cpu_count() or 4
            threads_per_job = max(1, cores // workers)

            mov_files = find_mov_files(self.root_path)
            if not mov_files:
                self.log(f"No .mov files found under {self.root_path}")
                self.finished_signal.emit(True)
                return

            self.log(f"Found {len(mov_files)} unique .mov file(s). Converting with {workers} worker(s)...\n")

            results = []
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(convert_file, f, use_gpu, threads_per_job): f
                    for f in mov_files
                }
                for future in as_completed(futures):
                    src, dst, success, msg = future.result()
                    
                    if success:
                        self.log(f"[OK] {src.name} :: {msg}")
                        try:
                            # Tiny delay to guarantee Windows releases the file handle fully
                            time.sleep(0.1) 
                            src.unlink()
                            self.log(f"      Deleted original: {src.name}")
                        except OSError as e:
                            self.log(f"      Warning: could not delete {src.name}: {e}")
                    else:
                        self.log(f"\n[FAIL] {src.name}")
                        self.log(msg + "\n")
                    
                    results.append((src, dst, success, msg))

            succeeded = sum(1 for _, _, ok, _ in results if ok)
            failed = len(results) - succeeded
            self.log(f"\nDone. {succeeded} successful, {failed} failed.")
            
            self.finished_signal.emit(failed == 0)

        except Exception as e:
            self.log(f"\nCRITICAL ERROR: {str(e)}")
            self.finished_signal.emit(False)


# --- GUI WINDOW ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MOV to MP4 Converter")
        self.resize(800, 600)
        self.setAcceptDrops(True) 

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.label = QLabel("Drag & Drop a folder below, or paste the path:")
        layout.addWidget(self.label)

        input_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("e.g. C:/Users/Name/Videos")
        input_layout.addWidget(self.path_input)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_folder)
        input_layout.addWidget(self.browse_btn)
        layout.addLayout(input_layout)

        self.start_btn = QPushButton("Start Conversion")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self.start_conversion)
        layout.addWidget(self.start_btn)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("font-family: Consolas, 'Courier New', monospace;")
        layout.addWidget(self.log_output)

        self.worker = None

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            if Path(url.toLocalFile()).is_dir():
                event.acceptProposedAction()

    def dropEvent(self, event):
        url = event.mimeData().urls()[0]
        self.path_input.setText(url.toLocalFile())

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.path_input.setText(folder)

    def start_conversion(self):
        folder_path = self.path_input.text().strip()
        if not folder_path or not Path(folder_path).is_dir():
            self.log_output.append("Error: Please provide a valid directory path.")
            return

        self.start_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.path_input.setEnabled(False)
        self.log_output.clear()

        self.worker = ConversionWorker(folder_path)
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.conversion_finished)
        self.worker.start()

    def append_log(self, text):
        self.log_output.append(text)
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def conversion_finished(self, success):
        self.start_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.path_input.setEnabled(True)
        self.worker = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
