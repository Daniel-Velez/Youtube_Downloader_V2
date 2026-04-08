import os
import sys
import requests
import isodate 
import subprocess
import psutil
from dotenv import load_dotenv
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QPushButton, 
                               QLineEdit, QListWidget, QWidget, QMessageBox, QLabel, 
                               QFileDialog, QHBoxLayout, QComboBox, QProgressBar, 
                               QListWidgetItem, QFrame, QAbstractItemView)
from PySide6.QtGui import QPixmap, QImage, Qt, QIcon, QColor, QFont, QPalette
from PySide6.QtCore import Qt, QThread, Signal, QSize
from pytubefix import YouTube
from googleapiclient.discovery import build

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Cargar variables de entorno
env_path = resource_path(".env")
load_dotenv(env_path)
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

# --- MANEJO DE RUTAS PARA EL EXE ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- ESTILO GRAPHENE COMPACT (Minimalista Técnico) ---
GRAPHENE_STYLE = """
    QMainWindow { background-color: #1e1e1e; }
    QWidget { color: #d4d4d4; font-family: 'Consolas', 'Monospace', sans-serif; font-size: 12px; }
    
    /* Panel Lateral */
    QFrame#Sidebar { 
        background-color: #252526; 
        border-right: 1px solid #3e3e42;
    }
    
    QLabel#SidebarTitle { 
        color: #007acc; 
        font-weight: bold; 
        font-size: 14px; 
        margin-bottom: 15px;
        font-family: 'Segoe UI', sans-serif;
    }

    /* Inputs y ComboBox Rectos */
    QLineEdit { 
        background-color: #333333; 
        border: 1px solid #3e3e42; 
        border-radius: 0px; 
        padding: 6px; 
        color: white; 
    }
    QLineEdit:focus { border: 1px solid #007acc; }

    QComboBox { 
        background-color: #333333; 
        border: 1px solid #3e3e42; 
        border-radius: 0px; 
        color: white; 
        padding: 2px 5px;
    }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView { background-color: #252526; border: 1px solid #3e3e42; selection-background-color: #0e639c; }

    /* Botones Rectos Estilo VS Code */
    QPushButton { 
        background-color: #333333; 
        border: 1px solid #3e3e42; 
        border-radius: 0px; 
        color: #d4d4d4; 
        padding: 6px 12px; 
        font-weight: bold;
    }
    QPushButton:hover { background-color: #3e3e42; border: 1px solid #007acc; }
    QPushButton:pressed { background-color: #0e639c; }
    
    QPushButton#btnActionVideo { background-color: #2d7d46; border: none; color: white; }
    QPushButton#btnActionVideo:hover { background-color: #389153; }
    
    QPushButton#btnActionAudio { background-color: #0e639c; border: none; color: white; }
    QPushButton#btnActionAudio:hover { background-color: #1177bb; }

    /* Lista de Resultados */
    QListWidget { 
        background-color: #1e1e1e; 
        border: none; 
        outline: none; 
    }
    QListWidget::item { background-color: transparent; border-bottom: 1px solid #2d2d2d; }
    QListWidget::item:selected { background-color: #2a2d2e; }

    /* Barra de progreso plana */
    QProgressBar { 
        border: 1px solid #3e3e42; 
        background-color: #1e1e1e; 
        height: 4px; 
        border-radius: 0px; 
        text-align: center; 
        color: transparent; 
    }
    QProgressBar::chunk { background-color: #007acc; }
    /* Estilo para el contenedor del título y logo */
    QWidget#TitleContainer { 
        background-color: transparent;
        margin-bottom: 15px; /* Movemos el margen aquí */
    }
    
    QLabel#SidebarTitle { 
        color: #007acc; 
        font-weight: bold; 
        font-size: 14px; 
        font-family: 'Segoe UI', sans-serif;
        /* margin-bottom: 15px;  <-- ELIMINA O COMENTA ESTA LÍNEA en tu estilo actual */
    }
"""

# Función de chequeo limpia
def check_gpu_acceleration():
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        output = subprocess.check_output(['ffmpeg', '-encoders'], startupinfo=startupinfo, stderr=subprocess.STDOUT).decode()
        return "nvidia" if 'h264_nvenc' in output else None
    except: return None

# --- HILOS DE PROCESAMIENTO ---
class QualityLoaderThread(QThread):
    finished_signal = Signal(list)
    def __init__(self, url):
        super().__init__(); self.url = url
    def run(self):
        try:
            yt = YouTube(self.url)
            streams = yt.streams.filter(file_extension='mp4').order_by('resolution').desc()
            vistas = set(); res = []
            for s in streams:
                if s.resolution and s.resolution not in vistas:
                    tag = "OK" if s.is_progressive else "HQ"
                    res.append((f"{s.resolution} ({tag})", s.itag))
                    vistas.add(s.resolution)
            self.finished_signal.emit(res)
        except: self.finished_signal.emit([("Error", None)])

class SearchThread(QThread):
    results_signal = Signal(list, str)
    error_signal = Signal(str)
    def __init__(self, query, api_service, page_token=None):
        super().__init__(); self.query = query; self.api_service = api_service; self.page_token = page_token
    def run(self):
        try:
            videos = []
            if "youtube.com" in self.query or "youtu.be" in self.query:
                yt = YouTube(self.query)
                videos.append({'titulo': yt.title, 'url': self.query, 'thumb': yt.thumbnail_url, 'duracion': yt.length, 'fecha': "N/A"})
                self.results_signal.emit(videos, "")
            else:
                req = self.api_service.search().list(q=self.query, part="snippet", type="video", maxResults=12, pageToken=self.page_token)
                res = req.execute(); next_token = res.get('nextPageToken', "")
                video_ids = [item['id']['videoId'] for item in res.get('items', []) if item.get('id', {}).get('kind') == 'youtube#video']
                if video_ids:
                    s_res = self.api_service.videos().list(id=",".join(video_ids), part="contentDetails,snippet").execute()
                    for item in s_res.get('items', []):
                        sec = int(isodate.parse_duration(item['contentDetails']['duration']).total_seconds())
                        videos.append({'titulo': item['snippet']['title'], 'url': f"https://www.youtube.com/watch?v={item['id']}",
                                     'thumb': item['snippet']['thumbnails']['high']['url'], 'duracion': sec, 'fecha': item['snippet']['publishedAt'][:10]})
                self.results_signal.emit(videos, next_token)
        except Exception as e: self.error_signal.emit(str(e))

class DownloadThread(QThread):
    progress_signal = Signal(int)
    status_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, url, tipo, itag, path, titulo, use_gpu=None):
        super().__init__()
        self.url = url; self.tipo = tipo; self.itag = itag; self.path = path
        self.titulo = "".join([c for c in titulo if c.isalnum() or c==' ']).strip()
        self.use_gpu = use_gpu

    def run(self):
        try:
            p = psutil.Process(os.getpid())
            if sys.platform == "win32": p.nice(psutil.HIGH_PRIORITY_CLASS)
            yt = YouTube(self.url, on_progress_callback=self.pytube_progress)
            
            if self.tipo == "audio":
                self.status_signal.emit("[proc] Descargando Audio...")
                audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
                file = audio_stream.download(output_path=self.path)
                final = os.path.join(self.path, f"{self.titulo}.mp3")
                if os.path.exists(final): os.remove(final)
                os.rename(file, final)
                self.finished_signal.emit(True, "Audio guardado.")
            else:
                s = yt.streams.get_by_itag(self.itag)
                if s.is_progressive:
                    self.status_signal.emit("[proc] Descarga directa...")
                    s.download(output_path=self.path, filename=f"{self.titulo}.mp4")
                else:
                    self.status_signal.emit("[proc] Descargando flujos HQ...")
                    v_tmp = s.download(output_path=self.path, filename="v_tmp.mp4")
                    a_tmp = yt.streams.filter(only_audio=True).first().download(output_path=self.path, filename="a_tmp.mp4")
                    final_path = os.path.join(self.path, f"{self.titulo}.mp4")
                    startupinfo = subprocess.STARTUPINFO()
                    if sys.platform == "win32": startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                    self.status_signal.emit("[ffmpeg] Muxing copia...")
                    cmd_copy = ['ffmpeg', '-y', '-i', v_tmp, '-i', a_tmp, '-c', 'copy', '-map', '0:v:0', '-map', '1:a:0', '-shortest', final_path]
                    res = subprocess.run(cmd_copy, startupinfo=startupinfo, capture_output=True)

                    if res.returncode != 0:
                        self.status_signal.emit("[ffmpeg] Re-encode (GPU)...")
                        codec = 'h264_nvenc' if self.use_gpu == "nvidia" else 'libx264'
                        preset = 'p4' if self.use_gpu == "nvidia" else 'ultrafast'
                        cmd_render = ['ffmpeg', '-y', '-i', v_tmp, '-i', a_tmp, '-c:v', codec, '-preset', preset, '-cq', '19', '-c:a', 'aac', '-b:a', '192k', '-shortest', final_path]
                        subprocess.run(cmd_render, startupinfo=startupinfo)

                    if os.path.exists(v_tmp): os.remove(v_tmp)
                    if os.path.exists(a_tmp): os.remove(a_tmp)
                self.finished_signal.emit(True, "Video completado.")
        except Exception as e: self.finished_signal.emit(False, str(e))

    def pytube_progress(self, stream, chunk, remaining):
        self.progress_signal.emit(int(((stream.filesize - remaining) / stream.filesize) * 100))

# --- NUEVO: HILO DE DESCARGA DE MINIATURAS ---
class ThumbnailLoaderThread(QThread):
    finished_signal = Signal(bytes)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            response = requests.get(self.url, timeout=5)
            if response.status_code == 200:
                self.finished_signal.emit(response.content)
        except Exception:
            pass

# --- COMPONENTES DE INTERFAZ ---
class VideoCard(QFrame):
    def __init__(self, v, parent=None):
        super().__init__(parent); self.url = v['url']; self.quality_loaded = False
        self.setObjectName("CompactCard")
        self.setStyleSheet("QFrame#CompactCard { background-color: transparent; padding: 5px; }")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        self.img = QLabel()
        self.img.setFixedSize(100, 60)
        self.img.setScaledContents(True)
        self.img.setStyleSheet("border: 1px solid #3e3e42; background-color: black;")
        layout.addWidget(self.img)

        info = QVBoxLayout()
        info.setSpacing(2)
        self.titulo_label = QLabel(v['titulo'])
        self.titulo_label.setStyleSheet("font-weight: bold; color: #e1e1e1; font-family: 'Segoe UI';")
        self.titulo_label.setWordWrap(True)
        self.titulo_label.setMaximumHeight(35)
        
        meta_row = QHBoxLayout()
        self.meta = QLabel(f"DATE: {v['fecha']}")
        self.meta.setStyleSheet("color: #888; font-size: 10px; font-family: 'Consolas';")
        
        self.combo = QComboBox()
        self.combo.addItem("SELECT QUALITY", None)
        self.combo.setFixedHeight(20)
        self.combo.setStyleSheet("font-size: 10px; font-family: 'Consolas'; padding: 0px 2px;")
        
        meta_row.addWidget(self.meta)
        meta_row.addStretch()
        meta_row.addWidget(self.combo)
        
        info.addWidget(self.titulo_label)
        info.addLayout(meta_row)
        layout.addLayout(info, 1)

        # --- CARGA ASÍNCRONA DE IMAGEN ---
        self.thumb_thread = ThumbnailLoaderThread(v['thumb'])
        self.thumb_thread.finished_signal.connect(self.set_thumbnail)
        self.thumb_thread.start()

    def set_thumbnail(self, image_data):
        pix = QImage()
        pix.loadFromData(image_data)
        self.img.setPixmap(QPixmap.fromImage(pix))

class YoutubeDownloader(QMainWindow):
    def get_version():
        try:
            version_path = resource_path("version.txt")
            with open(version_path, "r") as f:
                return f.read().strip()
        except:
            return "2.0.0" # Versión por defecto si falla la lectura
    def __init__(self):
        super().__init__(); self.setStyleSheet(GRAPHENE_STYLE)
        self.setWindowTitle("Yotube Downloader - V2")
        icon_path = resource_path("icoV2.ico")
        if os.path.exists(icon_path): self.setWindowIcon(QIcon(icon_path))
        
        self.setMinimumSize(1000, 700)
        self.path = os.path.join(os.path.expanduser("~"), "Downloads")
        self.api = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY) if YOUTUBE_API_KEY else None
        self.token = None; self.loading = False; self.query = ""; self.init_ui()

    def check_scroll(self, value):
    # Si el scroll llega al 90% del límite máximo y hay un token disponible...
        if value > self.list.verticalScrollBar().maximum() * 0.9:
            if not self.loading and self.token:
            # Llama automáticamente a la búsqueda para traer la siguiente página
                self.search()

    def get_version(self):
        """Lee la versión desde version.txt"""
        try:
            v_path = resource_path("version.txt")
            with open(v_path, "r") as f:
                return f.read().strip()
        except:
            return "v1.0.0"

    def init_ui(self):
            # Obtener versión antes de armar la UI
            self.current_version = self.get_version()
            
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            hbox_main = QHBoxLayout(central_widget)
            hbox_main.setContentsMargins(0, 0, 0, 0)
            hbox_main.setSpacing(0)

            # --- PANEL LATERAL (SIDEBAR) ---
            sidebar = QFrame()
            sidebar.setObjectName("Sidebar")
            sidebar.setFixedWidth(280)
            vbox_sidebar = QVBoxLayout(sidebar)
            vbox_sidebar.setContentsMargins(20, 20, 20, 20)
            vbox_sidebar.setSpacing(15)

            # --- CONTENEDOR DE TÍTULO Y LOGO ---
            title_container = QWidget()
            title_container.setObjectName("TitleContainer")
            hbox_title = QHBoxLayout(title_container)
            hbox_title.setContentsMargins(0, 0, 0, 0)
            hbox_title.setSpacing(10)

            # Contenedor vertical para Título + Versión
            vbox_text_title = QVBoxLayout()
            vbox_text_title.setSpacing(2)

            lbl_title = QLabel("Youtube Downloader")
            lbl_title.setObjectName("SidebarTitle")
            lbl_title.setStyleSheet("margin-bottom: 0px;") # Ajuste para que no se separe tanto de la versión
            
            # Label de Versión
            lbl_v_display = QLabel(f"Build: {self.current_version}")
            lbl_v_display.setStyleSheet("color: #007acc; font-family: 'Consolas'; font-size: 10px; font-weight: bold;")

            vbox_text_title.addWidget(lbl_title)
            vbox_text_title.addWidget(lbl_v_display)
            
            # El Logo
            lbl_logo = QLabel()
            logo_path = resource_path("youtube_logo.png")
            if os.path.exists(logo_path):
                pix_logo = QPixmap(logo_path).scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                lbl_logo.setPixmap(pix_logo)
            
            hbox_title.addLayout(vbox_text_title)
            hbox_title.addStretch()
            hbox_title.addWidget(lbl_logo)
            
            vbox_sidebar.addWidget(title_container)

            vbox_sidebar.addWidget(QLabel("SEARCH / URL"))
            self.input = QLineEdit()
            self.input.setPlaceholderText("Escribe tu búsqueda o pega el enlace...")
            self.input.returnPressed.connect(self.new_search)
            vbox_sidebar.addWidget(self.input)
            
            btn_s = QPushButton("REALIZAR BÚSQUEDA")
            btn_s.clicked.connect(self.new_search)
            vbox_sidebar.addWidget(btn_s)
            
            vbox_sidebar.addSpacing(10)
            vbox_sidebar.addWidget(QFrame(frameShape=QFrame.HLine, frameShadow=QFrame.Sunken))
            vbox_sidebar.addSpacing(10)

            vbox_sidebar.addWidget(QLabel("OUTPUT DIRECTORY"))
            self.lbl_path = QLabel(self.path)
            self.lbl_path.setStyleSheet("color: #888; font-size: 11px;")
            self.lbl_path.setWordWrap(True)
            vbox_sidebar.addWidget(self.lbl_path)
            
            btn_p = QPushButton("NAVEGAR...")
            btn_p.clicked.connect(self.sel_path)
            vbox_sidebar.addWidget(btn_p)

            vbox_sidebar.addStretch() 

            self.status = QLabel("STATUS: IDLE")
            self.status.setStyleSheet("color: #007acc; font-weight: bold; font-size: 11px;")
            vbox_sidebar.addWidget(self.status)
            
            self.pbar = QProgressBar()
            self.pbar.setValue(0)
            vbox_sidebar.addWidget(self.pbar)

            self.b_v = QPushButton("DOWNLOAD VIDEO (MP4)")
            self.b_v.setObjectName("btnActionVideo")
            self.b_v.clicked.connect(lambda: self.start_dl("video"))
            vbox_sidebar.addWidget(self.b_v)
            
            self.b_a = QPushButton("DOWNLOAD AUDIO (MP3)")
            self.b_a.setObjectName("btnActionAudio")
            self.b_a.clicked.connect(lambda: self.start_dl("audio"))
            vbox_sidebar.addWidget(self.b_a)

            hbox_main.addWidget(sidebar)

            # --- ÁREA DE RESULTADOS CORREGIDA ---
            self.list = QListWidget()
            self.list.setSelectionMode(QAbstractItemView.SingleSelection)
            self.list.itemSelectionChanged.connect(self.load_q)
            self.list.verticalScrollBar().valueChanged.connect(self.check_scroll)
            hbox_main.addWidget(self.list, 1)
    def sel_path(self):
        p = QFileDialog.getExistingDirectory(self, "Carpeta de descarga")
        if p: self.path = p; self.lbl_path.setText(p)

    def new_search(self):
        self.query = self.input.text().strip(); self.list.clear(); self.token = None; self.search()

    def search(self):
        if self.loading or not self.query: return
        self.loading = True; self.status.setText("STATUS: SEARCHING...")
        self.thr = SearchThread(self.query, self.api, self.token)
        self.thr.results_signal.connect(self.add_res); self.thr.start()

    def add_res(self, vids, token):
        self.token = token
        for v in vids:
            item = QListWidgetItem(self.list); item.setSizeHint(QSize(0, 80))
            w = VideoCard(v); self.list.addItem(item); self.list.setItemWidget(item, w)
        self.loading = False; self.status.setText("STATUS: IDLE")

    def load_q(self):
        item = self.list.currentItem()
        if not item: return
        w = self.list.itemWidget(item)
        if not w.quality_loaded:
            w.combo.clear(); w.combo.addItem("LOADING...", None)
            self.ql = QualityLoaderThread(w.url)
            self.ql.finished_signal.connect(lambda res: self.fill_q(w, res)); self.ql.start()

    def fill_q(self, w, res):
        w.combo.clear()
        for t, d in res: w.combo.addItem(t, d)
        w.quality_loaded = True

    def start_dl(self, tipo):
        item = self.list.currentItem()
        if not item: return
        w = self.list.itemWidget(item); gpu = None
        if tipo == "video": gpu = check_gpu_acceleration()
        
        self.b_v.setEnabled(False); self.b_a.setEnabled(False)
        self.dl = DownloadThread(w.url, tipo, w.combo.currentData(), self.path, w.titulo_label.text(), gpu)
        self.dl.progress_signal.connect(self.pbar.setValue); self.dl.status_signal.connect(self.status.setText)
        self.dl.finished_signal.connect(self.done); self.dl.start()

    def done(self, ok, msg):
        self.b_v.setEnabled(True); self.b_a.setEnabled(True); self.pbar.setValue(0)
        self.status.setText("STATUS: IDLE")
        QMessageBox.information(self, "Yachay", msg) if ok else QMessageBox.critical(self, "Error", msg)

if __name__ == "__main__":
    app = QApplication(sys.argv); win = YoutubeDownloader(); win.show(); sys.exit(app.exec())