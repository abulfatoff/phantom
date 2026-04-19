import os
import sys

if sys.platform == 'win32':
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("phantom.video.downloader.v4")
    except:
        pass

import json
import threading
import queue
import shlex
import shutil
import subprocess
import re
import requests
import zipfile
import asyncio
from typing import Dict, Any, Optional

import uvicorn
import webbrowser
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Enable CORS for local dev testing independent of PyWebView
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

APP_NAME = "PHANTOM"
CONFIG_FILE = "config.json"
DEFAULT_DOWNLOAD_DIR = os.path.expanduser("~/Downloads")

log_queue = queue.Queue()
active_downloads = 0
ffmpeg_download_progress = -2.0

def is_ffmpeg_available() -> bool:
    if os.path.isfile("ffmpeg.exe") and os.path.isfile("ffprobe.exe"):
        return True
    if os.path.isfile("ffmpeg") and os.path.isfile("ffprobe"):
        return True
    return False

class MyLogger:
    def __init__(self, log_queue: queue.Queue):
        self.log_queue = log_queue

    def debug(self, msg):
        if not msg.startswith("[debug] "):
            self.log_queue.put({"type": "log", "msg": f"{msg}\n"})

    def info(self, msg):
        self.log_queue.put({"type": "log", "msg": f"{msg}\n"})

    def warning(self, msg):
        self.log_queue.put({"type": "log", "msg": f"[yt-dlp UYARI]: {msg}\n"})

    def error(self, msg):
        self.log_queue.put({"type": "log", "msg": f"[yt-dlp ERROR]: {msg}\n"})

B_I18N = {
    "TR": {
        "start": "[SİSTEM] İndirme modülü aktif ediliyor...",
        "url": "[SİSTEM] Hedef Bağlantı",
        "wait": "[SİSTEM] Video meta verileri analiz ediliyor...",
        "success": "[BAŞARI] İşlem başarıyla tamamlandı!",
        "fail_cmd": "[HATA] Özel Komut Okunamadı",
        "override": "[AYAR] Manuel Parametre Tespit Edildi",
        "err": "[HATA]"
    },
    "AZ": {
        "start": "[SİSTEM] Yükləmə modulu aktivləşdirilir...",
        "url": "[SİSTEM] Hədəf Keçid",
        "wait": "[SİSTEM] Video meta məlumatları analiz edilir...",
        "success": "[UĞUR] Proses uğurla başa çatdı!",
        "fail_cmd": "[XƏTA] Xüsusi Əmr Oxuna Bilmədi",
        "override": "[AYAR] Manuel Parametr Təsbit Edildi",
        "err": "[XƏTA]"
    },
    "EN": {
        "start": "[SYSTEM] Download engine initializing...",
        "url": "[SYSTEM] Target URL",
        "wait": "[SYSTEM] Analyzing video metadata...",
        "success": "[SUCCESS] Operation completed successfully!",
        "fail_cmd": "[ERROR] Failed to Parse Custom Command",
        "override": "[FLAG] Manual Parameter Detected",
        "err": "[ERROR]"
    }
}

HISTORY_FILE = "history.json"

class HistoryManager:
    @staticmethod
    def load_history() -> list:
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    @staticmethod
    def add_history(title: str, url: str, format_str: str, file_path: str):
        import datetime
        data = HistoryManager.load_history()
        entry = {
            "title": title,
            "url": url,
            "format": format_str,
            "file_path": file_path,
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        data.insert(0, entry) # Prepend
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(data[:100], f, indent=4, ensure_ascii=False) # Latest 100
        except Exception:
            pass

class ConfigManager:
    @staticmethod
    def load_config() -> dict:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "remember": True,
            "format": 0,
            "custom_commands": "",
            "download_dir": DEFAULT_DOWNLOAD_DIR,
            "theme": "System",
            "language": "TR",
            "custom_templates": {}
        }

    @staticmethod
    def save_config(config_data: dict):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save config: {e}")

class CommandParser:
    @staticmethod
    def parse_to_ydl_opts(raw_text: str) -> Dict[str, Any]:
        import yt_dlp
        opts: Dict[str, Any] = {}
        if not raw_text.strip():
            return opts
        try:
            args = shlex.split(raw_text)
        except ValueError as e:
            raise ValueError(f"Komut ayrıştırma hatası: {e}")
        i = 0
        formats_found = []
        while i < len(args):
            arg = args[i]
            if arg in ('-f', '--format') and i + 1 < len(args):
                formats_found.append(args[i + 1])
                i += 1
            elif arg == '--embed-subs':
                opts['writesubtitles'] = True
                opts['subtitleslangs'] = ['all']
            elif arg in ('--write-auto-subs', '--write-auto-sub'):
                opts['writeautomaticsub'] = True
            elif arg == '--extract-audio' or arg == '-x':
                opts['extractaudio'] = True
            elif arg == '--audio-format' and i + 1 < len(args):
                opts['audioformat'] = args[i + 1]
                i += 1
            elif arg == '--audio-quality' and i + 1 < len(args):
                opts['audioquality'] = args[i + 1]
                i += 1
            elif arg == '--download-section' and i + 1 < len(args):
                val = args[i+1] # e.g. "*10:00-15:00"
                opts['download_ranges'] = yt_dlp.utils.download_range_func(None, [[val]])
                i += 1
            elif arg in ('--merge-output-format'):
                if i + 1 < len(args):
                    opts['merge_output_format'] = args[i + 1]
                    i += 1
            elif arg == '--embed-thumbnail':
                 opts['writethumbnail'] = True
                 opts.setdefault('postprocessors', []).append({'key': 'EmbedThumbnail'})
            elif arg == '--proxy' and i + 1 < len(args):
                 opts['proxy'] = args[i + 1]
                 i += 1
            i += 1
        if formats_found:
            opts['format'] = formats_found[-1] 
        return opts


class YTDLPWorker:
    def __init__(self, log_queue: queue.Queue):
        self.log_queue = log_queue
        if not is_ffmpeg_available():
            self.log_queue.put({"type": "log", "msg": "[UYARI] FFmpeg sistemde bulunamadı. Ses/Video birleştirme başarısız olabilir!\n"})

    def download_hook(self, d):
        import yt_dlp
        if d['status'] == 'downloading':
            percent_str = yt_dlp.utils.remove_quotes(d.get('_percent_str', '0%'))
            percent_clean = re.sub(r'\x1b[^m]*m', '', percent_str).strip()
            try:
                numeric_val = float(percent_clean.replace('%', '')) / 100.0
            except ValueError:
                numeric_val = 0.0

            speed = d.get('_speed_str', 'N/A')
            eta = d.get('_eta_str', 'N/A')
            # Changed string slightly to accommodate console log printing logically on web interface
            msg = f"> [yt-dlp] {percent_clean} | İndirme Hızı: {speed} | Kalan Süre: {eta}"
            self.log_queue.put({"type": "progress", "val": numeric_val, "msg": msg})

        elif d['status'] == 'finished':
            self.log_queue.put({"type": "log", "msg": "\n[yt-dlp] İndirme tamamlandı. Dosya işleniyor (Muxing/Dönüştürme)...\n"})

    def execute_download(self, url: str, format_id: str, download_type: str, start_time: str, end_time: str, custom_cmd: str, download_dir: str):
        import yt_dlp
        global active_downloads
        
        cfg = ConfigManager.load_config()
        lang = cfg.get("language", "EN")
        if lang not in B_I18N: lang = "EN"
        t = B_I18N[lang]

        self.log_queue.put({"type": "log", "msg": f"{t['start']}\n{t['url']}: {url}\n"})
        
        # Absolute path fix
        abs_dir = os.path.abspath(download_dir if download_dir.strip() else DEFAULT_DOWNLOAD_DIR)
        
        ydl_opts: Dict[str, Any] = {
            'logger': MyLogger(self.log_queue),
            'progress_hooks': [self.download_hook],
            'outtmpl': os.path.join(abs_dir, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'ffmpeg_location': '.',
        }

        # Format Logic
        if download_type == 'audio':
             ydl_opts['format'] = 'bestaudio/best'
             ydl_opts['postprocessors'] = [{
                 'key': 'FFmpegExtractAudio',
                 'preferredcodec': 'mp3',
                 'preferredquality': '320',
             }]
        else:
             if format_id == "Auto":
                 target_fmt = "bestvideo+bestaudio/best"
             else:
                 res = format_id.replace('p', '')
                 target_fmt = f"bestvideo[height<={res}]+bestaudio/best"
             ydl_opts['format'] = target_fmt
             ydl_opts['merge_output_format'] = 'mp4'

        # Bölgesel İndirme Güvenli Tetikleyicisi
        if start_time or end_time:
             import yt_dlp.utils
             s_time = yt_dlp.utils.parse_duration(start_time) if start_time else 0
             e_time = yt_dlp.utils.parse_duration(end_time) if end_time else 999999
             ydl_opts['download_ranges'] = lambda info_dict, ydl: [{'start_time': s_time, 'end_time': e_time}]

        try:
            custom_opts = CommandParser.parse_to_ydl_opts(custom_cmd)
            for k, v in custom_opts.items():
                ydl_opts[k] = v 
                val_repr = "Timestamp Interval" if k == "download_ranges" else v
                self.log_queue.put({"type": "log", "msg": f"{t['override']}: {k} = {val_repr}\n"})
        except Exception as e:
            self.log_queue.put({"type": "log", "msg": f"{t['fail_cmd']}: {str(e)}\n"})
            self.log_queue.put({"type": "done"})
            active_downloads -= 1
            return

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.log_queue.put({"type": "log", "msg": f"{t['wait']}\n"})
                info = ydl.extract_info(url, download=True)
                
                # History Hook
                if info:
                    title = info.get('title', 'Unknown')
                    ext = 'mp3' if download_type == 'audio' else 'mp4'
                    saved_path = os.path.join(abs_dir, f"{title}.{ext}")
                    HistoryManager.add_history(title, url, format_id if start_time == "" else f"{format_id} (Partial)", saved_path)

                self.log_queue.put({"type": "log", "msg": f"{t['success']}\n"})
        except Exception as e:
            self.log_queue.put({"type": "log", "msg": f"\n{t['err']}: {str(e)}\n"})
            
        self.log_queue.put({"type": "done"})
        active_downloads -= 1

# API ROUTE MODELS
class DownloadRequest(BaseModel):
    url: str
    format_id: str
    download_type: str = "video"
    start_time: str = ""
    end_time: str = ""
    custom_commands: str
    download_dir: str

class SettingsRequest(BaseModel):
    remember: bool
    format: int
    custom_commands: str
    download_dir: str
    theme: str
    language: str
    custom_templates: Dict[str, str] = {}

class InfoRequest(BaseModel):
    url: str

@app.post("/api/info")
def extract_video_info(req: InfoRequest):
    def fetch():
        import yt_dlp
        ydl_opts = {'noplaylist': True, 'quiet': True, 'ffmpeg_location': '.'}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(req.url, download=False)
                
                formats = []
                if 'formats' in info:
                    res_set = set()
                    for f in info['formats']:
                        if f.get('vcodec') != 'none' and f.get('height'):
                            h = f.get('height')
                            if h not in res_set:
                                res_set.add(h)
                    sorted_res = sorted(list(res_set), reverse=True)
                    formats = [f"{h}p" for h in sorted_res if h in [2160, 1440, 1080, 720, 480, 360]]
                
                return {
                    "title": info.get('title', 'Açıklama veya başlık bulunamadı.'),
                    "thumbnail": info.get('thumbnail', ''),
                    "formats": formats if formats else ["Auto"]
                }
        except Exception as e:
            return {"error": str(e)}
            
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(fetch)
        res = future.result()
        if "error" in res:
             return JSONResponse(status_code=400, content={"error": res["error"]})
        return res
@app.get("/api/select-folder")
def select_folder():
    import tkinter as tk
    from tkinter import filedialog
    import sys
    import os
    
    folder_path = ""
    # Sadece Windows'ta native pencere açmak için
    if sys.platform == 'win32':
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True) # Pencereyi en öne getir
        folder_path = filedialog.askdirectory(title="İndirme Klasörünü Seçin")
        root.destroy()
    
    if folder_path:
        # Yolları Windows formatında düzelt
        folder_path = os.path.normpath(folder_path)
    return {"path": folder_path or ""}

@app.get("/api/settings")
def get_settings():
    config_data = ConfigManager.load_config()
    return {"settings": config_data, "ffmpeg_available": is_ffmpeg_available()}

@app.get("/api/history")
def get_history():
    return {"history": HistoryManager.load_history()}

class LinkRequest(BaseModel):
    url: str

@app.post("/api/open-link")
def open_system_link(req: LinkRequest):
    import webbrowser
    def open_external():
        webbrowser.open(req.url)
    threading.Timer(0.1, open_external).start()
    return {"status": "ok"}

@app.post("/api/settings")
def save_settings(settings: SettingsRequest):
    ConfigManager.save_config(settings.dict())
    return {"status": "ok"}

@app.post("/api/download")
def trigger_download(req: DownloadRequest):
    global active_downloads
    if active_downloads > 0:
        return JSONResponse(status_code=400, content={"error": "Zaten aktif bir indirme veya işlem var."})
    
    if not req.url:
         return JSONResponse(status_code=400, content={"error": "Medya Bağlantısı (URL) boş olamaz."})
    
    active_downloads += 1
    worker = YTDLPWorker(log_queue)
    t = threading.Thread(target=worker.execute_download, args=(req.url, req.format_id, req.download_type, req.start_time, req.end_time, req.custom_commands, req.download_dir), daemon=True)
    t.start()
    return {"status": "started"}

@app.post("/api/update-motor")
def trigger_update_motor():
    def run_update():
        log_queue.put({"type": "log", "msg": "\n[SİSTEM] Pip üzerinden yt-dlp modülü güncelleniyor...\n"})
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            process = subprocess.Popen([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"], 
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                        startupinfo=startupinfo)
            for line in process.stdout:
                log_queue.put({"type": "log", "msg": f"{line.strip()}\n"})
            process.wait()
            log_queue.put({"type": "log", "msg": "\n[SİSTEM] Motor güncelleme işlemi tamamlandı.\n"})
        except Exception as e:
            log_queue.put({"type": "log", "msg": f"\n[HATA] {e}\n"})
        log_queue.put({"type": "done"})

    t = threading.Thread(target=run_update, daemon=True)
    t.start()
    return {"status": "updating"}

@app.get("/api/check-ffmpeg")
def check_ffmpeg():
    return {"installed": is_ffmpeg_available()}

@app.get("/api/ffmpeg-progress")
def get_ffmpeg_progress():
    global ffmpeg_download_progress
    return {"progress": ffmpeg_download_progress}

@app.post("/api/download-ffmpeg")
def trigger_download_ffmpeg():
    if sys.platform != 'win32':
         return {"status": "error", "msg": "Linux platformunda FFmpeg'i manuel kurmalısınız (sudo apt install ffmpeg)."}

    global ffmpeg_download_progress
    if ffmpeg_download_progress >= 0.0 and ffmpeg_download_progress < 1.0:
        return {"status": "already_downloading"}
        
    ffmpeg_download_progress = 0.0

    def fetch_worker():
        global ffmpeg_download_progress
        try:
            if sys.getwindowsversion().build <= 17763:
                url = "https://github.com/GyanD/codexffmpeg/releases/download/5.0.1/ffmpeg-5.0.1-essentials_build.zip"
            else:
                url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            download_zip_path = "ffmpeg_temp.zip"
            
            downloaded_size = 0
            with open(download_zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            ffmpeg_download_progress = downloaded_size / total_size
                            
            with zipfile.ZipFile(download_zip_path, 'r') as zip_ref:
                for file_info in zip_ref.namelist():
                    filename = os.path.basename(file_info)
                    if filename in ["ffmpeg.exe", "ffprobe.exe"]:
                        source = zip_ref.open(file_info)
                        with open(filename, "wb") as target:
                            target.write(source.read())
                            
            os.remove(download_zip_path) 
            ffmpeg_download_progress = 1.0 
        except Exception:
            ffmpeg_download_progress = -1.0 

    t = threading.Thread(target=fetch_worker, daemon=True)
    t.start()
    return {"status": "started"}

# WEBSOCKET: Canlı Terminal Portu
@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # Queue polling for Websocket streaming
    try:
        while True:
            try:
                msg = log_queue.get_nowait()
                await websocket.send_json(msg)
            except queue.Empty:
                await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        print("React Frontend Socket Disconnected")

# Statik Dosya (Frontend React Build) Sunumu
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), 'frontend', 'dist')
if not os.path.exists(FRONTEND_DIR):
    os.makedirs(FRONTEND_DIR, exist_ok=True)
    with open(os.path.join(FRONTEND_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write("<h1>UI Eksik / The Frontend UI is Missing. React icinde 'npm run build' calistirarak ciktilari <b>frontend/dist</b> klasorune tasiyin.</h1>")

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

import time
import subprocess

if __name__ == "__main__":
    def open_app_mode():
        import urllib.request
        import time
        
        url = "http://127.0.0.1:8000"
        server_ready = False
        
        # Dinamik Ping: Sadece API %100 ayağa kalkınca true olur
        for _ in range(30): # Maksimum 15 saniye dener
            try:
                res = urllib.request.urlopen(f"{url}/api/settings", timeout=1)
                if res.getcode() == 200:
                    server_ready = True
                    break
            except Exception:
                time.sleep(0.5)
                
        if not server_ready:
            return # Sunucu açılamadıysa tarayıcıyı hiç fırlatma
            
        def find_browser():
            if sys.platform == 'win32':
                import winreg
                # 1. Kayıt defteri kontrolü
                reg_paths = [
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"
                ]
                for p in reg_paths:
                    for base in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                        try:
                            with winreg.OpenKey(base, p) as key:
                                exe = winreg.QueryValue(key, None)
                                if exe and os.path.exists(exe):
                                    return exe
                        except:
                            pass
                
                # 2. Hardcoded fallback dizinleri
                common_paths = [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    os.environ.get("LocalAppData", "") + r"\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
                ]
                for cp in common_paths:
                    if cp and os.path.exists(cp):
                        return cp
            elif sys.platform.startswith('linux'):
                import shutil
                linux_browsers = ['google-chrome', 'chromium-browser', 'chromium', 'microsoft-edge-dev', 'microsoft-edge']
                for b in linux_browsers:
                    path = shutil.which(b)
                    if path:
                        return path
            return None

        exe_path = find_browser()
        try:
            import tempfile
            phantom_profile = os.path.join(tempfile.gettempdir(), "PhantomBrowserProfile")
            
            kwargs = {}
            if sys.platform == 'win32':
                kwargs['creationflags'] = 0x08000000
                
            if exe_path:
                process = subprocess.Popen([exe_path, f"--app={url}", f"--user-data-dir={phantom_profile}"], **kwargs)
            else:
                if sys.platform == 'win32':
                    process = subprocess.Popen(f'start /wait msedge --app={url}', shell=True, **kwargs)
                else:
                    process = subprocess.Popen(['xdg-open', url], **kwargs)
                
            process.wait()
            os._exit(0) # Artık sadece gerçek pencere kapandığında çalışacak
        except Exception:
            pass

    # Tarayıcıyı fırlatacak olan arka plan tetikleyicisi
    threading.Thread(target=open_app_mode, daemon=True).start()
    
    # Sunucuyu ana blokta sürekli hazır tut
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="critical", log_config=None)
