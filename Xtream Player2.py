#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Xtream Codes IPTV - GUI "Smarters-like" complètement améliorée
Version avec métadonnées étendues, recherche avancée et informations utilisateur
"""

import os
import sys
import json
import logging
import threading
import time
import subprocess
import re
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import requests
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QTimer, QThread, pyqtSignal
import base64


# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.expanduser("~"), f".xtream_player.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("XtreamPlayer")

# --- VLC intégré (python-vlc) ---
_EMBEDDED_VLC = True
try:
    import vlc
except Exception as e:
    logger.warning(f"VLC non disponible: {e}")
    _EMBEDDED_VLC = False

# Regex pour le nettoyage des titres
REGEX_ARABE = re.compile(r'[\u0600-\u06FF]')
REGEX_ANNEE_SIMPLE = re.compile(r'^\d{4}$')
REGEX_ANNEE_RANGE = re.compile(r'^\d{4}(-\d{4})?$')
REGEX_YEAR_IN_PAREN = re.compile(r'\s*\(\d{4}\)$')
REGEX_EPISODE = re.compile(r"S\d{1,2}[\sE\-\.]?[eE]?[pP]?\d{1,3}", re.IGNORECASE)

APP_NAME = "XtreamPlusVOD"
DATA_DIR = os.path.join(os.path.expanduser("~"), f".{APP_NAME.lower()}")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
DOWNLOAD_DIR = os.path.join(DATA_DIR, "downloads")
SUBTITLES_DIR = os.path.join(DATA_DIR, "subtitles")
PROFILES_PATH = os.path.join(DATA_DIR, "profiles.json")
FAVS_PATH = os.path.join(DATA_DIR, "favorites.json")
STATE_PATH = os.path.join(DATA_DIR, "state.json")
HISTORY_PATH = os.path.join(DATA_DIR, "history.json")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
DOWNLOAD_QUEUE_PATH = os.path.join(DATA_DIR, "download_queue.json")

# ------------------- Modèles améliorés -------------------
@dataclass
class Profile:
    name: str
    server: str
    user: str
    password: str
    live_container: str = "m3u8"
    movie_container: str = "mp4"
    series_container: str = "mp4"
    vlc_path: str = ""
    xmltv_url: str = ""
    max_bitrate: str = "0"
    timeout: int = 30

@dataclass
class UserInfo:
    username: str
    status: str
    exp_date: str
    active_cons: int
    max_connections: int
    created_at: str = ""
    is_trial: bool = False
    allowed_output_formats: List[str] = None

@dataclass
class ServerInfo:
    url: str
    port: str
    server_protocol: str
    timezone: str
    time_now: str
    version: str = ""

@dataclass
class Category:
    id: str
    name: str

@dataclass
class Channel:
    id: str
    name: str
    logo: Optional[str] = None
    group: str = ""

@dataclass
class ExtendedVodItem:
    id: str
    name: str
    logo: Optional[str] = None
    container: Optional[str] = None
    plot: str = ""
    releasedate: str = ""
    duration: str = ""
    cast: List[str] = None
    director: str = ""
    genre: str = ""
    rating: float = 0.0
    imdb_id: str = ""
    youtube_trailer: str = ""
    backdrop_path: List[str] = None
    added: str = ""
    category_id: Optional[str] = None  # 👈 AJOUT


@dataclass
class ExtendedSeriesItem:
    series_id: str
    name: str
    cover: Optional[str] = None
    plot: str = ""
    releaseDate: str = ""
    cast: List[str] = None
    genre: str = ""
    rating: float = 0.0
    imdb_id: str = ""
    youtube_trailer: str = ""
    backdrop_path: List[str] = None
    last_modified: str = ""
    category_id: Optional[str] = None  # 👈 AJOUT


@dataclass
class Episode:
    id: str
    season: int
    epnum: int
    title: str
    container: str = "mp4"
    plot: str = ""
    duration: str = ""

@dataclass
class HistoryItem:
    type: str
    id: str
    title: str
    timestamp: str
    position: int = 0
    duration: int = 0

@dataclass
class DownloadItem:
    id: str
    type: str
    title: str
    url: str
    output_path: str
    status: str = "pending"
    progress: float = 0.0
    file_size: int = 0
    downloaded: int = 0
    subtitle_url: str = ""

@dataclass
class SubtitleTrack:
    language: str
    url: str
    format: str = "srt"

def b64decode_safe(text: str) -> str:
    """Décodage Base64 sécurisé (évite erreurs si texte non encodé)."""
    if not text:
        return ""
    try:
        # Nettoyer et décoder en UTF-8
        return base64.b64decode(text).decode("utf-8", errors="ignore")
    except Exception:
        # Retourne tel quel si ce n’est pas du base64 valide
        return text




# ------------------- Utilitaires fichiers -------------------
def save_json(path, obj):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Erreur écriture {path}: {e}")
        return False

def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erreur lecture {path}: {e}")
        return default

# ------------------- Gestion des données -------------------
class DataManager:
    @staticmethod
    def ensure_data_dir():
        for path in [DATA_DIR, CACHE_DIR, DOWNLOAD_DIR, SUBTITLES_DIR]:
            os.makedirs(path, exist_ok=True)
        
        defaults = {
            PROFILES_PATH: {"profiles": []},
            FAVS_PATH: {"live": {}, "vod": {}, "series": {}},
            STATE_PATH: {},
            HISTORY_PATH: {"items": []},
            SETTINGS_PATH: {
                "theme": "dark", 
                "cache_enabled": True,
                "default_player": "embedded",
                "download_path": DOWNLOAD_DIR,
                "subtitle_language": "fr"
            },
            DOWNLOAD_QUEUE_PATH: {"items": []}
        }
        
        for path, default in defaults.items():
            if not os.path.exists(path):
                save_json(path, default)

DataManager.ensure_data_dir()

def load_profiles() -> Dict[str, Profile]:
    raw = load_json(PROFILES_PATH, {"profiles": []})
    out = {}
    for p in raw.get("profiles", []):
        out[p["name"]] = Profile(**p)
    return out

def save_profiles(profiles: Dict[str, Profile]):
    payload = {"profiles": [asdict(p) for p in profiles.values()]}
    save_json(PROFILES_PATH, payload)

def load_favorites() -> Dict[str, Dict[str, List[str]]]:
    return load_json(FAVS_PATH, {"live": {}, "vod": {}, "series": {}})

def save_favorites(data: Dict[str, Dict[str, List[str]]]):
    save_json(FAVS_PATH, data)

def load_settings() -> Dict[str, Any]:
    return load_json(SETTINGS_PATH, {})

def save_settings(settings: Dict[str, Any]):
    save_json(SETTINGS_PATH, settings)

def load_download_queue() -> List[DownloadItem]:
    data = load_json(DOWNLOAD_QUEUE_PATH, {"items": []})
    return [DownloadItem(**item) for item in data.get("items", [])]

def save_download_queue(queue: List[DownloadItem]):
    save_json(DOWNLOAD_QUEUE_PATH, {"items": [asdict(item) for item in queue]})

# ------------------- Fonctions de formatage -------------------
def contient_arabe(texte: str) -> bool:
    return bool(REGEX_ARABE.search(texte)) if texte else False

def nettoie_titre(titre_brut: str) -> Optional[str]:
    if not titre_brut:
        return titre_brut

    titre_brut = re.sub(r'\|\|+', '|', titre_brut)
    pattern_combine = re.compile(r'(^\|+\s*[^\|]+\s*\|+)|(\.mkv$)', re.IGNORECASE)
    titre_brut = pattern_combine.sub('', titre_brut)
    titre_brut = titre_brut.strip('|').strip()

    champs = [champ.strip() for champ in titre_brut.split('|') if champ.strip()]
    if not champs:
        return None

    champs = [champ for champ in champs if champ.lower() != "multi"]

    if len(champs) > 1 and REGEX_ANNEE_SIMPLE.fullmatch(champs[0]):
        annee = champs[0]
        champs = champs[1:]
        champs.append(annee)

    if len(champs) > 1 and not contient_arabe(champs[0]):
        champs = champs[1:]

    titres_possibles = []
    date_year = None

    for champ in champs:
        if REGEX_ANNEE_SIMPLE.fullmatch(champ):
            date_year = champ
            continue
        titres_possibles.append(champ)

    if not titres_possibles:
        return None

    titres_arabes = [t for t in titres_possibles if contient_arabe(t)]
    titre_selectionne = titres_arabes[0] if titres_arabes else titres_possibles[0]

    titre_selectionne = REGEX_YEAR_IN_PAREN.sub('', titre_selectionne).strip()

    return f"{titre_selectionne} ({date_year})" if date_year else titre_selectionne

def format_episode_title(series_title: str, episode_title: str) -> str:
    episode_title = episode_title.strip()
    if REGEX_EPISODE.match(episode_title):
        return f"{series_title} {episode_title}"
    return episode_title

# ------------------- API Xtream améliorée -------------------
def normalize_server(server: str) -> str:
    if not server.startswith("http"):
        server = "http://" + server
    return server.rstrip("/")

def player_api(server: str, username: str, password: str, **params):
    base = f"{server}/player_api.php"
    query = {"username": username, "password": password}
    query.update(params)
    try:
        r = requests.get(base, params=query, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"API error: {e}")
        raise

# LIVE
def api_info(p: Profile):
    return player_api(p.server, p.user, p.password, action="get_server_info")

def live_categories(p: Profile):
    return player_api(p.server, p.user, p.password, action="get_live_categories") or []

def live_streams(p: Profile, cat_id: str):
    return player_api(p.server, p.user, p.password, action="get_live_streams", category_id=cat_id) or []

def epg_short(p: Profile, stream_id: str):
    return player_api(p.server, p.user, p.password, action="get_short_epg", stream_id=stream_id) or {}

def live_url(p: Profile, sid: str):
    container = p.live_container if p.live_container in ("m3u8", "ts") else "m3u8"
    return f"{p.server}/live/{p.user}/{p.password}/{sid}.{container}"

# VOD
def vod_categories(p: Profile):
    return player_api(p.server, p.user, p.password, action="get_vod_categories") or []

def vod_streams(p: Profile, cat_id: str):
    return player_api(p.server, p.user, p.password, action="get_vod_streams", category_id=cat_id) or []

def vod_info(p: Profile, vod_id: str):
    return player_api(p.server, p.user, p.password, action="get_vod_info", vod_id=vod_id) or {}

def vod_url(p: Profile, vod_id: str, container: Optional[str]):
    ext = container if container else p.movie_container
    if ext not in ("mp4", "mkv", "ts", "m3u8"):
        ext = "mp4"
    return f"{p.server}/movie/{p.user}/{p.password}/{vod_id}.{ext}"

def vod_subtitles(p: Profile, vod_id: str) -> List[SubtitleTrack]:
    try:
        info = vod_info(p, vod_id)
        subtitles = info.get("movie_data", {}).get("subtitles", [])
        tracks = []
        for sub in subtitles:
            if sub.get("url"):
                tracks.append(SubtitleTrack(
                    language=sub.get("language", "unknown"),
                    url=sub.get("url"),
                    format=sub.get("format", "srt")
                ))
        return tracks
    except Exception as e:
        logger.error(f"Erreur sous-titres VOD: {e}")
        return []

# SERIES
def series_categories(p: Profile):
    return player_api(p.server, p.user, p.password, action="get_series_categories") or []

def series_list(p: Profile, cat_id: str):
    return player_api(p.server, p.user, p.password, action="get_series", category_id=cat_id) or []

def series_info(p: Profile, series_id: str):
    return player_api(p.server, p.user, p.password, action="get_series_info", series_id=series_id) or {}

def series_episode_url(p: Profile, episode_id: str, container: Optional[str]):
    ext = container if container else p.series_container
    if ext not in ("mp4", "mkv", "ts", "m3u8"):
        ext = "mp4"
    return f"{p.server}/series/{p.user}/{p.password}/{episode_id}.{ext}"

# FONCTIONS ÉTENDUES
def get_user_info(p: Profile) -> Optional[Dict[str, Any]]:
    return player_api(p.server, p.user, p.password, action="get_user_info")

def get_server_info(p: Profile) -> Optional[Dict[str, Any]]:
    return player_api(p.server, p.user, p.password, action="get_server_info")

def get_vod_streams_all(p: Profile) -> List[ExtendedVodItem]:
    data = player_api(p.server, p.user, p.password, action="get_vod_streams") or []
    items = []
    for item in data:
        items.append(ExtendedVodItem(
            id=str(item.get("stream_id")),
            name=item.get("name", ""),
            logo=item.get("stream_icon"),
            container=item.get("container_extension"),
            plot=item.get("plot", ""),
            releasedate=item.get("releasedate", ""),
            duration=item.get("duration", ""),
            cast=item.get("cast", "").split(",") if item.get("cast") else [],
            director=item.get("director", ""),
            genre=item.get("genre", ""),
            rating=float(item.get("rating", 0)) if item.get("rating") else 0.0,
            imdb_id=item.get("imdb_id", ""),
            youtube_trailer=item.get("youtube_trailer", ""),
            backdrop_path=item.get("backdrop_path", []),
            added=item.get("added", ""),
            category_id=str(item.get("category_id")) if item.get("category_id") else None  # 👈 AJOUT
        ))
    return items

def get_series_all(p: Profile) -> List[ExtendedSeriesItem]:
    data = player_api(p.server, p.user, p.password, action="get_series") or []
    items = []
    for item in data:
        items.append(ExtendedSeriesItem(
            series_id=str(item.get("series_id")),
            name=item.get("name", ""),
            cover=item.get("cover"),
            plot=item.get("plot", ""),
            releaseDate=item.get("releaseDate", ""),
            cast=item.get("cast", "").split(",") if item.get("cast") else [],
            genre=item.get("genre", ""),
            rating=float(item.get("rating", 0)) if item.get("rating") else 0.0,
            imdb_id=item.get("imdb_id", ""),
            youtube_trailer=item.get("youtube_trailer", ""),
            backdrop_path=item.get("backdrop_path", []),
            last_modified=item.get("last_modified", ""),
            category_id=str(item.get("category_id")) if item.get("category_id") else None  # 👈 AJOUT
))

    return items

def search_all_content(p: Profile, query: str) -> Dict[str, List]:
    results = {"live": [], "vod": [], "series": []}
    
    try:
        # Recherche Live
        live_cats = live_categories(p)
        for cat in live_cats:
            channels = live_streams(p, cat.get("category_id"))
            for channel in channels:
                if query.lower() in channel.get("name", "").lower():
                    results["live"].append({
                        "type": "live", "id": channel.get("stream_id"),
                        "name": channel.get("name"), "category": cat.get("category_name"),
                        "logo": channel.get("stream_icon")
                    })
        
        # Recherche VOD
        vod_items = get_vod_streams_all(p)
        for item in vod_items:
            if query.lower() in item.name.lower():
                results["vod"].append({
                    "type": "vod", "id": item.id, "name": item.name,
                    "year": item.releasedate, "rating": item.rating, "logo": item.logo
                })
        
        # Recherche Séries
        series_items = get_series_all(p)
        for item in series_items:
            if query.lower() in item.name.lower():
                results["series"].append({
                    "type": "series", "id": item.series_id, "name": item.name,
                    "year": item.releaseDate, "rating": item.rating, "logo": item.cover
                })
                
    except Exception as e:
        logger.error(f"Erreur recherche: {e}")
    
    return results

# ------------------- Gestionnaire de téléchargement -------------------
class DownloadManager(QThread):
    progress_updated = pyqtSignal(DownloadItem)
    download_completed = pyqtSignal(DownloadItem)
    download_error = pyqtSignal(DownloadItem, str)
    
    def __init__(self):
        super().__init__()
        self.queue: List[DownloadItem] = load_download_queue()
        self.current_download: Optional[DownloadItem] = None
        self.is_paused = False
        
    def add_download(self, item: DownloadItem):
        self.queue.append(item)
        save_download_queue(self.queue)
        if not self.isRunning():
            self.start()
            
    def pause_download(self):
        self.is_paused = True
        
    def resume_download(self):
        self.is_paused = False
        
    def cancel_download(self, item_id: str):
        if self.current_download and self.current_download.id == item_id:
            self.current_download.status = "cancelled"
        self.queue = [item for item in self.queue if item.id != item_id]
        save_download_queue(self.queue)
        
    def run(self):
        while self.queue and not self.is_paused:
            self.current_download = self.queue.pop(0)
            self.current_download.status = "downloading"
            self.progress_updated.emit(self.current_download)
            
            try:
                self.download_file(self.current_download)
                self.current_download.status = "completed"
                self.current_download.progress = 100.0
                self.download_completed.emit(self.current_download)
            except Exception as e:
                self.current_download.status = "error"
                self.download_error.emit(self.current_download, str(e))
            
            save_download_queue(self.queue)
            self.current_download = None
            
    def download_file(self, item: DownloadItem):
        response = requests.get(item.url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        item.file_size = total_size
        
        os.makedirs(os.path.dirname(item.output_path), exist_ok=True)
        
        with open(item.output_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                if self.is_paused:
                    break
                    
                if chunk:
                    file.write(chunk)
                    item.downloaded += len(chunk)
                    if total_size > 0:
                        item.progress = (item.downloaded / total_size) * 100
                    self.progress_updated.emit(item)
        
        if item.subtitle_url:
            self.download_subtitles(item)

    def download_subtitles(self, item: DownloadItem):
        try:
            sub_response = requests.get(item.subtitle_url, timeout=30)
            sub_response.raise_for_status()
            
            sub_path = item.output_path.replace('.mp4', '.srt').replace('.mkv', '.srt')
            with open(sub_path, 'w', encoding='utf-8') as sub_file:
                sub_file.write(sub_response.text)
        except Exception as e:
            logger.error(f"Erreur téléchargement sous-titres: {e}")

# ------------------- Lecteur VLC amélioré -------------------
class EnhancedVlcWidget(QtWidgets.QFrame):
    positionChanged = pyqtSignal(float)
    stateChanged = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self.setLineWidth(2)
        
        self.instance = None
        self.player = None
        self.media = None
        self.current_url = ""
        self.current_subtitles: List[SubtitleTrack] = []
        self.current_subtitle_index = -1
        
        self.setup_vlc()
        self.setup_ui()
        self.setup_timer()

    def setup_vlc(self):
        if not _EMBEDDED_VLC:
            return
            
        try:
            self.instance = vlc.Instance("--no-xlib --quiet")
            self.player = self.instance.media_player_new()
        except Exception as e:
            logger.error(f"Erreur initialisation VLC: {e}")
            self.instance = None
            self.player = None

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Zone vidéo
        self.video_frame = QtWidgets.QFrame()
        self.video_frame.setStyleSheet("background-color: black;")
        layout.addWidget(self.video_frame, 1)
        
        # Contrôles
        controls_layout = QtWidgets.QHBoxLayout()
        
        self.btnPlayPause = QtWidgets.QPushButton("⏸")
        self.btnStop = QtWidgets.QPushButton("⏹")
        self.sliderPosition = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.sliderPosition.setRange(0, 1000)
        self.labelTime = QtWidgets.QLabel("00:00 / 00:00")
        
        self.btnSubtitles = QtWidgets.QPushButton("🎬 ST")
        self.btnSubtitles.setToolTip("Sous-titres")
        
        self.btnMute = QtWidgets.QPushButton("🔊")
        self.sliderVolume = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.sliderVolume.setRange(0, 100)
        self.sliderVolume.setValue(80)
        
        controls_layout.addWidget(self.btnPlayPause)
        controls_layout.addWidget(self.btnStop)
        controls_layout.addWidget(self.sliderPosition, 1)
        controls_layout.addWidget(self.labelTime)
        controls_layout.addWidget(self.btnSubtitles)
        controls_layout.addWidget(self.btnMute)
        controls_layout.addWidget(self.sliderVolume)
        
        layout.addLayout(controls_layout)
        
        # Connexions
        self.btnPlayPause.clicked.connect(self.toggle_play_pause)
        self.btnStop.clicked.connect(self.stop)
        self.btnSubtitles.clicked.connect(self.cycle_subtitles)
        self.btnMute.clicked.connect(self.toggle_mute)
        self.sliderPosition.sliderMoved.connect(self.set_position)
        self.sliderVolume.valueChanged.connect(self.set_volume)

    def setup_timer(self):
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)

    def play_url(self, url: str, subtitles: List[SubtitleTrack] = None, start_position: float = 0) -> bool:
        self.current_url = url
        self.current_subtitles = subtitles or []
        self.current_subtitle_index = -1
        
        if not _EMBEDDED_VLC or not self.player:
            return False
            
        try:
            self.media = self.instance.media_new(url)
            self.player.set_media(self.media)
            
            if self.current_subtitles:
                self.set_subtitle(0)
            
            if sys.platform.startswith("win"):
                self.player.set_hwnd(int(self.video_frame.winId()))
            elif sys.platform == "darwin":
                self.player.set_nsobject(int(self.video_frame.winId()))
            else:
                self.player.set_xwindow(int(self.video_frame.winId()))
            
            self.player.play()
            
            if start_position > 0:
                QTimer.singleShot(1000, lambda: self.set_position(start_position))
                
            return True
            
        except Exception as e:
            logger.error(f"Erreur lecture {url}: {e}")
            return False

    def set_subtitle(self, index: int):
        if not self.current_subtitles or index >= len(self.current_subtitles):
            return
            
        try:
            subtitle_track = self.current_subtitles[index]
            media = self.player.get_media()
            if media:
                media.add_option(f":sub-file={subtitle_track.url}")
            self.current_subtitle_index = index
            self.update_subtitle_button()
        except Exception as e:
            logger.error(f"Erreur sous-titres: {e}")

    def cycle_subtitles(self):
        if not self.current_subtitles:
            return
            
        self.current_subtitle_index = (self.current_subtitle_index + 1) % (len(self.current_subtitles) + 1)
        
        if self.current_subtitle_index == 0:
            self.player.video_set_spu(-1)
        else:
            self.set_subtitle(self.current_subtitle_index - 1)
        
        self.update_subtitle_button()

    def update_subtitle_button(self):
        if not self.current_subtitles:
            self.btnSubtitles.setText("🎬 ST")
            self.btnSubtitles.setToolTip("Aucun sous-titre")
        elif self.current_subtitle_index == 0:
            self.btnSubtitles.setText("🎬 OFF")
            self.btnSubtitles.setToolTip("Sous-titres désactivés")
        else:
            current_sub = self.current_subtitles[self.current_subtitle_index - 1]
            self.btnSubtitles.setText(f"🎬 {current_sub.language.upper()}")
            self.btnSubtitles.setToolTip(f"Sous-titres: {current_sub.language}")

    def toggle_play_pause(self):
        if _EMBEDDED_VLC and self.player:
            self.player.pause()

    def stop(self):
        if _EMBEDDED_VLC and self.player:
            self.player.stop()
            self.sliderPosition.setValue(0)
            self.update_display()

    def toggle_mute(self):
        if _EMBEDDED_VLC and self.player:
            self.player.audio_toggle_mute()
            self.update_mute_button()

    def set_volume(self, value: int):
        if _EMBEDDED_VLC and self.player:
            self.player.audio_set_volume(value)
            self.update_mute_button()

    def set_position(self, position: float):
        if _EMBEDDED_VLC and self.player:
            self.player.set_position(position / 1000.0)

    def get_position(self) -> float:
        if _EMBEDDED_VLC and self.player:
            return self.player.get_position()
        return 0.0

    def update_display(self):
        if not _EMBEDDED_VLC or not self.player:
            return
            
        position = self.get_position()
        if position >= 0:
            self.sliderPosition.setValue(int(position * 1000))
        
        current_time = self.player.get_time() // 1000
        total_time = self.player.get_length() // 1000
        
        if total_time > 0:
            current_str = f"{current_time // 60:02d}:{current_time % 60:02d}"
            total_str = f"{total_time // 60:02d}:{total_time % 60:02d}"
            self.labelTime.setText(f"{current_str} / {total_str}")
        
        state = self.player.get_state()
        self.btnPlayPause.setText("⏸" if state == vlc.State.Playing else "▶")
        self.update_mute_button()

    def update_mute_button(self):
        if _EMBEDDED_VLC and self.player:
            is_muted = self.player.audio_get_mute()
            volume = self.player.audio_get_volume()
            self.btnMute.setText("🔇" if is_muted or volume == 0 else "🔊")

# ------------------- Onglet LIVE -------------------
class LiveTab(QtWidgets.QWidget):
    playRequested = QtCore.pyqtSignal(str, str)
    statusMsg = QtCore.pyqtSignal(str)

    def __init__(self, get_profile_fn, favorites_ref):
        super().__init__()
        self.get_profile = get_profile_fn
        self.favorites_ref = favorites_ref
        self.all_categories: List[Category] = []
        self.all_channels: List[Channel] = []
        self.filtered_channels: List[Channel] = []

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Recherche
        search_layout = QtWidgets.QHBoxLayout()
        self.searchCat = QtWidgets.QLineEdit(placeholderText="Rechercher catégorie...")
        self.searchChan = QtWidgets.QLineEdit(placeholderText="Rechercher chaîne...")
        search_layout.addWidget(self.searchCat)
        search_layout.addWidget(self.searchChan)
        layout.addLayout(search_layout)

        # Contenu principal
        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        # Catégories
        cat_widget = QtWidgets.QWidget()
        cat_layout = QtWidgets.QVBoxLayout(cat_widget)
        cat_layout.addWidget(QtWidgets.QLabel("Catégories LIVE:"))
        self.listCats = QtWidgets.QListWidget()
        cat_layout.addWidget(self.listCats)

        # Chaînes
        chan_widget = QtWidgets.QWidget()
        chan_layout = QtWidgets.QVBoxLayout(chan_widget)
        chan_layout.addWidget(QtWidgets.QLabel("Chaînes:"))
        self.listChans = QtWidgets.QListWidget()
        chan_layout.addWidget(self.listChans, 1)

        # Boutons
        btn_layout = QtWidgets.QHBoxLayout()
        self.btnFav = QtWidgets.QPushButton("⭐ Favori")
        self.btnPlay = QtWidgets.QPushButton("▶ Lire")
        self.btnStop = QtWidgets.QPushButton("■ Stop")
        btn_layout.addWidget(self.btnFav)
        btn_layout.addWidget(self.btnPlay)
        btn_layout.addWidget(self.btnStop)
        chan_layout.addLayout(btn_layout)

        # EPG
        chan_layout.addWidget(QtWidgets.QLabel("EPG:"))
        self.epgBox = QtWidgets.QTextEdit(readOnly=True)
        self.epgBox.setMaximumHeight(150)
        chan_layout.addWidget(self.epgBox)

        main_splitter.addWidget(cat_widget)
        main_splitter.addWidget(chan_widget)
        main_splitter.setSizes([300, 500])

        layout.addWidget(main_splitter, 1)

    def setup_connections(self):
        self.searchCat.textChanged.connect(self.filter_categories)
        self.searchChan.textChanged.connect(self.filter_channels)
        self.listCats.itemSelectionChanged.connect(self.on_cat_select)
        self.listChans.itemDoubleClicked.connect(self.play_selected)
        self.btnPlay.clicked.connect(self.play_selected)
        self.btnStop.clicked.connect(lambda: self.playRequested.emit("", ""))
        self.btnFav.clicked.connect(self.toggle_fav)

    def reload(self):
        self.all_categories.clear()
        self.listCats.clear()
        self.all_channels.clear()
        self.listChans.clear()
        self.epgBox.clear()

        p = self.get_profile()
        if not p:
            return

        def worker():
            try:
                info = api_info(p)
                ui = info.get("user_info", {})
                if not ui or (str(ui.get("auth","0"))!="1" and str(ui.get("status","")).lower()!="active"):
                    raise RuntimeError("Profil inactif/non autorisé.")
                
                cats = live_categories(p)
                self.all_categories = [Category(id=str(c.get("category_id")), name=c.get("category_name","N/A")) for c in cats]
                self.all_categories.sort(key=lambda c: c.name.lower())
                
                fav_ids = set(self.favorites_ref()["live"].get(p.name, []))
                if fav_ids:
                    self.all_categories.insert(0, Category(id="_FAV_", name="⭐ Favoris"))
                
                QtCore.QMetaObject.invokeMethod(self, "_populate_cats", QtCore.Qt.ConnectionType.QueuedConnection)
                self.statusMsg.emit(f"{len(self.all_categories)} catégories LIVE.")
            except Exception as e:
                self.statusMsg.emit(f"Erreur: {e}")

        threading.Thread(target=worker, daemon=True).start()

    @QtCore.pyqtSlot()
    def _populate_cats(self):
        self.listCats.clear()
        for c in self.all_categories:
            self.listCats.addItem(f"{c.name}")

    def on_cat_select(self):
        items = self.listCats.selectedItems()
        if not items:
            return
        cat_name = items[0].text()
        cat_id = next((c.id for c in self.all_categories if c.name == cat_name), None)
        if cat_id:
            self.load_channels(cat_id)

    def load_channels(self, cat_id: str):
        p = self.get_profile()
        if not p:
            return

        def worker():
            try:
                chs: List[Channel] = []
                if cat_id == "_FAV_":
                    fav_ids = set(self.favorites_ref()["live"].get(p.name, []))
                    all_streams = []
                    for c in live_categories(p):
                        all_streams.extend(live_streams(p, c.get("category_id")))
                    for s in all_streams:
                        sid = str(s.get("stream_id"))
                        if sid in fav_ids:
                            chs.append(Channel(id=sid, name=s.get("name","N/A"), logo=s.get("stream_icon")))
                else:
                    for s in live_streams(p, cat_id):
                        chs.append(Channel(id=str(s.get("stream_id")), name=s.get("name","N/A"), logo=s.get("stream_icon")))
                
                chs.sort(key=lambda x: x.name.lower())
                self.all_channels = chs
                self.filtered_channels = chs
                QtCore.QMetaObject.invokeMethod(self, "_populate_channels", QtCore.Qt.ConnectionType.QueuedConnection)
                self.statusMsg.emit(f"{len(chs)} chaînes.")
            except Exception as e:
                self.statusMsg.emit(f"Erreur: {e}")

        threading.Thread(target=worker, daemon=True).start()

    @QtCore.pyqtSlot()
    def _populate_channels(self):
        self.listChans.clear()
        for ch in self.filtered_channels:
            self.listChans.addItem(f"{ch.name}")

    def filter_categories(self, txt: str):
        self.listCats.clear()
        low = txt.lower()
        for c in self.all_categories:
            if low in c.name.lower():
                self.listCats.addItem(f"{c.name}")

    def filter_channels(self, txt: str):
        low = txt.lower()
        self.filtered_channels = [c for c in self.all_channels if low in c.name.lower()]
        self._populate_channels()

    def current_channel(self) -> Optional[Channel]:
        items = self.listChans.selectedItems()
        if not items:
            return None
        chan_name = items[0].text()
        for c in self.filtered_channels:
            if c.name == chan_name:
                return c
        return None

    def play_selected(self):
        p = self.get_profile()
        ch = self.current_channel()
        if not (p and ch):
            self.statusMsg.emit("Sélectionnez une chaîne")
            return

        url = live_url(p, ch.id)
        
        def worker():
            try:
                short = epg_short(p, ch.id)
                lines = []
                for e in short.get("epg_listings", [])[:5]:
                    start = e.get("start", "")
                    title = b64decode_safe(e.get("title", ""))            # ✅ décodage base64
                    lines.append(f"• {start} - {title}")
                txt = "\n".join(lines) if lines else "(Pas d'EPG)"
            except Exception:
                txt = "(EPG indisponible)"
            QtCore.QMetaObject.invokeMethod(
                self.epgBox, "setPlainText",
                QtCore.Qt.ConnectionType.QueuedConnection,
                QtCore.Q_ARG(str, txt)
    )


        threading.Thread(target=worker, daemon=True).start()
        self.playRequested.emit(url, ch.name)

    def toggle_fav(self):
        p = self.get_profile()
        ch = self.current_channel()
        if not (p and ch):
            return

        favs = load_favorites()
        lst = set(favs["live"].get(p.name, []))
        if ch.id in lst:
            lst.remove(ch.id)
            self.statusMsg.emit("Retiré des favoris")
        else:
            lst.add(ch.id)
            self.statusMsg.emit("Ajouté aux favoris")
        
        favs["live"][p.name] = sorted(lst)
        save_favorites(favs)

# ------------------- Onglet VOD Amélioré -------------------
class EnhancedVodTab(QtWidgets.QWidget):
    playRequested = QtCore.pyqtSignal(str, str, list)
    playExternalRequested = QtCore.pyqtSignal(str, str, list)
    downloadRequested = QtCore.pyqtSignal(DownloadItem)
    statusMsg = QtCore.pyqtSignal(str)

    def __init__(self, get_profile_fn, favorites_ref):
        super().__init__()
        self.get_profile = get_profile_fn
        self.favorites_ref = favorites_ref
        self.all_categories: List[Category] = []
        self.items: List[ExtendedVodItem] = []
        self.filtered: List[ExtendedVodItem] = []
        self.current_subtitles: List[SubtitleTrack] = []

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Recherche
        search_layout = QtWidgets.QHBoxLayout()
        self.searchCat = QtWidgets.QLineEdit(placeholderText="Rechercher catégorie...")
        self.searchVod = QtWidgets.QLineEdit(placeholderText="Rechercher film...")
        search_layout.addWidget(self.searchCat)
        search_layout.addWidget(self.searchVod)
        layout.addLayout(search_layout)

        # Contenu principal
        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        # Catégories
        cat_widget = QtWidgets.QWidget()
        cat_layout = QtWidgets.QVBoxLayout(cat_widget)
        cat_layout.addWidget(QtWidgets.QLabel("Catégories VOD:"))
        self.listCats = QtWidgets.QListWidget()
        cat_layout.addWidget(self.listCats)

        # Films
        vod_widget = QtWidgets.QWidget()
        vod_layout = QtWidgets.QVBoxLayout(vod_widget)
        vod_layout.addWidget(QtWidgets.QLabel("Films:"))
        self.listVod = QtWidgets.QListWidget()
        vod_layout.addWidget(self.listVod, 1)

        # Boutons améliorés
        btn_layout = QtWidgets.QHBoxLayout()
        self.btnFav = QtWidgets.QPushButton("⭐ Favori")
        self.btnPlay = QtWidgets.QPushButton("▶ Lire")
        self.btnPlayExternal = QtWidgets.QPushButton("📺 VLC Externe")
        self.btnDownload = QtWidgets.QPushButton("⏬ Télécharger")
        self.btnRecent = QtWidgets.QPushButton("🕐 Films Récents")
        btn_layout.addWidget(self.btnFav)
        btn_layout.addWidget(self.btnPlay)
        btn_layout.addWidget(self.btnPlayExternal)
        btn_layout.addWidget(self.btnDownload)
        btn_layout.addWidget(self.btnRecent)
        vod_layout.addLayout(btn_layout)

        # Infos enrichies
        info_widget = QtWidgets.QWidget()
        info_layout = QtWidgets.QVBoxLayout(info_widget)
        info_layout.addWidget(QtWidgets.QLabel("📋 Informations Détaillées:"))
        self.infoBox = QtWidgets.QTextEdit(readOnly=True)
        self.infoBox.setMaximumHeight(200)
        info_layout.addWidget(self.infoBox)
        
        self.subtitlesLabel = QtWidgets.QLabel("🎬 Sous-titres: Aucun")
        info_layout.addWidget(self.subtitlesLabel)

        vod_layout.addWidget(info_widget)

        main_splitter.addWidget(cat_widget)
        main_splitter.addWidget(vod_widget)
        main_splitter.setSizes([300, 500])

        layout.addWidget(main_splitter, 1)

    def setup_connections(self):
        self.searchCat.textChanged.connect(self.filter_categories)
        self.searchVod.textChanged.connect(self.filter_items)
        self.listCats.itemSelectionChanged.connect(self.on_cat_select)
        self.listVod.itemSelectionChanged.connect(self.show_info)
        self.listVod.itemDoubleClicked.connect(self.play_selected)
        self.btnPlay.clicked.connect(self.play_selected)
        self.btnPlayExternal.clicked.connect(self.play_external)
        self.btnDownload.clicked.connect(self.download_selected)
        self.btnFav.clicked.connect(self.toggle_fav)
        self.btnRecent.clicked.connect(self.show_recent_movies)

    def reload(self):
        self.all_categories.clear()
        self.listCats.clear()
        self.items.clear()
        self.listVod.clear()
        self.infoBox.clear()
        self.subtitlesLabel.setText("🎬 Sous-titres: Aucun")

        p = self.get_profile()
        if not p:
            return

        def worker():
            try:
                cats = vod_categories(p)
                self.all_categories = [Category(id=str(c.get("category_id")), name=c.get("category_name","N/A")) for c in cats]
                self.all_categories.sort(key=lambda c: c.name.lower())
                
                fav_ids = set(self.favorites_ref()["vod"].get(p.name, []))
                if fav_ids:
                    self.all_categories.insert(0, Category(id="_FAV_", name="⭐ Favoris"))
                
                QtCore.QMetaObject.invokeMethod(self, "_populate_cats", QtCore.Qt.ConnectionType.QueuedConnection)
                self.statusMsg.emit(f"{len(self.all_categories)} catégories VOD.")
            except Exception as e:
                self.statusMsg.emit(f"Erreur: {e}")

        threading.Thread(target=worker, daemon=True).start()

    @QtCore.pyqtSlot()
    def _populate_cats(self):
        self.listCats.clear()
        for c in self.all_categories:
            self.listCats.addItem(f"{c.name}")

    def on_cat_select(self):
        items = self.listCats.selectedItems()
        if not items:
            return
        cat_name = items[0].text()
        cat_id = next((c.id for c in self.all_categories if c.name == cat_name), None)
        if cat_id:
            self.load_items(cat_id)

    def load_items(self, cat_id: str):
        p = self.get_profile()
        if not p:
            return

        def worker():
            try:
                if cat_id == "_FAV_":
                    fav_ids = set(self.favorites_ref()["vod"].get(p.name, []))
                    all_items = get_vod_streams_all(p)
                    items = [it for it in all_items if it.id in fav_ids]
                else:
                    # ✅ Filtrage par category_id des ITEMS (et non pas par existence de la catégorie)
                    all_items = get_vod_streams_all(p)
                    items = [it for it in all_items if it.category_id == str(cat_id)]

                    # 👉 Variante possible (appel direct par catégorie) :
                    # raw = vod_streams(p, cat_id)
                    # items = []
                    # for s in raw:
                    #     items.append(ExtendedVodItem(
                    #         id=str(s.get("stream_id")),
                    #         name=s.get("name",""),
                    #         logo=s.get("stream_icon"),
                    #         container=s.get("container_extension") or None,
                    #         plot=s.get("plot",""),
                    #         releasedate=s.get("releasedate",""),
                    #         duration=s.get("duration",""),
                    #         rating=float(s.get("rating", 0) or 0),
                    #         added=str(s.get("added","0")),
                    #         category_id=str(s.get("category_id")) if s.get("category_id") else None
                    #     ))

                # Tri "récents"
                items.sort(key=lambda x: int(x.added) if str(x.added).isdigit() else 0, reverse=True)
                self.items = self.filtered = items

                QtCore.QMetaObject.invokeMethod(
                    self, "_populate_items",
                    QtCore.Qt.ConnectionType.QueuedConnection
                )
                self.statusMsg.emit(f"{len(self.items)} films chargés avec métadonnées.")
            except Exception as e:
                self.statusMsg.emit(f"Erreur: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def show_recent_movies(self):
        p = self.get_profile()
        if not p:
            return

        def worker():
            try:
                all_movies = get_vod_streams_all(p)
                all_movies.sort(key=lambda x: int(x.added) if x.added.isdigit() else 0, reverse=True)
                self.items = all_movies[:50]
                self.filtered = self.items
                QtCore.QMetaObject.invokeMethod(self, "_populate_items", QtCore.Qt.ConnectionType.QueuedConnection)
                self.statusMsg.emit(f"{len(self.items)} films récents chargés.")
            except Exception as e:
                self.statusMsg.emit(f"Erreur: {e}")

        threading.Thread(target=worker, daemon=True).start()

    @QtCore.pyqtSlot()
    def _populate_items(self):
        self.listVod.clear()
        for v in self.filtered:
            rating_str = f"⭐ {v.rating}/10 " if v.rating > 0 else ""
            year_str = f"({v.releasedate})" if v.releasedate else ""
            it = QtWidgets.QListWidgetItem(f"{rating_str}{v.name} {year_str}")
            # ✅ Stocker l'ID pour éviter les confusions de titres
            it.setData(QtCore.Qt.ItemDataRole.UserRole, v.id)
            self.listVod.addItem(it)


    def filter_categories(self, txt: str):
        self.listCats.clear()
        low = txt.lower()
        for c in self.all_categories:
            if low in c.name.lower():
                self.listCats.addItem(f"{c.name}")

    def filter_items(self, txt: str):
        low = txt.lower()
        self.filtered = [v for v in self.items if low in v.name.lower()]
        self._populate_items()

    def current_item(self) -> Optional[ExtendedVodItem]:
        items = self.listVod.selectedItems()
        if not items:
            return None
        sel = items[0]
        vid = sel.data(QtCore.Qt.ItemDataRole.UserRole)
        if not vid:
            return None
        for v in self.filtered:
            if v.id == vid:
                return v
        return None


    def show_info(self):
        p = self.get_profile()
        v = self.current_item()
        self.current_subtitles = []
        
        if not (p and v):
            self.infoBox.clear()
            self.subtitlesLabel.setText("🎬 Sous-titres: Aucun")
            return

        def worker():
            try:
                # Récupérer les sous-titres
                subtitles = vod_subtitles(p, v.id)
                self.current_subtitles = subtitles
                
                # Construire l'affichage enrichi
                cast_str = ', '.join(v.cast) if v.cast else 'Non disponible'
                info_text = f"""🎬 {v.name}

📅 Année: {v.releasedate}
⏱️ Durée: {v.duration} min
⭐ Rating: {v.rating}/10
🎭 Genre: {v.genre}
🎬 Réalisateur: {v.director}

👥 Casting: {cast_str}

📖 Synopsis:
{v.plot}

🎬 Bande-annonce: {'Disponible' if v.youtube_trailer else 'Non disponible'}
                """
                
                subs_text = f"🎬 Sous-titres: {len(subtitles)} disponible(s)" if subtitles else "🎬 Sous-titres: Aucun"
                
                QtCore.QMetaObject.invokeMethod(self, "_update_info",
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(str, info_text),
                    QtCore.Q_ARG(str, subs_text))
                    
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(self, "_update_info",
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(str, f"🎬 {v.name}\n\n❌ Informations détaillées non disponibles"),
                    QtCore.Q_ARG(str, "🎬 Sous-titres: Aucun"))

        threading.Thread(target=worker, daemon=True).start()

    @QtCore.pyqtSlot(str, str)
    def _update_info(self, info_text: str, subs_text: str):
        self.infoBox.setPlainText(info_text)
        self.subtitlesLabel.setText(subs_text)

    def play_selected(self):
        p = self.get_profile()
        v = self.current_item()
        if not (p and v):
            self.statusMsg.emit("Sélectionnez un film")
            return

        url = vod_url(p, v.id, v.container)
        self.playRequested.emit(url, v.name, self.current_subtitles)

    def play_external(self):
        p = self.get_profile()
        v = self.current_item()
        if not (p and v):
            self.statusMsg.emit("Sélectionnez un film")
            return

        url = vod_url(p, v.id, v.container)
        self.playExternalRequested.emit(url, v.name, self.current_subtitles)

    def download_selected(self):
        p = self.get_profile()
        v = self.current_item()
        if not (p and v):
            self.statusMsg.emit("Sélectionnez un film")
            return

        url = vod_url(p, v.id, v.container)
        download_path = os.path.join(
            load_settings().get("download_path", DOWNLOAD_DIR),
            "VOD",
            f"{v.name}.{v.container or 'mp4'}"
        )
        
        subtitle_url = self.current_subtitles[0].url if self.current_subtitles else ""
        
        download_item = DownloadItem(
            id=f"vod_{v.id}_{int(time.time())}",
            type="vod",
            title=v.name,
            url=url,
            output_path=download_path,
            subtitle_url=subtitle_url
        )
        
        self.downloadRequested.emit(download_item)
        self.statusMsg.emit(f"📥 Téléchargement ajouté: {v.name}")

    def toggle_fav(self):
        p = self.get_profile()
        v = self.current_item()
        if not (p and v):
            return

        favs = load_favorites()
        lst = set(favs["vod"].get(p.name, []))
        if v.id in lst:
            lst.remove(v.id)
            self.statusMsg.emit("❌ Retiré des favoris")
        else:
            lst.add(v.id)
            self.statusMsg.emit("✅ Ajouté aux favoris")
        
        favs["vod"][p.name] = sorted(lst)
        save_favorites(favs)

# ------------------- Onglet Séries -------------------
class SeriesTab(QtWidgets.QWidget):
    playRequested = QtCore.pyqtSignal(str, str)
    statusMsg = QtCore.pyqtSignal(str)

    def __init__(self, get_profile_fn):
        super().__init__()
        self.get_profile = get_profile_fn
        self.all_categories: List[Category] = []
        self.series_items: List[ExtendedSeriesItem] = []
        self.filtered_series: List[ExtendedSeriesItem] = []
        self.episodes: List[Episode] = []

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Recherche
        search_layout = QtWidgets.QHBoxLayout()
        self.searchCat = QtWidgets.QLineEdit(placeholderText="Rechercher catégorie...")
        self.searchSerie = QtWidgets.QLineEdit(placeholderText="Rechercher série...")
        search_layout.addWidget(self.searchCat)
        search_layout.addWidget(self.searchSerie)
        layout.addLayout(search_layout)

        # Contenu principal
        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        # Catégories
        cat_widget = QtWidgets.QWidget()
        cat_layout = QtWidgets.QVBoxLayout(cat_widget)
        cat_layout.addWidget(QtWidgets.QLabel("Catégories Séries:"))
        self.listCats = QtWidgets.QListWidget()
        cat_layout.addWidget(self.listCats)

        # Séries
        series_widget = QtWidgets.QWidget()
        series_layout = QtWidgets.QVBoxLayout(series_widget)
        series_layout.addWidget(QtWidgets.QLabel("Séries:"))
        self.listSeries = QtWidgets.QListWidget()
        series_layout.addWidget(self.listSeries, 1)

        # Saisons et épisodes
        ep_widget = QtWidgets.QWidget()
        ep_layout = QtWidgets.QVBoxLayout(ep_widget)
        
        ep_layout.addWidget(QtWidgets.QLabel("Saison:"))
        self.cmbSeasons = QtWidgets.QComboBox()
        ep_layout.addWidget(self.cmbSeasons)
        
        ep_layout.addWidget(QtWidgets.QLabel("Épisodes:"))
        self.listEps = QtWidgets.QListWidget()
        ep_layout.addWidget(self.listEps, 1)
        
        self.btnPlay = QtWidgets.QPushButton("▶ Lire épisode")
        ep_layout.addWidget(self.btnPlay)

        # Infos
        ep_layout.addWidget(QtWidgets.QLabel("Infos:"))
        self.infoBox = QtWidgets.QTextEdit(readOnly=True)
        self.infoBox.setMaximumHeight(120)
        ep_layout.addWidget(self.infoBox)

        main_splitter.addWidget(cat_widget)
        main_splitter.addWidget(series_widget)
        main_splitter.addWidget(ep_widget)
        main_splitter.setSizes([250, 300, 350])

        layout.addWidget(main_splitter, 1)

    def setup_connections(self):
        self.searchCat.textChanged.connect(self.filter_categories)
        self.searchSerie.textChanged.connect(self.filter_series)
        self.listCats.itemSelectionChanged.connect(self.on_cat_select)
        self.listSeries.itemSelectionChanged.connect(self.on_series_select)
        self.cmbSeasons.currentIndexChanged.connect(self.populate_episodes_for_season)
        self.btnPlay.clicked.connect(self.play_selected)

    def reload(self):
        self.all_categories.clear()
        self.listCats.clear()
        self.series_items.clear()
        self.listSeries.clear()
        self.cmbSeasons.clear()
        self.listEps.clear()
        self.infoBox.clear()

        p = self.get_profile()
        if not p:
            return

        def worker():
            try:
                cats = series_categories(p)
                self.all_categories = [Category(id=str(c.get("category_id")), name=c.get("category_name","N/A")) for c in cats]
                self.all_categories.sort(key=lambda c: c.name.lower())
                QtCore.QMetaObject.invokeMethod(self, "_populate_cats", QtCore.Qt.ConnectionType.QueuedConnection)
                self.statusMsg.emit(f"{len(self.all_categories)} catégories Séries.")
            except Exception as e:
                self.statusMsg.emit(f"Erreur: {e}")

        threading.Thread(target=worker, daemon=True).start()

    @QtCore.pyqtSlot()
    def _populate_cats(self):
        self.listCats.clear()
        for c in self.all_categories:
            self.listCats.addItem(f"{c.name}")

    def on_cat_select(self):
        items = self.listCats.selectedItems()
        if not items:
            return
        cat_name = items[0].text()
        cat_id = next((c.id for c in self.all_categories if c.name == cat_name), None)
        if cat_id:
            self.load_series(cat_id)

    def load_series(self, cat_id: str):
        p = self.get_profile()
        if not p:
            return

        def worker():
            try:
                all_series = get_series_all(p)
                series = [s for s in all_series if s.category_id == str(cat_id)]
                series.sort(key=lambda x: int(x.last_modified) if str(x.last_modified).isdigit() else 0, reverse=True)
                self.series_items = self.filtered_series = series

                QtCore.QMetaObject.invokeMethod(
                    self, "_populate_series",
                    QtCore.Qt.ConnectionType.QueuedConnection
                )
                self.statusMsg.emit(f"{len(self.series_items)} séries chargées.")
            except Exception as e:
                self.statusMsg.emit(f"Erreur: {e}")

        threading.Thread(target=worker, daemon=True).start()


    @QtCore.pyqtSlot()
    def _populate_series(self):
        self.listSeries.clear()
        for s in self.filtered_series:
            rating_str = f"⭐ {s.rating}/10 " if s.rating > 0 else ""
            it = QtWidgets.QListWidgetItem(f"{rating_str}{s.name}")
            it.setData(QtCore.Qt.ItemDataRole.UserRole, s.series_id)  # ✅ store id
            self.listSeries.addItem(it)


    def filter_categories(self, txt: str):
        self.listCats.clear()
        low = txt.lower()
        for c in self.all_categories:
            if low in c.name.lower():
                self.listCats.addItem(f"{c.name}")

    def filter_series(self, txt: str):
        low = txt.lower()
        self.filtered_series = [s for s in self.series_items if low in s.name.lower()]
        self._populate_series()

    def current_series(self) -> Optional[ExtendedSeriesItem]:
        items = self.listSeries.selectedItems()
        if not items:
            return None
        sel = items[0]
        sid = sel.data(QtCore.Qt.ItemDataRole.UserRole)
        if not sid:
            return None
        for s in self.filtered_series:
            if s.series_id == sid:
                return s
        return None


    def on_series_select(self):
        p = self.get_profile()
        s = self.current_series()
        self.cmbSeasons.clear()
        self.listEps.clear()
        self.infoBox.clear()
        
        if not (p and s):
            return

        def worker():
            try:
                info = series_info(p, s.series_id)
                plot = info.get("info", {}).get("plot","")
                year = info.get("info", {}).get("releaseDate","")
                
                # Infos enrichies
                cast_str = ', '.join(s.cast) if s.cast else 'Non disponible'
                info_text = f"""📺 {s.name}

📅 Année: {year}
⭐ Rating: {s.rating}/10
🎭 Genre: {s.genre}
👥 Casting: {cast_str}

📖 Synopsis:
{plot}
                """
                
                eps_raw = info.get("episodes", {})
                seasons = sorted([int(k) for k in eps_raw.keys() if str(k).isdigit()])
                episodes: List[Episode] = []
                
                for sea in seasons:
                    for e in eps_raw[str(sea)]:
                        episodes.append(Episode(
                            id=str(e.get("id")),
                            season=sea,
                            epnum=int(e.get("episode_num", 0)),
                            title=e.get("title",""),
                            container=e.get("container_extension","mp4")
                        ))
                
                episodes.sort(key=lambda x: (x.season, x.epnum))
                self.episodes = episodes

                QtCore.QMetaObject.invokeMethod(self, "_update_series_ui", 
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(list, seasons),
                    QtCore.Q_ARG(str, info_text))
                
                self.statusMsg.emit(f"{len(episodes)} épisodes.")
            except Exception as e:
                self.statusMsg.emit(f"Erreur: {e}")

        threading.Thread(target=worker, daemon=True).start()

    @QtCore.pyqtSlot(list, str)
    def _update_series_ui(self, seasons: list, txt: str):
        self.cmbSeasons.clear()
        for sea in seasons:
            self.cmbSeasons.addItem(f"Saison {sea}", sea)
        self.infoBox.setPlainText(txt)
        self.populate_episodes_for_season()

    def populate_episodes_for_season(self):
        self.listEps.clear()
        if self.cmbSeasons.count() == 0:
            return
        sea = self.cmbSeasons.currentData()
        if sea is None:
            sea = 1
        for ep in self.episodes:
            if ep.season == sea:
                self.listEps.addItem(f"E{ep.epnum:02d} - {ep.title}")

    def current_episode(self) -> Optional[Episode]:
        items = self.listEps.selectedItems()
        if not items:
            return None
        ep_text = items[0].text()
        for ep in self.episodes:
            if f"E{ep.epnum:02d} - {ep.title}" == ep_text:
                return ep
        return None

    def play_selected(self):
        p = self.get_profile()
        ep = self.current_episode()
        if not (p and ep):
            self.statusMsg.emit("Choisissez un épisode")
            return

        url = series_episode_url(p, ep.id, ep.container)
        label = f"S{ep.season:02d}E{ep.epnum:02d} - {ep.title}"
        self.playRequested.emit(url, label)

# ------------------- Onglet Recherche Avancée -------------------
class SearchTab(QtWidgets.QWidget):
    playRequested = QtCore.pyqtSignal(str, str)
    statusMsg = QtCore.pyqtSignal(str)

    def __init__(self, get_profile_fn):
        super().__init__()
        self.get_profile = get_profile_fn
        self.last_results = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Barre de recherche
        search_layout = QtWidgets.QHBoxLayout()
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher films, séries, chaînes...")
        self.search_input.returnPressed.connect(self.perform_search)
        
        self.btn_search = QtWidgets.QPushButton("Rechercher")
        self.btn_search.clicked.connect(self.perform_search)
        
        self.btn_clear = QtWidgets.QPushButton("Effacer")
        self.btn_clear.clicked.connect(self.clear_search)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.btn_search)
        search_layout.addWidget(self.btn_clear)
        layout.addLayout(search_layout)
        
        # Résultats
        self.results_tabs = QtWidgets.QTabWidget()
        
        # Onglet Films
        self.vod_tab = QtWidgets.QWidget()
        vod_layout = QtWidgets.QVBoxLayout(self.vod_tab)
        self.vod_list = QtWidgets.QListWidget()
        self.vod_list.itemDoubleClicked.connect(self.play_vod_result)
        vod_layout.addWidget(self.vod_list)
        self.results_tabs.addTab(self.vod_tab, "🎬 Films (0)")
        
        # Onglet Séries
        self.series_tab = QtWidgets.QWidget()
        series_layout = QtWidgets.QVBoxLayout(self.series_tab)
        self.series_list = QtWidgets.QListWidget()
        self.series_list.itemDoubleClicked.connect(self.show_series_info)
        series_layout.addWidget(self.series_list)
        self.results_tabs.addTab(self.series_tab, "📺 Séries (0)")
        
        # Onglet Live
        self.live_tab = QtWidgets.QWidget()
        live_layout = QtWidgets.QVBoxLayout(self.live_tab)
        self.live_list = QtWidgets.QListWidget()
        self.live_list.itemDoubleClicked.connect(self.play_live_result)
        live_layout.addWidget(self.live_list)
        self.results_tabs.addTab(self.live_tab, "📡 Live (0)")
        
        layout.addWidget(self.results_tabs)
        
        # Statistiques
        self.stats_label = QtWidgets.QLabel("Prêt pour la recherche...")
        self.stats_label.setStyleSheet("color: #888; font-style: italic; padding: 5px;")
        layout.addWidget(self.stats_label)

    def perform_search(self):
        query = self.search_input.text().strip()
        if not query:
            QtWidgets.QMessageBox.warning(self, "Recherche", "Veuillez entrer un terme de recherche")
            return
            
        p = self.get_profile()
        if not p:
            QtWidgets.QMessageBox.warning(self, "Recherche", "Aucun profil sélectionné")
            return
            
        self.stats_label.setText("🔍 Recherche en cours...")
        
        def worker():
            try:
                results = search_all_content(p, query)
                self.last_results = results
                
                QtCore.QMetaObject.invokeMethod(self, "_display_results",
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(dict, results),
                    QtCore.Q_ARG(str, query))
                    
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(self, "_display_error",
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(str, str(e)))

        threading.Thread(target=worker, daemon=True).start()

    @QtCore.pyqtSlot(dict, str)
    def _display_results(self, results: dict, query: str):
        # Films VOD
        self.vod_list.clear()
        for item in results["vod"]:
            list_item = QtWidgets.QListWidgetItem(f"⭐ {item['rating']} | {item['name']} ({item['year']})")
            list_item.setData(QtCore.Qt.ItemDataRole.UserRole, item)
            self.vod_list.addItem(list_item)
        
        # Séries
        self.series_list.clear()
        for item in results["series"]:
            list_item = QtWidgets.QListWidgetItem(f"⭐ {item['rating']} | {item['name']} ({item['year']})")
            list_item.setData(QtCore.Qt.ItemDataRole.UserRole, item)
            self.series_list.addItem(list_item)
        
        # Live
        self.live_list.clear()
        for item in results["live"]:
            list_item = QtWidgets.QListWidgetItem(f"📺 {item['name']} [{item['category']}]")
            list_item.setData(QtCore.Qt.ItemDataRole.UserRole, item)
            self.live_list.addItem(list_item)
        
        # Mettre à jour les onglets
        self.results_tabs.setTabText(0, f"🎬 Films ({len(results['vod'])})")
        self.results_tabs.setTabText(1, f"📺 Séries ({len(results['series'])})")
        self.results_tabs.setTabText(2, f"📡 Live ({len(results['live'])})")
        
        total = sum(len(v) for v in results.values())
        self.stats_label.setText(f"✅ Recherche terminée: {total} résultat(s) trouvé(s) pour '{query}'")

    @QtCore.pyqtSlot(str)
    def _display_error(self, error: str):
        self.stats_label.setText(f"❌ Erreur: {error}")

    def clear_search(self):
        self.search_input.clear()
        self.vod_list.clear()
        self.series_list.clear()
        self.live_list.clear()
        self.results_tabs.setTabText(0, "🎬 Films (0)")
        self.results_tabs.setTabText(1, "📺 Séries (0)")
        self.results_tabs.setTabText(2, "📡 Live (0)")
        self.stats_label.setText("Prêt pour la recherche...")

    def play_vod_result(self, item):
        result_data = item.data(QtCore.Qt.ItemDataRole.UserRole)
        p = self.get_profile()
        if p and result_data:
            url = vod_url(p, result_data["id"], "mp4")
            self.playRequested.emit(url, result_data["name"])

    def show_series_info(self, item):
        result_data = item.data(QtCore.Qt.ItemDataRole.UserRole)
        QtWidgets.QMessageBox.information(self, "Série trouvée", 
            f"📺 {result_data['name']}\n⭐ Rating: {result_data['rating']}\n🎬 Année: {result_data['year']}")

    def play_live_result(self, item):
        result_data = item.data(QtCore.Qt.ItemDataRole.UserRole)
        p = self.get_profile()
        if p and result_data:
            url = live_url(p, result_data["id"])
            self.playRequested.emit(url, result_data["name"])

# ------------------- Onglet Informations Utilisateur -------------------
class UserInfoTab(QtWidgets.QWidget):
    def __init__(self, get_profile_fn):
        super().__init__()
        self.get_profile = get_profile_fn
        self.setup_ui()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Titre
        title = QtWidgets.QLabel("📊 Informations Utilisateur et Serveur")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px; color: #2a82da;")
        layout.addWidget(title)
        
        # Zone d'informations
        self.info_text = QtWidgets.QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setStyleSheet("""
            QTextEdit {
                font-family: 'Courier New', monospace;
                font-size: 12px;
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.info_text, 1)
        
        # Boutons
        button_layout = QtWidgets.QHBoxLayout()
        
        self.btn_refresh = QtWidgets.QPushButton("🔄 Actualiser")
        self.btn_refresh.setStyleSheet("QPushButton { padding: 8px; font-weight: bold; }")
        self.btn_refresh.clicked.connect(self.load_user_info)
        
        self.btn_export = QtWidgets.QPushButton("💾 Exporter")
        self.btn_export.setStyleSheet("QPushButton { padding: 8px; font-weight: bold; }")
        self.btn_export.clicked.connect(self.export_info)
        
        button_layout.addWidget(self.btn_refresh)
        button_layout.addWidget(self.btn_export)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)

    def load_user_info(self):
        p = self.get_profile()
        if not p:
            self.info_text.setText("❌ Aucun profil sélectionné")
            return
            
        self.info_text.setText("🔄 Chargement des informations...")
            
        def worker():
            try:
                user_data = get_user_info(p)
                server_data = get_server_info(p)
                
                if not user_data or not server_data:
                    raise Exception("Impossible de récupérer les informations")
                
                user_info = user_data.get("user_info", {})
                server_info = server_data.get("server_info", {})
                
                # Formatage de la date d'expiration
                exp_date = user_info.get('exp_date', '0')
                if exp_date and exp_date != '0':
                    try:
                        exp_date = datetime.fromtimestamp(int(exp_date)).strftime('%d/%m/%Y %H:%M:%S')
                    except (ValueError, TypeError):
                        exp_date = 'Inconnu'
                else:
                    exp_date = 'Illimité'
                
                # Statut avec emoji
                status = user_info.get('status', 'Inconnu')
                status_emoji = "✅" if status.lower() == "active" else "⚠️" if status.lower() == "trial" else "❌"
                
                info_text = f"""
{status_emoji} INFORMATIONS UTILISATEUR {status_emoji}
{'='*50}

👤 Nom d'utilisateur: {user_info.get('username', 'Inconnu')}
📊 Statut: {status}
📅 Date d'expiration: {exp_date}
🔗 Connexions actives: {user_info.get('active_cons', 'Inconnu')} / {user_info.get('max_connections', 'Inconnu')}
📝 Compte créé le: {user_info.get('created_at', 'Inconnu')}
🎯 Compte d'essai: {'Oui' if user_info.get('is_trial', False) else 'Non'}

{'='*50}

🌐 INFORMATIONS SERVEUR
{'='*50}

🔗 Serveur: {server_info.get('url', 'Inconnu')}
🚪 Port: {server_info.get('port', 'Inconnu')}
📡 Protocole: {server_info.get('server_protocol', 'Inconnu')}
🌍 Fuseau horaire: {server_info.get('timezone', 'Inconnu')}
🕐 Heure actuelle: {server_info.get('time_now', 'Inconnu')}
🔧 Version: {server_info.get('version', 'Inconnu')}

{'='*50}

💾 Dernière mise à jour: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
                """
                
                QtCore.QMetaObject.invokeMethod(self, "_update_info",
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(str, info_text))
                    
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(self, "_update_info",
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(str, f"❌ Erreur: {str(e)}"))

        threading.Thread(target=worker, daemon=True).start()

    @QtCore.pyqtSlot(str)
    def _update_info(self, text: str):
        self.info_text.setText(text)

    def export_info(self):
        p = self.get_profile()
        if not p:
            return
            
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Exporter les informations", 
            f"xtream_info_{p.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Fichiers texte (*.txt)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.info_text.toPlainText())
                QtWidgets.QMessageBox.information(self, "Export réussi", 
                    f"Informations exportées vers:\n{filename}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Erreur", 
                    f"Erreur lors de l'export:\n{str(e)}")

# ------------------- Dialogue de téléchargement -------------------
class DownloadDialog(QtWidgets.QDialog):
    def __init__(self, download_manager: DownloadManager, parent=None):
        super().__init__(parent)
        self.download_manager = download_manager
        self.setWindowTitle("Gestion des téléchargements")
        self.setModal(False)
        self.resize(600, 400)
        
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        self.download_list = QtWidgets.QListWidget()
        layout.addWidget(self.download_list)
        
        controls_layout = QtWidgets.QHBoxLayout()
        self.btnPause = QtWidgets.QPushButton("⏸ Pause")
        self.btnResume = QtWidgets.QPushButton("▶ Reprendre")
        self.btnCancel = QtWidgets.QPushButton("❌ Annuler")
        self.btnOpenFolder = QtWidgets.QPushButton("📁 Dossier")
        
        controls_layout.addWidget(self.btnPause)
        controls_layout.addWidget(self.btnResume)
        controls_layout.addWidget(self.btnCancel)
        controls_layout.addWidget(self.btnOpenFolder)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        self.progress_bar = QtWidgets.QProgressBar()
        layout.addWidget(self.progress_bar)
        
        self.update_list()
        
    def setup_connections(self):
        self.download_manager.progress_updated.connect(self.on_download_progress)
        self.download_manager.download_completed.connect(self.on_download_completed)
        self.btnPause.clicked.connect(self.download_manager.pause_download)
        self.btnResume.clicked.connect(self.download_manager.resume_download)
        self.btnCancel.clicked.connect(self.cancel_selected)
        self.btnOpenFolder.clicked.connect(self.open_download_folder)
        
    def update_list(self):
        self.download_list.clear()
        for item in self.download_manager.queue:
            status_icon = "⏳" if item.status == "pending" else "⬇️" if item.status == "downloading" else "✅" if item.status == "completed" else "❌"
            list_item = QtWidgets.QListWidgetItem(f"{status_icon} {item.title} - {item.progress:.1f}%")
            list_item.setData(QtCore.Qt.ItemDataRole.UserRole, item.id)
            self.download_list.addItem(list_item)
            
    def on_download_progress(self, item: DownloadItem):
        self.update_list()
        if item.status == "downloading":
            self.progress_bar.setValue(int(item.progress))
            
    def on_download_completed(self, item: DownloadItem):
        self.update_list()
        self.progress_bar.setValue(0)
        
    def cancel_selected(self):
        current_item = self.download_list.currentItem()
        if current_item:
            item_id = current_item.data(QtCore.Qt.ItemDataRole.UserRole)
            self.download_manager.cancel_download(item_id)
            self.update_list()
            
    def open_download_folder(self):
        download_path = load_settings().get("download_path", DOWNLOAD_DIR)
        if sys.platform.startswith("win"):
            os.startfile(download_path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", download_path])
        else:
            subprocess.Popen(["xdg-open", download_path])

# ------------------- Dialogue de profil -------------------
class ProfileDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, existing: Optional[Profile] = None):
        super().__init__(parent)
        self.setWindowTitle("Profil Xtream")
        self.setModal(True)
        self.setMinimumWidth(500)

        self.edName = QtWidgets.QLineEdit()
        self.edServer = QtWidgets.QLineEdit()
        self.edUser = QtWidgets.QLineEdit()
        self.edPass = QtWidgets.QLineEdit()
        self.edPass.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)

        form = QtWidgets.QFormLayout()
        form.addRow("Nom du profil", self.edName)
        form.addRow("Serveur", self.edServer)
        form.addRow("Utilisateur", self.edUser)
        form.addRow("Mot de passe", self.edPass)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | 
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(btns)

        if existing:
            self.edName.setText(existing.name)
            self.edServer.setText(existing.server)
            self.edUser.setText(existing.user)
            self.edPass.setText(existing.password)

    def get_profile(self):
        name = self.edName.text().strip()
        server = normalize_server(self.edServer.text().strip())
        user = self.edUser.text().strip()
        pw = self.edPass.text().strip()
        
        if not all([name, server, user, pw]):
            QtWidgets.QMessageBox.warning(self, "Erreur", "Tous les champs sont requis")
            return None
            
        return Profile(name=name, server=server, user=user, password=pw)

# ------------------- Fenêtre principale améliorée -------------------
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Xtream IPTV Plus — LIVE • VOD • Séries • Recherche • Infos")
        self.resize(1400, 800)

        self.profiles = load_profiles()
        self.current_profile = None
        self.download_manager = DownloadManager()
        self.download_dialog = None

        self.setup_ui()
        self.setup_shortcuts()
        self.populate_profiles()
        self.setStyleSheet("""
        QListWidget {
        background: #0f1115;
        border: none;
        padding: 8px;
        color: #e7e9ee;
        font-size: 13px;
        }
        QListWidget::item {
        background: #151922;
        border: 1px solid #202534;
        border-radius: 12px;
        padding: 6px;
        }
        QListWidget::item:hover {
        border-color: #2d3750;
        background: #1a1f2b;
        }
        QListWidget::item:selected {
        border: 1px solid #3b82f6;
        background: rgba(59,130,246,0.15);
        }
        QToolTip {
        background-color: #0f1115;
        color: #e7e9ee;
        border: 1px solid #2d3750;
        padding: 6px;
        border-radius: 8px;
        }
        """)


    def setup_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        # Barre supérieure améliorée
        layout.addWidget(self.create_top_bar())

        # Split principal
        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        # Onglets
        self.tabs = QtWidgets.QTabWidget()
        self.liveTab = LiveTab(self.get_profile, lambda: load_favorites())
        self.vodTab = EnhancedVodTab(self.get_profile, lambda: load_favorites())
        self.seriesTab = SeriesTab(self.get_profile)
        self.searchTab = SearchTab(self.get_profile)
        self.userInfoTab = UserInfoTab(self.get_profile)

        # Connexions
        self.liveTab.playRequested.connect(self.on_play_request)
        self.vodTab.playRequested.connect(self.on_play_request)
        self.vodTab.playExternalRequested.connect(self.on_play_external_request)
        self.vodTab.downloadRequested.connect(self.on_download_request)
        self.seriesTab.playRequested.connect(self.on_play_request)
        self.searchTab.playRequested.connect(self.on_play_request)
        
        self.liveTab.statusMsg.connect(self.statusBar().showMessage)
        self.vodTab.statusMsg.connect(self.statusBar().showMessage)
        self.seriesTab.statusMsg.connect(self.statusBar().showMessage)
        self.searchTab.statusMsg.connect(self.statusBar().showMessage)

        self.tabs.addTab(self.liveTab, "📺 LIVE")
        self.tabs.addTab(self.vodTab, "🎬 VOD Amélioré")
        self.tabs.addTab(self.seriesTab, "📚 Séries")
        self.tabs.addTab(self.searchTab, "🔍 Recherche Avancée")
        self.tabs.addTab(self.userInfoTab, "📊 Infos Utilisateur")

        # Lecteur amélioré
        self.video = EnhancedVlcWidget(self)
        self.nowPlaying = QtWidgets.QLabel("Prêt.")
        self.nowPlaying.setStyleSheet("font-weight: bold; padding: 5px; color: #2a82da;")

        player_widget = QtWidgets.QWidget()
        player_layout = QtWidgets.QVBoxLayout(player_widget)
        player_layout.addWidget(self.video, 1)
        player_layout.addWidget(self.nowPlaying)

        main_splitter.addWidget(self.tabs)
        main_splitter.addWidget(player_widget)
        main_splitter.setSizes([800, 400])

        layout.addWidget(main_splitter, 1)

        # Appliquer le style
        self.apply_styles()

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: white;
            }
            QTabWidget::pane {
                border: 1px solid #555;
                background-color: #2b2b2b;
            }
            QTabBar::tab {
                background-color: #404040;
                color: white;
                padding: 8px 16px;
                margin-right: 2px;
                border-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #2a82da;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #4a4a4a;
            }
            QListWidget {
                background-color: #353535;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #444;
            }
            QListWidget::item:selected {
                background-color: #2a82da;
            }
            QLineEdit {
                background-color: #404040;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
            }
            QTextEdit {
                background-color: #404040;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton {
                background-color: #404040;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a82da;
            }
            QComboBox {
                background-color: #404040;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 8px;
            }
            QProgressBar {
                border: 2px solid #555;
                border-radius: 5px;
                text-align: center;
                background-color: #353535;
            }
            QProgressBar::chunk {
                background-color: #2a82da;
                width: 20px;
            }
        """)

    def create_top_bar(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)

        layout.addWidget(QtWidgets.QLabel("Profil:"))
        self.cmbProfiles = QtWidgets.QComboBox()
        self.cmbProfiles.setMinimumWidth(200)
        layout.addWidget(self.cmbProfiles)

        self.btnAdd = QtWidgets.QPushButton("➕ Ajouter")
        self.btnEdit = QtWidgets.QPushButton("✏️ Modifier")
        self.btnDel = QtWidgets.QPushButton("🗑️ Supprimer")
        self.btnReload = QtWidgets.QPushButton("↻ Actualiser")
        self.btnDownloads = QtWidgets.QPushButton("⏬ Téléchargements")
        self.btnSettings = QtWidgets.QPushButton("⚙️ Paramètres")

        layout.addWidget(self.btnAdd)
        layout.addWidget(self.btnEdit)
        layout.addWidget(self.btnDel)
        layout.addStretch()
        layout.addWidget(self.btnDownloads)
        layout.addWidget(self.btnSettings)
        layout.addWidget(self.btnReload)

        # Connexions
        self.cmbProfiles.currentTextChanged.connect(self.on_profile_changed)
        self.btnAdd.clicked.connect(self.add_profile)
        self.btnEdit.clicked.connect(self.edit_profile)
        self.btnDel.clicked.connect(self.del_profile)
        self.btnReload.clicked.connect(self.reload_current_tab)
        self.btnDownloads.clicked.connect(self.show_downloads)
        self.btnSettings.clicked.connect(self.show_settings)

        return widget

    def setup_shortcuts(self):
        QtGui.QShortcut(QtGui.QKeySequence("F11"), self, self.toggle_fullscreen)
        QtGui.QShortcut(QtGui.QKeySequence("Escape"), self, self.exit_fullscreen)

    def populate_profiles(self):
        self.cmbProfiles.blockSignals(True)
        self.cmbProfiles.clear()
        self.cmbProfiles.addItems(sorted(self.profiles.keys()))
        self.cmbProfiles.blockSignals(False)
        
        if self.cmbProfiles.count() > 0:
            self.cmbProfiles.setCurrentIndex(0)

    def get_profile(self):
        return self.current_profile

    def on_profile_changed(self):
        name = self.cmbProfiles.currentText()
        self.current_profile = self.profiles.get(name)
        if self.current_profile:
            self.statusBar().showMessage(f"✅ Profil chargé: {name}")
            self.reload_all_tabs()

    def reload_all_tabs(self):
        self.liveTab.reload()
        self.vodTab.reload()
        self.seriesTab.reload()
        self.userInfoTab.load_user_info()

    def reload_current_tab(self):
        idx = self.tabs.currentIndex()
        if idx == 0:
            self.liveTab.reload()
        elif idx == 1:
            self.vodTab.reload()
        elif idx == 2:
            self.seriesTab.reload()
        elif idx == 4:
            self.userInfoTab.load_user_info()

    def on_play_request(self, url: str, label: str, subtitles: List[SubtitleTrack] = None):
        if not url:
            self.video.stop()
            self.nowPlaying.setText("⏹️ Arrêté.")
            return

        if _EMBEDDED_VLC and self.video.play_url(url, subtitles):
            self.nowPlaying.setText(f"▶️ Lecture: {label}")
        else:
            self.play_external(url, label, subtitles)
            self.nowPlaying.setText(f"📺 Lecture (externe): {label}")

    def on_play_external_request(self, url: str, label: str, subtitles: List[SubtitleTrack] = None):
        self.play_external(url, label, subtitles)
        self.nowPlaying.setText(f"📺 Lecture (VLC externe): {label}")

    def play_external(self, url: str, label: str, subtitles: List[SubtitleTrack] = None):
        vlc_path = self.find_vlc_path()
        
        if not vlc_path:
            QtWidgets.QMessageBox.warning(self, "VLC non trouvé", "VLC n'a pas été trouvé sur votre système.")
            return

        try:
            command = [vlc_path, url]
            
            if subtitles and len(subtitles) > 0:
                command.extend(["--sub-file", subtitles[0].url])
            
            subprocess.Popen(command)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Impossible de lancer VLC: {e}")

    def find_vlc_path(self):
        if self.current_profile and self.current_profile.vlc_path and os.path.exists(self.current_profile.vlc_path):
            return self.current_profile.vlc_path
            
        default_paths = [
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
            "/Applications/VLC.app/Contents/MacOS/VLC",
            "/usr/bin/vlc",
            "/usr/local/bin/vlc"
        ]
        
        for path in default_paths:
            if os.path.exists(path):
                return path
                
        return None

    def on_download_request(self, item: DownloadItem):
        self.download_manager.add_download(item)
        if not self.download_dialog:
            self.download_dialog = DownloadDialog(self.download_manager, self)
        self.download_dialog.show()
        self.download_dialog.raise_()

    def show_downloads(self):
        if not self.download_dialog:
            self.download_dialog = DownloadDialog(self.download_manager, self)
        self.download_dialog.show()
        self.download_dialog.raise_()

    def show_settings(self):
        settings = load_settings()
        
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Paramètres")
        dialog.setModal(True)
        dialog.resize(400, 300)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        form = QtWidgets.QFormLayout()
        
        self.cmbDefaultPlayer = QtWidgets.QComboBox()
        self.cmbDefaultPlayer.addItems(["Lecteur intégré", "VLC externe"])
        current_player = settings.get("default_player", "embedded")
        self.cmbDefaultPlayer.setCurrentIndex(0 if current_player == "embedded" else 1)
        form.addRow("Lecteur par défaut:", self.cmbDefaultPlayer)
        
        download_layout = QtWidgets.QHBoxLayout()
        self.edDownloadPath = QtWidgets.QLineEdit(settings.get("download_path", DOWNLOAD_DIR))
        self.btnBrowseDownload = QtWidgets.QPushButton("Parcourir")
        download_layout.addWidget(self.edDownloadPath)
        download_layout.addWidget(self.btnBrowseDownload)
        form.addRow("Dossier de téléchargement:", download_layout)
        
        self.cmbSubtitleLang = QtWidgets.QComboBox()
        self.cmbSubtitleLang.addItems(["Français", "Anglais", "Automatique"])
        current_lang = settings.get("subtitle_language", "fr")
        index = 0 if current_lang == "fr" else 1 if current_lang == "en" else 2
        self.cmbSubtitleLang.setCurrentIndex(index)
        form.addRow("Langue des sous-titres:", self.cmbSubtitleLang)
        
        layout.addLayout(form)
        
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | 
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(lambda: self.save_settings(dialog))
        btns.rejected.connect(dialog.reject)
        
        self.btnBrowseDownload.clicked.connect(self.browse_download_path)
        
        layout.addWidget(btns)
        dialog.exec()

    def browse_download_path(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Sélectionner le dossier de téléchargement")
        if path:
            self.edDownloadPath.setText(path)

    def save_settings(self, dialog):
        settings = load_settings()
        settings["default_player"] = "embedded" if self.cmbDefaultPlayer.currentIndex() == 0 else "external"
        settings["download_path"] = self.edDownloadPath.text()
        
        lang_index = self.cmbSubtitleLang.currentIndex()
        settings["subtitle_language"] = "fr" if lang_index == 0 else "en" if lang_index == 1 else "auto"
        
        save_settings(settings)
        dialog.accept()
        QtWidgets.QMessageBox.information(self, "Paramètres", "✅ Paramètres sauvegardés!")

    def add_profile(self):
        dialog = ProfileDialog(self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            profile = dialog.get_profile()
            if profile:
                self.profiles[profile.name] = profile
                save_profiles(self.profiles)
                self.populate_profiles()
                self.cmbProfiles.setCurrentText(profile.name)

    def edit_profile(self):
        if not self.current_profile:
            return
        dialog = ProfileDialog(self, self.current_profile)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            profile = dialog.get_profile()
            if profile:
                if profile.name != self.current_profile.name:
                    del self.profiles[self.current_profile.name]
                self.profiles[profile.name] = profile
                save_profiles(self.profiles)
                self.populate_profiles()
                self.cmbProfiles.setCurrentText(profile.name)

    def del_profile(self):
        if not self.current_profile:
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Confirmation", f"Supprimer le profil '{self.current_profile.name}' ?"
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            name = self.current_profile.name
            del self.profiles[name]
            save_profiles(self.profiles)
            self.populate_profiles()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def exit_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()

# ------------------- Application -------------------
def main():
    app = QtWidgets.QApplication(sys.argv)
    
    # Style sombre
    app.setStyle("Fusion")
    dark_palette = QtGui.QPalette()
    dark_palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(53, 53, 53))
    dark_palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(255, 255, 255))
    dark_palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(35, 35, 35))
    dark_palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(255, 255, 255))
    dark_palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(53, 53, 53))
    dark_palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(255, 255, 255))
    app.setPalette(dark_palette)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()