import sys
import os
import re
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk  
from tkinter import filedialog  # <-- IMPORTANTE: Ventana interactiva para elegir carpeta
import yt_dlp
import threading 

def obtener_ruta_recursos():
    """Detecta la ruta interna temporal si es un .exe empaquetado, o la normal si es script."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def mi_hook_progreso(d):
    """Función de yt_dlp que recibe la información del estado de la descarga en tiempo real."""
    if d['status'] == 'downloading':
        porcentaje_str = d.get('_percent_str', '0%')
        limpio = re.sub(r'\x1b\[[0-9;]*m', '', porcentaje_str).strip().replace('%', '')
        
        try:
            porcentaje = float(limpio)
        except ValueError:
            porcentaje = 0.0

        velocidad = d.get('_speed_str', 'Desconocida')
        descargado = d.get('_downloaded_bytes_str', '0MB')
        total = d.get('_total_bytes_str', d.get('_total_bytes_estimate_str', 'Desconocido'))

        texto_estado = f"Descargando: {porcentaje:.1f}% ({descargado} de {total}) a {velocidad}"
        root.after(0, lambda: lbl_status.config(text=texto_estado, fg="blue"))
        root.after(0, lambda: barra_progreso.config(value=porcentaje))
        
    elif d['status'] == 'finished':
        root.after(0, lambda: lbl_status.config(text="Procesando, uniendo y convirtiendo archivo... por favor espera.", fg="purple"))
        root.after(0, lambda: barra_progreso.config(value=100))

def proceso_descarga(url, formato, calidad, ruta_recursos, ruta_completa_guardado):
    """Esta función corre en segundo plano sin congelar la ventana."""
    opciones_base = {
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'mweb', 'android'],
            }
        },
        # Guardamos usando la ruta exacta y el nombre completo elegidos por el usuario
        'outtmpl': ruta_completa_guardado,
        'ffmpeg_location': ruta_recursos, 
        'progress_hooks': [mi_hook_progreso],
    }

    if formato == "audio":
        ydl_opts = {
            **opciones_base,
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    else:
        if calidad == "Máxima Calidad":
            ydl_opts = {
                **opciones_base,
                'format': 'bestvideo+bestaudio/best',
                'merge_output_format': 'mp4',
            }
        else:
            if calidad == "1080p Full HD":
                limite_altura = 1080
            elif calidad == "720p HD":
                limite_altura = 720
            elif calidad == "480p":
                limite_altura = 480
            else: 
                limite_altura = 360

            ydl_opts = {
                **opciones_base,
                'format': f'bestvideo[height<={limite_altura}]+bestaudio/best',
                'merge_output_format': 'mp4',
                'format_sort': [f'res:{limite_altura}', 'quality'],
            }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        root.after(0, lambda: lbl_status.config(text="¡Descarga completada con éxito!", fg="green"))
        root.after(0, lambda: messagebox.showinfo("Éxito", f"El archivo se guardó correctamente en tu equipo."))
        root.after(0, lambda: entry_url.delete(0, tk.END))
        root.after(0, lambda: barra_progreso.config(value=0))
    except Exception as ex:
        root.after(0, lambda: lbl_status.config(text="Ocurrió un error en la descarga.", fg="red"))
        root.after(0, lambda: messagebox.showerror("Error", f"No se pudo completar la descarga.\n{str(ex)}"))
        root.after(0, lambda: barra_progreso.config(value=0))
    finally:
        root.after(0, lambda: btn_download.config(state="normal"))

def iniciar_descarga():
    url = entry_url.get().strip()
    if not url:
        messagebox.showwarning("Atención", "Por favor, introduce una URL de YouTube.")
        return

    # 1. Obtener información previa del video para sugerir un nombre de archivo válido
    lbl_status.config(text="Obteniendo información del video...", fg="blue")
    root.update()
    
    ruta_recursos = obtener_ruta_recursos()
    formato = var_format.get()
    calidad = combo_calidad.get()

    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'extractor_args': {'youtube': {'player_client': ['web', 'mweb', 'android']}}}) as ydl:
            info = ydl.extract_info(url, download=False)
            titulo_video = info.get('title', 'video_descargado')
            # Limpiamos caracteres extraños que Windows no acepte en nombres
            titulo_valido = re.sub(r'[\\/*?:"<>|]', "", titulo_video)
    except Exception:
        titulo_valido = "archivo_descargado"

    # 2. Abrir el cuadro de diálogo para guardar el archivo
    extension = ".mp3" if formato == "audio" else ".mp4"
    tipos_archivos = [("Archivos de Audio MP3", "*.mp3")] if formato == "audio" else [("Video MP4", "*.mp4")]

    ruta_elegida = filedialog.asksaveasfilename(
        title="Selecciona dónde guardar la descarga",
        initialfile=titulo_valido + extension,
        filetypes=tipos_archivos,
        defaultextension=extension
    )

    # Si el usuario cierra la ventana de guardar o le da a cancelar
    if not ruta_elegida:
        lbl_status.config(text="Descarga cancelada por el usuario.", fg="orange")
        return

    # Si eligió MP3, yt_dlp descarga temporalmente en otra extensión, así que le pasamos una plantilla limpia
    if formato == "audio":
        # Extrae la carpeta y el nombre sin la extensión final dura, yt_dlp le pondrá .mp3 automáticamente al procesar
        directorio, archivo = os.path.split(ruta_elegida)
        nombre_sin_ext = os.path.splitext(archivo)[0]
        ruta_pasada = os.path.join(directorio, f"{nombre_sin_ext}.%(ext)s")
    else:
        ruta_pasada = ruta_elegida

    # 3. Bloquear botón e iniciar hilo secundario de descarga
    btn_download.config(state="disabled")
    lbl_status.config(text="Iniciando descarga...", fg="blue")
    barra_progreso.config(value=0)

    hilo = threading.Thread(target=proceso_descarga, args=(url, formato, calidad, ruta_recursos, ruta_pasada), daemon=True)
    hilo.start()

def actualizar_interfaz():
    if var_format.get() == "video":
        combo_calidad.config(state="readonly")
    else:
        combo_calidad.config(state="disabled")

# Interfaz visual
root = tk.Tk()
root.title("Descargador musica YT")
root.geometry("480x330") 
root.resizable(False, False)

lbl_title = tk.Label(root, text="Descargador musica YT", font=("Arial", 16, "bold"))
lbl_title.pack(pady=10)

entry_url = tk.Entry(root, width=54)
entry_url.pack(pady=5)
entry_url.focus()

var_format = tk.StringVar(value="video")
frame_options = tk.Frame(root)
frame_options.pack(pady=10)

rb_video = tk.Radiobutton(frame_options, text="Video (MP4)", variable=var_format, value="video", command=actualizar_interfaz)
rb_video.grid(row=0, column=0, padx=10)

combo_calidad = ttk.Combobox(frame_options, values=["Máxima Calidad", "1080p Full HD", "720p HD", "480p", "360p"], width=15, state="readonly")
combo_calidad.current(0) 
combo_calidad.grid(row=0, column=1, padx=5)

rb_audio = tk.Radiobutton(frame_options, text="Solo Audio (MP3)", variable=var_format, value="audio", command=actualizar_interfaz)
rb_audio.grid(row=0, column=2, padx=15)

lbl_status = tk.Label(root, text="", font=("Arial", 9), wraplength=440)
lbl_status.pack(pady=5)

barra_progreso = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
barra_progreso.pack(pady=5)

btn_download = tk.Button(root, text="Descargar ahora", command=iniciar_descarga, bg="#2196F3", fg="white", font=("Arial", 11, "bold"), padx=10, pady=5)
btn_download.pack(pady=15)

root.mainloop()










