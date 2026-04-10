## 📺 YouTube Downloader V2
Una aplicación de escritorio moderna y eficiente construida con Python y PySide6 para buscar y descargar videos o audio de YouTube. Esta versión incluye una interfaz inspirada en el modo oscuro de YouTube ("Graphene Style"), soporte para colas de descarga y aceleración por hardware.

✨ Características
Búsqueda Integrada: Busca videos directamente desde la aplicación sin necesidad de copiar URLs (aunque también las soporta).

Scroll Infinito: Los resultados se cargan dinámicamente a medida que navegas.

Descarga de Listas de Reproducción: Detecta automáticamente si un link pertenece a una playlist y ofrece descargarla completa.

Cola de Descargas: Gestiona múltiples descargas de forma secuencial. Puedes ver y limpiar la cola en tiempo real.

Selección de Calidad: Carga dinámicamente las resoluciones disponibles para cada video (MP4).

Conversión a MP3: Extrae audio de alta calidad (192kbps) de forma automática.

Aceleración por Hardware: Detecta automáticamente si tienes NVIDIA (NVENC) para optimizar procesos de FFmpeg.

Actualizaciones Automáticas: El sistema verifica si hay una nueva versión en el repositorio y permite actualizar el ejecutable con un solo clic.

🚀 Requisitos
Para ejecutar el código fuente o realizar modificaciones, necesitarás:

Python 3.8+

FFmpeg instalado en el sistema y añadido al PATH (necesario para la conversión de audio y fusión de video HQ).

## 🛠️ Instalación
1. Clona el repositorio.
2. Crea un entorno virtual: `python -m venv venv`.
3. Instala dependencias: `pip install -r requirements.txt`.
4. Usa la aplicación.
   
La interfaz utiliza un diseño Graphene Style personalizado:

Sidebar: Control de búsqueda, cambio de carpeta de destino y gestión de la cola.

Resultados: Tarjetas visuales con miniatura, duración y selector de calidad.

Barra de Progreso: Visualización del estado actual de la descarga en curso.

📝 Notas de Versión (v2.0.0)
Migración completa a yt-dlp para búsquedas más rápidas.

Uso de pytubefix para mayor estabilidad con los cambios de la API de YouTube.

Implementación de hilos (QThread) para evitar que la interfaz se congele.

Desarrollado por Daniel Vélez 🚀
