import os
import sys
import time
import sqlite3
import requests
import webbrowser
import ctypes

from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QPushButton,
                               QLineEdit, QListWidget, QWidget, QMessageBox, QLabel,
                               QFileDialog, QHBoxLayout, QComboBox, QProgressBar,
                               QListWidgetItem, QFrame, QStackedWidget, QDialog,
                               QSizePolicy)
from PySide6.QtGui import QPixmap, QImage, QIcon, QFont, QFontMetrics
from PySide6.QtCore import Qt, QThread, Signal, QSize, QRunnable, QObject, QThreadPool, QProcess, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
import yt_dlp
from plyer import notification
import jaraco.text
import platformdirs

# ==========================================
# CONFIGURACIÓN DE VERSIÓN Y GITHUB
# ==========================================
CURRENT_VERSION = "2.1.1"
GITHUB_REPO = "Daniel-Velez/Youtube_Downloader_V2"
MAX_THUMBNAIL_CACHE = 200

# ==========================================
# BASE DE DATOS
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
# UTILIDADES
# ==========================================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath('.')
    return os.path.join(base_path, relative_path)

# ==========================================
# ESTILOS
# ==========================================
PREMIUM_DARK_STYLE = """
    QMainWindow { background-color: #0d0d12; }
    QWidget { font-family: 'Segoe UI', sans-serif; color: #e2e2e5; }

    QFrame#Sidebar {
        background-color: #111118;
        border-right: 1px solid #1e1e2a;
    }

    QPushButton#MenuBtn {
        background-color: transparent; border: none; text-align: left;
        padding: 13px 22px; font-size: 13px; font-weight: 600; color: #6a6a7d;
        border-radius: 8px; margin: 2px 12px;
    }
    QPushButton#MenuBtn:hover { background-color: #1a1a24; color: #ccccdd; }
    QPushButton#MenuBtn[active="true"] {
        color: #00e5ff; background-color: #0d1f2d;
        border-left: 3px solid #00e5ff; padding-left: 19px;
        border-radius: 0px 8px 8px 0px;
    }

    QLineEdit {
        background-color: #13131c; border: 1.5px solid #1e1e2a; padding: 11px 16px;
        border-radius: 10px; color: white; font-size: 14px;
    }
    QLineEdit:focus { border: 1.5px solid #00e5ff; background-color: #16161f; }
    QLineEdit::placeholder { color: #44445a; }

    QListWidget { background-color: transparent; border: none; outline: none; }
    QScrollBar:vertical { border: none; background: transparent; width: 4px; }
    QScrollBar::handle:vertical { background: #2a2a3a; border-radius: 2px; min-height: 24px; }
    QScrollBar::handle:vertical:hover { background: #00e5ff; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

    QPushButton {
        background-color: #1e1e2b; border: 1px solid #252535; padding: 10px 16px;
        border-radius: 8px; font-weight: 700; font-size: 12px; color: #e2e2e5;
        letter-spacing: 0.5px;
    }
    QPushButton:hover { background-color: #28283a; border-color: #363650; }
    QPushButton:pressed { background-color: #13131c; }

    QPushButton#btnSearch {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00c8e0, stop:1 #0099bb);
        border: none; color: #050a0c; font-weight: 800; border-radius: 10px;
    }
    QPushButton#btnSearch:hover {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #33d4ed, stop:1 #00b0cc);
    }
    QPushButton#btnFolder {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #7c6df0, stop:1 #5a4dcc);
        border: none; color: white; font-weight: 800; border-radius: 10px;
    }
    QPushButton#btnFolder:hover {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #9480f5, stop:1 #7060e0);
    }

    QPushButton#btnClear {
        background-color: transparent; border: 1px solid #cc3344; color: #cc3344;
        border-radius: 8px;
    }
    QPushButton#btnClear:hover { background-color: #cc3344; color: white; }

    QComboBox {
        background-color: #1a1a26; color: #c8c8d8; border: 1px solid #252535;
        border-radius: 6px; padding: 5px 10px; font-size: 12px; font-weight: 600;
    }
    QComboBox::drop-down { border: none; width: 20px; }
    QComboBox QAbstractItemView {
        background-color: #1a1a26; color: white;
        selection-background-color: #00e5ff; selection-color: #050a0c;
        border: 1px solid #252535; border-radius: 6px;
    }

    QProgressBar {
        border: none; background-color: #1a1a26; height: 5px;
        text-align: center; color: transparent; border-radius: 3px;
    }
    QProgressBar::chunk {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 #00e5ff, stop:0.5 #5f72ff, stop:1 #a855f7);
        border-radius: 3px;
    }

    QFrame#VideoCard {
        background-color: #13131c;
        border-radius: 12px;
        border: 1px solid #1e1e2a;
    }
    QFrame#VideoCard:hover {
        background-color: #16161f;
        border: 1px solid #2a2a3e;
    }

    QFrame#QueuePanel {
        background: #111118; border-radius: 14px; border: 1px solid #1e1e2a;
    }

    QMessageBox { background-color: #13131c; }
    QMessageBox QLabel { color: #ffffff; font-size: 13px; }
    QMessageBox QPushButton {
        background-color: #00e5ff; color: #050a0c; min-width: 90px;
        padding: 8px; font-weight: 800; border-radius: 8px; border: none;
    }
    QMessageBox QPushButton:hover { background-color: #33eeff; }
"""

# ==========================================
# HILOS
# ==========================================
class UpdateChecker(QThread):
    update_available = Signal(str, str)
    def run(self):
        try:
            api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            r = requests.get(api_url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                latest = data.get("tag_name", "").lstrip("v")
                url = data.get("html_url", "")
                if latest and latest != CURRENT_VERSION:
                    self.update_available.emit(latest, url)
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
        is_link = "http" in self.query
        sq = self.query if is_link else f"ytsearch100:{self.query}"
        opts = {'quiet': True, 'extract_flat': True, 'skip_download': True, 'noplaylist': True}
        if not is_link:
            opts['playlist_items'] = f"{self.start_index+1}-{self.start_index+20}"
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                res = ydl.extract_info(sq, download=False)
                if res:
                    entries = res.get('entries') if 'entries' in res else [res]
                    for e in (entries or []):
                        if not e:
                            continue
                        url = e.get('webpage_url') or e.get('original_url') or e.get('url')
                        if not url and e.get('id'):
                            url = f"https://www.youtube.com/watch?v={e['id']}"
                        thumb = e.get('thumbnails', [{}])[-1].get('url', '')
                        dur = e.get('duration', 0) or 0
                        self.video_found.emit({
                            'titulo': e.get('title', 'Sin título'),
                            'url': url,
                            'thumb': thumb,
                            'duracion': f"{int(dur//60)}:{int(dur%60):02d}",
                            'uploader': e.get('uploader', 'YouTube'),
                        })
        except Exception as e:
            self.error_signal.emit(str(e)[:60])
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
            opts = {'quiet': True, 'skip_download': True, 'no_warnings': True, 'noplaylist': True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                q_list, seen = [], set()
                formats = sorted(
                    [f for f in info.get('formats', []) if f.get('height') and f.get('ext') == 'mp4'],
                    key=lambda x: x.get('height', 0), reverse=True
                )
                for f in formats:
                    note = f.get('format_note', '')
                    h = f.get('height', 0)
                    if note and 'p' in str(note).lower():
                        res = str(note)
                    else:
                        if h >= 2160: res = "2160p (4K)"
                        elif h >= 1440: res = "1440p (2K)"
                        elif h >= 1080: res = "1080p"
                        elif h >= 720: res = "720p"
                        else: res = f"{h}p"
                    if res not in seen:
                        q_list.append((res, f['format_id']))
                        seen.add(res)
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
        sanitized = "".join(c for c in titulo if c.isalnum() or c in (' ', '-', '_')).strip()
        self.titulo = sanitized if sanitized else "descarga_sin_titulo"
        self._is_paused = False
        self._is_cancelled = False

    def stop(self): self._is_cancelled = True
    def toggle_pause(self):
        self._is_paused = not self._is_paused
        return self._is_paused

    def run(self):
        try:
            has_ffprobe = os.path.exists(resource_path('ffprobe.exe'))
            opts = {
                'ffmpeg_location': resource_path('ffmpeg.exe'),
                'outtmpl': os.path.join(self.path, f"{self.titulo}.%(ext)s"),
                'quiet': True, 'no_warnings': True, 'noprogress': True,
                'noplaylist': True, 'progress_hooks': [self.progress_hook],
                'postprocessors': [],
            }
            if has_ffprobe:
                opts['writethumbnail'] = True
                opts['postprocessors'].extend([
                    {'key': 'FFmpegMetadata', 'add_metadata': True},
                    {'key': 'EmbedThumbnail', 'already_have_thumbnail': False},
                ])
            if self.tipo == "audio":
                opts['format'] = 'bestaudio/best'
                opts['postprocessors'].insert(0, {
                    'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'
                })
            else:
                fmt = f"{self.format_id}+bestaudio/best" if self.format_id \
                    else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                opts['format'] = fmt
                opts['merge_output_format'] = 'mp4'

            self.status.emit("Iniciando descarga...")
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([self.url])

            ext = "mp3" if self.tipo == "audio" else "mp4"
            final = os.path.join(self.path, f"{self.titulo}.{ext}")
            if not self._is_cancelled:
                self.finished_dl.emit(True, final)
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
            dl = d.get('downloaded_bytes', 0)
            if total and total > 0:
                self.progress.emit(int(dl / total * 100))
                self.status.emit(f"Descargando ({dl/(1024*1024):.1f} / {total/(1024*1024):.1f} MB)...")
            else:
                self.status.emit(f"Descargando ({dl/(1024*1024):.1f} MB)...")
        elif d['status'] == 'finished':
            self.progress.emit(100)
            self.status.emit("Procesando y guardando...")


class StreamFetcher(QThread):
    stream_url_ready = Signal(str)
    error = Signal(str)

    def __init__(self, yt_url, parent=None):
        super().__init__(parent)
        self.yt_url = yt_url
        self._cancelled = False

    def cancel(self): self._cancelled = True

    def run(self):
        opts = {'format': 'best', 'quiet': True, 'noplaylist': True}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.yt_url, download=False)
                if not self._cancelled:
                    self.stream_url_ready.emit(info['url'])
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))


# ==========================================
# DIÁLOGO DE PREVISUALIZACIÓN
# ==========================================
class PreviewDialog(QDialog):
    def __init__(self, video_url, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Previsualización: {title}")
        self.setFixedSize(840, 500)
        self.setStyleSheet("QDialog { background-color: #0d0d12; border: 1px solid #1e1e2a; }")
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)

        self.loading_lbl = QLabel("Cargando stream... ⚡")
        self.loading_lbl.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #00e5ff; padding: 20px;"
        )
        self.loading_lbl.setAlignment(Qt.AlignCenter)
        lyt.addWidget(self.loading_lbl)

        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background: black;")
        lyt.addWidget(self.video_widget)
        self.video_widget.hide()

        self.player = QMediaPlayer()
        self.audio_out = QAudioOutput()
        self.player.setAudioOutput(self.audio_out)
        self.player.setVideoOutput(self.video_widget)
        self.audio_out.setVolume(0.8)

        self.fetcher = StreamFetcher(video_url)
        self.fetcher.stream_url_ready.connect(self.play_video)
        self.fetcher.error.connect(self.show_error)
        self.fetcher.start()

    def play_video(self, url):
        self.loading_lbl.hide()
        self.video_widget.show()
        self.player.setSource(QUrl(url))
        self.player.play()

    def show_error(self, msg):
        self.loading_lbl.setText("No se pudo cargar el stream.")
        self.loading_lbl.setStyleSheet("color: #ff4757; font-size: 14px; padding: 20px;")

    def closeEvent(self, event):
        self.player.stop()
        if self.fetcher.isRunning():
            self.fetcher.cancel()
            self.fetcher.quit()
            self.fetcher.wait(3000)
        super().closeEvent(event)


# ==========================================
# VIDEO CARD — ALTURA DINÁMICA, SIN TRUNCAR
# ==========================================
class VideoCard(QFrame):
    # Señales para comunicar descargas al padre sin acoplamiento
    request_download = Signal(dict)   # emite el task dict completo

    def __init__(self, data, cache_refe, cache_setter=None, parent=None):
        super().__init__(parent)
        self.url = data['url']
        self.thumb_url = data['thumb']
        self.cache = cache_refe
        self._cache_setter = cache_setter if cache_setter else lambda u, c: cache_refe.__setitem__(u, c)
        self.q_ready = False
        self._titulo = data['titulo']
        self._uploader = data['uploader']
        self._duracion = data['duracion']

        self.setObjectName("VideoCard")
        # Altura dinámica: se ajusta al contenido
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # ── Layout raíz ─────────────────────────────────────────────────
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 14, 0)
        root.setSpacing(0)

        # ── MINIATURA (186×116) ─────────────────────────────────────────
# ── MINIATURA (160x90) ─────────────────────────────────────────
        thumb_container = QWidget()
        thumb_container.setFixedSize(160, 90)
        thumb_container.setStyleSheet("background: transparent;")

        self.img = QLabel(thumb_container)
        self.img.setFixedSize(160, 90)
        self.img.setStyleSheet(
            "background-color: #0d0d16; border-radius: 11px 0 0 11px;"
        )
        self.img.setScaledContents(True)

        # Badge duración sobre miniatura
        self.dur_badge = QLabel(data['duracion'], thumb_container)
        self.dur_badge.setStyleSheet(
            "background-color: rgba(0,0,0,0.82); color: #ffffff; "
            "font-size: 11px; font-weight: 700; "
            "font-family: 'Consolas','Courier New',monospace; "
            "padding: 2px 7px; border-radius: 4px;"
        )
        self.dur_badge.adjustSize()
        # Ajustamos las coordenadas para el nuevo tamaño de 160x90
        self.dur_badge.move(
            160 - self.dur_badge.width() - 7,
            90 - self.dur_badge.height() - 7
        )
        self.dur_badge.raise_()

        # Badge duración sobre miniatura
        self.dur_badge = QLabel(data['duracion'], thumb_container)
        self.dur_badge.setStyleSheet(
            "background-color: rgba(0,0,0,0.82); color: #ffffff; "
            "font-size: 11px; font-weight: 700; "
            "font-family: 'Consolas','Courier New',monospace; "
            "padding: 2px 7px; border-radius: 4px;"
        )
        self.dur_badge.adjustSize()
        self.dur_badge.move(
            186 - self.dur_badge.width() - 7,
            116 - self.dur_badge.height() - 7
        )
        self.dur_badge.raise_()

        root.addWidget(thumb_container)

        # ── CUERPO ───────────────────────────────────────────────────────
        body = QVBoxLayout()
        body.setContentsMargins(14, 11, 0, 11)
        body.setSpacing(0)

        # Título — word wrap completo, sin límite de líneas
        self.title_lbl = QLabel(data['titulo'])
        self.title_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #f0f0f8; "
            "background: transparent; border: none; line-height: 1.45;"
        )
        self.title_lbl.setWordWrap(True)
        # Sin setMaximumHeight → se expande libremente
        self.title_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        body.addWidget(self.title_lbl)

        body.addSpacing(7)

        # Fila de metadatos
        meta = QHBoxLayout()
        meta.setSpacing(14)
        meta.setContentsMargins(0, 0, 0, 0)

        dot = QLabel("●")
        dot.setFixedWidth(10)
        dot.setStyleSheet("color: #00c8e0; font-size: 10px; background:transparent; border:none;")

        ch_lbl = QLabel(data['uploader'])
        ch_lbl.setStyleSheet(
            "color: #00c8e0; font-size: 12px; font-weight: 600; "
            "background:transparent; border:none;"
        )

        sep_lbl = QLabel("|")
        sep_lbl.setStyleSheet("color: #333344; font-size: 12px; background:transparent; border:none;")

        clock_lbl = QLabel("⏱")
        clock_lbl.setStyleSheet("font-size: 11px; background:transparent; border:none;")

        dur_lbl = QLabel(data['duracion'])
        dur_lbl.setStyleSheet(
            "color: #8080a0; font-size: 12px; font-weight: 500; "
            "background:transparent; border:none;"
        )

        meta.addWidget(dot)
        meta.addWidget(ch_lbl)
        meta.addWidget(sep_lbl)
        meta.addWidget(clock_lbl)
        meta.addWidget(dur_lbl)
        meta.addStretch()
        body.addLayout(meta)

        body.addSpacing(10)

        # Línea separadora
        sep_line = QFrame()
        sep_line.setFrameShape(QFrame.HLine)
        sep_line.setFixedHeight(1)
        sep_line.setStyleSheet("background: #1e1e2a; border: none;")
        body.addWidget(sep_line)

        body.addSpacing(10)

        # ── FILA DE ACCIONES ─────────────────────────────────────────────
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.setContentsMargins(0, 0, 0, 0)

        # Botón PREVIA
        self.btn_preview = QPushButton("▶  PREVIA")
        self.btn_preview.setFixedHeight(30)
        self.btn_preview.setCursor(Qt.PointingHandCursor)
        self.btn_preview.setStyleSheet("""
            QPushButton {
                background-color: #c0392b; color: #ffffff; border: none;
                border-radius: 6px; font-size: 11px; font-weight: 800;
                padding: 0 12px; letter-spacing: 0.3px;
            }
            QPushButton:hover { background-color: #e74c3c; }
            QPushButton:pressed { background-color: #96281b; }
        """)
        self.btn_preview.clicked.connect(self.show_preview)

        # Selector de calidad
        self.combo = QComboBox()
        self.combo.addItem("Calidad...", None)
        self.combo.setFixedHeight(30)
        self.combo.setFixedWidth(96)
        self.combo.setCursor(Qt.PointingHandCursor)

        # Botón MP4
        self.btn_mp4 = QPushButton("⬇  MP4")
        self.btn_mp4.setFixedHeight(30)
        self.btn_mp4.setCursor(Qt.PointingHandCursor)
        self.btn_mp4.setStyleSheet("""
            QPushButton {
                background-color: #1e1e2b; color: #c0c0d8;
                border: 1px solid #2a2a3c;
                border-radius: 6px; font-size: 11px; font-weight: 800;
                padding: 0 12px; letter-spacing: 0.3px;
            }
            QPushButton:hover { background-color: #28283c; border-color: #3a3a50; color: #ffffff; }
            QPushButton:pressed { background-color: #13131e; }
        """)
        self.btn_mp4.clicked.connect(self._on_mp4_clicked)

        # Botón MP3 (acento cyan)
        self.btn_mp3 = QPushButton("♫  MP3")
        self.btn_mp3.setFixedHeight(30)
        self.btn_mp3.setCursor(Qt.PointingHandCursor)
        self.btn_mp3.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #00c8e0, stop:1 #0099bb);
                color: #050a0c; border: none;
                border-radius: 6px; font-size: 11px; font-weight: 800;
                padding: 0 12px; letter-spacing: 0.3px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #33d4ed, stop:1 #00b0cc);
            }
            QPushButton:pressed { background-color: #007a93; }
        """)
        self.btn_mp3.clicked.connect(self._on_mp3_clicked)

        actions.addWidget(self.btn_preview)
        actions.addWidget(self.combo)
        actions.addWidget(self.btn_mp4)
        actions.addWidget(self.btn_mp3)
        actions.addStretch()

        body.addLayout(actions)
        root.addLayout(body, 1)

        # Carga de miniatura
        if self.thumb_url in self.cache:
            self.set_thumb(self.cache[self.thumb_url])
        else:
            worker = ThumbnailWorker(self.thumb_url)
            worker.signals.done.connect(self.save_and_set_thumb)
            QThreadPool.globalInstance().start(worker)

    # ── SLOTS INTERNOS ───────────────────────────────────────────────────
    def _on_mp4_clicked(self):
        if self.combo.currentData() is None:
            QMessageBox.warning(
                self, "Calidad no cargada",
                "Selecciona el video primero para cargar las calidades disponibles."
            )
            return
        self.request_download.emit({
            'url': self.url, 'tipo': 'video',
            'itag': self.combo.currentData(),
            'titulo': self._titulo,
        })

    def _on_mp3_clicked(self):
        self.request_download.emit({
            'url': self.url, 'tipo': 'audio',
            'itag': None,
            'titulo': self._titulo,
        })

    def show_preview(self):
        self.preview_window = PreviewDialog(self.url, self._titulo, self)
        self.preview_window.exec()

    def save_and_set_thumb(self, content, url):
        self._cache_setter(url, content)
        self.set_thumb(content)

    def set_thumb(self, content):
        img = QImage()
        if img.loadFromData(content):
            self.img.setPixmap(QPixmap.fromImage(img))


# ==========================================
# VENTANA PRINCIPAL
# ==========================================
class YoutubeDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()
        self.setStyleSheet(PREMIUM_DARK_STYLE)
        self.setWindowTitle(f"Dynatube Pro  —  {CURRENT_VERSION}")
        self.setMinimumSize(1180, 780)

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

    # ── CACHÉ LIMITADO ───────────────────────────────────────────────────
    def safe_cache_thumbnail(self, url, content):
        if len(self.thumbnail_cache) >= MAX_THUMBNAIL_CACHE:
            del self.thumbnail_cache[next(iter(self.thumbnail_cache))]
        self.thumbnail_cache[url] = content

    # ── ACTUALIZACIÓN ────────────────────────────────────────────────────
    def check_for_updates(self):
        self.updater = UpdateChecker()
        self.updater.update_available.connect(self.show_update_dialog)
        self.updater.start()

    def show_update_dialog(self, latest, url):
        msg = QMessageBox(self)
        msg.setWindowTitle("Actualización disponible")
        msg.setText(
            f"<h3>Nueva versión {latest} disponible</h3>"
            f"<p>Versión actual: {CURRENT_VERSION}</p>"
            f"<p>¿Abrir GitHub para descargar?</p>"
        )
        msg.setIcon(QMessageBox.Icon.Information)
        yes = msg.addButton("Descargar", QMessageBox.ButtonRole.AcceptRole)
        no = msg.addButton("Quizá más tarde", QMessageBox.ButtonRole.RejectRole)
        no.setStyleSheet("background:#1e1e2b; color:white;")
        msg.exec()
        if msg.clickedButton() == yes:
            webbrowser.open(url)

    # ── UI ───────────────────────────────────────────────────────────────
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # SIDEBAR
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(272)
        sl = QVBoxLayout(self.sidebar)
        sl.setContentsMargins(0, 36, 0, 20)
        sl.setSpacing(6)

        # Logo
        logo = QLabel("⚡  Dynatube Pro")
        logo.setStyleSheet(
            "font-weight: 900; font-size: 22px; color: white; "
            "padding: 0 20px 28px 20px; letter-spacing: 1px;"
        )
        sl.addWidget(logo)

        self.btn_nav_search = self._nav_btn("🔍   Buscar y Descargar", 0, True)
        self.btn_nav_conv   = self._nav_btn("🔄   Convertidor Local", 1)
        self.btn_nav_hist   = self._nav_btn("📜   Historial", 2)
        sl.addWidget(self.btn_nav_search)
        sl.addWidget(self.btn_nav_conv)
        sl.addWidget(self.btn_nav_hist)
        sl.addStretch()

        ver = QLabel(f"v{CURRENT_VERSION}")
        ver.setStyleSheet("color: #333344; font-size: 11px; font-weight: 700; padding-left: 22px;")
        sl.addWidget(ver)

        root.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        self._setup_search_page()
        self._setup_converter_page()
        self._setup_history_page()

    def _nav_btn(self, text, index, active=False):
        btn = QPushButton(text)
        btn.setObjectName("MenuBtn")
        btn.setProperty("active", active)
        btn.clicked.connect(lambda: self.switch_page(index))
        return btn

    # ── PÁGINA DE BÚSQUEDA ───────────────────────────────────────────────
    def _setup_search_page(self):
        page = QWidget()
        lyt = QVBoxLayout(page)
        lyt.setContentsMargins(36, 32, 36, 20)
        lyt.setSpacing(18)

        # Barra superior
        top = QHBoxLayout()
        top.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Pega un enlace de YouTube o escribe lo que buscas..."
        )
        self.search_input.setFixedHeight(46)
        self.search_input.returnPressed.connect(self.start_search)

        btn_search = QPushButton("BUSCAR")
        btn_search.setObjectName("btnSearch")
        btn_search.setFixedSize(120, 46)
        btn_search.clicked.connect(self.start_search)

        btn_folder = QPushButton("DIRECTORIO")
        btn_folder.setObjectName("btnFolder")
        btn_folder.setFixedSize(120, 46)
        btn_folder.clicked.connect(self.select_folder)

        top.addWidget(self.search_input)
        top.addWidget(btn_search)
        top.addWidget(btn_folder)
        lyt.addLayout(top)

        self.path_display = QLabel(f"Guardando en: {self.download_path}")
        self.path_display.setStyleSheet(
            "color: #44445a; font-size: 12px; font-weight: 500;"
        )
        lyt.addWidget(self.path_display)

        # Body
        body = QHBoxLayout()
        body.setSpacing(22)

        # Lista de resultados — sin altura fija de ítem (dinámica)
        self.result_list = QListWidget()
        self.result_list.setSpacing(6)
        self.result_list.itemSelectionChanged.connect(self.load_qualities)
        self.result_list.verticalScrollBar().valueChanged.connect(self.handle_scroll)
        body.addWidget(self.result_list, 8)

        # Panel de cola
        queue_panel = QFrame()
        queue_panel.setObjectName("QueuePanel")
        ql = QVBoxLayout(queue_panel)
        ql.setContentsMargins(18, 18, 18, 18)
        ql.setSpacing(14)

        lbl_q = QLabel("COLA DE DESCARGAS")
        lbl_q.setStyleSheet(
            "color: #e0e0f0; font-weight: 800; font-size: 12px; letter-spacing: 1px;"
        )
        ql.addWidget(lbl_q)

        self.queue_list_widget = QListWidget()
        self.queue_list_widget.setStyleSheet(
            "QListWidget { border:none; background:transparent; }"
            "QListWidget::item { padding:9px; color:#9090a8; border-bottom:1px solid #1e1e2a; }"
        )
        ql.addWidget(self.queue_list_widget)

        ctrl = QHBoxLayout()
        self.btn_pause = QPushButton("PAUSAR")
        self.btn_pause.setStyleSheet(
            "background: #c0392b; color:white; border:none; border-radius:8px;"
        )
        self.btn_pause.clicked.connect(self.toggle_pause)

        btn_clear = QPushButton("LIMPIAR")
        btn_clear.setObjectName("btnClear")
        btn_clear.clicked.connect(self.clear_queue)

        ctrl.addWidget(self.btn_pause)
        ctrl.addWidget(btn_clear)
        ql.addLayout(ctrl)

        body.addWidget(queue_panel, 2)
        lyt.addLayout(body)

        # Estado y barra de progreso (SIN botones de descarga global)
        self.status_lbl = QLabel("ESTADO: EN ESPERA")
        self.status_lbl.setStyleSheet(
            "color: #00e5ff; font-weight: 800; font-size: 11px; letter-spacing: 1px;"
        )
        lyt.addWidget(self.status_lbl)

        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(5)
        lyt.addWidget(self.pbar)

        self.stack.addWidget(page)

    def _setup_converter_page(self):
        page = QWidget()
        lyt = QVBoxLayout(page)
        lyt.setAlignment(Qt.AlignCenter)
        lyt.setSpacing(28)

        QLabel("⚡", page)

        icon = QLabel("⚡")
        icon.setStyleSheet("font-size: 44px;")
        icon.setAlignment(Qt.AlignCenter)

        title = QLabel("Conversión Local")
        title.setStyleSheet("font-size: 22px; color:white; font-weight: 800;")
        title.setAlignment(Qt.AlignCenter)

        desc = QLabel("Convierte archivos de video a MP3 sin conexión.")
        desc.setStyleSheet("color:#44445a; font-size:13px;")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)

        btn = QPushButton("SELECCIONAR ARCHIVOS")
        btn.setFixedSize(300, 48)
        btn.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #00c8e0, stop:1 #0099bb); "
            "color:#050a0c; font-size:13px; font-weight:800; border:none; border-radius:10px;"
        )
        btn.clicked.connect(self.start_local_conversion)

        self.conv_status = QLabel("Listo.")
        self.conv_status.setStyleSheet("color:#00e5ff; font-weight:700;")
        self.conv_status.setAlignment(Qt.AlignCenter)

        self.conv_pbar = QProgressBar()
        self.conv_pbar.setFixedWidth(380)
        self.conv_pbar.setFixedHeight(7)

        lyt.addWidget(icon)
        lyt.addWidget(title)
        lyt.addWidget(desc)
        lyt.addWidget(btn, alignment=Qt.AlignCenter)
        lyt.addWidget(self.conv_status)
        lyt.addWidget(self.conv_pbar, alignment=Qt.AlignCenter)

        self.stack.addWidget(page)

    def _setup_history_page(self):
        page = QWidget()
        lyt = QVBoxLayout(page)
        lyt.setContentsMargins(36, 32, 36, 32)
        lyt.setSpacing(18)

        title = QLabel("HISTORIAL DE DESCARGAS")
        title.setStyleSheet(
            "font-size: 17px; font-weight: 800; color: white; letter-spacing: 1px;"
        )
        lyt.addWidget(title)

        self.hist_list = QListWidget()
        self.hist_list.setStyleSheet("""
            QListWidget { background:#111118; border:1px solid #1e1e2a;
                          border-radius:12px; padding:12px; }
            QListWidget::item { padding:11px; border-bottom:1px solid #1e1e2a;
                                color:#c0c0d8; font-size:13px; }
            QListWidget::item:hover { background:#16161f; border-radius:6px; }
        """)
        lyt.addWidget(self.hist_list)

        btn_ref = QPushButton("ACTUALIZAR")
        btn_ref.setFixedSize(180, 42)
        btn_ref.setStyleSheet(
            "background:#5a4dcc; border:none; color:white; "
            "font-weight:800; border-radius:8px;"
        )
        btn_ref.clicked.connect(self.load_history)
        lyt.addWidget(btn_ref, alignment=Qt.AlignRight)

        self.stack.addWidget(page)

    # ── NAVEGACIÓN ───────────────────────────────────────────────────────
    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate([self.btn_nav_search, self.btn_nav_conv, self.btn_nav_hist]):
            btn.setProperty("active", i == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if index == 2:
            self.load_history()

    def load_history(self):
        self.hist_list.clear()
        with get_db_connection() as conn:
            for row in conn.execute(
                "SELECT title, type, date FROM downloads ORDER BY id DESC LIMIT 100"
            ).fetchall():
                emoji = "🎵" if row[1] == "audio" else "🎬"
                self.hist_list.addItem(f"{emoji}   {row[0]}   —   {row[2]}")

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta")
        if folder:
            self.download_path = folder
            self.path_display.setText(f"Guardando en: {folder}")

    # ── THREAD UTILS ─────────────────────────────────────────────────────
    def _stop_thread(self, attr):
        t = getattr(self, attr, None)
        if t and t.isRunning():
            t.quit()
            t.wait(2000)

    # ── BÚSQUEDA ─────────────────────────────────────────────────────────
    def start_search(self):
        q = self.search_input.text().strip()
        if not q:
            return
        self.result_list.clear()
        self.last_query = q
        self.current_page = 0
        self._execute_search()

    def _execute_search(self):
        if self.is_loading:
            return
        self._stop_thread('search_thr')
        self.is_loading = True
        self._set_status("BUSCANDO...", "#ff9f43")

        self.search_thr = YtDlpSearchEngine(self.last_query, self.current_page)
        self.search_thr.video_found.connect(self.add_video_card)
        self.search_thr.error_signal.connect(lambda e: self._set_status(f"ERROR: {e}", "#ff4757"))
        self.search_thr.finished_search.connect(self._on_search_done)
        self.search_thr.start()

    def _on_search_done(self):
        self.is_loading = False
        if "ERROR" not in self.status_lbl.text():
            self._set_status("BÚSQUEDA COMPLETADA", "#00e5ff")

    def _set_status(self, text, color="#00e5ff"):
        self.status_lbl.setText(f"ESTADO: {text}")
        self.status_lbl.setStyleSheet(
            f"color:{color}; font-weight:800; font-size:11px; letter-spacing:1px;"
        )

    def add_video_card(self, data):
        item = QListWidgetItem(self.result_list)
        card = VideoCard(data, self.thumbnail_cache, cache_setter=self.safe_cache_thumbnail)
        card.request_download.connect(self._enqueue_from_card)
        # Altura dinámica: mide el sizeHint del card después de crearlo
        # Se usa un mínimo de 130px y se le da margen extra al título
        item.setSizeHint(QSize(0, max(130, card.sizeHint().height() + 12)))
        self.result_list.setItemWidget(item, card)

    def handle_scroll(self, val):
        bar = self.result_list.verticalScrollBar()
        if val > bar.maximum() * 0.9 and not self.is_loading and self.last_query:
            self.current_page += 20
            self._execute_search()

    # ── CALIDADES ────────────────────────────────────────────────────────
    def load_qualities(self):
        item = self.result_list.currentItem()
        if not item:
            return
        card = self.result_list.itemWidget(item)
        if card and not card.q_ready:
            self._stop_thread('q_thr')
            card.combo.clear()
            card.combo.addItem("Cargando...", None)
            self.q_thr = QualityLoader(card.url)
            self.q_thr.qualities_ready.connect(lambda q: self._fill_combo(card, q))
            self.q_thr.start()

    def _fill_combo(self, card, qualities):
        try:
            if card and not card.isHidden():
                card.combo.clear()
                for res, itag in qualities:
                    card.combo.addItem(res, itag)
                card.q_ready = True
        except RuntimeError:
            pass

    # ── COLA DE DESCARGAS ────────────────────────────────────────────────
    def _enqueue_from_card(self, task_partial):
        """Recibe señal del VideoCard con url, tipo, itag, titulo."""
        task = {
            'url':   task_partial['url'],
            'tipo':  task_partial['tipo'],
            'itag':  task_partial['itag'],
            'path':  self.download_path,
            'titulo': task_partial['titulo'],
        }
        self.download_queue.append(task)
        self.queue_list_widget.addItem(task['titulo'])
        if not self.is_downloading:
            self._process_next()

    def _process_next(self):
        if not self.download_queue:
            self.is_downloading = False
            self._set_status("TODAS LAS TAREAS COMPLETADAS", "#00e5ff")
            self.pbar.setValue(0)
            self.btn_pause.setText("PAUSAR")
            self.btn_pause.setStyleSheet(
                "background:#c0392b; color:white; border:none; border-radius:8px;"
            )
            return

        self.is_downloading = True
        task = self.download_queue[0]
        self.current_worker = DownloadWorker(
            task['url'], task['tipo'], task['itag'], task['path'], task['titulo']
        )
        self.current_worker.progress.connect(self.pbar.setValue)
        self.current_worker.status.connect(lambda s: self._set_status(s.upper()))
        self.current_worker.finished_dl.connect(lambda ok, msg: self._finish_dl(ok, msg, task))
        self.current_worker.start()

    def _finish_dl(self, ok, msg, task):
        if ok:
            try:
                notification.notify(
                    title="¡Descarga completada! ✅",
                    message=task['titulo'], app_name="Dynatube Pro", timeout=5
                )
            except Exception:
                pass
            add_to_history(task['titulo'], task['tipo'])
        else:
            QMessageBox.warning(self, "Error de descarga", msg)

        if self.download_queue:
            self.download_queue.pop(0)
        if self.queue_list_widget.count() > 0:
            self.queue_list_widget.takeItem(0)

        self._process_next()

    def toggle_pause(self):
        if self.current_worker and self.current_worker.isRunning():
            paused = self.current_worker.toggle_pause()
            if paused:
                self.btn_pause.setText("REANUDAR")
                self.btn_pause.setStyleSheet(
                    "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                    "stop:0 #00c8e0,stop:1 #0099bb); "
                    "color:#050a0c; border:none; border-radius:8px;"
                )
                self._set_status("DESCARGA EN PAUSA", "#ff9f43")
            else:
                self.btn_pause.setText("PAUSAR")
                self.btn_pause.setStyleSheet(
                    "background:#c0392b; color:white; border:none; border-radius:8px;"
                )

    def clear_queue(self):
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.stop()
        self.download_queue.clear()
        self.queue_list_widget.clear()
        self.is_downloading = False
        self._set_status("COLA VACIADA", "#8080a0")
        self.pbar.setValue(0)
        self.btn_pause.setText("PAUSAR")
        self.btn_pause.setStyleSheet(
            "background:#c0392b; color:white; border:none; border-radius:8px;"
        )

    # ── CONVERTIDOR LOCAL ────────────────────────────────────────────────
    def start_local_conversion(self):
        if self.local_process and self.local_process.state() == QProcess.ProcessState.Running:
            QMessageBox.warning(self, "Aviso", "Ya hay una conversión en curso.")
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar videos", "", "Videos (*.mp4 *.mkv *.avi *.webm *.mov)"
        )
        if not files:
            return
        self.conv_queue = [f for f in files if f.lower().endswith(('.mp4','.mkv','.avi','.mov','.webm'))]
        self.total_conv = len(self.conv_queue)
        if not self.total_conv:
            return
        self.conv_pbar.setValue(0)
        self._next_conversion()

    def _next_conversion(self):
        if not self.conv_queue:
            QMessageBox.information(self, "Completado", f"Se convirtieron {self.total_conv} archivos.")
            self.conv_status.setText("Conversión finalizada")
            self.conv_pbar.setValue(0)
            return
        current = self.conv_queue.pop(0)
        out = f"{os.path.splitext(current)[0]}.mp3"
        self.conv_status.setText(f"Procesando: {os.path.basename(current)}")
        self.local_process = QProcess(self)
        self.local_process.finished.connect(self._on_conv_done)
        self.local_process.start(resource_path('ffmpeg.exe'), [
            '-y', '-i', current, '-vn', '-c:a', 'libmp3lame',
            '-q:a', '2', '-threads', '0', out
        ])

    def _on_conv_done(self, code, _):
        if code == 0:
            done = self.total_conv - len(self.conv_queue)
            self.conv_pbar.setValue(int(done / self.total_conv * 100))
            self._next_conversion()
        else:
            QMessageBox.critical(
                self, "Error de conversión",
                "FFmpeg no pudo procesar el archivo.\n"
                "Verifica que el formato sea compatible y que ffmpeg.exe esté presente."
            )
            self.conv_queue.clear()
            self.conv_status.setText("Operación interrumpida")
            self.conv_pbar.setValue(0)


# ==========================================
# ENTRY POINT
# ==========================================
if __name__ == "__main__":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            'DaynatubePro.App'
        )
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    window = YoutubeDownloader()
    window.show()
    sys.exit(app.exec())