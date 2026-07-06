import sys
import os
import shutil
import subprocess
import json
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
    
    # Check if running as compiled PyInstaller exe
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
        
    raise FileNotFoundError(f"{exe_name} missing! Please place it in the 'bin/' folder.")

# [Keep your existing functions here: detect_qsv_support, default_worker_count, 
# find_mov_files, ffprobe_info, build_cmd, convert_file, verify_mp4]
# *Make sure to update the subprocess calls to use get_bin_path("ffmpeg") 
# instead of hardcoding "ffmpeg"*


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
            
            # Note: Update detect_qsv_support in your original code to use get_bin_path
            use_gpu = False # detect_qsv_support() 
            self.log("\nIntel Quick Sync: " + ("Available" if use_gpu else "Not available (Using CPU)"))

            workers = default_worker_count(use_gpu)
            cores = os.cpu_count() or 4
            threads_per_job = max(1, cores // workers)

            mov_files = find_mov_files(self.root_path)
            if not mov_files:
                self.log(f"No .mov files found under {self.root_path}")
                self.finished_signal.emit(True)
                return

            self.log(f"Found {len(mov_files)} .mov file(s). Converting with {workers} worker(s)...\n")

            results = []
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(convert_file, f, use_gpu, threads_per_job): f
                    for f in mov_files
                }
                for future in as_completed(futures):
                    src, dst, success, msg = future.result()
                    status = "OK  " if success else "FAIL"
                    self.log(f"[{status}] {src.name} :: {msg}")
                    
                    if success:
                        try:
                            src.unlink()
                            self.log(f"      Deleted original: {src.name}")
                        except OSError as e:
                            self.log(f"      Warning: could not delete {src}: {e}")
                    
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
        self.resize(700, 500)
        self.setAcceptDrops(True) # Enable window-level drops

        # Layout setup
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Instructions
        self.label = QLabel("Drag & Drop a folder below, or paste the path:")
        layout.addWidget(self.label)

        # Input Row
        input_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("e.g. C:/Users/Name/Videos")
        input_layout.addWidget(self.path_input)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_folder)
        input_layout.addWidget(self.browse_btn)
        layout.addLayout(input_layout)

        # Action Button
        self.start_btn = QPushButton("Start Conversion")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self.start_conversion)
        layout.addWidget(self.start_btn)

        # Log Output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.worker = None

    # Drag and Drop Event Handlers
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            if Path(url.toLocalFile()).is_dir():
                event.acceptProposedAction()

    def dropEvent(self, event):
        url = event.mimeData().urls()[0]
        self.path_input.setText(url.toLocalFile())

    # Button Handlers
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.path_input.setText(folder)

    def start_conversion(self):
        folder_path = self.path_input.text().strip()
        if not folder_path or not Path(folder_path).is_dir():
            self.log_output.append("Error: Please provide a valid directory path.")
            return

        # Lock UI
        self.start_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.path_input.setEnabled(False)
        self.log_output.clear()

        # Start background thread
        self.worker = ConversionWorker(folder_path)
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.conversion_finished)
        self.worker.start()

    def append_log(self, text):
        self.log_output.append(text)
        # Auto-scroll to bottom
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
