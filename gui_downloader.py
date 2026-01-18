#!/usr/bin/env python3
"""
ZIM Universal Media Downloader - GUI Version with Queue Management
Premium Black Edition
Author: Ziabul Islam
"""

import os
import sys
import json
import time
import re
import threading
import shutil
from datetime import datetime
from tkinter import filedialog, messagebox, simpledialog
from enum import Enum
import customtkinter as ctk
from yt_dlp import YoutubeDL
import urllib.request
import subprocess

APP_VERSION = "3.0"
UPDATE_URL = "https://raw.githubusercontent.com/ziabul2/GUI_Downloader/main/gui_downloader.py"
REPO_URL = "https://github.com/ziabul2/GUI_Downloader"

# ================================================================
# CONFIGURATION & THEME
# ================================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Premium Colors - "Bold & Black"
COLOR_BG = "#121212"           # Deep Black Background
COLOR_MENU_BAR = "#000000"     # Pure Black for Menu Bar
COLOR_MENU_HOVER = "#333333"   # Dark Gray Hover
COLOR_SURFACE = "#1E1E1E"      # Dark Gray Surface
COLOR_ACCENT = "#D4AF37"       # Gold Accent
COLOR_ACCENT_HOVER = "#B4941F" 
COLOR_TEXT_PRIMARY = "#FFFFFF"
COLOR_TEXT_SECONDARY = "#B0B0B0"
COLOR_SUCCESS = "#4CAF50"
COLOR_ERROR = "#F44336"
COLOR_WARNING = "#FF9800"

# ----------------------------------------------------------------
# DYNAMIC DIRECTORY SETUP
# ----------------------------------------------------------------

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    os.environ["PATH"] += os.pathsep + BASE_DIR
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Data Directory (Persistent Config)
DATA_DIR = os.path.join(BASE_DIR, "Downloads", "Data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
HISTORY_FILE = os.path.join(DATA_DIR, "download_history.json")
MONITORED_PLAYLISTS_FILE = os.path.join(DATA_DIR, "monitored_playlists.json")

def load_json_file(filepath, default_value):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default_value
    return default_value

def save_json_file(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except:
        pass

# Load Config
config = load_json_file(CONFIG_FILE, {"download_path": os.path.join(BASE_DIR, "Downloads")})
CURRENT_DOWNLOAD_DIR = config.get("download_path", os.path.join(BASE_DIR, "Downloads"))

# Paths Dictionary (Dynamic)
PATHS = {}

def setup_directories(base_path):
    """Initialize or updating directory paths"""
    global PATHS, CURRENT_DOWNLOAD_DIR
    
    CURRENT_DOWNLOAD_DIR = base_path
    
    PATHS['base'] = base_path
    PATHS['youtube_video'] = os.path.join(base_path, "YouTube", "Videos")
    PATHS['youtube_audio'] = os.path.join(base_path, "YouTube", "Audio")
    PATHS['facebook_video'] = os.path.join(base_path, "Facebook", "Videos")
    PATHS['facebook_audio'] = os.path.join(base_path, "Facebook", "Audio")
    PATHS['tiktok_video'] = os.path.join(base_path, "TikTok", "Videos")
    PATHS['tiktok_audio'] = os.path.join(base_path, "TikTok", "Audio")
    PATHS['other_video'] = os.path.join(base_path, "Other", "Videos")
    PATHS['other_audio'] = os.path.join(base_path, "Other", "Audio")
    PATHS['batch'] = os.path.join(base_path, "Batch")
    PATHS['metadata'] = os.path.join(base_path, "Metadata")
    
    # Create them
    for key, path in PATHS.items():
        if key != 'base':
            os.makedirs(path, exist_ok=True)

# Initial Setup
setup_directories(CURRENT_DOWNLOAD_DIR)

MAX_CONCURRENT_DOWNLOADS = 1

# ================================================================
# ENUMS & UTILS
# ================================================================

class DownloadStatus(Enum):
    QUEUED = "queued"
    PENDING = "pending" # Waiting for user to start
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

def detect_platform(url):
    url_lower = url.lower()
    if any(domain in url_lower for domain in ['youtube.com', 'youtu.be', 'm.youtube.com']):
        return 'youtube'
    elif any(domain in url_lower for domain in ['facebook.com', 'fb.com', 'fb.watch']):
        return 'facebook'
    elif 'tiktok.com' in url_lower:
        return 'tiktok'
    else:
        return 'other'

def get_output_dir(platform, media_type):
    # Use PATHS dict dynamically
    key_map = {
        'youtube': {'video': 'youtube_video', 'audio': 'youtube_audio'},
        'facebook': {'video': 'facebook_video', 'audio': 'facebook_audio'},
        'tiktok': {'video': 'tiktok_video', 'audio': 'tiktok_audio'},
        'other': {'video': 'other_video', 'audio': 'other_audio'}
    }
    key_set = key_map.get(platform, key_map['other'])
    path_key = key_set.get(media_type, 'other_video')
    return PATHS.get(path_key, PATHS['other_video'])

def clean_youtube_url(url):
    url = url.strip()
    try:
        if "list=" not in url:
             patterns = [
                r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})',
            ]
             for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    video_id = match.group(1)
                    return f"https://www.youtube.com/watch?v={video_id}"
    except: pass
    return url

def load_history():
    return load_json_file(HISTORY_FILE, {"downloads": [], "total": 0, "by_platform": {}})

def save_download(title, url, download_type, filepath, platform):
    history = load_history()
    entry = {
        "title": title[:60],
        "url": url,
        "type": download_type,
        "platform": platform,
        "filepath": filepath,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "size": os.path.getsize(filepath) if os.path.exists(filepath) else 0
    }
    history["downloads"].insert(0, entry)
    history["downloads"] = history["downloads"][:200]
    history["total"] = history.get("total", 0) + 1
    
    if "by_platform" not in history:
        history["by_platform"] = {}
    history["by_platform"][platform] = history["by_platform"].get(platform, 0) + 1
    save_json_file(HISTORY_FILE, history)

def save_metadata(info, filepath):
    try:
        video_name = os.path.splitext(os.path.basename(filepath))[0]
        metadata_file = os.path.join(PATHS['metadata'], f"{video_name}_metadata.txt") # Use dynamic path
        with open(metadata_file, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write(f"Title: {info.get('title', 'N/A')}\n")
            f.write(f"Uploader: {info.get('uploader', 'N/A')}\n")
            f.write(f"Upload Date: {info.get('upload_date', 'N/A')}\n")
            f.write(f"Original URL: {info.get('webpage_url', 'N/A')}\n")
            f.write(f"Description:\n{info.get('description', 'N/A')[:500]}...\n")
            f.write("="*70 + "\n")
    except:
        pass

# ================================================================
# PLAYLIST MONITORING
# ================================================================

def load_monitored_playlists():
    return load_json_file(MONITORED_PLAYLISTS_FILE, {})

def save_monitored_playlists(playlists):
    save_json_file(MONITORED_PLAYLISTS_FILE, playlists)

def add_playlist_to_monitor(url, playlist_title):
    playlists = load_monitored_playlists()
    playlist_id = url
    playlists[playlist_id] = {
        "title": playlist_title,
        "url": url,
        "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "downloaded_videos": [],
        "last_check": None
    }
    save_monitored_playlists(playlists)

# ================================================================
# DOWNLOAD MANAGER & ITEMS
# ================================================================

class DownloadQueueItem:
    def __init__(self, url, download_type, platform, title="Unknown", quality="best", format="mp4"):
        self.id = f"dl_{int(time.time()*1000)}_{id(self)}"
        self.url = url
        self.download_type = download_type
        self.platform = platform
        self.title = title
        self.quality = quality
        self.format = format
        self.status = DownloadStatus.QUEUED
        self.progress = 0.0
        self.speed = "N/A"
        self.eta = "N/A"
        self.downloaded = "0 B"
        self.total = "0 B"
        self.filepath = None
        self.error = None

class DownloadManager:
    def __init__(self, max_concurrent=MAX_CONCURRENT_DOWNLOADS):
        self.queue = []
        self.active_downloads = {}
        self.completed_downloads = []
        self.max_concurrent = max_concurrent
        self.max_concurrent = max_concurrent
        self.lock = threading.Lock()
        self.running = True
        self.callback = None
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()
        
    def set_callback(self, callback):
        self.callback = callback
        
    def add_to_queue(self, item):
        with self.lock:
            self.queue.append(item)
        return item.id
    
    def remove_from_queue(self, item_id):
        with self.lock:
            # Check in queue
            self.queue = [item for item in self.queue if item.id != item_id]
            # Check in active
            if item_id in self.active_downloads:
                self.active_downloads[item_id].status = DownloadStatus.CANCELLED
            # Check in completed? No need.
            
    def pause_download(self, item_id):
        with self.lock:
             if item_id in self.active_downloads:
                 self.active_downloads[item_id].status = DownloadStatus.PAUSED
                 
    def resume_download(self, item_id):
        with self.lock:
             if item_id in self.active_downloads:
                 self.active_downloads[item_id].status = DownloadStatus.DOWNLOADING
                 
    def start_item(self, item_id):
        with self.lock:
            for item in self.queue:
                if item.id == item_id and item.status == DownloadStatus.PENDING:
                    item.status = DownloadStatus.QUEUED
                    break

    def get_queue_status(self):
        with self.lock:
            return {
                'queued': [item for item in self.queue if item.status in [DownloadStatus.QUEUED, DownloadStatus.PENDING]],
                'downloading': list(self.active_downloads.values()),
                'total_active': len(self.active_downloads)
            }
    
    def _process_queue(self):
        while self.running:
            try:
                with self.lock:
                    if len(self.active_downloads) < self.max_concurrent:
                        queued_items = [item for item in self.queue if item.status == DownloadStatus.QUEUED]
                        if queued_items:
                            item = queued_items[0]
                            item.status = DownloadStatus.DOWNLOADING
                            self.active_downloads[item.id] = item
                            if self.callback: self.callback("started", item)
                            threading.Thread(target=self._download_item, args=(item,), daemon=True).start()
                time.sleep(0.5)
            except Exception as e:
                print(f"Queue error: {e}")
    
    def _download_item(self, item):
        try:
            url_clean = item.url
            if item.platform == 'youtube' and 'youtube.com' in url_clean:
                url_clean = clean_youtube_url(url_clean)
            
            output_dir = get_output_dir(item.platform, item.download_type)
            ffmpeg_path = os.path.join(BASE_DIR)
            
            def progress_hook(d):
                # Check Pause/Cancel state
                if item.status == DownloadStatus.CANCELLED:
                    raise Exception("Cancelled")
                
                while item.status == DownloadStatus.PAUSED:
                    time.sleep(0.5)
                    if item.status == DownloadStatus.CANCELLED:
                        raise Exception("Cancelled")

                if d['status'] == 'downloading':
                    try:
                        if not item.title or item.title == "Unknown":
                             filename = d.get('filename', '')
                             if filename: item.title = os.path.splitext(os.path.basename(filename))[0]
                        downloaded = d.get('downloaded_bytes', 0)
                        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                        if total > 0: item.progress = downloaded / total
                        speed = d.get('speed', 0)
                        item.speed = f"{speed/1024/1024:.2f} MB/s" if speed else "0.0 MB/s"
                        eta = d.get('eta', 0)
                        item.eta = f"{eta//60:02d}:{eta%60:02d}" if eta else "--:--"
                        item.downloaded = f"{downloaded/1024/1024:.1f} MB" if downloaded > 1024*1024 else "0 MB"
                    except: pass
                elif d['status'] == 'finished':
                    item.progress = 1.0

            ydl_opts = {
                "outtmpl": f"{output_dir}/%(title)s.%(ext)s",
                "progress_hooks": [progress_hook],
                "quiet": False, 
                "no_warnings": False,
                "ffmpeg_location": ffmpeg_path,
                "nocheckcertificate": True,
                "ignoreerrors": True,
                "retries": 10,
                "fragment_retries": 10,
                "source_address": "0.0.0.0",
            }
            
            if item.download_type == "video":
                # Allow 3gp
                valid_formats = ['mp4', 'mkv', 'webm', '3gp']
                format_ext = item.format if item.format in valid_formats else 'mp4'
                
                if item.quality == "4k":
                    ydl_opts["format"] = f"bestvideo[height>=2160][ext={format_ext}]+bestaudio/best[height>=2160][ext={format_ext}]/best"
                elif item.quality == "1080p":
                    ydl_opts["format"] = f"bestvideo[height<=1080][ext={format_ext}]+bestaudio/best[height<=1080][ext={format_ext}]/best"
                elif item.quality == "720p":
                    ydl_opts["format"] = f"bestvideo[height<=720][ext={format_ext}]+bestaudio/best[height<=720][ext={format_ext}]/best"
                elif item.quality == "480p":
                     ydl_opts["format"] = f"bestvideo[height<=480][ext={format_ext}]+bestaudio/best[height<=480][ext={format_ext}]/best"
                elif item.quality == "240p":
                     ydl_opts["format"] = f"bestvideo[height<=240][ext={format_ext}]+bestaudio/best[height<=240][ext={format_ext}]/best"
                elif item.quality == "144p":
                     ydl_opts["format"] = f"bestvideo[height<=144][ext={format_ext}]+bestaudio/best[height<=144][ext={format_ext}]/best"
                else: 
                   ydl_opts["format"] = f"bestvideo[ext={format_ext}]+bestaudio/best[ext={format_ext}]/best"
                ydl_opts["merge_output_format"] = format_ext
            else:
                ydl_opts["format"] = "bestaudio/best"
                ydl_opts["postprocessors"] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': item.format if item.format in ['mp3', 'm4a', 'wav'] else 'mp3',
                    'preferredquality': '192',
                }]
            
            with YoutubeDL(ydl_opts) as ydl:
                # 1. Pre-check info and existence
                info = ydl.extract_info(url_clean, download=False)
                filename = ydl.prepare_filename(info)
                
                if os.path.exists(filename):
                    # Ask user on main thread? Tkinter messagebox works from threads on Windows usually, 
                    # but strictly should be main thread. Given simple needs, direct call often works.
                    if not messagebox.askyesno("File Exists", f"File already exists:\n\n{os.path.basename(filename)}\n\nDownload again (Overwrite)?"):
                        item.status = DownloadStatus.COMPLETED
                        item.progress = 1.0
                        item.downloaded = "Skipped"
                        item.title = info.get('title', item.title)
                        return

                result = ydl.extract_info(url_clean, download=True)
                if result:
                    item.title = result.get('title', 'Unknown')
                    item.filepath = ydl.prepare_filename(result)
                    save_metadata(result, item.filepath)
                    save_download(item.title, url_clean, item.download_type, item.filepath, item.platform)
                    item.status = DownloadStatus.COMPLETED
                    if self.callback: self.callback("finished", item)
                else:
                    item.status = DownloadStatus.FAILED
                    item.error = "No info"
            
        except Exception as e:
            if item.status != DownloadStatus.CANCELLED: # Don't overwrite cancelled status
                item.status = DownloadStatus.FAILED
                item.error = str(e)
        finally:
            with self.lock:
                if item.id in self.active_downloads: del self.active_downloads[item.id]
                if item.status != DownloadStatus.QUEUED: # If not re-queued
                     self.completed_downloads.append(item)
                self.queue = [i for i in self.queue if i.id != item.id]

class DownloadItemWidget(ctk.CTkFrame):
    def __init__(self, master, item, manager=None, **kwargs):
        super().__init__(master, fg_color=COLOR_SURFACE, border_color="#333", border_width=1, **kwargs)
        self.item = item
        self.manager = manager
        self.grid_columnconfigure(0, weight=1)
        
        # Header Row
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,5))
        
        platform_emoji = {'youtube': '📺', 'facebook': '👥', 'tiktok': '🎵', 'other': '🌐'}
        emoji = platform_emoji.get(item.platform, '🌐')
        
        self.title_lbl = ctk.CTkLabel(header, text=f"{emoji} {item.title[:50]}", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_TEXT_PRIMARY, anchor="w")
        self.title_lbl.pack(side="left", fill="x", expand=True)

        # Controls
        self.btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        self.btn_frame.pack(side="right")
        
        # Pause/Resume Button
        self.pause_btn = ctk.CTkButton(self.btn_frame, text="⏸", width=30, height=25, fg_color=COLOR_WARNING, text_color=COLOR_BG,
                                       command=self.toggle_pause)
        self.pause_btn.pack(side="left", padx=2)
        
        # Cancel Button
        ctk.CTkButton(self.btn_frame, text="✕", width=30, height=25, fg_color=COLOR_ERROR, 
                      command=lambda: manager.remove_from_queue(item.id)).pack(side="left", padx=2)

        # Progress Row
        self.progress_bar = ctk.CTkProgressBar(self, progress_color=COLOR_ACCENT, height=8)
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self.progress_bar.set(item.progress)
        
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0,10))
        
        status_colors = {
            DownloadStatus.QUEUED: COLOR_WARNING,
            DownloadStatus.DOWNLOADING: COLOR_ACCENT,
            DownloadStatus.COMPLETED: COLOR_SUCCESS,
            DownloadStatus.FAILED: COLOR_ERROR,
            DownloadStatus.CANCELLED: COLOR_TEXT_SECONDARY
        }
        self.status_lbl = ctk.CTkLabel(info_frame, text=item.status.value.upper(), font=ctk.CTkFont(size=11, weight="bold"), text_color=status_colors.get(item.status, COLOR_TEXT_PRIMARY))
        self.status_lbl.pack(side="left", padx=(0,10))
        
        type_str = f"{item.download_type.upper()} ({item.quality if item.download_type == 'video' else ''})"
        ctk.CTkLabel(info_frame, text=type_str, font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_SECONDARY).pack(side="left")
        
        self.stats_lbl = ctk.CTkLabel(info_frame, text="Waiting...", font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_SECONDARY)
        self.stats_lbl.pack(side="right")

    def toggle_pause(self):
        if self.item.status == DownloadStatus.DOWNLOADING:
            self.manager.pause_download(self.item.id)
        elif self.item.status == DownloadStatus.PAUSED:
            self.manager.resume_download(self.item.id)
        elif self.item.status == DownloadStatus.PENDING:
            self.manager.start_item(self.item.id)
        
    def update_display(self):
        # Update Controls Visibility
        if self.item.status == DownloadStatus.PENDING:
             self.pause_btn.configure(state="normal", text="▶") # Start button
        elif self.item.status in [DownloadStatus.DOWNLOADING, DownloadStatus.PAUSED]:
            self.pause_btn.configure(state="normal", text="▶" if self.item.status == DownloadStatus.PAUSED else "⏸")
        else:
            self.pause_btn.configure(state="disabled", text="⏸")

        current_title_display = self.title_lbl.cget("text")
        platform_emoji = {'youtube': '📺', 'facebook': '👥', 'tiktok': '🎵', 'other': '🌐'}
        emoji = platform_emoji.get(self.item.platform, '🌐')
        
        if self.item.title and self.item.title != "Unknown" and self.item.title not in current_title_display:
             self.title_lbl.configure(text=f"{emoji} {self.item.title[:60]}")

        self.progress_bar.set(self.item.progress)
        
        status_colors = {
            DownloadStatus.QUEUED: COLOR_WARNING,
            DownloadStatus.DOWNLOADING: COLOR_ACCENT,
            DownloadStatus.COMPLETED: COLOR_SUCCESS,
            DownloadStatus.FAILED: COLOR_ERROR,
            DownloadStatus.CANCELLED: COLOR_TEXT_SECONDARY
        }
        self.status_lbl.configure(text=self.item.status.value.upper(), text_color=status_colors.get(self.item.status, COLOR_TEXT_PRIMARY))
        
        # Progress Color (Yellow for Paused)
        # Progress Color
        if self.item.status == DownloadStatus.PAUSED:
            self.progress_bar.configure(progress_color=COLOR_WARNING)
        elif self.item.status == DownloadStatus.PENDING:
            self.progress_bar.configure(progress_color=COLOR_TEXT_SECONDARY)
        elif self.item.status == DownloadStatus.FAILED:
            self.progress_bar.configure(progress_color=COLOR_ERROR)
        else:
            self.progress_bar.configure(progress_color=COLOR_ACCENT)

        status_colors = {
            DownloadStatus.QUEUED: COLOR_WARNING,
            DownloadStatus.DOWNLOADING: COLOR_ACCENT,
            DownloadStatus.PAUSED: COLOR_WARNING,
            DownloadStatus.COMPLETED: COLOR_SUCCESS,
            DownloadStatus.FAILED: COLOR_ERROR,
            DownloadStatus.CANCELLED: COLOR_TEXT_SECONDARY
        }
        self.status_lbl.configure(text=self.item.status.value.upper(), text_color=status_colors.get(self.item.status, COLOR_TEXT_PRIMARY))
        
        if self.item.status == DownloadStatus.DOWNLOADING:
            self.stats_lbl.configure(text=f"{self.item.speed} | ETA: {self.item.eta} | {self.item.downloaded}")
        elif self.item.status == DownloadStatus.PAUSED:
            self.stats_lbl.configure(text=f"PAUSED | {self.item.downloaded}")
        elif self.item.status == DownloadStatus.PENDING:
            self.stats_lbl.configure(text="Click to Start")
        elif self.item.status == DownloadStatus.FAILED:
            self.stats_lbl.configure(text=f"Error: {str(self.item.error)[:20]}", text_color=COLOR_ERROR)
        elif self.item.status == DownloadStatus.COMPLETED:
            self.stats_lbl.configure(text=f"Done!", text_color=COLOR_SUCCESS)
        elif self.item.status == DownloadStatus.QUEUED:
             self.stats_lbl.configure(text="Queued")

# ================================================================
# NOTIFICATION SYSTEM
# ================================================================

class DesktopNotification(ctk.CTkToplevel):
    def __init__(self, title, message, on_click_text=None, on_click_command=None):
        super().__init__()
        
        try:
            # Style & Safety
            self.overrideredirect(True)
            self.attributes("-topmost", True)
            try: self.configure(fg_color=COLOR_MENU_BAR)
            except: pass
            
            # Position (Bottom Right)
            ws = self.winfo_screenwidth()
            hs = self.winfo_screenheight()
            w, h = 320, 80
            x = ws - w - 20
            y = hs - h - 60
            self.geometry(f"{w}x{h}+{x}+{y}")
            
            # Content
            ctk.CTkLabel(self, text="🔔", font=ctk.CTkFont(size=24)).pack(side="left", padx=15)
            
            info_frame = ctk.CTkFrame(self, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, pady=10)
            
            ctk.CTkLabel(info_frame, text=title, font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_ACCENT, anchor="w").pack(fill="x")
            ctk.CTkLabel(info_frame, text=message, font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(fill="x")
            
            if on_click_text and on_click_command:
                ctk.CTkButton(self, text=on_click_text, width=80, height=25, font=ctk.CTkFont(size=11), 
                              fg_color=COLOR_SURFACE, border_width=1, border_color=COLOR_TEXT_SECONDARY,
                              command=lambda: [on_click_command(), self.destroy()]).pack(side="right", padx=10)

            self.after(4000, self.fade_out)
            self.attributes("-alpha", 0)
            self.animate_in()
        except Exception as e:
            print(f"Notification Error: {e}")
            self.destroy()

    def animate_in(self):
        try:
            alpha = self.attributes("-alpha")
            if alpha < 1:
                self.attributes("-alpha", alpha + 0.1)
                self.after(20, self.animate_in)
        except: pass

    def fade_out(self):
        try:
            alpha = self.attributes("-alpha")
            if alpha > 0:
                self.attributes("-alpha", alpha - 0.1)
                self.after(20, self.fade_out)
            else:
                self.destroy()
        except: self.destroy()

# ================================================================
# MAIN APPLICATION
# ================================================================

class MediaDownloaderGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("ZIM Universal Downloader - Premium Edition")
        self.geometry("1100x750")
        self.configure(fg_color=COLOR_BG)
        
        self.download_manager = DownloadManager()
        self.download_widgets = {}
        self.active_notification = None # Track active notification
        
        # Menu State
        self.menu_close_job = None
        self.current_menu = None
        self.active_overlay = None
        
        # UI State
        self.download_type = ctk.StringVar(value="video")
        self.video_quality = ctk.StringVar(value="best")
        self.video_format = ctk.StringVar(value="mp4")
        
        self.setup_ui()
        self.update_loop()
        
        # Notification Events
        self.download_manager.set_callback(self.on_download_event)
        
    def on_download_event(self, event_type, item):
        # if event_type == "started":
        #    self.after(0, lambda: self.show_notification("Download Started", f"{item.title[:30]}...", sound=False))
        if event_type == "finished":
            self.after(0, lambda: self.show_notification("Download Finished!", f"{item.title[:30]}...", "Open File", lambda: os.system(f'explorer /select,"{item.filepath}"'), sound=False))

    def show_notification(self, title, message, btn_text=None, btn_cmd=None, sound=False):
        # Prevent overlapping by closing previous
        if self.active_notification:
            try: self.active_notification.destroy()
            except: pass
        
        try: 
            self.active_notification = DesktopNotification(title, message, btn_text, btn_cmd)
        except: pass

    def setup_ui(self):
        # 1. Custom Bold Black Menu Bar
        self.create_custom_menu_bar()
        
        # 2. Main Content Area
        self.main_content = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 2.1 Top Input Section
        self.create_input_section()
        
        # 2.2 Queue Section
        ctk.CTkLabel(self.main_content, text="ACTIVE DOWNLOADS", font=ctk.CTkFont(size=12, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", pady=(20,5))
        
        self.queue_frame = ctk.CTkScrollableFrame(self.main_content, fg_color="transparent")
        self.queue_frame.pack(fill="both", expand=True)

    def create_custom_menu_bar(self):
        # Full width custom menu bar - Black and Bold
        self.menu_bar = ctk.CTkFrame(self, height=50, fg_color=COLOR_MENU_BAR, corner_radius=0)
        self.menu_bar.pack(fill="x", side="top")
        
        # Logo / Title
        ctk.CTkLabel(self.menu_bar, text="ZIM DOWNLOADER", font=ctk.CTkFont(size=20, weight="bold"), text_color=COLOR_ACCENT).pack(side="left", padx=30)
        
        # Menu Buttons Container
        self.menu_buttons_frame = ctk.CTkFrame(self.menu_bar, fg_color="transparent")
        self.menu_buttons_frame.pack(side="left", padx=30)
        
        # Bold Big Buttons
        buttons = ["File", "Tools", "Settings", "Help"]
        for i, text in enumerate(buttons):
            btn = ctk.CTkButton(self.menu_buttons_frame, text=text, width=110, height=40, 
                                fg_color="transparent", hover_color=COLOR_MENU_HOVER, 
                                text_color=COLOR_TEXT_PRIMARY, corner_radius=5, 
                                font=ctk.CTkFont(size=16, weight="bold"))
            btn.pack(side="left", padx=5)
            btn.bind("<Enter>", lambda e, m=text: self.on_menu_hover(m, e))
            
        # Menu Overlay (For Dropdowns)
        self.menu_overlay = ctk.CTkFrame(self, fg_color=COLOR_MENU_BAR, corner_radius=5, border_width=1, border_color=COLOR_ACCENT)
        self.menu_overlay.lift()
        self.menu_overlay_visible = False
        
        self.menu_overlay.bind("<Enter>", self.on_menu_enter_overlay)
        self.menu_overlay.bind("<Leave>", self.on_menu_leave)

    def on_menu_hover(self, menu_name, event):
        self.cancel_close_timer()
        base_offset = 260
        button_width = 120
        idx = ["File", "Tools", "Settings", "Help"].index(menu_name)
        x_pos = base_offset + (idx * button_width)
        self.show_menu(menu_name, x_pos)

    def on_menu_leave(self, event=None):
        self.start_close_timer()

    def on_menu_enter_overlay(self, event=None):
        self.cancel_close_timer()
    
    def start_close_timer(self):
        if self.menu_close_job: self.after_cancel(self.menu_close_job)
        self.menu_close_job = self.after(300, self.hide_menu)

    def cancel_close_timer(self):
        if self.menu_close_job:
            self.after_cancel(self.menu_close_job)
            self.menu_close_job = None

    def show_menu(self, menu_name, x_pos):
        self.menu_overlay.configure(width=250, height=200)
        self.menu_overlay.place(x=x_pos, y=50)
        self.menu_overlay.tkraise()
        self.menu_overlay_visible = True
        self.current_menu = menu_name
        
        for widget in self.menu_overlay.winfo_children():
            widget.destroy()
        
        if menu_name == "File":
            self.add_menu_item("Import Batch File (.txt)", self.import_batch_file)
            self.add_menu_item("Open Download Folder", lambda: os.startfile(CURRENT_DOWNLOAD_DIR))
            self.add_menu_item("Exit", self.safe_destroy, color=COLOR_ERROR)
            
        elif menu_name == "Tools":
            self.add_menu_item("Monitor Playlists (New)", self.show_monitor_panel)
            self.add_menu_item("Download History", self.show_history_panel)
            self.add_menu_item("Check FFmpeg Status", self.check_ffmpeg_status)
            self.add_menu_item("Clear History", self.clear_history_data)
        
        elif menu_name == "Settings":
            self.add_menu_item("Application Settings", self.show_settings_panel)
            self.add_menu_item("Reset Theme", lambda: messagebox.showinfo("Info", "Theme reset applied!"))

        elif menu_name == "Help":
            ctk.CTkLabel(self.menu_overlay, text=f"ZIM Downloader v{APP_VERSION}", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_ACCENT).pack(pady=(15,5))
            self.add_menu_item("Check for Updates", self.check_for_updates)
            self.add_menu_item("About", lambda: messagebox.showinfo("About", f"ZIM Universal Media Downloader\nPremium Portable Edition\nVersion: {APP_VERSION}"))

    def safe_destroy(self):
        if self.menu_overlay_visible:
            self.menu_overlay.place_forget()
        self.destroy()

    def add_menu_item(self, text, command, color=None):
        def clicked():
            if command == self.safe_destroy:
                command()
            else:
                self.hide_menu()
                command()

        btn = ctk.CTkButton(self.menu_overlay, text=text, command=clicked,
                            width=230, height=35, fg_color="transparent", hover_color=COLOR_MENU_HOVER, 
                            text_color=color if color else COLOR_TEXT_PRIMARY, anchor="w", font=ctk.CTkFont(size=13))
        btn.pack(pady=1, padx=10)
        btn.bind("<Enter>", self.on_menu_enter_overlay)
        btn.bind("<Leave>", self.on_menu_leave)

    def hide_menu(self):
        try:
            if self.menu_overlay.winfo_exists():
                self.menu_overlay.place_forget()
                self.menu_overlay_visible = False
                self.current_menu = None
        except: pass

    # --- PANELS & ACTIONS ---
    
    def show_overlay_frame(self, title):
        if self.active_overlay:
            self.active_overlay.destroy()
            
        self.active_overlay = ctk.CTkFrame(self.main_content, fg_color=COLOR_BG)
        self.active_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        
        header = ctk.CTkFrame(self.active_overlay, fg_color=COLOR_SURFACE, height=50)
        header.pack(fill="x")
        ctk.CTkButton(header, text="⬅ Back", width=60, command=self.close_overlay, fg_color="transparent", border_width=1).pack(side="left", padx=10, pady=10)
        ctk.CTkLabel(header, text=title, font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=10)
        
        return self.active_overlay

    def close_overlay(self):
        if self.active_overlay:
            self.active_overlay.destroy()
            self.active_overlay = None

    def show_history_panel(self):
        self.hide_menu()
        overlay = self.show_overlay_frame("Download History")
        
        scroll = ctk.CTkScrollableFrame(overlay, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=20)
        
        history = load_history()
        if not history.get("downloads"):
            ctk.CTkLabel(scroll, text="No download history found.", text_color=COLOR_TEXT_SECONDARY).pack(pady=20)
            return

        for item in history.get("downloads", []):
            f = ctk.CTkFrame(scroll, fg_color=COLOR_SURFACE)
            f.pack(fill="x", pady=2)
            icon = "🎵" if item['type'] == 'audio' else "🎥"
            ctk.CTkLabel(f, text=f"{icon}  {item['title'][:50]}", anchor="w").pack(side="left", padx=10, fill="x", expand=True)
            ctk.CTkButton(f, text="Open", width=50, command=lambda p=item['filepath']: self.open_file_folder(p)).pack(side="right", padx=5, pady=5)

    def show_monitor_panel(self):
        self.hide_menu()
        overlay = self.show_overlay_frame("Monitor Playlists")
        
        # Tools Bar
        tools = ctk.CTkFrame(overlay, fg_color="transparent")
        tools.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(tools, text="+ Add Playlist", width=120, command=self.add_monitor_dialog, fg_color=COLOR_ACCENT, text_color=COLOR_BG).pack(side="left")
        ctk.CTkButton(tools, text="🔄 Check Now", width=100, command=self.run_monitor_check, fg_color=COLOR_SURFACE, border_width=1, border_color=COLOR_ACCENT, text_color=COLOR_ACCENT).pack(side="left", padx=10)
        
        # List
        self.monitor_scroll = ctk.CTkScrollableFrame(overlay, fg_color="transparent")
        self.monitor_scroll.pack(fill="both", expand=True, padx=20, pady=10)
        self.refresh_monitor_list()

    def refresh_monitor_list(self):
        for w in self.monitor_scroll.winfo_children(): w.destroy()
        
        playlists = load_monitored_playlists()
        if not playlists:
            ctk.CTkLabel(self.monitor_scroll, text="No playlists monitored yet.", text_color=COLOR_TEXT_SECONDARY).pack(pady=20)
            return

        for pid, data in playlists.items():
            f = ctk.CTkFrame(self.monitor_scroll, fg_color=COLOR_SURFACE)
            f.pack(fill="x", pady=5)
            
            ctk.CTkLabel(f, text=f"📺 {data['title']}", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(5,0))
            ctk.CTkLabel(f, text=f"URL: {data['url'][:50]}...", text_color=COLOR_TEXT_SECONDARY, font=ctk.CTkFont(size=11)).pack(anchor="w", padx=10)
            ctk.CTkLabel(f, text=f"Downloaded: {len(data['downloaded_videos'])} videos | Last Check: {data['last_check'] or 'Never'}", text_color=COLOR_TEXT_SECONDARY, font=ctk.CTkFont(size=11)).pack(anchor="w", padx=10, pady=(0,5))
            
            ctk.CTkButton(f, text="Remove", width=60, height=25, fg_color=COLOR_ERROR, command=lambda p=pid: self.remove_monitor(p)).pack(anchor="e", padx=10, pady=(0,10))

    def add_monitor_dialog(self):
        url = simpledialog.askstring("Add Playlist", "Enter YouTube Playlist URL:")
        if url and "list=" in url:
            title = simpledialog.askstring("Playlist Title", "Enter a name for this playlist:")
            if title:
                add_playlist_to_monitor(url, title)
                self.refresh_monitor_list()
        elif url:
            messagebox.showerror("Error", "Invalid playlist URL.")

    def remove_monitor(self, pid):
        if messagebox.askyesno("Confirm", "Remove this playlist from monitoring?"):
            playlists = load_monitored_playlists()
            if pid in playlists:
                del playlists[pid]
                save_monitored_playlists(playlists)
                self.refresh_monitor_list()

    def run_monitor_check(self):
        messagebox.showinfo("Monitor", "Checking playlists in background... New videos will be added to queue.")
        threading.Thread(target=self.bg_monitor_check, daemon=True).start()

    def bg_monitor_check(self):
        playlists = load_monitored_playlists()
        for pid, data in playlists.items():
            try:
                ydl_opts = {"quiet": True, "extract_flat": True, "safe_to_auto_run": True}
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(data['url'], download=False)
                    for entry in info.get('entries', []):
                        if entry['id'] not in data['downloaded_videos']:
                            # Auto add to queue
                            vid_url = f"https://www.youtube.com/watch?v={entry['id']}"
                            item = DownloadQueueItem(vid_url, "video", "youtube", entry.get('title', 'Monitor Auto'), "best", "mp4")
                            self.download_manager.add_to_queue(item)
                            data['downloaded_videos'].append(entry['id'])
                    data['last_check'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            except: pass
        save_monitored_playlists(playlists)

    def show_settings_panel(self):
        self.hide_menu()
        overlay = self.show_overlay_frame("Application Settings")
        
        content = ctk.CTkFrame(overlay, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=40, pady=20)
        
        # General
        ctk.CTkLabel(content, text="General Preferences", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_ACCENT).pack(anchor="w", pady=(0, 10))
        ctk.CTkSwitch(content, text="Dark Mode (Always On)", onvalue="on", offvalue="off").pack(anchor="w", pady=5)
        ctk.CTkSwitch(content, text="Auto-Move to Subfolders", onvalue="on", offvalue="off").pack(anchor="w", pady=5)
        
        # Path
        ctk.CTkLabel(content, text="Path Configuration", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_ACCENT).pack(anchor="w", pady=(20, 10))
        
        path_frame = ctk.CTkFrame(content, fg_color="transparent")
        path_frame.pack(fill="x", pady=5)
        
        self.path_label = ctk.CTkLabel(path_frame, text=f"Download Path: {CURRENT_DOWNLOAD_DIR}", text_color=COLOR_TEXT_SECONDARY, anchor="w")
        self.path_label.pack(side="left", fill="x", expand=True)
        
        ctk.CTkButton(path_frame, text="Change Folder", width=100, height=30, command=self.change_download_path).pack(side="right")

    def change_download_path(self):
        new_path = filedialog.askdirectory(initialdir=CURRENT_DOWNLOAD_DIR)
        if new_path:
            # Update Global Config
            config["download_path"] = new_path
            save_json_file(CONFIG_FILE, config)
            
            # Update Runtime Directories
            setup_directories(new_path)
            
            # Update UI
            self.path_label.configure(text=f"Download Path: {new_path}")
            messagebox.showinfo("Success", "Download path updated!\nNew downloads will be saved to this folder.")

    def check_ffmpeg_status(self):
        ffmpeg_exists = os.path.exists(os.path.join(BASE_DIR, "ffmpeg.exe"))
        status = "INSTALLED ✅" if ffmpeg_exists else "MISSING ❌"
        messagebox.showinfo("FFmpeg Status", f"FFmpeg Binary Status:\n\n{status}\n\nPath: {BASE_DIR}")

    def clear_history_data(self):
        if messagebox.askyesno("Clear History", "Are you sure you want to delete all download history?"):
            try:
                if os.path.exists(HISTORY_FILE):
                    os.remove(HISTORY_FILE)
                messagebox.showinfo("Success", "History cleared.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not clear history: {e}")

    def check_for_updates(self):
        self.hide_menu()
        # Run in thread to prevent freezing UI
        threading.Thread(target=self._run_update_check, daemon=True).start()

    def _run_update_check(self):
        try:
            # 1. Fetch Remote Code
            print(f"Connecting to: {UPDATE_URL}")
            try:
                import ssl
                import urllib.error # Import for error handling
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                
                req = urllib.request.Request(
                    UPDATE_URL, 
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                )
                
                with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                    content = response.read().decode('utf-8')
            
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    self.after(0, lambda: messagebox.showerror("File Not Found (404)", "The file 'gui_downloader.py' is NOT on GitHub yet.\n\nPlease push your file to GitHub first:\n1. git add gui_downloader.py\n2. git commit -m 'upload'\n3. git push"))
                else:
                    self.after(0, lambda: messagebox.showerror("Connection Error", f"Server Error: {e.code} {e.reason}"))
                return
                    
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Connection Error", f"Could not connect to GitHub.\n\nDetails: {str(e)}\n\nCheck your internet connection."))
                return

            # 2. Parse Version
            import re
            match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', content)
            
            if match:
                remote_version = match.group(1)
                print(f"Remote Version: {remote_version} | Local: {APP_VERSION}")
                
                # Compare Versions
                if remote_version != APP_VERSION:
                    self.after(0, lambda: self.confirm_update(remote_version, content))
                else:
                    self.after(0, lambda: messagebox.showinfo("Up to Date", f"You are using the latest version ({APP_VERSION})."))
            else:
                 # This usually happens if the file on GitHub is the OLD version that doesn't have APP_VERSION line yet
                 self.after(0, lambda: messagebox.showwarning("Version Error", "Could not find version info in the remote file.\n\nDid you push the new code to GitHub yet?"))
                 
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", f"Update check failed: {e}"))

    def confirm_update(self, remote_version, content):
        if messagebox.askyesno("Update Available", f"New version {remote_version} is available.\nCurrent version: {APP_VERSION}\n\nUpdate now?"):
            self.perform_update(content)

    def perform_update(self, new_content):
        try:
             # Determine current file path
            if getattr(sys, 'frozen', False):
                 if messagebox.askyesno("Update", "Auto-update is not supported for the frozen executable version directly.\n\nOpen download page?"):
                     os.system(f"start {REPO_URL}")
                 return

            current_file = os.path.abspath(__file__)
            new_file = current_file + ".new"

            # Write new content
            with open(new_file, 'w', encoding='utf-8') as f:
                f.write(new_content)

            # Create batch script for clean swap and restart
            bat_script = f"""
@echo off
title Updating ZIM Downloader...
timeout /t 2 /nobreak >nul
del "{current_file}"
move "{new_file}" "{current_file}"
start "" "{sys.executable}" "{current_file}"
del "%~f0"
"""
            bat_path = os.path.join(os.path.dirname(current_file), "update_script.bat")
            with open(bat_path, 'w') as f:
                f.write(bat_script)

            messagebox.showinfo("Restarting", "Application will restart to apply updates.")
            
            # Execute batch and exit
            subprocess.Popen([bat_path], shell=True)
            self.destroy()
            sys.exit()

        except Exception as e:
            messagebox.showerror("Error", f"Update failed: {e}")

    # ... [Rest of functionality remains same: import_batch, process items, etc.] ...
    def import_batch_file(self):
        self.hide_menu()
        file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if file_path: threading.Thread(target=self.process_batch_file, args=(file_path,), daemon=True).start()

    def process_batch_file(self, file_path):
        try:
            with open(file_path, 'r') as f:
                urls = f.readlines()
                count = 0
                for url in urls:
                    if url.strip():
                        self.process_url(url.strip())
                        count += 1
                self.after(0, lambda: messagebox.showinfo("Batch Import", f"Added {count} URLs to queue."))
        except Exception as e:
            print(f"Batch error: {e}")

    def create_input_section(self):
        input_frame = ctk.CTkFrame(self.main_content, fg_color=COLOR_SURFACE, corner_radius=10)
        input_frame.pack(fill="x")
        
        url_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        url_row.pack(fill="x", padx=15, pady=15)
        
        self.url_entry = ctk.CTkEntry(url_row, placeholder_text="Paste Video or Playlist URL here...", height=45, font=ctk.CTkFont(size=14), border_color=COLOR_ACCENT)
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(url_row, text="PASTE", width=80, height=45, fg_color=COLOR_SURFACE, border_width=1, border_color=COLOR_ACCENT, text_color=COLOR_ACCENT, hover_color="#333", command=self.paste_url).pack(side="left")
        
        opt_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        opt_row.pack(fill="x", padx=15, pady=(0, 15))
        
        ctk.CTkLabel(opt_row, text="Type:", text_color=COLOR_TEXT_SECONDARY).pack(side="left", padx=(0,5))
        ctk.CTkOptionMenu(opt_row, variable=self.download_type, values=["video", "audio"], width=100, fg_color="#333", button_color="#444", command=self.update_options).pack(side="left", padx=(0, 20))
        
        self.quality_lbl = ctk.CTkLabel(opt_row, text="Quality:", text_color=COLOR_TEXT_SECONDARY)
        self.quality_lbl.pack(side="left", padx=(0,5))
        self.quality_menu = ctk.CTkOptionMenu(opt_row, variable=self.video_quality, values=["best", "4k", "1080p", "720p", "480p", "240p", "144p"], width=100, fg_color="#333", button_color="#444")
        self.quality_menu.pack(side="left", padx=(0, 20))
        
        self.format_lbl = ctk.CTkLabel(opt_row, text="Format:", text_color=COLOR_TEXT_SECONDARY)
        self.format_lbl.pack(side="left", padx=(0,5))
        self.format_menu = ctk.CTkOptionMenu(opt_row, variable=self.video_format, values=["mp4", "mkv", "webm", "3gp"], width=100, fg_color="#333", button_color="#444")
        self.format_menu.pack(side="left", padx=(0, 20))
        
        ctk.CTkButton(opt_row, text="ADD TO QUEUE", width=150, height=35, fg_color=COLOR_ACCENT, text_color=COLOR_BG, hover_color=COLOR_ACCENT_HOVER, font=ctk.CTkFont(weight="bold"), command=self.add_download).pack(side="right")

    def update_options(self, choice):
        if choice == "audio":
            self.quality_lbl.pack_forget()
            self.quality_menu.pack_forget()
            self.format_menu.configure(values=["mp3", "m4a", "wav"])
            self.video_format.set("mp3")
        else:
            self.quality_lbl.pack(side="left", padx=(0,5), before=self.format_lbl)
            self.quality_menu.pack(side="left", padx=(0,20), before=self.format_lbl)
            self.format_menu.configure(values=["mp4", "mkv", "webm", "3gp"])
            self.video_format.set("mp4")

    def paste_url(self):
        try:
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, self.clipboard_get())
        except: pass

    def open_file_folder(self, filepath):
        try:
            if os.path.exists(filepath): os.system(f'explorer /select,"{filepath}"')
        except: pass

    def add_download(self):
        url = self.url_entry.get().strip()
        if not url: return
        self.process_url(url)
        self.url_entry.delete(0, "end")

    def process_url(self, url):
        # Check if playlist
        if "list=" in url and self.download_type.get() == "video":
             if messagebox.askyesno("Playlist Detect", "This looks like a playlist.\n\nDownload all videos one by one from the queue?\n(This will expand the playlist into individual items)"):
                 threading.Thread(target=self.process_playlist, args=(url,), daemon=True).start()
                 return
        
        # Single Video
        item = DownloadQueueItem(url, self.download_type.get(), detect_platform(url), "Unknown", self.video_quality.get(), self.video_format.get())
        self.download_manager.add_to_queue(item)

    def process_playlist(self, url):
        try:
             print("Expanding playlist...")
             
             ydl_opts = {
                 'extract_flat': 'in_playlist', # Critical for speed/no-JS-warnings
                 'skip_download': True,
                 'ignoreerrors': True,
                 'quiet': True,
                 'no_warnings': True,
                 'safe_to_auto_run': True
             }
             
             with YoutubeDL(ydl_opts) as ydl:
                 info = ydl.extract_info(url, download=False)
                 if 'entries' in info:
                     entries = list(info['entries'])
                     print(f"Found {len(entries)} videos")
                     
                     for i, entry in enumerate(entries, 1):
                         if entry:
                             video_id = entry.get('id')
                             if not video_id: continue
                             
                             title = entry.get('title', f"Video {i}")
                             video_url = entry.get('url') or f"https://www.youtube.com/watch?v={video_id}"
                             
                             item = DownloadQueueItem(video_url, "video", "youtube", title, self.video_quality.get(), self.video_format.get())
                             item.status = DownloadStatus.PENDING # Start as Pending
                             self.download_manager.add_to_queue(item)
                             time.sleep(0.05) # Small delay to keep order
                             
             messagebox.showinfo("Playlist Added", f"Added {len(entries)} videos to the queue!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to expand playlist: {e}")

    def update_loop(self):
        status = self.download_manager.get_queue_status()
        active_items = status['downloading'] + status['queued']
        current_ids = [item.id for item in active_items]
        to_remove = [iid for iid in self.download_widgets if iid not in current_ids]
        for iid in to_remove:
            self.download_widgets[iid].destroy()
            del self.download_widgets[iid]
        # Add new
        for item in active_items:
            if item.id not in self.download_widgets:
                w = DownloadItemWidget(self.queue_frame, item, manager=self.download_manager)
                w.pack(fill="x", pady=5)
                self.download_widgets[item.id] = w
            else:
                self.download_widgets[item.id].update_display()
            
        self.after(500, self.update_loop)

if __name__ == "__main__":
    try:
        app = MediaDownloaderGUI()
        app.mainloop()
    except KeyboardInterrupt:
        print("\nUser Interrupted (Ctrl+C). Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Critical Error: {e}")
