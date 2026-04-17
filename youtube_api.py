import os
import sys
import time
import sqlite3
import requests
import webbrowser
import ctypes
import collections
import subprocess
import tempfile
import shutil
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Tuple

from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QPushButton,
                               QLineEdit, QListWidget, QWidget, QMessageBox, QLabel,
                               QFileDialog, QHBoxLayout, QComboBox, QProgressBar,
                               QListWidgetItem, QFrame, QStackedWidget, QDialog,
                               QSizePolicy)
from PySide6.QtGui import QPixmap, QImage, QIcon, QFont
from PySide6.QtCore import Qt, QThread, Signal, QSize, QRunnable, QObject, QThreadPool, QProcess, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
import yt_dlp
from plyer import notification
from contextlib import contextmanager

# ==========================================
# CONFIGURACIÓN DE VERSIÓN Y GITHUB
# ==========================================
CURRENT_VERSION = "2.2.1"
GITHUB_REPO = "Daniel-Velez/Youtube_Downloader_V2"
MAX_THUMBNAIL_CACHE = 200
TEMP_THUMBS_DIR = Path(tempfile.gettempdir()) / "dynatube_thumbs"

# ==========================================
# UTILIDADES DE LIMPIEZA
# ==========================================
def init_temp_dir():
    """Inicializa el directorio temporal para miniaturas"""
    TEMP_THUMBS_DIR.mkdir(exist_ok=True)
    
def cleanup_temp_thumbs(older_than_hours: int = 24):
    """Limpia miniaturas temporales antiguas"""
    if not TEMP_THUMBS_DIR.exists():
        return
    
    current_time = time.time()
    for thumb_file in TEMP_THUMBS_DIR.glob("*.jpg"):
        try:
            if current_time - thumb_file.stat().st_mtime > (older_than_hours * 3600):
                thumb_file.unlink()
        except Exception as e:
            print(f"Error limpiando {thumb_file}: {e}")

def cleanup_all_temp_thumbs():
    """Elimina todas las miniaturas temporales"""
    if TEMP_THUMBS_DIR.exists():
        try:
            shutil.rmtree(TEMP_THUMBS_DIR)
        except Exception as e:
            print(f"Error limpiando directorio temporal: {e}")

# ==========================================
# BASE DE DATOS
# ==========================================
DB_NAME = "history.db"

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    try:
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error en base de datos: {e}")
        raise
    finally:
        conn.close()

def init_db():
    with get_db_connection() as conn:
        # Modificamos la tabla de descargas para incluir el username
        conn.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                title TEXT NOT NULL,
                type TEXT NOT NULL,
                url TEXT,
                file_path TEXT,
                date TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON downloads(date DESC)")
        
        # Nueva tabla para usuarios
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
            )
        """)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username: str, password: str) -> bool:
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, hash_password(password))
            )
        return True
    except sqlite3.IntegrityError:
        return False  # El usuario ya existe

def verify_user(username: str, password: str) -> bool:
    try:
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT password_hash FROM users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()
            if row and row[0] == hash_password(password):
                return True
            return False
    except sqlite3.Error as e:
        print(f"Error verificando usuario: {e}")
        return False

def add_to_history(username: str, title: str, tipo: str, url: str = "", file_path: str = ""):
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO downloads (username, title, type, url, file_path) VALUES (?, ?, ?, ?, ?)",
                (username, title, tipo, url, file_path)
            )
    except sqlite3.Error as e:
        print(f"Error guardando historial: {e}")

def get_recent_history(username: str, limit: int = 100) -> List[Tuple]:
    try:
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT title, type, date, url, file_path FROM downloads WHERE username = ? OR username IS NULL ORDER BY id DESC LIMIT ?",
                (username, limit)
            )
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error leyendo historial: {e}")
        return []

def clear_history(username: str):
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM downloads WHERE username = ?", (username,))
    except sqlite3.Error as e:
        print(f"Error limpiando historial: {e}")


# ==========================================
# UTILIDADES
# ==========================================
def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath('.')
    return os.path.join(base_path, relative_path)

def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """Sanitiza nombres de archivo de forma más robusta"""
    # Caracteres permitidos
    valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_")
    sanitized = "".join(c if c in valid_chars else "_" for c in filename)
    sanitized = " ".join(sanitized.split())  # Normaliza espacios
    sanitized = sanitized.strip()[:max_length]
    return sanitized if sanitized else "descarga_sin_titulo"

# ==========================================
# ESTILOS (sin cambios, mantener igual)
# ==========================================
PREMIUM_DARK_STYLE = """
    QMainWindow, QDialog { background-color: #0d0d12; }
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
    QScrollBar:vertical { border: none; background: transparent; width: 6px; }
    QScrollBar::handle:vertical { background: #2a2a3a; border-radius: 3px; min-height: 24px; }
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
        border-radius: 14px;
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
    
    QListWidget#HistoryList { 
        background: #111118; border: 1px solid #1e1e2a;
        border-radius: 12px; padding: 12px; 
    }
    QListWidget#HistoryList::item { 
        padding: 11px; border-bottom: 1px solid #1e1e2a;
        color: #c0c0d8; font-size: 13px; 
    }
    QListWidget#HistoryList::item:hover { 
        background: #16161f; border-radius: 6px; 
    }

    QFrame#HistoryCard { border-bottom: 1px solid #1e1e2a; padding: 0px 5px; background: transparent; }
    QFrame#HistoryCard:hover { background: #16161f; border-radius: 5px; }
    QLabel#HistoryText { color: #c0c0d8; font-size: 13px; background: transparent; }
    QPushButton#HistoryBtnUrl, QPushButton#HistoryBtnFolder {
        background-color: #1e1e2b; border: 1px solid #2a2a3e; border-radius: 6px; 
        font-size: 11px; font-weight: bold; padding: 0px 15px;
    }
    QPushButton#HistoryBtnUrl { color: #00e5ff; }
    QPushButton#HistoryBtnUrl:hover { background-color: #2a2a3e; color: #33eeff; }
    QPushButton#HistoryBtnFolder { color: #a855f7; }
    QPushButton#HistoryBtnFolder:hover { background-color: #2a2a3e; color: #c084fc; }

    QFrame#QueueItem { border-bottom: 1px solid #1e1e2a; background: transparent; padding: 0px; }
    QFrame#QueueItem:hover { background: #16161f; border-radius: 6px; }
    QLabel#QueueTitle { color: #c0c0d8; font-size: 12px; font-weight: bold; background: transparent; }
    QLabel#QueueStatus { color: #8080a0; font-size: 10px; background: transparent; }
    QPushButton#QueueBtnPause, QPushButton#QueueBtnCancel {
        border-radius: 4px; font-size: 14px; background: #2a2a3e; border: none; padding: 4px;
    }
    QPushButton#QueueBtnPause:hover { background: #363650; }
    QPushButton#QueueBtnCancel { 
        background: #1e2a2a;
        color: #00e5ff;
        border: 1px solid #2a3e3e;
    }
    QPushButton#QueueBtnCancel:hover { 
        background: #2a3e3e; 
        color: #ff4757;
    }
    QPushButton#btnPrimary {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00c8e0, stop:1 #0099bb);
    border: none; color: #050a0c; font-weight: 800; border-radius: 10px;
    }
    QPushButton#btnPrimary:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #33d4ed, stop:1 #00b0cc);
    }
    QPushButton#btnSecondary {
    background: transparent;
    border: 2px solid #252535; color: #e2e2e5; font-weight: 800; border-radius: 10px;
    }
    QPushButton#btnSecondary:hover { border-color: #00e5ff; color: #00e5ff; }
"""

PREMIUM_LIGHT_STYLE = """
    QMainWindow { background-color: #f5f5f7; }
    QWidget { font-family: 'Segoe UI', sans-serif; color: #1d1d1f; }

    QFrame#Sidebar {
        background-color: #ffffff;
        border-right: 1px solid #d2d2d7;
    }

    QPushButton#MenuBtn {
        background-color: transparent; border: none; text-align: left;
        padding: 13px 22px; font-size: 13px; font-weight: 600; color: #86868b;
        border-radius: 8px; margin: 2px 12px;
    }
    QPushButton#MenuBtn:hover { background-color: #f5f5f7; color: #1d1d1f; }
    QPushButton#MenuBtn[active="true"] {
        color: #0071e3; background-color: #e8f2ff;
        border-left: 3px solid #0071e3; padding-left: 19px;
        border-radius: 0px 8px 8px 0px;
    }

    QLineEdit {
        background-color: #ffffff; border: 1.5px solid #d2d2d7; padding: 11px 16px;
        border-radius: 10px; color: #1d1d1f; font-size: 14px;
    }
    QLineEdit:focus { border: 1.5px solid #0071e3; background-color: #ffffff; }
    QLineEdit::placeholder { color: #86868b; }

    QListWidget { background-color: transparent; border: none; outline: none; }
    QScrollBar:vertical { border: none; background: transparent; width: 6px; }
    QScrollBar::handle:vertical { background: #d2d2d7; border-radius: 3px; min-height: 24px; }
    QScrollBar::handle:vertical:hover { background: #0071e3; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

    QPushButton {
        background-color: #ffffff; border: 1px solid #d2d2d7; padding: 10px 16px;
        border-radius: 8px; font-weight: 700; font-size: 12px; color: #1d1d1f;
        letter-spacing: 0.5px;
    }
    QPushButton:hover { background-color: #f5f5f7; border-color: #c8c8cf; }
    QPushButton:pressed { background-color: #e8e8ed; }

    QPushButton#btnSearch {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0071e3, stop:1 #005bb5);
        border: none; color: white; font-weight: 800; border-radius: 10px;
    }
    QPushButton#btnSearch:hover {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0081f2, stop:1 #0066cc);
    }
    QPushButton#btnFolder {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #5e5ce6, stop:1 #4b49b8);
        border: none; color: white; font-weight: 800; border-radius: 10px;
    }
    QPushButton#btnFolder:hover {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #6c6af0, stop:1 #5553cc);
    }

    QPushButton#btnClear {
        background-color: transparent; border: 1px solid #ff3b30; color: #ff3b30;
        border-radius: 8px;
    }
    QPushButton#btnClear:hover { background-color: #ff3b30; color: white; }

    QComboBox {
        background-color: #ffffff; color: #1d1d1f; border: 1px solid #d2d2d7;
        border-radius: 6px; padding: 5px 10px; font-size: 12px; font-weight: 600;
    }
    QComboBox::drop-down { border: none; width: 20px; }
    QComboBox QAbstractItemView {
        background-color: #ffffff; color: #1d1d1f;
        selection-background-color: #0071e3; selection-color: white;
        border: 1px solid #d2d2d7; border-radius: 6px;
    }

    QProgressBar {
        border: none; background-color: #e8e8ed; height: 5px;
        text-align: center; color: transparent; border-radius: 3px;
    }
    QProgressBar::chunk {
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 #0071e3, stop:0.5 #5e5ce6, stop:1 #bf5af2);
        border-radius: 3px;
    }

    QFrame#VideoCard {
        background-color: #ffffff;
        border-radius: 14px;
        border: 1px solid #d2d2d7;
    }
    QFrame#VideoCard:hover {
        background-color: #fafafa;
        border: 1px solid #c8c8cf;
    }

    QFrame#QueuePanel {
        background: #ffffff; border-radius: 14px; border: 1px solid #d2d2d7;
    }

    QLabel#TitleCard { color: #1d1d1f; }

    QMessageBox { background-color: #ffffff; }
    QMessageBox QLabel { color: #1d1d1f; font-size: 13px; }
    QMessageBox QPushButton {
        background-color: #0071e3; color: white; min-width: 90px;
        padding: 8px; font-weight: 800; border-radius: 8px; border: none;
    }
    QMessageBox QPushButton:hover { background-color: #0081f2; }
    
    QListWidget#HistoryList { 
        background: transparent; border: 1px solid #d2d2d7;
        border-radius: 12px; padding: 12px; 
    }
    QListWidget#HistoryList::item { 
        padding: 11px; border-bottom: 1px solid #d2d2d7;
        color: #1d1d1f; font-size: 13px; 
    }
    QListWidget#HistoryList::item:hover { 
        background: #f5f5f7; border-radius: 6px; 
    }

    QFrame#HistoryCard { border-bottom: 1px solid #d2d2d7; padding: 0px 5px; background: transparent; }
    QFrame#HistoryCard:hover { background: #f5f5f7; border-radius: 5px; }
    QLabel#HistoryText { color: #1d1d1f; font-size: 13px; font-weight: 500; background: transparent; }
    QPushButton#HistoryBtnUrl, QPushButton#HistoryBtnFolder {
        border-radius: 6px; font-size: 11px; font-weight: bold; padding: 0px 15px;
    }
    QPushButton#HistoryBtnUrl { background-color: #e8f2ff; color: #0071e3; border: 1px solid #bce0fd; }
    QPushButton#HistoryBtnUrl:hover { background-color: #cce4ff; }
    QPushButton#HistoryBtnFolder { background-color: #f0eafb; color: #5e5ce6; border: 1px solid #d8ccf8; }
    QPushButton#HistoryBtnFolder:hover { background-color: #e2d4f5; }

    QFrame#QueueItem { border-bottom: 1px solid #d2d2d7; background: transparent; padding: 0px; }
    QFrame#QueueItem:hover { background: #f5f5f7; border-radius: 6px; }
    QLabel#QueueTitle { color: #1d1d1f; font-size: 12px; font-weight: bold; background: transparent; }
    QLabel#QueueStatus { color: #86868b; font-size: 10px; background: transparent; }
    QPushButton#QueueBtnPause, QPushButton#QueueBtnCancel {
        border-radius: 4px; font-size: 14px; background: #e8e8ed; border: none; padding: 4px;
    }
    QPushButton#QueueBtnPause:hover { background: #d2d2d7; }
    QPushButton#QueueBtnCancel { 
        background: #f0f4f4; 
        color: #0071e3; 
        border: 1px solid #d2dada;
    }
    QPushButton#QueueBtnCancel:hover { 
        background: #ffebeb;
        color: #ff3b30; 
    }
"""

# ==========================================
# DIÁLOGO DE LOGIN
# ==========================================
class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dynatube - Iniciar Sesión")
        self.setFixedSize(400, 520) # Aumenté un poco el alto para que quepa el nuevo botón
        self.setStyleSheet(PREMIUM_DARK_STYLE)
        self.logged_in_user = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(15) # Reduje un poco el espaciado

        # Logo
        logo = QLabel("⚡")
        logo.setStyleSheet("font-size: 60px; font-weight: bold; color: #00e5ff;")
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)

        title = QLabel("Bienvenido a Dynatube")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(10)

        # Inputs
        self.txt_username = QLineEdit()
        self.txt_username.setPlaceholderText("Nombre de usuario")
        self.txt_username.setFixedHeight(45)
        layout.addWidget(self.txt_username)

        self.txt_password = QLineEdit()
        self.txt_password.setPlaceholderText("Contraseña")
        self.txt_password.setEchoMode(QLineEdit.Password)
        self.txt_password.setFixedHeight(45)
        layout.addWidget(self.txt_password)

        layout.addSpacing(10)

        # Botones Principales
        self.btn_login = QPushButton("INICIAR SESIÓN")
        self.btn_login.setObjectName("btnPrimary")
        self.btn_login.setFixedHeight(45)
        self.btn_login.clicked.connect(self.attempt_login)
        layout.addWidget(self.btn_login)

        self.btn_register = QPushButton("CREAR CUENTA")
        self.btn_register.setObjectName("btnSecondary")
        self.btn_register.setFixedHeight(45)
        self.btn_register.clicked.connect(self.attempt_register)
        layout.addWidget(self.btn_register)

        # --- NUEVO BOTÓN DE INVITADO ---
        self.btn_guest = QPushButton("Continuar sin cuenta")
        self.btn_guest.setFixedHeight(30)
        self.btn_guest.setCursor(Qt.PointingHandCursor)
        self.btn_guest.setStyleSheet("""
            QPushButton { background: transparent; border: none; color: #8080a0; font-weight: bold; }
            QPushButton:hover { color: #00e5ff; text-decoration: underline; }
        """)
        self.btn_guest.clicked.connect(self.attempt_guest)
        layout.addWidget(self.btn_guest, alignment=Qt.AlignCenter)

    def attempt_login(self):
        user = self.txt_username.text().strip()
        pwd = self.txt_password.text().strip()

        if not user or not pwd:
            QMessageBox.warning(self, "Error", "Por favor, llena ambos campos.")
            return

        if verify_user(user, pwd):
            self.logged_in_user = user
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Usuario o contraseña incorrectos.")

    def attempt_register(self):
        user = self.txt_username.text().strip()
        pwd = self.txt_password.text().strip()

        if not user or not pwd:
            QMessageBox.warning(self, "Error", "Por favor, llena ambos campos para registrarte.")
            return

        if register_user(user, pwd):
            QMessageBox.information(self, "Éxito", "Cuenta creada. Ahora puedes iniciar sesión.")
        else:
            QMessageBox.warning(self, "Error", "Ese nombre de usuario ya existe.")

    def attempt_guest(self):
        self.logged_in_user = "Invitado"
        self.accept()

# ==========================================
# TARJETA DE HISTORIAL
# ==========================================
class HistoryCard(QFrame):
    def __init__(self, title: str, type_emoji: str, date: str, url: str, file_path: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.file_path = file_path
        
        self.setObjectName("HistoryCard")
        self.setFixedHeight(55)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(15)

        text = f"{type_emoji}   {title}   —   {date}"
        self.lbl_text = QLabel(text)
        self.lbl_text.setObjectName("HistoryText")
        layout.addWidget(self.lbl_text, 1)

        if url:
            self.btn_open_url = QPushButton("🌐 Abrir Link")
            self.btn_open_url.setObjectName("HistoryBtnUrl")
            self.btn_open_url.setFixedHeight(30)
            self.btn_open_url.setCursor(Qt.PointingHandCursor)
            self.btn_open_url.clicked.connect(self._open_url)
            layout.addWidget(self.btn_open_url)

        if file_path:
            self.btn_open_folder = QPushButton("📁 Ver Archivo")
            self.btn_open_folder.setObjectName("HistoryBtnFolder")
            self.btn_open_folder.setFixedHeight(30)
            self.btn_open_folder.setCursor(Qt.PointingHandCursor)
            self.btn_open_folder.clicked.connect(self._open_folder)
            layout.addWidget(self.btn_open_folder)

    def _open_url(self):
        if self.url:
            webbrowser.open(self.url)

    def _open_folder(self):
        if not self.file_path:
            return
        try:
            path = os.path.normpath(self.file_path)
            if os.path.exists(path):
                subprocess.run(['explorer', '/select,', path], check=False)
            else:
                folder = os.path.dirname(path)
                if os.path.exists(folder):
                    os.startfile(folder)
        except Exception as e:
            print(f"Error al abrir: {e}")

# ==========================================
# WIDGET DE ITEM DE COLA (INTERACTIVO)
# ==========================================
class QueueItemWidget(QFrame):
    pause_toggled = Signal(int)
    cancel_clicked = Signal(int)

    def __init__(self, tid: int, title: str, parent=None):
        super().__init__(parent)
        self.tid = tid
        self.setFixedHeight(55)
        self.setObjectName("QueueItem")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(10)

        info_lyt = QVBoxLayout()
        info_lyt.setSpacing(2)
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("QueueTitle")
        
        self.lbl_status = QLabel("En espera")
        self.lbl_status.setObjectName("QueueStatus")
        
        info_lyt.addWidget(self.lbl_title)
        info_lyt.addWidget(self.lbl_status)
        layout.addLayout(info_lyt, 1)

        self.btn_pause = QPushButton("⏸️")
        self.btn_pause.setObjectName("QueueBtnPause")
        self.btn_pause.setFixedSize(30, 30)
        self.btn_pause.setCursor(Qt.PointingHandCursor)
        self.btn_pause.clicked.connect(lambda: self.pause_toggled.emit(self.tid))
        self.btn_pause.hide()

        self.btn_cancel = QPushButton("❌")
        self.btn_cancel.setObjectName("QueueBtnCancel")
        self.btn_cancel.setFixedSize(30, 30)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(lambda: self.cancel_clicked.emit(self.tid))
        self.btn_cancel.hide()

        layout.addWidget(self.btn_pause)
        layout.addWidget(self.btn_cancel)

    def set_status(self, status: str):
        self.lbl_status.setText(status)
        
    def set_pause_icon(self, is_paused: bool):
        self.btn_pause.setText("▶️" if is_paused else "⏸️")

    def enterEvent(self, event):
        self.btn_pause.show()
        self.btn_cancel.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.btn_pause.hide()
        self.btn_cancel.hide()
        super().leaveEvent(event)

# ==========================================
# HILOS OPTIMIZADOS
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

    def __init__(self, query: str, start_index: int = 0, parent=None):
        super().__init__(parent)
        self.query = query
        self.start_index = start_index
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        is_link = "http" in self.query
        is_playlist_link = is_link and ("list=" in self.query or "/playlist" in self.query)
        sq = self.query if is_link else f"ytsearch100:{self.query}"
        
        opts = {
            'quiet': True, 
            'extract_flat': True, 
            'skip_download': True, 
            'noplaylist': not is_playlist_link, 
            'ignoreerrors': True, 
            'no_warnings': True
        }
        
        if not is_link or is_playlist_link:
            opts['playlist_items'] = f"{self.start_index+1}-{self.start_index+20}"
            
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                res = ydl.extract_info(sq, download=False)
                if self._cancelled:
                    return
                    
                if res:
                    entries = res.get('entries', [res])
                    for e in (entries or []):
                        if self._cancelled:
                            return
                        if not e:
                            continue
                            
                        v_id = e.get('id')
                        url = e.get('webpage_url') or e.get('url')
                        if not url and v_id:
                            url = f"https://www.youtube.com/watch?v={v_id}"
                            
                        thumb = ""
                        if e.get('thumbnails'):
                            thumb = e['thumbnails'][-1].get('url', '')
                        elif v_id:
                            thumb = f"https://i.ytimg.com/vi/{v_id}/hqdefault.jpg"
                            
                        dur = e.get('duration', 0) or 0
                        
                        self.video_found.emit({
                            'titulo': e.get('title', 'Sin título'), 
                            'url': url, 
                            'thumb': thumb,
                            'duracion': f"{int(dur//60)}:{int(dur%60):02d}", 
                            'uploader': e.get('uploader', 'YouTube'),
                        })
        except Exception as e:
            if not self._cancelled:
                self.error_signal.emit(str(e)[:60])
        finally:
            self.finished_search.emit()


class QualityLoader(QThread):
    qualities_ready = Signal(list)
    error = Signal()

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            opts = {
                'quiet': True, 
                'skip_download': True, 
                'no_warnings': True, 
                'noplaylist': True, 
                'extract_flat': 'in_playlist'
            }
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                
                if self._cancelled:
                    return
                    
                q_list, seen = [], set()
                formats = sorted(
                    [f for f in info.get('formats', []) if f.get('height') and f.get('ext') == 'mp4'],
                    key=lambda x: x.get('height', 0), 
                    reverse=True
                )
                
                for f in formats:
                    if self._cancelled:
                        return
                        
                    note = f.get('format_note', '')
                    h = f.get('height', 0)
                    
                    if note and 'p' in str(note).lower():
                        res = str(note)
                    else:
                        if h >= 2160:
                            res = "2160p (4K)"
                        elif h >= 1440:
                            res = "1440p (2K)"
                        elif h >= 1080:
                            res = "1080p"
                        elif h >= 720:
                            res = "720p"
                        else:
                            res = f"{h}p"
                            
                    if res not in seen:
                        q_list.append((res, f['format_id']))
                        seen.add(res)
                        
            if not self._cancelled:
                self.qualities_ready.emit(q_list)
        except Exception:
            if not self._cancelled:
                self.error.emit()


class ThumbnailSignals(QObject):
    done = Signal(bytes, str)


class ThumbnailWorker(QRunnable):
    def __init__(self, url: str):
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
    progress = Signal(int, int) 
    status = Signal(str, int)
    finished_dl = Signal(bool, str, int)

    def __init__(self, url: str, tipo: str, format_id: Optional[str], path: str, titulo: str, tid: int, parent=None):
        super().__init__(parent)
        self.url = url
        self.tipo = tipo
        self.format_id = format_id
        self.path = path
        self.tid = tid
        self.titulo = sanitize_filename(titulo)
        self._is_cancelled = False
        self._temp_thumb_path = None

    def stop(self): 
        self._is_cancelled = True

    def run(self):
        try:
            has_ffprobe = os.path.exists(resource_path('ffprobe.exe'))
            is_playlist = "list=" in self.url
            
            template = os.path.join(
                self.path, 
                "%(playlist_title)s", 
                "%(title)s.%(ext)s"
            ) if is_playlist else os.path.join(self.path, f"{self.titulo}.%(ext)s")

            opts = {
                'ffmpeg_location': resource_path('ffmpeg.exe'),
                'outtmpl': template, 
                'quiet': True, 
                'no_warnings': True, 
                'noprogress': True,
                'noplaylist': False if is_playlist else True,
                'playlist_items': None if is_playlist else '1', 
                'progress_hooks': [self.progress_hook], 
                'postprocessors': [],
            }

            # Gestión optimizada de miniaturas para MP3
            if self.tipo == "audio" and has_ffprobe:
                # Crear archivo temporal para la miniatura
                self._temp_thumb_path = TEMP_THUMBS_DIR / f"thumb_{self.tid}_{int(time.time())}.jpg"
                
                opts['writethumbnail'] = True
                opts['postprocessors'].extend([
                    {'key': 'FFmpegMetadata', 'add_metadata': True},
                    {'key': 'EmbedThumbnail', 'already_have_thumbnail': False},
                ])
                opts['format'] = 'bestaudio/best'
                opts['postprocessors'].insert(0, {
                    'key': 'FFmpegExtractAudio', 
                    'preferredcodec': 'mp3', 
                    'preferredquality': '192'
                })
                
            elif self.tipo == "video":
                if has_ffprobe:
                    opts['writethumbnail'] = True
                    opts['postprocessors'].extend([
                        {'key': 'FFmpegMetadata', 'add_metadata': True},
                        {'key': 'EmbedThumbnail', 'already_have_thumbnail': False},
                    ])
                    
                fmt = f"{self.format_id}+bestaudio[ext=m4a]/{self.format_id}+bestaudio/best" if self.format_id else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                opts['format'] = fmt
                opts['merge_output_format'] = 'mp4'

            self.status.emit("Iniciando..." if not is_playlist else "Iniciando lista...", self.tid)
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([self.url])

            ext = "mp3" if self.tipo == "audio" else "mp4"
            final_path = self.path if is_playlist else os.path.join(self.path, f"{self.titulo}.{ext}")
            
            if not self._is_cancelled:
                self.finished_dl.emit(True, final_path, self.tid)
                
        except Exception as e:
            if self._is_cancelled:
                self.finished_dl.emit(False, "Cancelado", self.tid)
            else:
                self.finished_dl.emit(False, str(e), self.tid)
        finally:
            # Limpieza de miniatura temporal para MP3
            self._cleanup_temp_thumbnail()

    def _cleanup_temp_thumbnail(self):
        """Elimina la miniatura temporal después del procesamiento"""
        if self._temp_thumb_path and self._temp_thumb_path.exists():
            try:
                # Buscar y eliminar archivos de miniatura temporales asociados
                base_name = os.path.splitext(self.titulo)[0]
                output_dir = Path(self.path)
                
                # Patrones comunes de miniaturas de yt-dlp
                thumb_patterns = [
                    f"{base_name}.jpg",
                    f"{base_name}.webp",
                    f"{base_name}.png",
                ]
                
                for pattern in thumb_patterns:
                    thumb_file = output_dir / pattern
                    if thumb_file.exists():
                        thumb_file.unlink()
                        
                # Eliminar el archivo temporal marcado
                self._temp_thumb_path.unlink()
                
            except Exception as e:
                print(f"Error limpiando miniatura temporal: {e}")

    def progress_hook(self, d):
        if self._is_cancelled:
            raise Exception("Cancelado") 
            
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            dl = d.get('downloaded_bytes', 0)
            if total and total > 0:
                self.progress.emit(int(dl / total * 100), self.tid)
                self.status.emit(f"({dl/(1024*1024):.1f} / {total/(1024*1024):.1f} MB)", self.tid)
            else:
                self.status.emit(f"Descargando ({dl/(1024*1024):.1f} MB)...", self.tid)
        elif d['status'] == 'finished':
            self.progress.emit(100, self.tid)
            self.status.emit("Procesando...", self.tid)


class StreamFetcher(QThread):
    stream_url_ready = Signal(str)
    error = Signal(str)

    def __init__(self, yt_url: str, parent=None):
        super().__init__(parent)
        self.yt_url = yt_url
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

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
    def __init__(self, video_url: str, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Previsualización: {title}")
        self.setFixedSize(840, 500)
        self.setStyleSheet("QDialog { background-color: #0d0d12; border: 1px solid #1e1e2a; }")
        
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)

        self.loading_lbl = QLabel("Cargando stream... ⚡")
        self.loading_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #00e5ff; padding: 20px;")
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

    def play_video(self, url: str):
        self.loading_lbl.hide()
        self.video_widget.show()
        self.player.setSource(QUrl(url))
        self.player.play()

    def show_error(self, msg: str):
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
# VIDEO CARD OPTIMIZADO
# ==========================================
class VideoCard(QFrame):
    request_download = Signal(dict)

    def __init__(self, data: Dict, cache_refe: collections.OrderedDict, cache_setter=None, parent=None):
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
        self.setFixedWidth(300)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 14)
        root.setSpacing(10)

        thumb_container = QWidget()
        thumb_container.setFixedSize(300, 168)
        thumb_container.setStyleSheet("background: transparent;")

        self.img = QLabel(thumb_container)
        self.img.setFixedSize(300, 168)
        self.img.setStyleSheet("background-color: #0d0d16; border-radius: 12px;")
        self.img.setScaledContents(True)

        self.btn_preview = QPushButton("▶", thumb_container)
        self.btn_preview.setFixedSize(54, 54)
        self.btn_preview.setCursor(Qt.PointingHandCursor)
        self.btn_preview.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 140); color: rgba(255, 255, 255, 220);
                border-radius: 27px; font-size: 22px; padding-left: 4px;
                border: 2px solid rgba(255, 255, 255, 50);
            }
            QPushButton:hover {
                background-color: rgba(255, 0, 0, 200); color: white;
                border: 2px solid rgba(255, 255, 255, 100);
            }
        """)
        self.btn_preview.move(123, 57)
        self.btn_preview.clicked.connect(self.show_preview)
        self.btn_preview.raise_()

        self.dur_badge = QLabel(data['duracion'], thumb_container)
        self.dur_badge.setStyleSheet(
            "background-color: rgba(0,0,0,0.85); color: #ffffff; "
            "font-size: 11px; font-weight: 700; padding: 3px 6px; border-radius: 4px;"
        )
        self.dur_badge.adjustSize()
        self.dur_badge.move(300 - self.dur_badge.width() - 8, 168 - self.dur_badge.height() - 8)
        self.dur_badge.raise_()

        root.addWidget(thumb_container)

        body = QHBoxLayout()
        body.setContentsMargins(12, 0, 12, 0)
        body.setSpacing(12)

        self.avatar = QLabel(self._uploader[0].upper() if self._uploader else "?")
        self.avatar.setFixedSize(36, 36)
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setStyleSheet("background-color: #2a2a3e; color: #ffffff; font-weight: bold; font-size: 16px; border-radius: 18px;")
        body.addWidget(self.avatar, alignment=Qt.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self.title_lbl = QLabel(data['titulo'])
        self.title_lbl.setObjectName("TitleCard")
        self.title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; line-height: 1.2; border: none;")
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.channel_lbl = QLabel(data['uploader'])
        self.channel_lbl.setStyleSheet("color: #aaaaaa; font-size: 12px; font-weight: 500; border: none;")

        text_layout.addWidget(self.title_lbl)
        text_layout.addWidget(self.channel_lbl)
        body.addLayout(text_layout)
        root.addLayout(body)

        actions = QHBoxLayout()
        actions.setContentsMargins(12, 8, 12, 0)
        actions.setSpacing(6)

        self.combo = QComboBox()
        self.combo.addItem("Calidad...", None)
        self.combo.setFixedHeight(28)
        self.combo.setCursor(Qt.PointingHandCursor)
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.btn_mp4 = QPushButton("⬇ MP4")
        self.btn_mp4.setFixedHeight(28)
        self.btn_mp4.setCursor(Qt.PointingHandCursor)
        self.btn_mp4.clicked.connect(self._on_mp4_clicked)
        self.btn_mp4.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00c8e0, stop:1 #0099bb);
                color: #ffffff; border: none; font-weight: 800; border-radius: 6px; padding: 4px 8px;
            }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #33d4ed, stop:1 #00b0cc); }
        """)

        self.btn_mp3 = QPushButton("♫ MP3")
        self.btn_mp3.setFixedHeight(28)
        self.btn_mp3.setCursor(Qt.PointingHandCursor)
        self.btn_mp3.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00c8e0, stop:1 #0099bb);
                color: #ffffff; border: none; font-weight: 800; border-radius: 6px; padding: 4px 8px;
            }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #33d4ed, stop:1 #00b0cc); }
        """)
        self.btn_mp3.clicked.connect(self._on_mp3_clicked)

        actions.addWidget(self.combo)
        actions.addWidget(self.btn_mp4)
        actions.addWidget(self.btn_mp3)
        root.addLayout(actions)

        if self.thumb_url in self.cache:
            self.set_thumb(self.cache[self.thumb_url])
        else:
            worker = ThumbnailWorker(self.thumb_url)
            worker.signals.done.connect(self.save_and_set_thumb)
            QThreadPool.globalInstance().start(worker)

    def _on_mp4_clicked(self):
        if self.combo.currentData() is None:
            QMessageBox.warning(self, "Calidad no cargada", "Selecciona el video primero para cargar las calidades disponibles.")
            return
        self.request_download.emit({
            'url': self.url, 
            'tipo': 'video', 
            'itag': self.combo.currentData(), 
            'titulo': self._titulo
        })

    def _on_mp3_clicked(self):
        self.request_download.emit({
            'url': self.url, 
            'tipo': 'audio', 
            'itag': None, 
            'titulo': self._titulo
        })

    def show_preview(self):
        self.preview_window = PreviewDialog(self.url, self._titulo, self)
        self.preview_window.exec()

    def save_and_set_thumb(self, content: bytes, url: str):
        self._cache_setter(url, content)
        self.set_thumb(content)

    def set_thumb(self, content: bytes):
        img = QImage()
        if img.loadFromData(content):
            self.img.setPixmap(QPixmap.fromImage(img))


# ==========================================
# VENTANA PRINCIPAL OPTIMIZADA
# ==========================================
class YoutubeDownloader(QMainWindow):
    def __init__(self, username: str):
        super().__init__()
        self.current_user = username if username else "Invitado"
        init_db()
        init_temp_dir()
        cleanup_temp_thumbs(24)  # Limpia miniaturas de más de 24 horas
        
        self.is_dark_mode = True 
        self.setStyleSheet(PREMIUM_DARK_STYLE)
        self.setWindowTitle(f"Dynatube Pro — {CURRENT_VERSION} | Usuario: {self.current_user}")
        
        self.setMinimumSize(1480, 800) 
        self.resize(1500, 850)

        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.download_path = os.path.join(os.path.expanduser("~"), "Downloads")
        self.is_loading = False
        self.current_page = 0
        self.last_query = ""
        
        # Sistema de cola inteligente
        self.task_counter = 0
        self.tasks: Dict[int, Dict] = {}
        self.queue_order: List[int] = []
        self.current_task_id: Optional[int] = None
        
        self.thumbnail_cache = collections.OrderedDict()
        self.qualities_cache: Dict[str, List[Tuple[str, str]]] = {}

        self.search_thr: Optional[YtDlpSearchEngine] = None
        self.q_thr: Optional[QualityLoader] = None
        self.current_worker: Optional[DownloadWorker] = None
        self.local_process: Optional[QProcess] = None

        self.threadpool = QThreadPool.globalInstance()
        self.threadpool.setMaxThreadCount(max(4, QThread.idealThreadCount() // 2))

        self.init_ui()
        self.check_for_updates()

    def safe_cache_thumbnail(self, url: str, content: bytes):
        """Gestión segura de caché de miniaturas con límite"""
        if url in self.thumbnail_cache:
            self.thumbnail_cache.move_to_end(url)
            return
        if len(self.thumbnail_cache) >= MAX_THUMBNAIL_CACHE:
            self.thumbnail_cache.popitem(last=False)
        self.thumbnail_cache[url] = content

    def check_for_updates(self):
        self.updater = UpdateChecker()
        self.updater.update_available.connect(self.show_update_dialog)
        self.updater.start()

    def show_update_dialog(self, latest: str, url: str):
        msg = QMessageBox(self)
        msg.setWindowTitle("Actualización disponible")
        msg.setText(f"<h3>Nueva versión {latest} disponible</h3><p>Versión actual: {CURRENT_VERSION}</p><p>¿Abrir GitHub para descargar?</p>")
        msg.setIcon(QMessageBox.Icon.Information)
        yes = msg.addButton("Descargar", QMessageBox.ButtonRole.AcceptRole)
        no = msg.addButton("Quizá más tarde", QMessageBox.ButtonRole.RejectRole)
        no.setStyleSheet("background:#1e1e2b; color:white;")
        msg.exec()
        if msg.clickedButton() == yes:
            webbrowser.open(url)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # SIDEBAR
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(200) 
        sl = QVBoxLayout(self.sidebar)
        sl.setContentsMargins(0, 36, 0, 20)
        sl.setSpacing(6)

        logo = QLabel("⚡  Dynatube")
        logo.setStyleSheet("font-weight: 900; font-size: 20px; color: #00e5ff; padding: 0 10px 28px 10px; letter-spacing: 1px;")
        sl.addWidget(logo)

        self.btn_nav_search = self._nav_btn("🔍   Descargar", 0, True)
        self.btn_nav_conv   = self._nav_btn("🔄   Convertidor", 1)
        self.btn_nav_hist   = self._nav_btn("📜   Historial", 2)
        sl.addWidget(self.btn_nav_search)
        sl.addWidget(self.btn_nav_conv)
        sl.addWidget(self.btn_nav_hist)
        sl.addStretch()

        self.btn_theme = QPushButton("☀️  Modo Claro")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.setStyleSheet("""
            QPushButton { background-color: #1a1a24; color: #ccccdd; border: 1px solid #1e1e2a; 
                          border-radius: 18px; margin: 10px; padding: 10px; font-weight: bold; font-size: 11px;}
            QPushButton:hover { background-color: #252535; }
        """)
        self.btn_theme.clicked.connect(self.toggle_theme)
        sl.addWidget(self.btn_theme)

        ver = QLabel(f"v{CURRENT_VERSION}")
        ver.setStyleSheet("color: #8080a0; font-size: 11px; font-weight: 700; padding-left: 12px;")
        sl.addWidget(ver)

        root.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        self._setup_search_page()
        self._setup_converter_page()
        self._setup_history_page()

    def _nav_btn(self, text: str, index: int, active: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("MenuBtn")
        btn.setProperty("active", active)
        btn.clicked.connect(lambda: self.switch_page(index))
        return btn

    def _setup_search_page(self):
        page = QWidget()
        lyt = QVBoxLayout(page)
        lyt.setContentsMargins(36, 32, 36, 20)
        lyt.setSpacing(18)

        # Barra superior
        top = QHBoxLayout()
        top.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Pega un enlace o escribe lo que buscas...")
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
        self.path_display.setStyleSheet("color: #8080a0; font-size: 12px; font-weight: 500;")
        lyt.addWidget(self.path_display)

        # Body
        body = QHBoxLayout()
        body.setSpacing(22)

        # Lista de resultados
        self.result_list = QListWidget()
        self.result_list.setSpacing(15) 
        self.result_list.setViewMode(QListWidget.IconMode)
        self.result_list.setResizeMode(QListWidget.Adjust) 
        self.result_list.setMovement(QListWidget.Static)
        self.result_list.setWordWrap(True)
        self.result_list.setStyleSheet(
            self.result_list.styleSheet() + 
            "QListWidget { padding-left: 30px; } QListWidget::item { margin: 5px; background: transparent; }"
        )

        self.result_list.itemSelectionChanged.connect(self.load_qualities)
        self.result_list.verticalScrollBar().valueChanged.connect(self.handle_scroll)
        body.addWidget(self.result_list, 7) 

        # Panel de cola interactiva
        queue_panel = QFrame()
        queue_panel.setObjectName("QueuePanel")
        queue_panel.setMaximumWidth(380)
        queue_panel.setMinimumWidth(300)
        
        ql = QVBoxLayout(queue_panel)
        ql.setContentsMargins(18, 18, 18, 18)
        ql.setSpacing(14)

        lbl_q = QLabel("COLA DE DESCARGAS")
        lbl_q.setStyleSheet("color: #8080a0; font-weight: 800; font-size: 12px; letter-spacing: 1px;")
        ql.addWidget(lbl_q)

        self.queue_list_widget = QListWidget()
        self.queue_list_widget.setStyleSheet("QListWidget { border:none; background:transparent; }")
        ql.addWidget(self.queue_list_widget)

        btn_clear = QPushButton("LIMPIAR TODO")
        btn_clear.setObjectName("btnClear")
        btn_clear.clicked.connect(self.clear_queue)
        ql.addWidget(btn_clear)

        body.addWidget(queue_panel, 3) 
        lyt.addLayout(body)

        self.status_lbl = QLabel("ESTADO: EN ESPERA")
        self.status_lbl.setStyleSheet("color: #0071e3; font-weight: 800; font-size: 11px; letter-spacing: 1px;")
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

        icon = QLabel("⚡")
        icon.setStyleSheet("font-size: 44px;")
        icon.setAlignment(Qt.AlignCenter)

        title = QLabel("Conversión Local")
        title.setObjectName("TitleCard")
        title.setStyleSheet("font-size: 22px; font-weight: 800;")
        title.setAlignment(Qt.AlignCenter)

        desc = QLabel("Convierte archivos de video a MP3 sin conexión.")
        desc.setStyleSheet("color:#8080a0; font-size:13px;")
        desc.setAlignment(Qt.AlignCenter)

        btn = QPushButton("SELECCIONAR ARCHIVOS")
        btn.setFixedSize(300, 48)
        btn.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0071e3, stop:1 #005bb5); color:white; font-size:13px; font-weight:800; border:none; border-radius:10px;")
        btn.clicked.connect(self.start_local_conversion)

        self.conv_status = QLabel("Listo.")
        self.conv_status.setStyleSheet("color:#0071e3; font-weight:700;")
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
        title.setObjectName("TitleCard")
        title.setStyleSheet("font-size: 17px; font-weight: 800; letter-spacing: 1px;")
        lyt.addWidget(title)

        self.hist_list = QListWidget(page)
        self.hist_list.setObjectName("HistoryList")
        lyt.addWidget(self.hist_list)

        btn_ref = QPushButton("ACTUALIZAR")
        btn_ref.setFixedSize(180, 42)
        btn_ref.setStyleSheet("background:#5e5ce6; border:none; color:white; font-weight:800; border-radius:8px;")
        btn_ref.clicked.connect(self.load_history)
        lyt.addWidget(btn_ref, alignment=Qt.AlignRight)

        self.stack.addWidget(page)

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        if self.is_dark_mode:
            self.setStyleSheet(PREMIUM_DARK_STYLE)
            self.btn_theme.setText("☀️  Modo Claro")
            self.btn_theme.setStyleSheet("""
                QPushButton { background-color: #1a1a24; color: #ccccdd; border: 1px solid #1e1e2a; 
                              border-radius: 18px; margin: 10px; padding: 10px; font-weight: bold; font-size: 11px;}
                QPushButton:hover { background-color: #252535; }
            """)
        else:
            self.setStyleSheet(PREMIUM_LIGHT_STYLE)
            self.btn_theme.setText("🌙  Modo Oscuro")
            self.btn_theme.setStyleSheet("""
                QPushButton { background-color: #e8e8ed; color: #1d1d1f; border: 1px solid #d2d2d7; 
                              border-radius: 18px; margin: 10px; padding: 10px; font-weight: bold; font-size: 11px;}
                QPushButton:hover { background-color: #d2d2d7; }
            """)
        
        # Refrescar estilos
        self.style().unpolish(self)
        self.style().polish(self)
        
        for i in range(self.result_list.count()):
            widget = self.result_list.itemWidget(self.result_list.item(i))
            if widget:
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                
        for i in range(self.hist_list.count()):
            widget = self.hist_list.itemWidget(self.hist_list.item(i))
            if widget:
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                
        for i in range(self.queue_list_widget.count()):
            widget = self.queue_list_widget.itemWidget(self.queue_list_widget.item(i))
            if widget:
                widget.style().unpolish(widget)
                widget.style().polish(widget)

    def switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate([self.btn_nav_search, self.btn_nav_conv, self.btn_nav_hist]):
            btn.setProperty("active", i == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if index == 2:
            self.load_history()

    def load_history(self):
        self.hist_list.clear()
        records = get_recent_history(self.current_user, 100)
        for row in records:
            title, tipo, date, url, file_path = row
            emoji = "🎵" if tipo == "audio" else "🎬"
            item = QListWidgetItem(self.hist_list)
            card = HistoryCard(title, emoji, date, url, file_path)
            item.setSizeHint(QSize(0, 55)) 
            self.hist_list.setItemWidget(item, card)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta")
        if folder:
            self.download_path = folder
            self.path_display.setText(f"Guardando en: {folder}")

    def _stop_thread(self, attr: str):
        """Para y limpia threads de forma segura"""
        t = getattr(self, attr, None)
        if t and t.isRunning():
            try:
                if hasattr(t, 'cancel'):
                    t.cancel()
                t.disconnect()
            except:
                pass
            t.quit()
            t.wait(2000)
            setattr(self, attr, None)

    def start_search(self):
        q = self.search_input.text().strip()
        if not q:
            return

        if "list=" in q:
            reply = QMessageBox.question(
                self, 
                "Lista", 
                "¿Deseas cargar la lista completa?", 
                QMessageBox.Yes | QMessageBox.No
            )
            self.last_query = q if reply == QMessageBox.Yes else q.split("&list=")[0]
        else:
            self.last_query = q

        self.result_list.clear()
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
            self._set_status("BÚSQUEDA COMPLETADA", "#0071e3" if not self.is_dark_mode else "#00e5ff")

    def _set_status(self, text: str, color: str = "#00e5ff"):
        self.status_lbl.setText(f"ESTADO: {text}")
        self.status_lbl.setStyleSheet(f"color:{color}; font-weight:800; font-size:11px; letter-spacing:1px;")

    def add_video_card(self, data: Dict):
        item = QListWidgetItem(self.result_list)
        card = VideoCard(data, self.thumbnail_cache, cache_setter=self.safe_cache_thumbnail)
        card.request_download.connect(self._enqueue_from_card)
        item.setSizeHint(QSize(300, 290)) 
        self.result_list.setItemWidget(item, card)

    def handle_scroll(self, val: int):
        bar = self.result_list.verticalScrollBar()
        if val > bar.maximum() * 0.9 and not self.is_loading and self.last_query:
            self.current_page += 20
            self._execute_search()

    def load_qualities(self):
        item = self.result_list.currentItem()
        if not item:
            return
            
        card = self.result_list.itemWidget(item)
        if card and not card.q_ready:
            if card.url in self.qualities_cache:
                self._fill_combo(card, self.qualities_cache[card.url])
                return
                
            self._stop_thread('q_thr')
            card.combo.clear()
            card.combo.addItem("Cargando...", None)
            
            self.q_thr = QualityLoader(card.url)
            self.q_thr.qualities_ready.connect(lambda q: self._on_qualities_loaded(card, q))
            self.q_thr.start()

    def _on_qualities_loaded(self, card: VideoCard, qualities: List[Tuple[str, str]]):
        self.qualities_cache[card.url] = qualities
        self._fill_combo(card, qualities)

    def _fill_combo(self, card: VideoCard, qualities: List[Tuple[str, str]]):
        try:
            if card and not card.isHidden():
                card.combo.clear()
                for res, itag in qualities:
                    card.combo.addItem(res, itag)
                card.q_ready = True
        except RuntimeError:
            pass

    # ==========================================
    # LÓGICA DE COLA INTELIGENTE
    # ==========================================
    def _enqueue_from_card(self, task_partial: Dict):
        self.task_counter += 1
        tid = self.task_counter

        task = {
            'url':   task_partial['url'],
            'tipo':  task_partial['tipo'],
            'itag':  task_partial['itag'],
            'path':  self.download_path,
            'titulo': task_partial['titulo'],
        }

        widget = QueueItemWidget(tid, task['titulo'])
        widget.pause_toggled.connect(self.on_queue_pause)
        widget.cancel_clicked.connect(self.on_queue_cancel)

        self.tasks[tid] = {
            'id': tid,
            'data': task,
            'status': 'pending',
            'widget': widget
        }
        self.queue_order.append(tid)

        item = QListWidgetItem(self.queue_list_widget)
        item.setSizeHint(QSize(0, 55))
        self.queue_list_widget.setItemWidget(item, widget)
        self.tasks[tid]['list_item'] = item

        if self.current_task_id is None:
            self._process_next()

    def on_queue_pause(self, tid: int):
        if tid not in self.tasks:
            return
            
        task_info = self.tasks[tid]

        if task_info['status'] == 'paused':
            # Reanudar
            task_info['status'] = 'pending'
            task_info['widget'].set_status("En espera")
            task_info['widget'].set_pause_icon(False)
            
            if self.current_task_id is None:
                self._process_next()

        elif task_info['status'] in ('pending', 'downloading'):
            # Pausar
            was_downloading = (task_info['status'] == 'downloading')
            task_info['status'] = 'paused'
            task_info['widget'].set_status("Pausado")
            task_info['widget'].set_pause_icon(True)

            if was_downloading:
                self.current_task_id = None
                if self.current_worker:
                    self.current_worker.stop()
                self._process_next()

    def on_queue_cancel(self, tid: int):
        if tid not in self.tasks:
            return
            
        was_downloading = (self.tasks[tid]['status'] == 'downloading')

        # Remover de la lista visual
        item = self.tasks[tid]['list_item']
        row = self.queue_list_widget.row(item)
        self.queue_list_widget.takeItem(row)

        # Eliminar de registros
        del self.tasks[tid]
        self.queue_order.remove(tid)

        if was_downloading:
            self.current_task_id = None
            if self.current_worker:
                self.current_worker.stop()
            self._process_next()
        elif self.current_task_id is None:
            self._process_next()

    def _process_next(self):
        if self.current_task_id is not None:
            return

        # Buscar primera tarea pendiente
        for tid in self.queue_order:
            if self.tasks[tid]['status'] == 'pending':
                self.current_task_id = tid
                self.tasks[tid]['status'] = 'downloading'
                self.tasks[tid]['widget'].set_status("Iniciando...")
                
                t_data = self.tasks[tid]['data']
                self.current_worker = DownloadWorker(
                    t_data['url'], 
                    t_data['tipo'], 
                    t_data['itag'], 
                    t_data['path'], 
                    t_data['titulo'], 
                    tid
                )
                self.current_worker.progress.connect(self.update_progress)
                self.current_worker.status.connect(self.update_status)
                self.current_worker.finished_dl.connect(self._finish_dl)
                self.current_worker.start()
                return

        # No hay nada pendiente
        self.current_task_id = None
        self.pbar.setValue(0)
        self._set_status("COLA EN ESPERA", "#8080a0")

    def update_progress(self, val: int, tid: int):
        if tid == self.current_task_id:
            self.pbar.setValue(val)

    def update_status(self, msg: str, tid: int):
        if tid == self.current_task_id:
            self._set_status(msg.upper(), "#00e5ff" if self.is_dark_mode else "#0071e3")
        if tid in self.tasks and self.tasks[tid]['status'] == 'downloading':
            self.tasks[tid]['widget'].set_status(msg)

    def _finish_dl(self, ok: bool, msg: str, tid: int):
        if tid not in self.tasks:
            return

        if msg == "Cancelado":
            pass
        elif ok:
            task = self.tasks[tid]['data']
            try:
                notification.notify(
                    title="¡Descarga completada! ✅", 
                    message=task['titulo'], 
                    app_name="Dynatube", 
                    timeout=5
                )
            except Exception:
                pass
            
            add_to_history(self.current_user, task['titulo'], task['tipo'], task['url'], msg)

            # Remover de lista y registros
            item = self.tasks[tid]['list_item']
            row = self.queue_list_widget.row(item)
            self.queue_list_widget.takeItem(row)
            del self.tasks[tid]
            self.queue_order.remove(tid)

            self.current_task_id = None
            self._process_next()
        else:
            QMessageBox.warning(self, "Error de descarga", msg)
            self.tasks[tid]['status'] = 'error'
            self.tasks[tid]['widget'].set_status("Error de descarga")
            self.current_task_id = None
            self._process_next()

    def clear_queue(self):
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.stop()
        self.tasks.clear()
        self.queue_order.clear()
        self.queue_list_widget.clear()
        self.current_task_id = None
        self._set_status("COLA VACIADA", "#8080a0")
        self.pbar.setValue(0)

    # ==========================================
    # CONVERTIDOR LOCAL
    # ==========================================
    def start_local_conversion(self):
        if self.local_process and self.local_process.state() == QProcess.ProcessState.Running:
            QMessageBox.warning(self, "Aviso", "Ya hay una conversión en curso.")
            return
            
        files, _ = QFileDialog.getOpenFileNames(
            self, 
            "Seleccionar videos", 
            "", 
            "Videos (*.mp4 *.mkv *.avi *.webm *.mov)"
        )
        
        if not files:
            return
            
        self.conv_queue = [f for f in files if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm'))]
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
        self.local_process.start(
            resource_path('ffmpeg.exe'), 
            ['-y', '-i', current, '-vn', '-c:a', 'libmp3lame', '-q:a', '2', '-threads', '0', out]
        )

    def _on_conv_done(self, code: int, _):
        if code == 0:
            done = self.total_conv - len(self.conv_queue)
            self.conv_pbar.setValue(int(done / self.total_conv * 100))
            self._next_conversion()
        else:
            QMessageBox.critical(self, "Error de conversión", "Verifica el formato o ffmpeg.exe.")
            self.conv_queue.clear()
            self.conv_status.setText("Operación interrumpida")
            self.conv_pbar.setValue(0)

    def closeEvent(self, event):
        """Limpieza al cerrar la aplicación"""
        # Detener descargas activas
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.stop()
            self.current_worker.quit()
            self.current_worker.wait(3000)
        
        # Detener threads de búsqueda
        self._stop_thread('search_thr')
        self._stop_thread('q_thr')
        
        # Limpiar miniaturas temporales
        cleanup_all_temp_thumbs()
        
        event.accept()


# ==========================================
# ENTRY POINT
# ==========================================
if __name__ == "__main__":
    os.environ["QT_LOGGING_RULES"] = "qt.qpa.*=false"

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('DynatubePro.App')
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    # 1. Inicializar base de datos primero
    init_db()

    # 2. Lanzar la ventana de Login
    login_dialog = LoginDialog()
    if login_dialog.exec() == QDialog.Accepted:
        # 3. Solo si el login es exitoso, abrimos la aplicación principal
        window = YoutubeDownloader(username=login_dialog.logged_in_user)
        window.show() 
        sys.exit(app.exec())
    else:
        # Si el usuario cierra la ventana de login, la app termina
        sys.exit(0)