import sys
import os
import json
import subprocess
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import requests
from packaging import version

# yt-dlp python API
try:
    import yt_dlp as ytdlp
except Exception as e:
    raise RuntimeError("yt-dlp Python package not found. Install with: pip install yt-dlp") from e

# GUI
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QFileDialog, QListWidget, QListWidgetItem, QProgressBar, QMessageBox,
    QFormLayout, QFrame, QMenu, QTextEdit, QDialog, QCheckBox, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon

from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

APP_NAME = "yt2convert"
APP_VERSION = "1.1.1"
GITHUB_REPO = "HossEz/yt2convert" 
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

SCRIPT_DIR = Path(__file__).parent.resolve()

# AppData directory setup for Windows
if sys.platform.startswith("win"):
    APPDATA_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME
else:
    # Fallback for non-Windows systems
    APPDATA_DIR = Path.home() / f".{APP_NAME.lower()}"

# Ensure AppData directory exists
APPDATA_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = APPDATA_DIR / "history.json"
SETTINGS_FILE = APPDATA_DIR / "settings.json"
DEFAULT_CONVERTED_DIR = SCRIPT_DIR / "converted"

# Audio format and quality mappings
AUDIO_FORMATS = {
    "MP3": {
        "320 kbps": {"bitrate": "320k", "codec": "libmp3lame"},
        "256 kbps": {"bitrate": "256k", "codec": "libmp3lame"},
        "192 kbps": {"bitrate": "192k", "codec": "libmp3lame"},
        "128 kbps": {"bitrate": "128k", "codec": "libmp3lame"},
        "64 kbps": {"bitrate": "64k", "codec": "libmp3lame"}
    },
    "WAV": {
        "32-bit (48 kHz)": {"codec": "pcm_f32le", "sample_rate": "48000"},
        "24-bit (48 kHz)": {"codec": "pcm_s24le", "sample_rate": "48000"},
        "16-bit (44.1 kHz)": {"codec": "pcm_s16le", "sample_rate": "44100"}
    }
}

# More realistic video codec to yt-dlp format mapping
VIDEO_CODEC_FORMATS = {
    "H.264 (AVC)": {
        "format_selector": "avc1",
        "common_name": "h264",
        "audio_codec": "aac"
    },
    "VP9": {
        "format_selector": "vp9", 
        "common_name": "vp9",
        "audio_codec": "opus"
    },
    "AV1": {
        "format_selector": "av01",
        "common_name": "av1",
        "audio_codec": "opus"
    }
}

# Realistic resolution availability by codec
CODEC_RESOLUTION_MATRIX = {
    "H.264 (AVC)": {
        "1080p": {"height": 1080, "common": True},
        "720p": {"height": 720, "common": True},
        "480p": {"height": 480, "common": True},
        "360p": {"height": 360, "common": True},
        "240p": {"height": 240, "common": False},
        "144p": {"height": 144, "common": False}
    },
    "VP9": {
        "2160p (4K)": {"height": 2160, "common": True},
        "1440p (2K)": {"height": 1440, "common": True},
        "1080p": {"height": 1080, "common": True}, 
        "720p": {"height": 720, "common": True},
        "480p": {"height": 480, "common": False},
        "360p": {"height": 360, "common": False}
    },
    "AV1": {
        "2160p (4K)": {"height": 2160, "common": True},
        "1440p (2K)": {"height": 1440, "common": False},
        "1080p": {"height": 1080, "common": False},
        "720p": {"height": 720, "common": False}
    }
}

RESOLUTION_CODEC_MATRIX = {
    "2160p (4K)": ["VP9", "AV1"],
    "1440p (2K)": ["VP9", "AV1"],
    "1080p": ["H.264 (AVC)", "VP9"],
    "720p": ["H.264 (AVC)", "VP9"],
    "480p": ["H.264 (AVC)"],
    "360p": ["H.264 (AVC)"],
    "240p": ["H.264 (AVC)"],
    "144p": ["H.264 (AVC)"]
}

# ---------- Settings persistence ----------
DEFAULT_SETTINGS = {
    "download_folder": str(DEFAULT_CONVERTED_DIR),
    "theme": "Midnight Blue",
    "auto_check_updates": True,
    "last_update_check": "",
    "last_ytdlp_update": "",
    "use_speed_optimizations": True,  # New: enable speed optimizations by default
}


def load_settings() -> Dict:
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                s = json.load(f)
                return {**DEFAULT_SETTINGS, **s}
        except Exception:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: Dict):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print("Warning: could not save settings:", e)

# ---------- History persistence ----------

def load_history() -> List[Dict]:
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history: List[Dict]):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("Warning: could not save history:", e)

# ---------- Icon Handling Function ----------
def get_icon_path():
    """Get the path to the app icon, handling both development and built environments"""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    icon_paths = [
        os.path.join(base_path, "appicon.ico"),
        os.path.join(base_path, "resources", "appicon.ico"),
        os.path.join(base_path, "..", "resources", "appicon.ico"),
    ]
    
    for path in icon_paths:
        if os.path.exists(path):
            return path
    
    return None

# ---------- yt-dlp Auto-Update ----------
class YtdlpUpdater(QThread):
    """Thread for updating yt-dlp executable automatically"""
    update_started = Signal()
    update_progress = Signal(str)  # Progress message
    update_finished = Signal(bool, str)  # (success, message)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ytdlp_exe_path = self._get_ytdlp_path()
    
    def _get_ytdlp_path(self):
        """Get the path where yt-dlp.exe should be located"""
        if hasattr(sys, '_MEIPASS'):
            # Running as PyInstaller bundle - yt-dlp.exe should be in the same directory as the .exe
            return Path(sys.executable).parent / "yt-dlp.exe"
        else:
            # Running as script - look in script directory
            return SCRIPT_DIR / "yt-dlp.exe"
    
    def run(self):
        self.update_started.emit()
        self.update_progress.emit("Checking yt-dlp version...")
        
        try:
            # Check if yt-dlp.exe exists
            if not self.ytdlp_exe_path.exists():
                self.update_progress.emit("yt-dlp.exe not found, downloading...")
                self._download_ytdlp()
                return
            
            # Method 1: Try using yt-dlp.exe's built-in update (--update flag)
            try:
                self.update_progress.emit("Updating yt-dlp.exe using --update...")
                
                result = subprocess.run(
                    [str(self.ytdlp_exe_path), "--update"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
                )
                
                output = result.stdout + result.stderr
                
                if "Updated" in output or "up to date" in output.lower() or "already" in output.lower():
                    self.update_progress.emit("yt-dlp is up to date")
                    self.update_finished.emit(True, "yt-dlp is already up to date")
                    return
                elif result.returncode == 0:
                    self.update_progress.emit("yt-dlp updated successfully")
                    self.update_finished.emit(True, "yt-dlp has been updated to the latest version")
                    return
                else:
                    self.update_progress.emit("Self-update failed, trying manual download...")
                    raise Exception("Self-update returned non-zero exit code")
            
            except Exception as self_update_error:
                self.update_progress.emit(f"Self-update method failed: {str(self_update_error)}")
            
            # Method 2: Download latest yt-dlp.exe from GitHub
            self._download_ytdlp()
                
        except Exception as e:
            self.update_progress.emit(f"Update failed: {str(e)}")
            self.update_finished.emit(False, f"Failed to update yt-dlp: {str(e)}")
    
    def _download_ytdlp(self):
        """Download the latest yt-dlp.exe from GitHub"""
        try:
            self.update_progress.emit("Downloading latest yt-dlp.exe from GitHub...")
            
            # Get latest release info
            response = requests.get(
                "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest",
                timeout=10
            )
            response.raise_for_status()
            release_data = response.json()
            
            # Find the Windows executable
            download_url = None
            for asset in release_data.get("assets", []):
                if asset["name"] == "yt-dlp.exe":
                    download_url = asset["browser_download_url"]
                    break
            
            if not download_url:
                raise Exception("Could not find yt-dlp.exe in latest release")
            
            self.update_progress.emit(f"Downloading from {download_url}...")
            
            # Download the file
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            # Download to temporary file first
            temp_path = self.ytdlp_exe_path.with_suffix('.tmp')
            
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress_pct = int((downloaded / total_size) * 100)
                            self.update_progress.emit(f"Downloading: {progress_pct}%")
            
            # Replace old yt-dlp.exe with new one
            if self.ytdlp_exe_path.exists():
                backup_path = self.ytdlp_exe_path.with_suffix('.old')
                if backup_path.exists():
                    backup_path.unlink()
                self.ytdlp_exe_path.rename(backup_path)
            
            temp_path.rename(self.ytdlp_exe_path)
            
            self.update_progress.emit("yt-dlp.exe updated successfully")
            self.update_finished.emit(True, "yt-dlp has been updated to the latest version")
            
        except Exception as e:
            self.update_progress.emit(f"Download failed: {str(e)}")
            self.update_finished.emit(False, f"Failed to download yt-dlp: {str(e)}")


def should_check_ytdlp_update(settings: Dict) -> bool:
    """Check if it's time to update yt-dlp (every 24 hours)"""
    last_check = settings.get("last_ytdlp_update", "")
    if not last_check:
        return True
    
    try:
        last_dt = datetime.fromisoformat(last_check)
        now = datetime.now()
        hours_since = (now - last_dt).total_seconds() / 3600
        return hours_since >= 24
    except:
        return True


# ---------- Helper functions for update management ----------
def get_current_executable_path():
    """Get the path of the currently running executable"""
    if hasattr(sys, 'frozen'):
        return sys.executable
    else:
        return os.path.abspath(sys.argv[0])

def get_executable_directory():
    """Get the directory containing the current executable"""
    return Path(get_current_executable_path()).parent

def create_update_batch_script(old_exe_path, new_exe_path, app_name):
    """Create a batch script that will handle the update after the app closes"""
    batch_content = f'''@echo off
timeout /t 2 /nobreak >nul
echo Updating {app_name}...

:retry
del /f /q "{old_exe_path}" 2>nul
if exist "{old_exe_path}" (
    timeout /t 1 /nobreak >nul
    goto retry
)

move "{new_exe_path}" "{old_exe_path}"
if errorlevel 1 (
    echo Update failed. Press any key to exit.
    pause >nul
    exit /b 1
)

echo Update completed successfully!
echo Starting {app_name}...
start "" "{old_exe_path}"

del /f /q "%~f0" 2>nul & exit /b 0
'''
    
    batch_path = Path(tempfile.gettempdir()) / f"update_{app_name}_{os.getpid()}.bat"
    with open(batch_path, 'w') as f:
        f.write(batch_content)
    
    return batch_path

def safe_replace_executable_delayed(old_path, new_path, app_name="yt2convert"):
    """Safely replace the old executable using a delayed batch script approach"""
    old_path = Path(old_path)
    new_path = Path(new_path)
    
    try:
        batch_script = create_update_batch_script(str(old_path), str(new_path), app_name)
        
        if sys.platform.startswith("win"):
            subprocess.Popen(
                [str(batch_script)], 
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_CONSOLE,
                cwd=tempfile.gettempdir()
            )
        
        return True
    except Exception as e:
        raise e

def safe_replace_executable_move_and_restart(old_path, new_path):
    """Alternative approach: rename old exe and place new one, then restart"""
    old_path = Path(old_path)
    new_path = Path(new_path)
    backup_path = old_path.with_suffix('.old')
    
    try:
        if old_path.exists():
            if backup_path.exists():
                backup_path.unlink()
            old_path.rename(backup_path)
        
        shutil.move(str(new_path), str(old_path))
        
        return True
    except Exception as e:
        if backup_path.exists() and not old_path.exists():
            try:
                backup_path.rename(old_path)
            except:
                pass
        raise e

# ---------- Update Checker Thread ----------
class UpdateChecker(QThread):
    update_available = Signal(dict)
    no_update = Signal()
    check_failed = Signal(str)
    
    def __init__(self, silent_check=False, parent=None):
        super().__init__(parent)
        self.silent_check = silent_check
    
    def run(self):
        try:
            response = requests.get(GITHUB_API_URL, timeout=10)
            response.raise_for_status()
            
            release_data = response.json()
            latest_version = release_data.get("tag_name", "").lstrip("v")
            
            if not latest_version:
                if not self.silent_check:
                    self.check_failed.emit("Invalid version format from GitHub")
                return
            
            if version.parse(latest_version) > version.parse(APP_VERSION):
                download_url = None
                for asset in release_data.get("assets", []):
                    if asset["name"].endswith(".exe") or asset["name"].endswith(".zip"):
                        download_url = asset["browser_download_url"]
                        break
                
                if download_url:
                    self.update_available.emit({
                        "version": latest_version,
                        "download_url": download_url,
                        "changelog": release_data.get("body", "No changelog available."),
                        "release_name": release_data.get("name", f"Version {latest_version}")
                    })
                else:
                    if not self.silent_check:
                        self.check_failed.emit("No compatible download found")
            else:
                self.no_update.emit()
                
        except requests.RequestException as e:
            if not self.silent_check:
                self.check_failed.emit(f"Network error: {str(e)}")
        except Exception as e:
            if not self.silent_check:
                self.check_failed.emit(f"Update check failed: {str(e)}")

# ---------- Update Downloader Thread ----------
class UpdateDownloader(QThread):
    progress_changed = Signal(int)
    download_finished = Signal(str)
    download_failed = Signal(str)
    
    def __init__(self, download_url, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self._stop_requested = False
    
    def run(self):
        try:
            response = requests.get(self.download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".exe") as temp_file:
                temp_path = temp_file.name
                downloaded = 0
                
                for chunk in response.iter_content(chunk_size=8192):
                    if self._stop_requested:
                        return
                    
                    if chunk:
                        temp_file.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.progress_changed.emit(progress)
            
            self.download_finished.emit(temp_path)
            
        except Exception as e:
            self.download_failed.emit(f"Download failed: {str(e)}")
    
    def request_stop(self):
        self._stop_requested = True

# ---------- Worker Thread for Download + Convert ----------
class DownloadWorker(QThread):
    progress_changed = Signal(float)
    status_message = Signal(str, str)
    finished_success = Signal(dict)
    log_line = Signal(str)

    def __init__(self, url: str, format_choice: str, quality_choice: str, outdir: str, codec_choice: str = None, settings: Dict = None, parent=None):
        super().__init__(parent)
        self.url = url
        self.format_choice = format_choice
        self.quality_choice = quality_choice
        self.codec_choice = codec_choice
        self.outdir = str(Path(outdir).expanduser())
        self.settings = settings or {}
        self._stop_requested = False

    def run(self):
        # Get paths for external executables
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
            app_dir = Path(sys.executable).parent
        else:
            base_path = SCRIPT_DIR
            app_dir = SCRIPT_DIR
        
        # FFmpeg path
        ffmpeg_path = os.path.join(base_path, "ffmpeg.exe")
        if not os.path.exists(ffmpeg_path):
            self.status_message.emit("error", "FFmpeg not found. Make sure ffmpeg is bundled with the application.")
            return
        
        # yt-dlp executable path (stored in app directory, not in _MEIPASS)
        ytdlp_exe = app_dir / "yt-dlp.exe"
        if not ytdlp_exe.exists():
            self.status_message.emit("error", "yt-dlp.exe not found. Please wait for automatic download or check settings.")
            return

        Path(self.outdir).mkdir(parents=True, exist_ok=True)

        tmp_template = os.path.join(self.outdir, "%(title).200s.%(ext)s")
        
        ytdlp_opts = {
            "outtmpl": tmp_template,
            "restrictfilenames": False,
            "no_warnings": True,
            "quiet": True,
            "ignoreerrors": False,
            "noplaylist": True,
            "progress_hooks": [self._progress_hook],
            "postprocessors": [],
            "nocheckcertificate": True,
            "extract_flat": False,
            "cookiefile": None,
        }

        if self.format_choice in ["MP3", "WAV"]:
            ytdlp_opts["format"] = "bestaudio/best"
            ytdlp_opts["postprocessors"] = []
        else:
            resolution = self.quality_choice
            codec = self.codec_choice or "Best Available"
            
            if resolution == "Best Available" and codec == "Best Available":
                ytdlp_opts["format"] = "bestvideo+bestaudio/best"
            else:
                format_parts = []
                
                if resolution != "Best Available" and resolution in RESOLUTION_CODEC_MATRIX:
                    height = None
                    for codec_name, resolutions in CODEC_RESOLUTION_MATRIX.items():
                        if resolution in resolutions:
                            height = resolutions[resolution]["height"]
                            break
                    
                    if height is None:
                        import re
                        height_match = re.search(r'(\d+)p', resolution)
                        height = int(height_match.group(1)) if height_match else 720
                    
                    format_parts.append(f"height<={height}")
                
                if codec != "Best Available" and codec in VIDEO_CODEC_FORMATS:
                    codec_selector = VIDEO_CODEC_FORMATS[codec]["format_selector"]
                    format_parts.append(f"vcodec^={codec_selector}")
                
                if format_parts:
                    constraints = "[" + "][".join(format_parts) + "]"
                    
                    if codec == "H.264 (AVC)":
                        format_string = f"bestvideo{constraints}+bestaudio[acodec^=mp4a]/best{constraints}/bestvideo+bestaudio/best"
                    else:
                        format_string = f"bestvideo{constraints}+bestaudio/best{constraints}/bestvideo+bestaudio/best"
                else:
                    format_string = "bestvideo+bestaudio/best"
                
                ytdlp_opts["format"] = format_string
            
            ytdlp_opts["merge_output_format"] = "mp4"

        self.log_line.emit("Starting yt-dlp download...")
        self.status_message.emit("info", "Starting download...")

        try:
            # Use yt-dlp executable instead of Python package
            ytdlp_cmd = [str(ytdlp_exe)]
            
            # Add common options
            ytdlp_cmd.extend([
                "-o", tmp_template,
                "--no-warnings",
                "--no-playlist",
                "--progress",
                "--newline"
            ])
            
            # Apply speed optimizations if enabled
            if self.settings.get("use_speed_optimizations", True):
                # Speed optimization options
                ytdlp_cmd.extend([
                    "--concurrent-fragments", "4",  # Download multiple fragments simultaneously
                    "--extractor-retries", "3",
                    "--fragment-retries", "3",
                    "--file-access-retries", "3",
                    "--throttled-rate", "100K",  # Only consider it throttled below 100KB/s
                ])
                
                # Add user-agent to mimic real browser
                user_agents = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ]
                import random
                ytdlp_cmd.extend(["--user-agent", random.choice(user_agents)])
                
                # Note: We skip browser cookies due to DPAPI decryption issues on Windows
                # The other optimizations (concurrent downloads, user-agent) are enough
            
            # Add format-specific options
            if self.format_choice in ["MP3", "WAV"]:
                ytdlp_cmd.extend(["-f", "bestaudio/best"])
            else:
                # Video download format selection
                resolution = self.quality_choice
                codec = self.codec_choice or "Best Available"
                
                if resolution == "Best Available" and codec == "Best Available":
                    ytdlp_cmd.extend(["-f", "bestvideo+bestaudio/best"])
                else:
                    format_parts = []
                    
                    if resolution != "Best Available" and resolution in RESOLUTION_CODEC_MATRIX:
                        height = None
                        for codec_name, resolutions in CODEC_RESOLUTION_MATRIX.items():
                            if resolution in resolutions:
                                height = resolutions[resolution]["height"]
                                break
                        
                        if height is None:
                            import re
                            height_match = re.search(r'(\d+)p', resolution)
                            height = int(height_match.group(1)) if height_match else 720
                        
                        format_parts.append(f"height<={height}")
                    
                    if codec != "Best Available" and codec in VIDEO_CODEC_FORMATS:
                        codec_selector = VIDEO_CODEC_FORMATS[codec]["format_selector"]
                        format_parts.append(f"vcodec^={codec_selector}")
                    
                    if format_parts:
                        constraints = "[" + "][".join(format_parts) + "]"
                        
                        if codec == "H.264 (AVC)":
                            format_string = f"bestvideo{constraints}+bestaudio[acodec^=mp4a]/best{constraints}/bestvideo+bestaudio/best"
                        else:
                            format_string = f"bestvideo{constraints}+bestaudio/best{constraints}/bestvideo+bestaudio/best"
                    else:
                        format_string = "bestvideo+bestaudio/best"
                    
                    ytdlp_cmd.extend(["-f", format_string])
                
                ytdlp_cmd.extend(["--merge-output-format", "mp4"])
            
            ytdlp_cmd.append(self.url)
            
            # Run yt-dlp executable
            proc = subprocess.Popen(
                ytdlp_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
            )
            
            downloaded_file = None
            while True:
                if self._stop_requested:
                    proc.terminate()
                    self.status_message.emit("error", "Operation cancelled by user.")
                    return
                    
                line = proc.stdout.readline()
                if line == "" and proc.poll() is not None:
                    break
                    
                if line:
                    line = line.strip()
                    self.log_line.emit(line)
                    
                    # Parse progress from yt-dlp output
                    if "[download]" in line and "%" in line:
                        try:
                            import re
                            match = re.search(r'(\d+\.?\d*)%', line)
                            if match:
                                pct = float(match.group(1))
                                self.progress_changed.emit(min(80.0, pct * 0.8))
                        except:
                            pass
                    
                    # Capture the destination filename
                    if "[download] Destination:" in line or "Merging formats into" in line:
                        parts = line.split(":", 1)
                        if len(parts) > 1:
                            downloaded_file = parts[1].strip().strip('"')
            
            ret = proc.wait()
            if ret != 0:
                self.status_message.emit("error", f"yt-dlp failed with exit code {ret}.")
                return
            
            # Find the downloaded file
            if not downloaded_file or not os.path.exists(downloaded_file):
                # Try to find the most recent file in output directory
                output_files = list(Path(self.outdir).glob("*"))
                if output_files:
                    downloaded_file = str(max(output_files, key=lambda p: p.stat().st_mtime))
                else:
                    self.status_message.emit("error", "Could not locate downloaded file.")
                    return
            
            downloaded_path = downloaded_file
            
        except Exception as e:
            self.status_message.emit("error", f"Download failed: {e}")
            return

        # Get video title for naming
        base_title = Path(downloaded_path).stem
        if base_title.startswith("yt_"):
            base_title = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        safe_basename = "".join(c for c in base_title if c.isalnum() or c in " .-_()").strip()
        
        if self.format_choice in ["MP3", "WAV"]:
            out_ext = self.format_choice.lower()
        else:
            out_ext = "mp4"
            
        out_name = f"{safe_basename}.{out_ext}"
        out_path = os.path.join(self.outdir, out_name)

        self.log_line.emit(f"Downloaded to: {downloaded_path}")
        
        if self.format_choice in ["MP3", "WAV"]:
            self.status_message.emit("info", "Converting audio...")
            
            format_settings = AUDIO_FORMATS[self.format_choice.upper()][self.quality_choice]
            
            if out_ext == "mp3":
                ff_args = [
                    ffmpeg_path, "-y", "-i", downloaded_path,
                    "-vn", "-map", "0:a",
                    "-c:a", format_settings["codec"], 
                    "-b:a", format_settings["bitrate"],
                    out_path
                ]
            else:
                ff_args = [
                    ffmpeg_path, "-y", "-i", downloaded_path,
                    "-vn", "-map", "0:a",
                    "-c:a", format_settings["codec"],
                    "-ar", format_settings["sample_rate"],
                    out_path
                ]

            try:
                proc = subprocess.Popen(
                    ff_args,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                while True:
                    if self._stop_requested:
                        proc.terminate()
                        self.status_message.emit("error", "Operation cancelled by user.")
                        return
                    line = proc.stderr.readline()
                    if line == "" and proc.poll() is not None:
                        break
                    if line:
                        self.log_line.emit(line.strip())
                ret = proc.wait()
                if ret != 0:
                    self.status_message.emit("error", f"ffmpeg failed with exit code {ret}.")
                    return
            except Exception as e:
                self.status_message.emit("error", f"Conversion error: {e}")
                return

            if out_ext == "mp3":
                try:
                    audio = MP3(out_path, ID3=EasyID3)
                    tags = {}
                    tags["title"] = base_title
                    # Can't get uploader info from executable output easily
                    audio.update(tags)
                    audio.save()
                except Exception as e:
                    self.log_line.emit(f"Tagging warning: {e}")

            try:
                dp = Path(downloaded_path)
                op = Path(out_path)
                if dp.exists() and dp.resolve() != op.resolve():
                    try:
                        dp.unlink()
                        self.log_line.emit(f"Removed intermediate file: {dp.name}")
                    except Exception as e:
                        self.log_line.emit(f"Could not remove intermediate file {dp.name}: {e}")
            except Exception:
                pass
        else:
            if downloaded_path != out_path:
                try:
                    shutil.move(downloaded_path, out_path)
                    self.log_line.emit(f"Renamed video file to: {out_path}")
                except Exception as e:
                    self.log_line.emit(f"Could not rename video file: {e}")
                    out_path = downloaded_path

        self.progress_changed.emit(100.0)
        self.status_message.emit("success", f"Saved: {out_path}")
        self.finished_success.emit({
            "outfile": out_path,
            "title": base_title,
            "format": out_ext,
            "quality": self.quality_choice,
            "codec": self.codec_choice if self.format_choice == "MP4" else "",
            "downloaded_path": downloaded_path
        })

    def _progress_hook(self, d):
        # This method is no longer used since we're using yt-dlp executable
        # Keeping it for backward compatibility
        pass

    def request_stop(self):
        self._stop_requested = True

# ---------- Update Dialog ----------
class UpdateDialog(QDialog):
    def __init__(self, update_info, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.downloader = None
        self.setWindowTitle("Update Available")
        self.setMinimumSize(500, 400)
        self.setModal(True)
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        header = QLabel(f"New version available: {self.update_info['version']}")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #2e7d32; margin-bottom: 10px;")
        layout.addWidget(header)
        
        if self.update_info.get('release_name'):
            release_label = QLabel(self.update_info['release_name'])
            release_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
            layout.addWidget(release_label)
        
        current_label = QLabel(f"Current version: {APP_VERSION}")
        current_label.setStyleSheet("color: #666; margin-bottom: 15px;")
        layout.addWidget(current_label)
        
        changelog_label = QLabel("What's New:")
        changelog_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        layout.addWidget(changelog_label)
        
        changelog = QTextEdit()
        changelog.setPlainText(self.update_info.get('changelog', 'No changelog available.'))
        changelog.setReadOnly(True)
        changelog.setMaximumHeight(150)
        layout.addWidget(changelog)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        
        button_layout = QHBoxLayout()
        
        self.download_btn = QPushButton("Download & Install")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1b5e20;
            }
        """)
        self.download_btn.clicked.connect(self._start_download)
        
        self.later_btn = QPushButton("Maybe Later")
        self.later_btn.clicked.connect(self.reject)
        
        self.cancel_btn = QPushButton("Cancel Download")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_download)
        
        button_layout.addWidget(self.later_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.download_btn)
        
        layout.addLayout(button_layout)
    
    def _start_download(self):
        self.download_btn.setVisible(False)
        self.cancel_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.status_label.setText("Downloading update...")
        
        self.downloader = UpdateDownloader(self.update_info['download_url'])
        self.downloader.progress_changed.connect(self.progress_bar.setValue)
        self.downloader.download_finished.connect(self._on_download_finished)
        self.downloader.download_failed.connect(self._on_download_failed)
        self.downloader.start()
    
    def _cancel_download(self):
        if self.downloader:
            self.downloader.request_stop()
            self.downloader.wait()
        self.reject()
    
    def _on_download_finished(self, temp_path):
        self.status_label.setText("Download complete! Installing...")
        self.progress_bar.setValue(100)
        
        try:
            current_exe = get_current_executable_path()
            
            try:
                safe_replace_executable_delayed(current_exe, temp_path, APP_NAME)
                
                msg = QMessageBox(self)
                msg.setWindowTitle("Update Complete")
                msg.setIcon(QMessageBox.Information)
                msg.setText("Update will be installed when you close the application!")
                msg.setInformativeText(
                    "The update has been prepared. When you close the application, "
                    "the update will be automatically installed and the application will restart.\n\n"
                    "Click OK to close the application now and apply the update."
                )
                msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
                msg.setDefaultButton(QMessageBox.Ok)
                
                if msg.exec() == QMessageBox.Ok:
                    QApplication.instance().quit()
                
            except Exception as batch_error:
                try:
                    safe_replace_executable_move_and_restart(current_exe, temp_path)
                    
                    msg = QMessageBox(self)
                    msg.setWindowTitle("Update Complete")
                    msg.setIcon(QMessageBox.Information)
                    msg.setText("Update installed successfully!")
                    msg.setInformativeText(
                        "The application has been updated. Please restart the application to use the new version.\n"
                        "The old version has been backed up as .old"
                    )
                    msg.setStandardButtons(QMessageBox.Ok)
                    
                    if msg.exec() == QMessageBox.Ok:
                        try:
                            subprocess.Popen([current_exe], cwd=Path(current_exe).parent)
                            QApplication.instance().quit()
                        except Exception as restart_error:
                            error_msg = QMessageBox(self)
                            error_msg.setIcon(QMessageBox.Warning)
                            error_msg.setWindowTitle("Restart Required")
                            error_msg.setText("Update installed successfully, but automatic restart failed.")
                            error_msg.setInformativeText(f"Please manually restart the application.\nRestart error: {str(restart_error)}")
                            error_msg.exec()
                            
                except Exception as rename_error:
                    error_msg = QMessageBox(self)
                    error_msg.setIcon(QMessageBox.Critical)
                    error_msg.setWindowTitle("Installation Error")
                    error_msg.setText("Could not install update automatically.")
                    error_msg.setInformativeText(
                        f"Batch script error: {str(batch_error)}\n"
                        f"Rename method error: {str(rename_error)}\n\n"
                        f"Downloaded file is available at:\n{temp_path}\n\n"
                        "Please manually replace the executable or run as administrator."
                    )
                    error_msg.exec()
                    
        except Exception as e:
            error_msg = QMessageBox(self)
            error_msg.setIcon(QMessageBox.Critical)
            error_msg.setWindowTitle("Installation Error")
            error_msg.setText(f"Unexpected error during update: {str(e)}")
            error_msg.setInformativeText(f"Downloaded file is available at:\n{temp_path}")
            error_msg.exec()
    
    def _on_download_failed(self, error_message):
        self.status_label.setText(f"Download failed: {error_message}")
        self.progress_bar.setVisible(False)
        self.download_btn.setVisible(True)
        self.cancel_btn.setVisible(False)

# ---------- Modern Main Window ----------
class ModernMainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(920, 600)
        
        icon_path = get_icon_path()
        if icon_path and os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)
            QApplication.instance().setWindowIcon(app_icon)

        self.settings = load_settings()
        Path(self.settings.get("download_folder", DEFAULT_SETTINGS["download_folder"])).mkdir(parents=True, exist_ok=True)
        self.worker: Optional[DownloadWorker] = None
        self.history: List[Dict] = load_history()
        self.update_checker: Optional[UpdateChecker] = None
        self.has_update_available = False
        self.ytdlp_updater: Optional[YtdlpUpdater] = None

        self._build_ui()
        self._apply_theme()
        self._load_history_list()
        
        # Check for app updates on startup if enabled
        if self.settings.get("auto_check_updates", True):
            QTimer.singleShot(2000, self._check_for_updates_silent)
        
        # Always check for yt-dlp updates on startup (automatic, silent)
        # This will download if missing, or update if 24+ hours have passed
        QTimer.singleShot(500, self._check_and_update_ytdlp)

    def _check_and_update_ytdlp(self):
        """Check and update yt-dlp automatically - downloads if missing or updates if 24hrs passed"""
        # Get yt-dlp.exe path
        if hasattr(sys, '_MEIPASS'):
            app_dir = Path(sys.executable).parent
        else:
            app_dir = SCRIPT_DIR
        
        ytdlp_exe = app_dir / "yt-dlp.exe"
        
        # Always update if yt-dlp.exe is missing
        if not ytdlp_exe.exists():
            self._append_log("yt-dlp.exe not found - downloading now...")
            self._force_ytdlp_update()
            return
        
        # Otherwise, check if 24 hours have passed
        if should_check_ytdlp_update(self.settings):
            self._append_log("Checking for yt-dlp updates...")
            self._force_ytdlp_update()
    
    def _force_ytdlp_update(self):
        """Force an immediate yt-dlp update"""
        self.ytdlp_updater = YtdlpUpdater()
        self.ytdlp_updater.update_progress.connect(self._on_ytdlp_update_progress)
        self.ytdlp_updater.update_finished.connect(self._on_ytdlp_update_finished)
        self.ytdlp_updater.start()
    
    def _on_ytdlp_update_progress(self, message: str):
        """Handle yt-dlp update progress messages"""
        self._append_log(f"yt-dlp: {message}")
    
    def _on_ytdlp_update_finished(self, success: bool, message: str):
        """Handle yt-dlp update completion"""
        if success:
            self._append_log(f"yt-dlp: {message}")
            self.settings["last_ytdlp_update"] = datetime.now().isoformat()
            save_settings(self.settings)
        else:
            self._append_log(f"yt-dlp update warning: {message}")
        
        self.ytdlp_updater = None

    def start_download(self):
        url = self.url_input.text().strip()
        if not url:
            self._set_status("error", "Please enter a YouTube URL.")
            return
        
        format_choice = self.format_dropdown.currentText()
        quality_choice = self.quality_dropdown.currentText()
        
        if not format_choice or not quality_choice:
            self._set_status("error", "Please select format and quality.")
            return

        codec_choice = None
        if format_choice == "MP4":
            codec_choice = self.codec_dropdown.currentText()

        outdir = self.settings.get("download_folder", DEFAULT_SETTINGS["download_folder"])

        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self._set_status("info", "Queued...")

        self.worker = DownloadWorker(url, format_choice, quality_choice, outdir, codec_choice, self.settings)
        self.worker.progress_changed.connect(self.progress_bar.setValue)
        self.worker.status_message.connect(self._set_status)
        self.worker.log_line.connect(self._append_log)
        self.worker.finished_success.connect(self._on_download_finish)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        card = QFrame()
        card.setObjectName("card")
        card.setMinimumHeight(540)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("app_title")
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        subtitle = QLabel("Audio/Video download & convert — yt-dlp + ffmpeg")
        subtitle.setObjectName("subtitle")
        header.addWidget(title)
        header.addWidget(subtitle, 0, Qt.AlignRight)
        card_layout.addLayout(header)

        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube URL or share link...")

        self.format_dropdown = QComboBox()
        self.format_dropdown.addItems(["MP3", "WAV", "MP4"])
        self.format_dropdown.setFixedWidth(100)
        self.format_dropdown.currentTextChanged.connect(self._update_format_options)

        self.quality_dropdown = QComboBox()
        self.quality_dropdown.setFixedWidth(130)

        self.codec_dropdown = QComboBox()
        self.codec_dropdown.setFixedWidth(130)
        self.codec_dropdown.addItems(["Auto (Best Available)"] + list(VIDEO_CODEC_FORMATS.keys()))
        self.codec_dropdown.setVisible(False)

        self.info_icon = QLabel()
        self.info_icon.setFixedSize(16, 16)
        self.info_icon.setVisible(False)
        self.info_icon.setToolTip("")
        self.info_icon.setCursor(Qt.PointingHandCursor)
        
        self.info_icon.setText("ⓘ")
        self.info_icon.setStyleSheet("""
            QLabel {
                color: #2bd3bf;
                font-weight: bold;
                font-size: 14px;
                background: transparent;
                border: none;
            }
            QLabel:hover {
                color: #0da78b;
            }
        """)
        
        self.info_icon.mousePressEvent = self._show_codec_info

        self.start_button = QPushButton("Download")
        self.start_button.setFixedWidth(140)

        controls.addWidget(self.url_input, 1)
        controls.addWidget(self.format_dropdown)
        controls.addWidget(self.quality_dropdown)
        controls.addWidget(self.codec_dropdown)
        controls.addWidget(self.info_icon)
        controls.addWidget(self.start_button)

        card_layout.addLayout(controls)

        self._update_format_options()

        self.codec_dropdown.currentTextChanged.connect(self._on_codec_changed)
        self.quality_dropdown.currentTextChanged.connect(self._on_quality_changed)

        prog_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(22)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_current)
        self.cancel_button.setFixedWidth(120)

        prog_row.addWidget(self.progress_bar, 1)
        prog_row.addWidget(self.cancel_button)
        card_layout.addLayout(prog_row)

        split_row = QHBoxLayout()
        left = QVBoxLayout()
        left_label = QLabel("Conversion history")
        left_label.setObjectName("section_label")
        left.addWidget(left_label)

        self.dl_list = QListWidget()
        self.dl_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.dl_list.customContextMenuRequested.connect(self._history_context_menu)
        left.addWidget(self.dl_list, 1)

        left_row = QHBoxLayout()
        clear_btn = QPushButton("Clear history")
        clear_btn.clicked.connect(self._clear_history)
        open_folder_btn = QPushButton("Open converted folder")
        open_folder_btn.clicked.connect(self._open_converted_folder)
        left_row.addWidget(clear_btn)
        left_row.addWidget(open_folder_btn)
        left.addLayout(left_row)

        split_row.addLayout(left, 2)

        right = QVBoxLayout()
        right_label = QLabel("Status & Log")
        right_label.setObjectName("section_label")
        right.addWidget(right_label)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setFixedHeight(48)
        right.addWidget(self.status_label)

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setFixedHeight(240)
        right.addWidget(self.log_edit)

        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self.open_settings_dialog)
        settings_btn.setFixedWidth(120)
        right.addWidget(settings_btn, 0, Qt.AlignRight)

        split_row.addLayout(right, 3)

        card_layout.addLayout(split_row)

        help_label = QLabel("Tip: Customize the output folder and theme in Settings.")
        help_label.setObjectName("help")
        card_layout.addWidget(help_label)

        root.addWidget(card)
        self.setLayout(root)
        
        self.url_input.returnPressed.connect(self.start_download)
        self.start_button.clicked.connect(self.start_download)

    def _show_codec_info(self, event):
        """Show a custom dialog with codec information"""
        dlg = QDialog(self)
        dlg.setWindowTitle("Codec Information")
        dlg.setMinimumWidth(400)
        dlg.setWindowModality(Qt.NonModal)
        
        layout = QVBoxLayout(dlg)
        
        dlg.setStyleSheet("""
            QDialog {
                background: rgba(25, 35, 45, 0.95);
                border-radius: 12px;
                color: #e6eef8;
            }
            QLabel {
                background: transparent;
                padding: 8px;
                font-size: 13px;
            }
        """)
        
        info_text = """
        <h3>Video Codec Information</h3>
        <p><b>H.264 (AVC):</b> Best compatibility, average quality. Max quality is 1080p. Prioritizes AAC audio for compatibility.</p>
        <p><b>VP9:</b> Better quality than H.264, supports 4K & HDR. Uses Opus audio.</p>
        <p><b>AV1:</b> Best quality and efficiency. Supports 8K & HDR. Uses Opus audio.</p>
        <p><i>Note: For H.264, if no high-quality AAC stream is available, it may fall back to other audio codecs to maintain video quality.</i></p>
        """
        
        label = QLabel(info_text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText)
        layout.addWidget(label)
        
        icon_pos = self.info_icon.mapToGlobal(self.info_icon.rect().topLeft())
        dlg.move(icon_pos.x() - 350, icon_pos.y() + 20)
        
        dlg.exec()

    def _update_format_options(self):
        """Update quality and codec dropdowns based on selected format"""
        current_format = self.format_dropdown.currentText()
        
        current_quality = self.quality_dropdown.currentText()
        current_codec = self.codec_dropdown.currentText()
        
        self.quality_dropdown.clear()
        
        self.info_icon.setVisible(current_format == "MP4")
        
        if current_format in AUDIO_FORMATS:
            qualities = list(AUDIO_FORMATS[current_format].keys())
            self.quality_dropdown.addItems(qualities)
            if current_quality in qualities:
                self.quality_dropdown.setCurrentText(current_quality)
            else:
                self.quality_dropdown.setCurrentIndex(0)
            self.codec_dropdown.setVisible(False)
        elif current_format == "MP4":
            self.codec_dropdown.setVisible(True)
            
            if current_codec and current_codec in list(VIDEO_CODEC_FORMATS.keys()) + ["Auto (Best Available)"]:
                available_resolutions = self._get_available_resolutions_for_codec(current_codec)
            else:
                available_resolutions = ["Best Available"] + list(RESOLUTION_CODEC_MATRIX.keys())
            
            self.quality_dropdown.addItems(available_resolutions)
            
            if current_quality in available_resolutions:
                self.quality_dropdown.setCurrentText(current_quality)
            else:
                self.quality_dropdown.setCurrentIndex(0)

    def _get_available_resolutions_for_codec(self, codec):
        """Get available resolutions for a specific codec"""
        if codec == "Auto (Best Available)":
            return ["Best Available"] + list(RESOLUTION_CODEC_MATRIX.keys())
        
        if codec in CODEC_RESOLUTION_MATRIX:
            available = ["Best Available"]
            resolutions = CODEC_RESOLUTION_MATRIX[codec]
            common_res = [res for res, info in resolutions.items() if info.get("common", False)]
            uncommon_res = [res for res, info in resolutions.items() if not info.get("common", False)]
            available.extend(common_res + uncommon_res)
            return available
        return ["Best Available"]

    def _get_available_codecs_for_resolution(self, resolution):
        """Get available codecs for a specific resolution"""
        if resolution == "Best Available":
            return ["Auto (Best Available)"] + list(VIDEO_CODEC_FORMATS.keys())
        
        if resolution in RESOLUTION_CODEC_MATRIX:
            available = ["Auto (Best Available)"]
            available.extend(RESOLUTION_CODEC_MATRIX[resolution])
            return available
        return ["Auto (Best Available)"]

    def _on_codec_changed(self):
        """Handle codec dropdown change - update available resolutions"""
        if self.format_dropdown.currentText() != "MP4":
            return
        
        current_codec = self.codec_dropdown.currentText()
        current_quality = self.quality_dropdown.currentText()
        
        available_resolutions = self._get_available_resolutions_for_codec(current_codec)
        
        self.quality_dropdown.blockSignals(True)
        self.quality_dropdown.clear()
        self.quality_dropdown.addItems(available_resolutions)
        
        if current_quality in available_resolutions:
            self.quality_dropdown.setCurrentText(current_quality)
        else:
            self.quality_dropdown.setCurrentIndex(0)
        
        self.quality_dropdown.blockSignals(False)

    def _on_quality_changed(self):
        """Handle quality/resolution dropdown change - update available codecs"""
        if self.format_dropdown.currentText() != "MP4":
            return
        
        current_quality = self.quality_dropdown.currentText()
        current_codec = self.codec_dropdown.currentText()
        
        available_codecs = self._get_available_codecs_for_resolution(current_quality)
        
        self.codec_dropdown.blockSignals(True)
        self.codec_dropdown.clear()
        self.codec_dropdown.addItems(available_codecs)
        
        if current_codec in available_codecs:
            self.codec_dropdown.setCurrentText(current_codec)
        else:
            self.codec_dropdown.setCurrentIndex(0)
        
        self.codec_dropdown.blockSignals(False)

    def _get_theme_styles(self, theme_name: str) -> str:
        """Return CSS styles for the specified theme"""
        themes = {
            "Midnight Blue": """
                QWidget { background: #0b1220; color: #e6eef8; font-family: 'Segoe UI', Roboto, Arial, sans-serif; }
                #card { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #07101a, stop:1 #0b1220); border-radius: 12px; }
                #app_title { font-size: 20px; font-weight: 700; color: #ffffff; }
                #subtitle { color: #9fb6c9; font-size: 12px; }

                QLineEdit, QComboBox, QListWidget, QTextEdit {
                    background: rgba(255,255,255,0.03);
                    border: 1px solid rgba(255,255,255,0.06);
                    border-radius: 8px;
                    padding: 8px;
                    font-size: 13px;
                }

                QPushButton {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(45,212,191,0.14), stop:1 rgba(45,212,191,0.12));
                    border: 1px solid rgba(45,212,191,0.25);
                    padding: 8px 12px;
                    border-radius: 10px;
                    min-height: 28px;
                    font-weight: 600;
                }
                QPushButton:hover { background: rgba(45,212,191,0.22); }
                QPushButton:pressed { background: rgba(45,212,191,0.28); }

                QProgressBar { background: rgba(255,255,255,0.03); border-radius: 10px; padding: 2px; text-align: center; }
                QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #2bd3bf, stop:1 #0da78b); border-radius: 10px; }

                #section_label { font-weight:700; color: #bfeee2; margin-bottom:4px; }
                #help { color:#9fb6c9; font-size:12px; }
                QLabel { font-size:13px; }
                QTextEdit { background: rgba(0,0,0,0.18); }
                QListWidget { background: rgba(0,0,0,0.12); }
                
                QToolTip {
                    background-color: rgba(25, 35, 45, 0.95);
                    color: #e6eef8;
                    border: 1px solid rgba(255,255,255,0.1);
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 12px;
                }
            """,
            "Pure Light": """
                QWidget { background: #ffffff; color: #1a1a1a; font-family: 'Segoe UI', Roboto, Arial, sans-serif; }
                #card { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #f8f9fa, stop:1 #ffffff); border-radius: 12px; border: 1px solid #e9ecef; }
                #app_title { font-size: 20px; font-weight: 700; color: #212529; }
                #subtitle { color: #6c757d; font-size: 12px; }

                QLineEdit, QComboBox, QListWidget, QTextEdit {
                    background: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                    padding: 8px;
                    font-size: 13px;
                    color: #212529;
                }
                QLineEdit:focus, QComboBox:focus { border-color: #0d6efd; }

                QPushButton {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0d6efd, stop:1 #0b5ed7);
                    border: 1px solid #0d6efd;
                    color: white;
                    padding: 8px 12px;
                    border-radius: 10px;
                    min-height: 28px;
                    font-weight: 600;
                }
                QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0b5ed7, stop:1 #0a58ca); }
                QPushButton:pressed { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0a58ca, stop:1 #0953ba); }

                QProgressBar { background: #e9ecef; border-radius: 10px; padding: 2px; text-align: center; color: #212529; }
                QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0d6efd, stop:1 #0b5ed7); border-radius: 10px; }

                #section_label { font-weight:700; color: #495057; margin-bottom:4px; }
                #help { color:#6c757d; font-size:12px; }
                QLabel { font-size:13px; color: #212529; }
                QTextEdit { background: #f8f9fa; color: #212529; }
                QListWidget { background: #ffffff; color: #212529; }
            """,
            "Forest": """
                QWidget { background: #0d1b0f; color: #e8f5e8; font-family: 'Segoe UI', Roboto, Arial, sans-serif; }
                #card { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0a1409, stop:1 #0d1b0f); border-radius: 12px; }
                #app_title { font-size: 20px; font-weight: 700; color: #ffffff; }
                #subtitle { color: #a8c9a8; font-size: 12px; }

                QLineEdit, QComboBox, QListWidget, QTextEdit {
                    background: rgba(255,255,255,0.03);
                    border: 1px solid rgba(120,200,120,0.1);
                    border-radius: 8px;
                    padding: 8px;
                    font-size: 13px;
                }

                QPushButton {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(34,197,94,0.14), stop:1 rgba(34,197,94,0.12));
                    border: 1px solid rgba(34,197,94,0.25);
                    padding: 8px 12px;
                    border-radius: 10px;
                    min-height: 28px;
                    font-weight: 600;
                }
                QPushButton:hover { background: rgba(34,197,94,0.22); }
                QPushButton:pressed { background: rgba(34,197,94,0.28); }

                QProgressBar { background: rgba(255,255,255,0.03); border-radius: 10px; padding: 2px; text-align: center; }
                QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #22c55e, stop:1 #16a34a); border-radius: 10px; }

                #section_label { font-weight:700; color: #86efac; margin-bottom:4px; }
                #help { color:#a8c9a8; font-size:12px; }
                QLabel { font-size:13px; }
                QTextEdit { background: rgba(0,0,0,0.18); }
                QListWidget { background: rgba(0,0,0,0.12); }
            """
        }
        return themes.get(theme_name, themes["Midnight Blue"])

    def _apply_theme(self):
        """Apply the current theme"""
        theme_name = self.settings.get("theme", "Midnight Blue")
        css = self._get_theme_styles(theme_name)
        self.setStyleSheet(css)

    def _update_window_title(self):
        """Update window title based on update status"""
        base_title = f"{APP_NAME} v{APP_VERSION}"
        if self.has_update_available:
            self.setWindowTitle(f"{base_title} - New Update Available")
        else:
            self.setWindowTitle(base_title)

    def _append_log(self, text: str):
        timestamp = f"[{datetime.now().strftime('%H:%M:%S')}]"
        self.log_edit.append(f"{timestamp} {text}")
        self.log_edit.verticalScrollBar().setValue(self.log_edit.verticalScrollBar().maximum())

    def _set_status(self, typ: str, message: str):
        color = {"info": "#7bf", "success": "#6f6", "error": "#f66"}.get(typ, "#7bf")
        self.status_label.setText(f"<span style='color:{color};font-weight:700'>{typ.upper()}</span>: {message}")
        QTimer.singleShot(6000, lambda: self.status_label.setText(""))

    def _check_for_updates_silent(self):
        """Check for updates without showing messages if no update is available"""
        self.silent_checker = UpdateChecker(silent_check=True)
        self.silent_checker.update_available.connect(self._on_update_available)
        self.silent_checker.check_failed.connect(lambda e: None) 
        self.silent_checker.finished.connect(lambda: setattr(self, 'silent_checker', None))
        self.silent_checker.start()

    def _check_for_updates_manual(self):
        """Manual update check triggered by user"""
        self._set_status("info", "Checking for updates...")
        self.update_checker = UpdateChecker(silent_check=False)
        self.update_checker.update_available.connect(self._on_update_available)
        self.update_checker.no_update.connect(self._on_no_update)
        self.update_checker.check_failed.connect(self._on_update_check_failed)
        self.update_checker.start()

    def _on_update_available(self, update_info):
        """Handle available update"""
        self.has_update_available = True
        self._update_window_title()
        
        update_dialog = UpdateDialog(update_info, self)
        update_dialog.exec()

    def _on_no_update(self):
        """Handle no update available"""
        self._set_status("success", "You have the latest version!")

    def _on_update_check_failed(self, error_message):
        """Handle update check failure"""
        self._set_status("error", f"Update check failed: {error_message}")

    def open_settings_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Settings")
        dlg.setMinimumSize(480, 380)
        layout = QFormLayout(dlg)

        folder_input = QLineEdit(self.settings.get("download_folder", DEFAULT_SETTINGS["download_folder"]))
        browse_btn = QPushButton("Browse")
        h = QHBoxLayout()
        h.addWidget(folder_input)
        h.addWidget(browse_btn)
        layout.addRow("Output folder:", h)

        theme_combo = QComboBox()
        theme_combo.addItems(["Midnight Blue", "Pure Light", "Forest"])
        theme_combo.setCurrentText(self.settings.get("theme", "Midnight Blue"))
        layout.addRow("Theme:", theme_combo)

        update_layout = QVBoxLayout()
        
        version_label = QLabel(f"Current version: {APP_VERSION}")
        update_layout.addWidget(version_label)
        
        auto_update_check = QCheckBox("Check for updates automatically")
        auto_update_check.setChecked(self.settings.get("auto_check_updates", True))
        update_layout.addWidget(auto_update_check)
        
        check_update_btn = QPushButton("Check for Updates")
        update_layout.addWidget(check_update_btn)
        
        layout.addRow("Updates:", update_layout)
        
        ytdlp_layout = QVBoxLayout()
        ytdlp_info = QLabel("yt-dlp updates automatically every 24 hours")
        ytdlp_info.setStyleSheet("color: #666; font-size: 11px;")
        ytdlp_layout.addWidget(ytdlp_info)
        
        force_ytdlp_btn = QPushButton("Force Update yt-dlp Now")
        ytdlp_layout.addWidget(force_ytdlp_btn)
        
        layout.addRow("yt-dlp:", ytdlp_layout)

        def browse_folder():
            d = QFileDialog.getExistingDirectory(self, "Select output folder", folder_input.text())
            if d:
                folder_input.setText(d)

        browse_btn.clicked.connect(browse_folder)

        def check_updates():
            dlg.setEnabled(False)
            original_text = check_update_btn.text()
            check_update_btn.setText("Checking...")
            QApplication.processEvents()
            
            dlg.checker = UpdateChecker(silent_check=False)
            
            def on_update_available(info):
                dlg.reject()
                self._on_update_available(info)
                
            def on_no_update():
                check_update_btn.setText("You're up to date!")
                dlg.setEnabled(True)
                self._on_no_update()
                QTimer.singleShot(5000, lambda: check_update_btn.setText(original_text))
                
            def on_check_failed(e):
                check_update_btn.setText(original_text)
                dlg.setEnabled(True)
                self._on_update_check_failed(e)
            
            dlg.checker.update_available.connect(on_update_available)
            dlg.checker.no_update.connect(on_no_update)
            dlg.checker.check_failed.connect(on_check_failed)
            dlg.checker.finished.connect(lambda: setattr(dlg, 'checker', None))
            dlg.checker.start()

        check_update_btn.clicked.connect(check_updates)
        
        def force_ytdlp_update():
            dlg.setEnabled(False)
            original_text = force_ytdlp_btn.text()
            force_ytdlp_btn.setText("Updating yt-dlp...")
            QApplication.processEvents()
            
            self._append_log("Manual yt-dlp update requested...")
            
            dlg.ytdlp_updater = YtdlpUpdater()
            
            def on_ytdlp_progress(msg):
                self._append_log(f"yt-dlp: {msg}")
            
            def on_ytdlp_finished(success, msg):
                force_ytdlp_btn.setText(original_text)
                dlg.setEnabled(True)
                if success:
                    self._append_log(f"yt-dlp: {msg}")
                    self.settings["last_ytdlp_update"] = datetime.now().isoformat()
                    save_settings(self.settings)
                    QMessageBox.information(dlg, "Success", msg)
                else:
                    self._append_log(f"yt-dlp update warning: {msg}")
                    QMessageBox.warning(dlg, "Warning", msg)
            
            dlg.ytdlp_updater.update_progress.connect(on_ytdlp_progress)
            dlg.ytdlp_updater.update_finished.connect(on_ytdlp_finished)
            dlg.ytdlp_updater.start()
        
        force_ytdlp_btn.clicked.connect(force_ytdlp_update)
        
        # Speed optimization settings
        speed_layout = QVBoxLayout()
        speed_check = QCheckBox("Enable download speed optimizations (recommended)")
        speed_check.setChecked(self.settings.get("use_speed_optimizations", True))
        speed_check.setToolTip("Uses browser cookies, concurrent downloads, and smart throttling bypass")
        speed_layout.addWidget(speed_check)
        
        speed_info = QLabel("Helps bypass YouTube throttling by using:\n• Browser cookies for authentication\n• Concurrent fragment downloads\n• Random user-agents")
        speed_info.setStyleSheet("color: #666; font-size: 11px;")
        speed_info.setWordWrap(True)
        speed_layout.addWidget(speed_info)
        
        layout.addRow("Speed:", speed_layout)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addRow(btn_row)

        def do_save():
            old_theme = self.settings.get("theme", "Midnight Blue")
            self.settings["download_folder"] = folder_input.text()
            self.settings["theme"] = theme_combo.currentText()
            self.settings["auto_check_updates"] = auto_update_check.isChecked()
            self.settings["use_speed_optimizations"] = speed_check.isChecked()
            save_settings(self.settings)
            
            if old_theme != self.settings["theme"]:
                self._apply_theme()
            
            self._set_status("success", "Settings saved and applied.")
            dlg.accept()

        def do_cancel():
            if hasattr(dlg, 'checker') and dlg.checker and dlg.checker.isRunning():
                dlg.checker.quit()
                dlg.checker.wait(1000)
            if hasattr(dlg, 'ytdlp_updater') and dlg.ytdlp_updater and dlg.ytdlp_updater.isRunning():
                dlg.ytdlp_updater.quit()
                dlg.ytdlp_updater.wait(1000)
            dlg.reject()

        save_btn.clicked.connect(do_save)
        cancel_btn.clicked.connect(do_cancel)
        dlg.exec()

    def _load_history_list(self):
        self.history = load_history()
        self.dl_list.clear()
        for entry in sorted(self.history, key=lambda e: e.get("timestamp", ""), reverse=True):
            ts = entry.get("timestamp", "")
            pretty_ts = ts.replace("T", " ") if ts else ""
            name = Path(entry.get("outfile", "")).name
            quality_info = entry.get("quality", "")
            codec_info = entry.get("codec", "")
            
            if codec_info:
                display = f"{name} — {entry.get('format','')} {quality_info} ({codec_info}) — {pretty_ts}"
            else:
                display = f"{name} — {entry.get('format','')} {quality_info} — {pretty_ts}"
                
            li = QListWidgetItem(display)
            li.setData(Qt.UserRole, entry)
            self.dl_list.addItem(li)

    def _history_context_menu(self, pos):
        item = self.dl_list.itemAt(pos)
        if not item:
            return
        entry = item.data(Qt.UserRole)
        outfile = entry.get("outfile", "")
        menu = QMenu(self)
        open_act = menu.addAction("Open")
        reveal_act = menu.addAction("Show in folder")
        remove_act = menu.addAction("Remove from history")
        delete_act = menu.addAction("Delete file and remove")

        action = menu.exec(self.dl_list.mapToGlobal(pos))
        if action == open_act:
            self._open_file(outfile)
        elif action == reveal_act:
            self._reveal_in_explorer(outfile)
        elif action == delete_act:
            self._delete_file_and_remove_history(outfile, entry)
        elif action == remove_act:
            self._remove_from_history(entry)

    def _open_file(self, path):
        p = Path(path)
        if p.exists():
            url = QUrl.fromLocalFile(str(p))
            QDesktopServices.openUrl(url)
        else:
            self._set_status("error", "File not found on disk.")
            self._append_log(f"Open failed, file missing: {path}")

    def _reveal_in_explorer(self, path):
        p = Path(path)
        if not p.exists():
            self._set_status("error", "File not found on disk.")
            return
        if sys.platform.startswith("win"):
            subprocess.run(["explorer", "/select,", str(p)])
        elif sys.platform.startswith("darwin"):
            subprocess.run(["open", "-R", str(p)])
        else:
            subprocess.run(["xdg-open", str(p.parent)])

    def _delete_file_and_remove_history(self, path, entry):
        p = Path(path)
        ok = QMessageBox.question(self, "Delete file", f"Delete file {p.name} permanently and remove from history?", QMessageBox.Yes | QMessageBox.No)
        if ok != QMessageBox.Yes:
            return
        try:
            if p.exists():
                p.unlink()
            self.history = [e for e in self.history if e != entry]
            save_history(self.history)
            self._load_history_list()
            self._append_log(f"Deleted file and removed from history: {p.name}")
            self._set_status("success", "Deleted file and removed from history.")
        except Exception as e:
            self._set_status("error", f"Delete failed: {e}")

    def _remove_from_history(self, entry):
        self.history = [e for e in self.history if e != entry]
        save_history(self.history)
        self._load_history_list()
        self._append_log("Removed entry from history.")
        self._set_status("success", "Removed from history.")

    def _clear_history(self):
        ok = QMessageBox.question(self, "Clear history", "Clear the conversion history? (This will NOT delete files on disk.)", QMessageBox.Yes | QMessageBox.No)
        if ok != QMessageBox.Yes:
            return
        self.history = []
        save_history(self.history)
        self._load_history_list()
        self._append_log("History cleared.")
        self._set_status("success", "History cleared.")

    def _open_converted_folder(self):
        folder = Path(self.settings.get("download_folder", DEFAULT_SETTINGS["download_folder"]))
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            subprocess.run(["explorer", str(folder)])
        elif sys.platform.startswith("darwin"):
            subprocess.run(["open", str(folder)])
        else:
            subprocess.run(["xdg-open", str(folder)])

    @Slot(dict)
    def _on_download_finish(self, info: dict):
        outfile = info.get("outfile")
        title = info.get("title")
        fmt = info.get("format")
        quality = info.get("quality")
        codec = info.get("codec", "")
        ts = datetime.now().isoformat(timespec="seconds")
        entry = {"outfile": outfile, "title": title, "format": fmt, "quality": quality, "codec": codec, "timestamp": ts}
        self.history = [entry] + [e for e in self.history if e.get("outfile") != outfile]
        save_history(self.history)
        self._append_log(f"Saved file: {outfile}")
        self._set_status("success", f"Finished: {Path(outfile).name}")
        self._load_history_list()

    def _on_worker_finished(self):
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.worker = None

    def cancel_current(self):
        if self.worker:
            self.worker.request_stop()
            self._set_status("info", "Cancel requested...")

def main():
    app = QApplication(sys.argv)
    w = ModernMainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()