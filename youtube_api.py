import os
import sys
import requests
import subprocess
import webbrowser
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QPushButton, 
                               QLineEdit, QListWidget, QWidget, QMessageBox, QLabel, 
                               QFileDialog, QHBoxLayout, QComboBox, QProgressBar, 
                               QListWidgetItem, QFrame)
from PySide6.QtGui import QPixmap, QImage, Qt, QIcon
from PySide6.QtCore import Qt, QThread, Signal, QSize
from pytubefix import YouTube
import yt_dlp
from pytubefix import Playlist


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath('.')
    return os.path.join(base_path, relative_path)


# --- ESTILO VISUAL ---
GRAPHENE_STYLE = """
    QMainWindow { background-color: #080808; }
    QWidget { color: #dcdcdc; font-family: 'Segoe UI', Roboto, Helvetica, sans-serif; }
    
    QFrame#Sidebar { 
        background-color: #0f0f0f; 
        border-right: 1px solid #1a1a1a; 
    }
    
    QLabel#SidebarTitle { 
        color: #ffffff; font-weight: 900; font-size: 22px; 
        margin-bottom: 20px; border-bottom: 3px solid #3ea6ff;
        padding-bottom: 10px; letter-spacing: 1px;
    }

    QLineEdit { 
        background-color: #161616; border: 1px solid #252525; 
        padding: 10px 15px; border-radius: 8px; color: white; font-size: 13px;
    }
    QLineEdit:focus { border: 1px solid #3ea6ff; background-color: #1a1a1a; }

    QListWidget { background-color: transparent; border: none; outline: none; padding: 10px; }
    
    /* Scrollbar Minimalista */
    QScrollBar:vertical { border: none; background: transparent; width: 5px; margin: 0; }
    QScrollBar::handle:vertical { background: #333; border-radius: 2px; min-height: 20px; }
    QScrollBar::handle:vertical:hover { background: #3ea6ff; }

    /* Botones Laterales */
    QPushButton { 
        background-color: #1c1c1c; border: 1px solid #2a2a2a; padding: 10px; 
        border-radius: 8px; font-weight: 700; font-size: 11px;
        color: #efefef; text-transform: uppercase;
    }
    QPushButton:hover { background-color: #252525; border: 1px solid #353535; }
    QPushButton:pressed { background-color: #121212; }

    QPushButton#btnActionVideo { background-color: #ffffff; color: #000000; border: none; }
    QPushButton#btnActionVideo:hover { background-color: #e0e0e0; }
    
    QPushButton#btnActionAudio { background-color: #3ea6ff; color: #ffffff; border: none; }
    QPushButton#btnActionAudio:hover { background-color: #52b1ff; }

    /* Estilo del ComboBox */
    QComboBox {
        background-color: #1c1c1c; color: #ddd; border: 1px solid #333;
        border-radius: 6px; padding: 4px 10px; font-size: 11px;
    }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView {
        background-color: #161616; color: white;
        selection-background-color: #3ea6ff; border: 1px solid #333;
    }

    /* Barra de Progreso */
    QProgressBar { 
        border: none; background-color: #161616; height: 4px; 
        text-align: center; color: transparent; border-radius: 2px; 
    }
    QProgressBar::chunk { background-color: #3ea6ff; border-radius: 2px; }

    /* Corrección para cuadros de mensajes (QMessageBox) */
    QMessageBox { background-color: #1a1a1a; }
    QMessageBox QLabel { color: #ffffff; font-size: 14px; }
    QMessageBox QPushButton { 
        background-color: #3ea6ff; 
        color: white; 
        min-width: 80px; 
        padding: 6px; 
    }
"""

def get_hw_acceleration():
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        out = subprocess.check_output(['ffmpeg', '-encoders'], startupinfo=si).decode()
        return "nvidia" if 'h264_nvenc' in out else "cpu"
    except: return "cpu"

# --- HILOS DE PROCESAMIENTO ---

class YtDlpSearchEngine(QThread):
    video_found = Signal(dict)
    finished = Signal()
    
    def __init__(self, query, start_index=0): # Cambiado a 0 por defecto
        super().__init__()
        self.query = query
        self.start_index = start_index 

    def run(self):
        # Si es URL directa, la usamos tal cual, si no, búsqueda de YT
        sq = self.query if "http" in self.query else f"ytsearch100:{self.query}"
        
        # yt-dlp usa índices basados en 1. 
        # Si start_index es 0 -> pedimos 1 a 20.
        # Si start_index es 20 -> pedimos 21 a 40.
        inicio = self.start_index + 1
        fin = self.start_index + 20

        opts = {
            'quiet': True, 
            'extract_flat': True, 
            'skip_download': True,
            'playlist_items': f"{inicio}-{fin}", 
            'noplaylist': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                res = ydl.extract_info(sq, download=False)
                if res:
                    # Manejo de resultados (si es lista o video único)
                    entries = res.get('entries', [res])
                    for e in entries:
                        if not e: continue
                        self.video_found.emit({
                            'titulo': e.get('title', 'Sin título'),
                            'url': e.get('url') or f"https://www.youtube.com/watch?v={e.get('id')}",
                            'thumb': e.get('thumbnails', [{}])[-1].get('url', ''),
                            'duracion': f"{int(e.get('duration', 0)//60)}:{int(e.get('duration', 0)%60):02d}",
                            'uploader': e.get('uploader', 'YouTube')
                        })
        except Exception as e:
            print(f"Error en extracción: {e}")
            
        self.finished.emit()

class QualityLoader(QThread):
    qualities_ready = Signal(list)
    error = Signal()

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            yt = YouTube(self.url)
            streams = yt.streams.filter(file_extension='mp4').order_by('resolution').desc()
            q_list = []
            seen_res = set()
            for s in streams:
                if s.resolution and s.resolution not in seen_res:
                    q_list.append((s.resolution, s.itag))
                    seen_res.add(s.resolution)
            self.qualities_ready.emit(q_list)
        except:
            self.error.emit()

class DownloadWorker(QThread):
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, url, tipo, itag, path, titulo):
        super().__init__()
        self.url, self.tipo, self.itag, self.path = url, tipo, itag, path
        self.titulo = "".join([c for c in titulo if c.isalnum() or c in (' ', '-', '_')]).strip()
        self.hw = get_hw_acceleration()

    def run(self):
        try:
            yt = YouTube(self.url, on_progress_callback=self.on_p)
            if self.titulo == "Cargando título..." or not self.titulo:
                raw_title = yt.title
                # Elimina caracteres no permitidos en nombres de archivos
                self.titulo = "".join([c for c in raw_title if c.isalnum() or c in (' ', '-', '_')]).strip()
            if self.tipo == "audio":
                self.status.emit("Descargando Audio...")
                audio_s = yt.streams.filter(only_audio=True).first()
                temp_file = audio_s.download(output_path=self.path, filename="audio_temp")
                final_mp3 = os.path.join(self.path, f"{self.titulo}.mp3")
                self.status.emit("Convirtiendo a MP3...")
                self.run_ffmpeg(['-i', temp_file, '-vn', '-ab', '192k', '-ar', '44100', '-y', final_mp3])
                if os.path.exists(temp_file): os.remove(temp_file)
            else:
                s = yt.streams.get_by_itag(self.itag)
                final_path = os.path.join(self.path, f"{self.titulo}.mp4")
                if s.is_progressive:
                    self.status.emit("Descargando...")
                    s.download(output_path=self.path, filename=f"{self.titulo}.mp4")
                else:
                    self.status.emit("Descargando Video HQ...")
                    v_t = s.download(output_path=self.path, filename="v_tmp.mp4")
                    self.status.emit("Descargando Audio...")
                    a_t = yt.streams.filter(only_audio=True).first().download(output_path=self.path, filename="a_tmp.mp4")
                    self.status.emit("Fusionando...")
                    self.run_ffmpeg(['-i', v_t, '-i', a_t, '-c', 'copy', '-y', final_path])
                    for f in [v_t, a_t]: 
                        if os.path.exists(f): os.remove(f)
            self.finished.emit(True, "Completado")
        except Exception as e: self.finished.emit(False, str(e))

    def run_ffmpeg(self, args):
        si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return subprocess.run(['ffmpeg'] + args, startupinfo=si).returncode == 0

    def on_p(self, stream, chunk, rem):
        self.progress.emit(int(((stream.filesize - rem) / stream.filesize) * 100))

# --- UI COMPONENTS ---

class ThumbnailWorker(QThread):
    done = Signal(bytes)
    def __init__(self, url): super().__init__(); self.url = url
    def run(self):
        try: 
            r = requests.get(self.url, timeout=5)
            self.done.emit(r.content)
        except: pass

class VideoCard(QFrame):
    def __init__(self, data):
        super().__init__()
        self.url = data['url']
        self.q_ready = False
        self.setObjectName("VideoCard")
        self.setStyleSheet("""
            QFrame#VideoCard { 
                background-color: #121212; 
                border-radius: 12px; 
                border: 1px solid #1e1e1e;
            }
            QFrame#VideoCard:hover { 
                background-color: #181818; 
                border: 1px solid #3ea6ff; 
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 15, 10)
        layout.setSpacing(15)
        
        # Miniatura con esquinas redondeadas
        self.img = QLabel()
        self.img.setFixedSize(140, 80)
        self.img.setStyleSheet("background-color: #000; border-radius: 8px;")
        self.img.setScaledContents(True)
        
        info_lyt = QVBoxLayout()
        info_lyt.setSpacing(4)
        
        self.title_lbl = QLabel(data['titulo'])
        self.title_lbl.setStyleSheet("font-size: 14px; color: #f0f0f0; font-weight: bold; background:transparent; border:none;")
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setMaximumHeight(40)
        
        self.meta_lbl = QLabel(f"● {data['uploader']}   |   {data['duracion']}")
        self.meta_lbl.setStyleSheet("color: #888; font-size: 11px; background:transparent; border:none;")
        
        bottom = QHBoxLayout()
        bottom.addWidget(self.meta_lbl)
        bottom.addStretch()
        
        self.combo = QComboBox()
        self.combo.addItem("Calidad...", None)
        self.combo.setFixedWidth(100)
        self.combo.setFixedHeight(26)
        bottom.addWidget(self.combo)
        
        info_lyt.addWidget(self.title_lbl)
        info_lyt.addLayout(bottom)
        
        layout.addWidget(self.img)
        layout.addLayout(info_lyt, 1)

        self.t_loader = ThumbnailWorker(data['thumb'])
        self.t_loader.done.connect(self.set_thumb)
        self.t_loader.start()

    def set_thumb(self, content):
        px = QImage(); px.loadFromData(content)
        self.img.setPixmap(QPixmap.fromImage(px))

class YoutubeDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(GRAPHENE_STYLE)
        self.setWindowTitle("YouTube Downloader - V2")
        self.setMinimumSize(1000, 700)
        self.download_path = os.path.join(os.path.expanduser("~"), "Downloads")
        self.is_loading = False
        self.current_page = 1
        self.last_query = ""
        self.init_ui()
        self.check_updates()
        self.download_queue = []  # Nueva lista para la cola
        self.is_downloading = False # Control de estado de la cola
        self.init_ui()

    def init_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        main_lyt = QHBoxLayout(central); main_lyt.setContentsMargins(0,0,0,0)
        
        icon_path = resource_path("icoV2.ico") 
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            # Si no encuentra el .ico, intentamos con el .png del logo como respaldo
            logo_respaldo = resource_path("youtube_logo.png")
            if os.path.exists(logo_respaldo):
                self.setWindowIcon(QIcon(logo_respaldo))

        sidebar = QFrame(); sidebar.setObjectName("Sidebar"); sidebar.setFixedWidth(280)
        side_lyt = QVBoxLayout(sidebar)
        side_lyt.setContentsMargins(20, 30, 20, 20) # Más espacio arriba
        
        # --- ENCABEZADO: TEXTO EN DOS LÍNEAS + LOGO ---
        header_layout = QHBoxLayout()
        header_layout.setSpacing(15)

        # Usamos \n para forzar el diseño de la imagen
        title = QLabel("YouTube\nDownloader") 
        title.setObjectName("SidebarTitle")
        title.setWordWrap(True) # Permite el salto de línea
        
        logo = QLabel()
        logo_pix = QPixmap("youtube_logo.png") # Asegúrate de tener tu logo.png
        if not logo_pix.isNull():
            logo.setPixmap(logo_pix.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        
        header_layout.addWidget(title)
        header_layout.addWidget(logo)
        header_layout.addStretch() # Mantiene todo alineado a la izquierda

        side_lyt.addLayout(header_layout)
        side_lyt.addSpacing(15) # Espacio antes del buscador
        # ------------------------------------------
        
        self.search_input = QLineEdit(); self.search_input.setPlaceholderText("Buscar...")
        self.search_input.returnPressed.connect(self.start_search)
        btn_search = QPushButton("BUSCAR"); btn_search.clicked.connect(self.start_search)
        
        path_box = QFrame(); path_box.setStyleSheet("background: #1a1a1a; border-radius: 6px;")
        # --- PANEL DE COLA ---
        side_lyt.addSpacing(10)
        cola_label = QLabel("COLA DE DESCARGAS")
        cola_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #555; letter-spacing: 1px;")
        side_lyt.addWidget(cola_label)

        self.queue_list_widget = QListWidget()
        self.queue_list_widget.setObjectName("QueueList")
        self.queue_list_widget.setStyleSheet("""
            QListWidget#QueueList { 
                background-color: #0a0a0a; 
                border: 1px solid #1a1a1a; 
                border-radius: 8px; 
                max-height: 200px; 
            }
            QListWidget#QueueList::item { 
                padding: 5px; 
                border-bottom: 1px solid #151515; 
                font-size: 11px;
            }
        """)
        # Permitir eliminar de la cola con doble clic
        self.queue_list_widget.itemDoubleClicked.connect(self.remove_from_queue)
        side_lyt.addWidget(self.queue_list_widget)
        
        btn_clear_queue = QPushButton("LIMPIAR COLA")
        btn_clear_queue.setStyleSheet("font-size: 9px; padding: 5px; color: #888;")
        btn_clear_queue.clicked.connect(self.clear_queue)
        side_lyt.addWidget(btn_clear_queue)
        path_lyt = QVBoxLayout(path_box)
        self.path_display = QLabel(f"RUTA:\n{self.download_path}")
        self.path_display.setStyleSheet("font-size: 10px; color: #888;")
        self.path_display.setWordWrap(True)
        btn_path = QPushButton("CAMBIAR CARPETA"); btn_path.clicked.connect(self.select_folder)
        path_lyt.addWidget(self.path_display); path_lyt.addWidget(btn_path)
        
        self.status_lbl = QLabel("Estado: Listo"); self.status_lbl.setStyleSheet("color: #3ea6ff;")
        self.pbar = QProgressBar()
        self.btn_dl_v = QPushButton("DESCARGAR MP4"); self.btn_dl_v.setObjectName("btnActionVideo")
        self.btn_dl_v.clicked.connect(lambda: self.start_dl("video"))
        self.btn_dl_a = QPushButton("DESCARGAR MP3"); self.btn_dl_a.setObjectName("btnActionAudio")
        self.btn_dl_a.clicked.connect(lambda: self.start_dl("audio"))
        
        # Añadimos los widgets restantes
        side_lyt.addWidget(self.search_input)
        side_lyt.addWidget(btn_search)
        side_lyt.addSpacing(20)
        side_lyt.addWidget(path_box)
        side_lyt.addStretch()
        side_lyt.addWidget(self.status_lbl)
        side_lyt.addWidget(self.pbar)
        side_lyt.addWidget(self.btn_dl_v)
        side_lyt.addWidget(self.btn_dl_a)
        
        self.result_list = QListWidget()
        self.result_list.setSpacing(10)
        self.result_list.itemSelectionChanged.connect(self.load_qualities)
        self.result_list.verticalScrollBar().valueChanged.connect(self.handle_scroll)
        
        main_lyt.addWidget(sidebar); main_lyt.addWidget(self.result_list, 1)

    def remove_from_queue(self, item):
        """Elimina un video de la cola si el usuario hace doble clic."""
        row = self.queue_list_widget.row(item)
        self.queue_list_widget.takeItem(row)
        if row < len(self.download_queue):
            self.download_queue.pop(row)
        self.status_lbl.setText(f"Eliminado: {item.text()}")

    def clear_queue(self):
        """Limpia toda la cola pendiente."""
        self.download_queue.clear()
        self.queue_list_widget.clear()
        self.status_lbl.setText("Cola vaciada")

    def safe_stop_thread(self, thread_name):
        """Detiene el hilo de forma segura sin errores de desconexión."""
        if hasattr(self, thread_name):
            thread = getattr(self, thread_name)
            if thread and thread.isRunning():
                # En PySide6, para desconectar todo se usa .disconnect() 
                # pero suele fallar si no hay conexiones activas.
                try:
                    thread.disconnect() 
                except Exception:
                    pass 
                
                thread.quit()
                thread.wait()

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta")
        if folder: self.download_path = folder; self.path_display.setText(f"RUTA:\n{folder}")

    def check_updates(self):
        # Lógica de actualización movida al hilo principal para evitar errores de UI
        try:
            url_txt = "https://raw.githubusercontent.com/Daniel-Velez/Youtube_Downloader_V2/main/version.txt"
            res = requests.get(url_txt, timeout=3)
            if res.status_code == 200 and res.text.strip() != "2.0.0":
                if QMessageBox.question(self, "Actualización", "Nueva versión disponible. ¿Descargar?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
                    webbrowser.open("https://github.com/Daniel-Velez/Youtube_Downloader_V2/releases")
        except: pass

    def start_search(self):
            q = self.search_input.text().strip()
            if not q: return
            
            # IMPORTANTE: Al iniciar búsqueda nueva, reiniciamos a 0 y limpiamos
            self.result_list.clear()
            self.last_query = q
            self.current_page = 0 # Reiniciamos el índice
            self.execute_search()

    def execute_search(self):
            if self.is_loading: return
            
            self.safe_stop_thread('search_thr') 
            self.is_loading = True
            self.status_lbl.setText(f"Estado: Cargando resultados ({self.current_page})...")
            
            # Pasamos el current_page acumulado
            self.search_thr = YtDlpSearchEngine(self.last_query, self.current_page)
            self.search_thr.video_found.connect(self.add_video_card)
            self.search_thr.finished.connect(self.on_search_complete)
            self.search_thr.start()

    def on_search_complete(self):
            self.is_loading = False
            self.status_lbl.setText("Estado: Listo")

    def add_video_card(self, data):
            item = QListWidgetItem(self.result_list)
            item.setSizeHint(QSize(0, 115)) # 115px es la altura ideal con los nuevos márgenes
            card = VideoCard(data)
            self.result_list.setItemWidget(item, card)

    def handle_scroll(self, val):
            # Si llegamos al 90% del scroll y no hay nada cargándose actualmente
            if val > self.result_list.verticalScrollBar().maximum() * 0.9 and not self.is_loading:
                # El scroll infinito solo tiene sentido en búsquedas (no en links directos de un solo video)
                if self.last_query:
                    self.current_page += 20 # Incrementamos para la siguiente página
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
            
            # Conexión segura con validación de existencia
            self.q_thr.qualities_ready.connect(lambda q: self.fill_combo(w, q))
            
            # Para el error, también verificamos antes de tocar el combo
            self.q_thr.error.connect(lambda: self.handle_q_error(w))
            
            self.q_thr.start()

    def handle_q_error(self, widget):
        try:
            if widget: widget.combo.setItemText(0, "Error")
        except RuntimeError: pass

    def fill_combo(self, widget, qualities):
        # Verificamos que el widget no haya sido eliminado por Python o C++
        try:
            if widget is not None and not widget.isHidden():
                widget.combo.clear()
                for res, itag in qualities: 
                    widget.combo.addItem(res, itag)
                widget.q_ready = True
        except RuntimeError:
            # El widget fue eliminado, ignoramos la actualización
            pass

    def start_dl(self, tipo):
        item = self.result_list.currentItem()
        if not item: return
        w = self.result_list.itemWidget(item)
        
        if tipo == "video" and w.combo.currentData() is None:
            QMessageBox.warning(self, "Aviso", "Espera a que carguen las calidades."); return

        # --- LÓGICA DE PLAYLIST ---
        if "list=" in w.url:
            resp = QMessageBox.question(
                self, "Playlist detectada", 
                "¿Deseas descargar toda la lista de reproducción?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if resp == QMessageBox.Yes:
                try:
                    pl = Playlist(w.url)
                    for video_url in pl.video_urls:
                        # Creamos una tarea por cada video (usamos resolución por defecto o la elegida)
                        task = {
                            'url': video_url,
                            'tipo': tipo,
                            'itag': w.combo.currentData(), # Intentará usar el mismo itag si es compatible
                            'path': self.download_path,
                            'titulo': "Cargando título..." # Se actualizará al descargar
                        }
                        self.download_queue.append(task)
                        self.queue_list_widget.addItem(f"⌛ [PL] {video_url}")
                    
                    if not self.is_downloading:
                        self.process_next_in_queue()
                    return # Salimos para no descargar el video individual dos veces
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"No se pudo cargar la playlist: {e}")
        
        # --- DESCARGA INDIVIDUAL (Lo que ya tenías) ---
        task = {
            'url': w.url,
            'tipo': tipo,
            'itag': w.combo.currentData(),
            'path': self.download_path,
            'titulo': w.title_lbl.text()
        }
        self.download_queue.append(task)
        icono = "🎵" if tipo == "audio" else "🎥"
        self.queue_list_widget.addItem(f"{icono} {task['titulo']}")
        
        if not self.is_downloading:
            self.process_next_in_queue()

    def process_next_in_queue(self):
            # --- VERIFICACIÓN DE SEGURIDAD (SOLUCIÓN AL ERROR) ---
            if not self.download_queue:
                self.is_downloading = False
                self.status_lbl.setText("Estado: Todas las descargas completadas")
                self.pbar.setValue(0)
                # También limpiamos la lista visual por si acaso quedaron residuos
                self.queue_list_widget.clear() 
                return
            # -----------------------------------------------------

            self.is_downloading = True
            
            # Ahora es seguro hacer el pop
            task = self.download_queue.pop(0) 
            
            # Eliminar el primer elemento visual si existe
            if self.queue_list_widget.count() > 0:
                item = self.queue_list_widget.takeItem(0)
                del item
            
            self.status_lbl.setText(f"Descargando: {task['titulo']}...")
            
            self.dl_worker = DownloadWorker(
                task['url'], task['tipo'], task['itag'], task['path'], task['titulo']
            )
            self.dl_worker.progress.connect(self.pbar.setValue)
            self.dl_worker.status.connect(lambda s: self.status_lbl.setText(f"[{len(self.download_queue)} en cola] {s}"))
            self.dl_worker.finished.connect(self.finish_dl)
            self.dl_worker.start()

    def finish_dl(self, ok, msg):
            if not ok:
                QMessageBox.critical(self, "Error en descarga", f"Ocurrió un error: {msg}")
            
            # Pequeña pausa visual antes de la siguiente
            self.pbar.setValue(100)
            
            # IMPORTANTE: Llamamos al siguiente proceso en la cola
            self.process_next_in_queue()

    def closeEvent(self, event):
        """Detiene todo antes de salir para evitar errores de QThread."""
        self.safe_stop_thread('search_thr')
        self.safe_stop_thread('q_thr')
        if hasattr(self, 'dl_worker') and self.dl_worker.isRunning():
            self.dl_worker.terminate()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv); win = YoutubeDownloader(); win.show(); sys.exit(app.exec())