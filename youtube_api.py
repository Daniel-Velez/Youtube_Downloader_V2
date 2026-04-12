import os
import sys
import time
import sqlite3
import requests
import webbrowser
import ctypes  # <--- AÑADIDO PARA LA BARRA DE TAREAS EN WINDOWS

from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QPushButton, 
                               QLineEdit, QListWidget, QWidget, QMessageBox, QLabel, 
                               QFileDialog, QHBoxLayout, QComboBox, QProgressBar, 
                               QListWidgetItem, QFrame, QStackedWidget, QDialog)
from PySide6.QtGui import QPixmap, QImage, QIcon, QFont  # <--- AÑADIDO QIcon, QFont
from PySide6.QtCore import Qt, QThread, Signal, QSize, QRunnable, QObject, QThreadPool, QProcess, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
import yt_dlp
from plyer import notification
import jaraco.text  # <-- Forzar detección para PyInstaller

# ==========================================
# CONFIGURACIÓN DE VERSIÓN Y GITHUB
# ==========================================
CURRENT_VERSION = "2.1.0"
GITHUB_REPO = "https://github.com/Daniel-Velez/Youtube_Downloader_V2/releases"

# ==========================================
# BASE DE DATOS - HISTORIAL (SQLITE)
# ==========================================
def get_db_connection():
    return sqlite3.connect("history.db", check_same_thread=False)

def init_db():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS downloads 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, type TEXT, date TEXT)
        """)

def add_to_history(title, tipo):
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO downloads (title, type, date) VALUES (?, ?, datetime('now', 'localtime'))", 
                (title, tipo)
            )
    except sqlite3.Error as e:
        print(f"Error guardando historial: {e}")

# ==========================================
# UTILIDADES Y ESTILOS PREMIUM
# ==========================================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath('.')
    return os.path.join(base_path, relative_path)

PREMIUM_DARK_STYLE = """
    QMainWindow { background-color: #0d0d12; }
    QWidget { font-family: 'Segoe UI', Roboto, sans-serif; color: #e2e2e5; }
    
    QFrame#Sidebar { background-color: #15151e; border-right: 1px solid #232333; }
    QPushButton#MenuBtn { 
        background-color: transparent; border: none; text-align: left; 
        padding: 14px 24px; font-size: 14px; font-weight: 600; color: #8a8a9d; 
        border-radius: 8px; margin: 4px 16px; 
    }
    QPushButton#MenuBtn:hover { background-color: #1e1e2b; color: #ffffff; }
    QPushButton#MenuBtn[active="true"] { 
        color: #00e5ff; background-color: #1a2235; 
        border-left: 4px solid #00e5ff; border-radius: 4px; 
    }

    QLineEdit { 
        background-color: #15151e; border: 2px solid #232333; padding: 12px 18px; 
        border-radius: 8px; color: white; font-size: 14px; font-weight: 500; 
    }
    QLineEdit:focus { border: 2px solid #00e5ff; background-color: #1a1a24; }

    QListWidget { background-color: transparent; border: none; outline: none; }
    QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0; }
    QScrollBar::handle:vertical { background: #3a3a4f; border-radius: 3px; min-height: 30px; }
    QScrollBar::handle:vertical:hover { background: #00e5ff; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

    QPushButton { 
        background-color: #232333; border: 1px solid #2a2a35; padding: 12px; 
        border-radius: 6px; font-weight: 700; font-size: 12px; color: #ffffff; 
        letter-spacing: 1px; 
    }
    QPushButton:hover { background-color: #2e2e42; border: 1px solid #3f3f4e; }
    QPushButton:pressed { background-color: #15151e; }

    QPushButton#btnSearch { background-color: #00e5ff; border: none; color: #0d0d12; }
    QPushButton#btnSearch:hover { background-color: #33eeff; }
    QPushButton#btnAudio { background-color: #00e5ff; color: #0d0d12; border: none; }
    QPushButton#btnAudio:hover { background-color: #33eeff; }
    QPushButton#btnFolder { background-color: #6c5ce7; color: white; border: none; }
    QPushButton#btnFolder:hover { background-color: #7d6ef0; }
    
    QPushButton#btnClear { 
        background-color: transparent; 
        border: 1px solid #ff4757; 
        color: #ff4757; 
    }
    QPushButton#btnClear:hover { 
        background-color: #ff4757; 
        color: white; 
    }

    QComboBox { 
        background-color: #1e1e2b; color: #e2e2e5; border: 1px solid #2a2a35; 
        border-radius: 6px; padding: 6px 12px; font-size: 12px; font-weight: 600; 
    }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView { 
        background-color: #1e1e2b; color: white; 
        selection-background-color: #00e5ff; selection-color: black; 
        border: 1px solid #2a2a35; border-radius: 4px; 
    }

    QProgressBar { 
        border: none; background-color: #232333; height: 6px; 
        text-align: center; color: transparent; border-radius: 3px; 
    }
    QProgressBar::chunk { 
        background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #00e5ff, stop:1 #6c5ce7); 
        border-radius: 3px; 
    }

    QFrame#VideoCard { background-color: #15151e; border-radius: 12px; border: 1px solid #232333; }
    QFrame#VideoCard:hover { background-color: #1a1a24; border: 1px solid #00e5ff; }
    QFrame#QueuePanel { background: #15151e; border-radius: 12px; border: 1px solid #232333; }

    QMessageBox { background-color: #15151e; border: 1px solid #232333; }
    QMessageBox QLabel { color: #ffffff; font-size: 13px; }
    QMessageBox QPushButton { 
        background-color: #00e5ff; color: black; min-width: 100px; 
        padding: 8px; font-weight: bold; border-radius: 6px;
    }
    QMessageBox QPushButton:hover { background-color: #33eeff; }
"""

# ==========================================
# HILOS DE PROCESAMIENTO
# ==========================================
class UpdateChecker(QThread):
    update_available = Signal(str, str)

    def run(self):
        try:
            api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("tag_name", "")
                release_url = data.get("html_url", "")
                
                if latest_version and latest_version != CURRENT_VERSION:
                    self.update_available.emit(latest_version, release_url)
        except requests.RequestException:
            pass 

class YtDlpSearchEngine(QThread):
    video_found = Signal(dict)
    finished_search = Signal()
    error_signal = Signal(str)
    
    def __init__(self, query, start_index=0, parent=None):
        super().__init__(parent)
        self.query = query
        self.start_index = start_index 

    def run(self):
        is_direct_link = "http" in self.query
        sq = self.query if is_direct_link else f"ytsearch100:{self.query}"
        
        opts = {
            'quiet': True, 
            'extract_flat': True, 
            'skip_download': True,
            'noplaylist': True  # FUERZA A IGNORAR PLAYLISTS Y MIXES
        }
        
        # Solo aplicamos paginación si NO es un enlace directo
        if not is_direct_link:
            inicio = self.start_index + 1
            fin = self.start_index + 20
            opts['playlist_items'] = f"{inicio}-{fin}"

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                res = ydl.extract_info(sq, download=False)
                
                if res:
                    # Unifica el formato tanto si es búsqueda como si es link directo
                    entradas = res.get('entries') if 'entries' in res else [res]
                    
                    for e in entradas:
                        if not e:
                            continue
                            
                        # Limpiar y priorizar URL
                        video_url = e.get('webpage_url') or e.get('original_url') or e.get('url')
                        if not video_url and e.get('id'):
                            video_url = f"https://www.youtube.com/watch?v={e.get('id')}"
                            
                        thumb_url = e.get('thumbnails', [{}])[-1].get('url', '')
                        
                        self.video_found.emit({
                            'titulo': e.get('title', 'Sin título'),
                            'url': video_url,
                            'thumb': thumb_url,
                            'duracion': f"{int(e.get('duration', 0)//60)}:{int(e.get('duration', 0)%60):02d}",
                            'uploader': e.get('uploader', 'YouTube')
                        })
        except Exception as e:
            self.error_signal.emit(f"Error: {str(e)[:50]}...")
        finally:
            self.finished_search.emit()

class QualityLoader(QThread):
    qualities_ready = Signal(list)
    error = Signal()

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            deno_path = resource_path("deno.exe")
            ydl_opts = {
                'quiet': True, 
                'skip_download': True, 
                'no_warnings': True,
                'noplaylist': True,
                'remote_components': 'ejs:github',  # <--- AÑADE ESTO
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                q_list = []
                seen_res = set()
                video_formats = sorted(
                    [f for f in info.get('formats', []) if f.get('height') and f.get('ext') == 'mp4'], 
                    key=lambda x: x.get('height', 0), 
                    reverse=True
                )
                
                for f in video_formats:
                    note = f.get('format_note', '')
                    height = f.get('height', 0)
                    
                    if note and 'p' in str(note).lower():
                        res = str(note)
                    else:
                        if height >= 2160: res = "2160p (4K)"
                        elif height >= 1440: res = "1440p (2K)"
                        elif height >= 1080: res = "1080p"
                        elif height >= 720: res = "720p"
                        else: res = f"{height}p"

                    if res not in seen_res:
                        q_list.append((res, f['format_id']))
                        seen_res.add(res)
                        
            self.qualities_ready.emit(q_list)
        except Exception:
            self.error.emit()

class ThumbnailSignals(QObject): 
    done = Signal(bytes, str)

class ThumbnailWorker(QRunnable):
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.signals = ThumbnailSignals()

    def run(self):
        try:
            r = requests.get(self.url, timeout=5)
            if r.status_code == 200: 
                self.signals.done.emit(r.content, self.url)
        except requests.RequestException: 
            pass

class DownloadWorker(QThread):
    progress = Signal(int)
    status = Signal(str)
    finished_dl = Signal(bool, str)

    def __init__(self, url, tipo, format_id, path, titulo, parent=None):
        super().__init__(parent)
        self.url = url
        self.tipo = tipo
        self.format_id = format_id
        self.path = path
        self.titulo = "".join([c for c in titulo if c.isalnum() or c in (' ', '-', '_')]).strip()
        self._is_paused = False
        self._is_cancelled = False

    def stop(self): 
        self._is_cancelled = True
        
    def toggle_pause(self):
        self._is_paused = not self._is_paused
        return self._is_paused

    def run(self):
        try:
            has_ffprobe = os.path.exists(resource_path('ffprobe.exe'))

            ydl_opts = {
                'ffmpeg_location': resource_path('ffmpeg.exe'),
                'outtmpl': os.path.join(self.path, f"{self.titulo}.%(ext)s"),
                'quiet': True, 
                'no_warnings': True, 
                'noprogress': True,
                'noplaylist': True,
                'remote_components': 'ejs:github',  # <--- AÑADE ESTO
                'progress_hooks': [self.progress_hook],
                'postprocessors': [],
            }

            if has_ffprobe:
                ydl_opts['writethumbnail'] = True
                ydl_opts['postprocessors'].extend([
                    {'key': 'FFmpegMetadata', 'add_metadata': True},
                    {'key': 'EmbedThumbnail', 'already_have_thumbnail': False},
                ])

            if self.tipo == "audio":
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'].insert(0, {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'})
            else:
                fmt = f"{self.format_id}+bestaudio/best" if self.format_id else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                ydl_opts['format'] = fmt
                ydl_opts['merge_output_format'] = 'mp4'

            self.status.emit("Iniciando descarga...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: 
                ydl.download([self.url])

            final_ext = "mp3" if self.tipo == "audio" else "mp4"
            final_file = os.path.join(self.path, f"{self.titulo}.{final_ext}")

            if not self._is_cancelled: 
                self.finished_dl.emit(True, final_file)

        except Exception as e:
            if self._is_cancelled: 
                self.finished_dl.emit(False, "Descarga cancelada.")
            else: 
                self.finished_dl.emit(False, str(e))

    def progress_hook(self, d):
        while self._is_paused and not self._is_cancelled: 
            time.sleep(0.2)
            
        if self._is_cancelled: 
            raise Exception("Cancelado")

        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            if total and total > 0:
                self.progress.emit(int((downloaded / total) * 100))
                self.status.emit(f"Descargando ({downloaded / (1024*1024):.1f} / {total / (1024*1024):.1f} MB)...")
            else:
                self.status.emit(f"Descargando ({downloaded / (1024*1024):.1f} MB)...")
        elif d['status'] == 'finished':
            self.progress.emit(100)
            self.status.emit("Procesando y guardando...")

# ==========================================
# VENTANA DE PREVISUALIZACIÓN (REPRODUCTOR)
# ==========================================
class StreamFetcher(QThread):
    stream_url_ready = Signal(str)
    error = Signal(str)

    def __init__(self, yt_url, parent=None):
        super().__init__(parent)
        self.yt_url = yt_url

    def run(self):
        ydl_opts = {'format': 'best', 'quiet': True, 'noplaylist': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.yt_url, download=False)
                self.stream_url_ready.emit(info['url'])
        except Exception as e:
            self.error.emit(str(e))

class PreviewDialog(QDialog):
    def __init__(self, video_url, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Previsualización: {title}")
        self.setFixedSize(800, 480)
        self.setStyleSheet("""
            QDialog { background-color: #0d0d12; border: 1px solid #232333; color: #e2e2e5; }
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.loading_lbl = QLabel("Cargando stream de alta velocidad... ⚡")
        self.loading_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #00e5ff;")
        self.loading_lbl.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.loading_lbl)
        
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: black;")
        self.layout.addWidget(self.video_widget)
        self.video_widget.hide()
        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.audio_output.setVolume(0.8)
        
        self.fetcher = StreamFetcher(video_url)
        self.fetcher.stream_url_ready.connect(self.play_video)
        self.fetcher.error.connect(self.show_error)
        self.fetcher.start()

    def play_video(self, stream_url):
        self.loading_lbl.hide()
        self.video_widget.show()
        self.player.setSource(QUrl(stream_url))
        self.player.play()

    def show_error(self, err_msg):
        self.loading_lbl.setText("Error al cargar el stream. El video podría tener restricciones.")
        self.loading_lbl.setStyleSheet("color: #ff4757;")
        print(f"Stream error: {err_msg}")

    def closeEvent(self, event):
        self.player.stop()
        if self.fetcher.isRunning():
            self.fetcher.terminate()
            self.fetcher.wait()
        super().closeEvent(event)

# ==========================================
# WIDGET DE TARJETA DE VIDEO
# ==========================================
class VideoCard(QFrame):
    def __init__(self, data, cache_refe, parent=None):
        super().__init__(parent)
        self.url = data['url']
        self.thumb_url = data['thumb']
        self.cache = cache_refe  
        self.q_ready = False
        self.setObjectName("VideoCard")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 15, 20, 15)
        layout.setSpacing(20)
        
        self.img = QLabel()
        self.img.setFixedSize(160, 90)
        self.img.setStyleSheet("background-color: #0d0d12; border-radius: 8px;")
        self.img.setScaledContents(True)
        
        info_lyt = QVBoxLayout()
        info_lyt.setSpacing(5)
        
        self.title_lbl = QLabel(data['titulo'])
        self.title_lbl.setStyleSheet("font-size: 15px; color: #ffffff; font-weight: 700; background:transparent; border:none;")
        self.title_lbl.setWordWrap(True)
        
        self.meta_lbl = QLabel(f"● {data['uploader']}   |   ⏳ {data['duracion']}")
        self.meta_lbl.setStyleSheet("color: #8a8a9d; font-size: 12px; font-weight: 600; background:transparent; border:none;")
        
        self.btn_preview = QPushButton("▶ PREVIA")
        self.btn_preview.setFixedSize(80, 26)
        self.btn_preview.setStyleSheet("""
            QPushButton { background-color: #e50914; color: white; border-radius: 4px; font-size: 10px; padding: 0px; letter-spacing: 0px;}
            QPushButton:hover { background-color: #f6121d; }
        """)
        self.btn_preview.clicked.connect(self.show_preview)

        bottom = QHBoxLayout()
        bottom.addWidget(self.meta_lbl)
        bottom.addStretch()
        bottom.addWidget(self.btn_preview)
        
        self.combo = QComboBox()
        self.combo.addItem("Calidad...", None)
        self.combo.setFixedWidth(110)
        bottom.addWidget(self.combo)
        
        info_lyt.addWidget(self.title_lbl)
        info_lyt.addStretch()
        info_lyt.addLayout(bottom)
        
        layout.addWidget(self.img)
        layout.addLayout(info_lyt, 1)

        if self.thumb_url in self.cache: 
            self.set_thumb(self.cache[self.thumb_url])
        else:
            worker = ThumbnailWorker(self.thumb_url)
            worker.signals.done.connect(self.save_and_set_thumb)
            QThreadPool.globalInstance().start(worker)

    def show_preview(self):
        self.preview_window = PreviewDialog(self.url, self.title_lbl.text(), self)
        self.preview_window.exec()

    def save_and_set_thumb(self, content, url):
        self.cache[url] = content 
        self.set_thumb(content)

    def set_thumb(self, content):
        px = QImage()
        if px.loadFromData(content): 
            self.img.setPixmap(QPixmap.fromImage(px))

# ==========================================
# CLASE PRINCIPAL - INTERFAZ
# ==========================================
class YoutubeDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()
        self.setStyleSheet(PREMIUM_DARK_STYLE)
        self.setWindowTitle(f"Dynatube Pro - {CURRENT_VERSION}")
        self.setMinimumSize(1200, 800)
        
        # --- APLICAR ICONO A LA VENTANA ---
        # Asegúrate de colocar un archivo llamado "icon.ico" en la misma carpeta de tu script.
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.download_path = os.path.join(os.path.expanduser("~"), "Downloads")
        self.is_loading = False
        self.current_page = 0
        self.last_query = ""
        self.download_queue = []
        self.is_downloading = False 
        self.thumbnail_cache = {}
        
        self.search_thr = None
        self.q_thr = None
        self.current_worker = None
        self.local_process = None 
        
        self.threadpool = QThreadPool.globalInstance()
        self.threadpool.setMaxThreadCount(max(4, QThread.idealThreadCount() // 2))

        self.init_ui()
        self.check_for_updates()

    def check_for_updates(self):
        self.updater_thread = UpdateChecker()
        self.updater_thread.update_available.connect(self.show_update_dialog)
        self.updater_thread.start()

    def show_update_dialog(self, latest_version, url):
        msg = QMessageBox(self)
        msg.setWindowTitle("¡Actualización Disponible!")
        msg.setText(f"<h3>Una nueva versión está lista</h3>"
                    f"<p>La versión <b>{latest_version}</b> ya está disponible en GitHub.</p>"
                    f"<p>Versión actual: {CURRENT_VERSION}</p>"
                    f"<p>¿Deseas abrir el navegador para descargarla de forma manual?</p>")
        msg.setIcon(QMessageBox.Icon.Information)
        
        btn_yes = msg.addButton("Descargar de GitHub", QMessageBox.ButtonRole.AcceptRole)
        btn_no = msg.addButton("Quizás más tarde", QMessageBox.ButtonRole.RejectRole)
        btn_no.setStyleSheet("background-color: #2a2a35; color: white;")
        
        msg.exec()
        if msg.clickedButton() == btn_yes:
            webbrowser.open(url)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- MENU LATERAL ---
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(280)
        side_lyt = QVBoxLayout(self.sidebar)
        side_lyt.setContentsMargins(0, 40, 0, 20)
        side_lyt.setSpacing(8)
        
        header = QLabel("⚡ Dynatube Pro")
        header.setStyleSheet("font-weight: 900; font-size: 24px; color: white; padding: 0px 20px 30px 20px; letter-spacing: 2px;")
        side_lyt.addWidget(header)

        self.btn_nav_search = self.create_nav_btn("🔍  Buscar y Descargar", 0, True)
        self.btn_nav_conv = self.create_nav_btn("🔄  Convertidor Local", 1)
        self.btn_nav_hist = self.create_nav_btn("📜  Historial de Descargas", 2)

        side_lyt.addWidget(self.btn_nav_search)
        side_lyt.addWidget(self.btn_nav_conv)
        side_lyt.addWidget(self.btn_nav_hist)
        side_lyt.addStretch()
        
        version_lbl = QLabel(f"Versión: {CURRENT_VERSION}")
        version_lbl.setStyleSheet("color: #4a4a59; font-size: 11px; font-weight: bold; padding-left: 24px;")
        side_lyt.addWidget(version_lbl)
        
        layout.addWidget(self.sidebar)

        # --- PANTALLAS ---
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        self.setup_search_page()
        self.setup_converter_page()
        self.setup_history_page()

    def create_nav_btn(self, text, index, is_active=False):
        btn = QPushButton(text)
        btn.setObjectName("MenuBtn")
        btn.setProperty("active", is_active)
        btn.clicked.connect(lambda: self.switch_page(index))
        return btn

    def setup_search_page(self):
        page = QWidget()
        lyt = QVBoxLayout(page)
        lyt.setContentsMargins(40, 40, 40, 40)
        lyt.setSpacing(25)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(15)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Pega el enlace de YouTube o ingresa términos de búsqueda...")
        self.search_input.returnPressed.connect(self.start_search)
        
        btn_search = QPushButton("BUSCAR")
        btn_search.setObjectName("btnSearch")
        btn_search.setFixedSize(130, 44)
        btn_search.clicked.connect(self.start_search)
        
        btn_folder = QPushButton("DIRECTORIO")
        btn_folder.setObjectName("btnFolder")
        btn_folder.setFixedSize(130, 44)
        btn_folder.clicked.connect(self.select_folder)

        top_bar.addWidget(self.search_input)
        top_bar.addWidget(btn_search)
        top_bar.addWidget(btn_folder)
        lyt.addLayout(top_bar)

        self.path_display = QLabel(f"Guardando en: {self.download_path}")
        self.path_display.setStyleSheet("color: #8a8a9d; font-size: 12px; font-weight: 600;")
        lyt.addWidget(self.path_display)

        body_lyt = QHBoxLayout()
        body_lyt.setSpacing(25)
        
        self.result_list = QListWidget()
        self.result_list.itemSelectionChanged.connect(self.load_qualities)
        self.result_list.verticalScrollBar().valueChanged.connect(self.handle_scroll)
        body_lyt.addWidget(self.result_list, 6)

        queue_panel = QFrame()
        queue_panel.setObjectName("QueuePanel")
        queue_lyt = QVBoxLayout(queue_panel)
        queue_lyt.setContentsMargins(20, 20, 20, 20)
        queue_lyt.setSpacing(15)
        
        lbl_queue = QLabel("COLA DE DESCARGAS")
        lbl_queue.setStyleSheet("color: #ffffff; font-weight: 800; font-size: 13px; letter-spacing: 1px;")
        queue_lyt.addWidget(lbl_queue)
        
        self.queue_list_widget = QListWidget()
        self.queue_list_widget.setStyleSheet(
            "QListWidget { border: none; background: transparent; } "
            "QListWidget::item { padding: 10px; color: #b0b0c0; border-bottom: 1px solid #232333; }"
        )
        queue_lyt.addWidget(self.queue_list_widget)

        ctrl_lyt = QHBoxLayout()
        
        self.btn_pause = QPushButton("PAUSAR")
        self.btn_pause.setStyleSheet("background-color: #ff2a6d; color: white; border: none; border-radius: 6px;")
        self.btn_pause.clicked.connect(self.toggle_pause)
        
        btn_clear = QPushButton("LIMPIAR")
        btn_clear.setObjectName("btnClear")
        btn_clear.clicked.connect(self.clear_queue)
        
        ctrl_lyt.addWidget(self.btn_pause)
        ctrl_lyt.addWidget(btn_clear)
        queue_lyt.addLayout(ctrl_lyt)
        
        body_lyt.addWidget(queue_panel, 4) 
        lyt.addLayout(body_lyt)

        action_lyt = QHBoxLayout()
        action_lyt.setSpacing(20)
        
        btn_dl_video = QPushButton("⬇️ DESCARGAR MP4")
        btn_dl_video.setFixedHeight(50)
        btn_dl_video.clicked.connect(lambda: self.start_dl("video"))
        
        btn_dl_audio = QPushButton("🎵 EXTRAER MP3")
        btn_dl_audio.setObjectName("btnAudio")
        btn_dl_audio.setFixedHeight(50)
        btn_dl_audio.clicked.connect(lambda: self.start_dl("audio"))

        action_lyt.addWidget(btn_dl_video)
        action_lyt.addWidget(btn_dl_audio)
        lyt.addLayout(action_lyt)

        status_lyt = QHBoxLayout()
        self.status_lbl = QLabel("ESTADO: EN ESPERA")
        self.status_lbl.setStyleSheet("color: #00e5ff; font-weight: 800; font-size: 11px; letter-spacing: 1px;")
        status_lyt.addWidget(self.status_lbl)
        
        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(6)
        lyt.addLayout(status_lyt)
        lyt.addWidget(self.pbar)

        self.stack.addWidget(page)

    def setup_converter_page(self):
        page = QWidget()
        lyt = QVBoxLayout(page)
        lyt.setAlignment(Qt.AlignCenter)
        lyt.setSpacing(30)
        
        icon_lbl = QLabel("⚡")
        icon_lbl.setStyleSheet("font-size: 48px;")
        icon_lbl.setAlignment(Qt.AlignCenter)
        
        title = QLabel("Conversión Local Multimedia")
        title.setStyleSheet("font-size: 24px; color: white; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)

        lbl = QLabel("Convierte tus archivos de video a audio sin salir de la aplicación.")
        lbl.setStyleSheet("color: #8a8a9d; font-size: 14px; font-weight: 500;")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        
        btn_conv = QPushButton("SELECCIONAR ARCHIVOS MULTIMEDIA")
        btn_conv.setFixedSize(350, 50)
        btn_conv.setStyleSheet("background: #00e5ff; color: black; font-size: 13px;")
        btn_conv.clicked.connect(self.start_local_conversion)
        
        self.conv_status = QLabel("Listo para procesar.")
        self.conv_status.setStyleSheet("color: #00e5ff; font-weight: bold;")
        self.conv_status.setAlignment(Qt.AlignCenter)
        
        self.conv_pbar = QProgressBar()
        self.conv_pbar.setFixedWidth(400)
        self.conv_pbar.setFixedHeight(8)
        
        lyt.addWidget(icon_lbl)
        lyt.addWidget(title)
        lyt.addWidget(lbl)
        lyt.addWidget(btn_conv, alignment=Qt.AlignCenter)
        lyt.addWidget(self.conv_status)
        lyt.addWidget(self.conv_pbar, alignment=Qt.AlignCenter)
        
        self.stack.addWidget(page)

    def setup_history_page(self):
        page = QWidget()
        lyt = QVBoxLayout(page)
        lyt.setContentsMargins(40, 40, 40, 40)
        lyt.setSpacing(20)
        
        title = QLabel("REGISTRO SQL DE DESCARGAS")
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: white; letter-spacing: 1px;")
        lyt.addWidget(title)
        
        self.hist_list = QListWidget()
        self.hist_list.setStyleSheet("""
            QListWidget { background: #15151e; border: 1px solid #232333; border-radius: 12px; padding: 15px; } 
            QListWidget::item { padding: 12px; border-bottom: 1px solid #232333; color: #e2e2e5; font-size: 13px; font-weight: 500;} 
            QListWidget::item:hover { background: #1a1a24; border-radius: 6px;}
        """)
        lyt.addWidget(self.hist_list)
        
        btn_refresh = QPushButton("ACTUALIZAR REGISTRO")
        btn_refresh.setFixedSize(200, 44)
        btn_refresh.setStyleSheet("background-color: #6c5ce7; border: none;")
        btn_refresh.clicked.connect(self.load_history)
        lyt.addWidget(btn_refresh, alignment=Qt.AlignRight)
        
        self.stack.addWidget(page)

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        buttons = [self.btn_nav_search, self.btn_nav_conv, self.btn_nav_hist]
        for i, btn in enumerate(buttons):
            btn.setProperty("active", i == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        
        if index == 2: 
            self.load_history()

    def load_history(self):
        self.hist_list.clear()
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT title, type, date FROM downloads ORDER BY id DESC LIMIT 100")
            for row in cursor.fetchall():
                emoji = "🎵" if row[1] == "audio" else "🎬"
                item = QListWidgetItem(f"{emoji}   {row[0]}   —   {row[2]}")
                self.hist_list.addItem(item)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta")
        if folder: 
            self.download_path = folder
            self.path_display.setText(f"Guardando en: {folder}")

    def safe_stop_thread(self, thread_attr):
        thread = getattr(self, thread_attr, None)
        if thread and thread.isRunning():
            try: 
                thread.disconnect() 
            except Exception: 
                pass 
            thread.quit()
            thread.wait()

    def start_search(self):
        q = self.search_input.text().strip()
        if not q: return
        self.result_list.clear()
        self.last_query = q
        self.current_page = 0 
        self.execute_search()

    def execute_search(self):
        if self.is_loading: return
        self.safe_stop_thread('search_thr') 
        self.is_loading = True
        self.status_lbl.setText("ESTADO: BUSCANDO RESULTADOS...")
        self.status_lbl.setStyleSheet("color: #ff9f43; font-weight: 800; font-size: 11px; letter-spacing: 1px;")
        
        self.search_thr = YtDlpSearchEngine(self.last_query, self.current_page)
        self.search_thr.video_found.connect(self.add_video_card)
        self.search_thr.error_signal.connect(lambda e: self.status_lbl.setText(f"ERROR: {e.upper()}"))
        self.search_thr.finished_search.connect(self.on_search_finished)
        self.search_thr.start()

    def on_search_finished(self):
        self.is_loading = False
        if "ERROR" not in self.status_lbl.text():
            self.status_lbl.setText("ESTADO: BÚSQUEDA COMPLETADA")
            self.status_lbl.setStyleSheet("color: #00e5ff; font-weight: 800; font-size: 11px; letter-spacing: 1px;")

    def add_video_card(self, data):
        item = QListWidgetItem(self.result_list)
        item.setSizeHint(QSize(0, 130))
        card = VideoCard(data, self.thumbnail_cache) 
        self.result_list.setItemWidget(item, card)

    def handle_scroll(self, val):
        if val > self.result_list.verticalScrollBar().maximum() * 0.9 and not self.is_loading and self.last_query:
            self.current_page += 20 
            self.execute_search()

    def load_qualities(self):
        item = self.result_list.currentItem()
        if not item: return
        w = self.result_list.itemWidget(item)
        if not w.q_ready:
            self.safe_stop_thread('q_thr')
            w.combo.clear()
            w.combo.addItem("Cargando...", None)
            self.q_thr = QualityLoader(w.url)
            self.q_thr.qualities_ready.connect(lambda q: self.fill_combo(w, q))
            self.q_thr.start()

    def fill_combo(self, widget, qualities):
        try:
            if widget is not None and not widget.isHidden():
                widget.combo.clear()
                for res, itag in qualities: 
                    widget.combo.addItem(res, itag)
                widget.q_ready = True
        except RuntimeError: 
            pass

    def start_dl(self, tipo):
        item = self.result_list.currentItem()
        if not item: 
            QMessageBox.warning(self, "Aviso", "Selecciona un video de la lista primero.")
            return
            
        w = self.result_list.itemWidget(item)
        if tipo == "video" and w.combo.currentData() is None:
            QMessageBox.warning(self, "Aviso", "Espera a que carguen las calidades.")
            return

        task = {
            'url': w.url, 'tipo': tipo, 'itag': w.combo.currentData(),
            'path': self.download_path, 'titulo': w.title_lbl.text()
        }
        self.download_queue.append(task)
        self.queue_list_widget.addItem(task['titulo'])
        
        if not self.is_downloading: 
            self.process_next_in_queue()

    def process_next_in_queue(self):
        if not self.download_queue:
            self.is_downloading = False
            self.status_lbl.setText("ESTADO: TODAS LAS TAREAS COMPLETADAS")
            self.pbar.setValue(0)
            
            # --- RESETEA EL BOTÓN DE PAUSA A MAGENTA ---
            self.btn_pause.setText("PAUSAR")
            self.btn_pause.setStyleSheet("background-color: #ff2a6d; color: white; border: none; border-radius: 6px;")
            return

        self.is_downloading = True
        task = self.download_queue[0]
        
        self.current_worker = DownloadWorker(task['url'], task['tipo'], task['itag'], task['path'], task['titulo'])
        self.current_worker.progress.connect(self.pbar.setValue)
        
        self.current_worker.status.connect(lambda s: self.status_lbl.setText(f"ESTADO: {s.upper()}"))
        self.current_worker.finished_dl.connect(lambda ok, msg: self.finish_download(ok, msg, task))
        self.current_worker.start()

    def finish_download(self, ok, msg, task):
        if ok:
            try: 
                notification.notify(title="¡Descarga Finalizada! ✅", message=task['titulo'], app_name="YT Pro", timeout=5)
            except: 
                pass
            add_to_history(task['titulo'], task['tipo'])
        else:
            QMessageBox.warning(self, "Error de Descarga", msg)

        if self.download_queue: 
            self.download_queue.pop(0)
        if self.queue_list_widget.count() > 0: 
            self.queue_list_widget.takeItem(0)

        self.process_next_in_queue()

    def toggle_pause(self):
        if self.current_worker and self.current_worker.isRunning():
            is_paused = self.current_worker.toggle_pause()
            if is_paused:
                self.btn_pause.setText("REANUDAR")
                self.btn_pause.setStyleSheet("background-color: #00e5ff; color: black; border: none; border-radius: 6px;")
                self.status_lbl.setText("ESTADO: DESCARGA EN PAUSA")
            else:
                self.btn_pause.setText("PAUSAR")
                self.btn_pause.setStyleSheet("background-color: #ff2a6d; color: white; border: none; border-radius: 6px;")

    def clear_queue(self):
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.stop()
        
        self.download_queue.clear()
        self.queue_list_widget.clear()
        self.is_downloading = False
        self.status_lbl.setText("ESTADO: COLA VACIADA")
        self.pbar.setValue(0)
        
        self.btn_pause.setText("PAUSAR")
        self.btn_pause.setStyleSheet("background-color: #ff2a6d; color: white; border: none; border-radius: 6px;")

    def start_local_conversion(self):
        if self.local_process and self.local_process.state() == QProcess.ProcessState.Running:
            QMessageBox.warning(self, "Aviso", "Ya hay una conversión en curso.")
            return

        files, _ = QFileDialog.getOpenFileNames(self, "Seleccionar videos", "", "Videos (*.mp4 *.mkv *.avi *.webm *.mov)")
        if not files: return

        self.conv_queue = [f for f in files if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm'))]
        self.total_conv = len(self.conv_queue)
        
        if self.total_conv == 0: return

        self.conv_pbar.setValue(0)
        self.process_next_conversion()

    def process_next_conversion(self):
        if not self.conv_queue:
            QMessageBox.information(self, "Completado", f"Se convirtieron {self.total_conv} archivos.")
            self.conv_status.setText("Conversión Finalizada con Éxito")
            self.conv_pbar.setValue(0)
            return

        current_file = self.conv_queue.pop(0)
        output_path = f"{os.path.splitext(current_file)[0]}.mp3"
        self.conv_status.setText(f"Procesando: {os.path.basename(current_file)}")

        self.local_process = QProcess(self)
        
        # <--- RUTA PORTABLE AÑADIDA AQUÍ
        command = resource_path('ffmpeg.exe') 
        
        args = [
            '-y', 
            '-i', current_file, 
            '-vn', 
            '-c:a', 'libmp3lame', 
            '-q:a', '2', 
            '-threads', '0', 
            output_path
        ]

        self.local_process.finished.connect(self.on_conversion_finished)
        self.local_process.start(command, args)

    def on_conversion_finished(self, exitCode, exitStatus):
        if exitCode == 0:
            converted = self.total_conv - len(self.conv_queue)
            self.conv_pbar.setValue(int((converted / self.total_conv) * 100))
            self.process_next_conversion()
        else:
            QMessageBox.critical(self, "Error", "Error durante la conversión de hardware.")
            self.conv_queue.clear()
            self.conv_status.setText("Operación Interrumpida")
            self.conv_pbar.setValue(0)

if __name__ == "__main__":
    # --- AÑADIDO PARA FORZAR EL ICONO EN LA BARRA DE TAREAS DE WINDOWS ---
    try:
        myappid = 'danielvelez.ytdownloader.v2'  # ID único arbitrario
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass
        
    app = QApplication(sys.argv)
    
    # --- EVITAR ADVERTENCIA DirectWrite DE FUENTES (8514oem) ---
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # OPCIONAL: Establecer el icono globalmente en toda la app
    # app.setWindowIcon(QIcon(resource_path("icon.ico")))
    
    window = YoutubeDownloader()
    window.show()
    sys.exit(app.exec())