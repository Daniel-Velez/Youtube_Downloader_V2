import PyInstaller.__main__
import os

def build():
    PyInstaller.__main__.run([
        'main.py',
        '--name=Yachay_Downloader_ROG',
        '--onefile',
        '--windowed',
        '--noconfirm',
        '--clean',
        '--add-data=.env;.', # Incluye tu API Key
        '--collect-all=PySide6',
        '--hidden-import=moviepy.video.io.VideoFileClip',
        '--hidden-import=moviepy.audio.io.AudioFileClip',
    ])

if __name__ == "__main__":
    build() 