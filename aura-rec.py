# -*- coding: utf-8 -*-
"""Aura Rec — grabadora de pantalla minimalista (inspirada en la arquitectura de OBS).
fuente (pantalla/ventana) + audio (mic opcional) -> codificador x264 -> mp4.
Sin dependencias Python: tkinter + ffmpeg (ya instalado).

  python aura-rec.py
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

# ---------------------------------------------------------------------------
# CONFIG — todo lo ajustable vive aquí
# ---------------------------------------------------------------------------
CONFIG = {
    "fps": 30,
    "preset": "veryfast",       # ultrafast | veryfast | medium (calidad vs CPU)
    "crf": 23,                  # calidad (menor = mejor)
    "salida": os.path.join(os.path.expanduser("~"), "Videos", "AuraRec"),
    "con_audio": True,          # micrófono
    "audio_bitrate": "128k",
    "min_disco_libre": 1_000_000_000,   # 1 GB antes de iniciar
    "stop_timeout": 8.0,        # s de gracia tras enviar 'q'
}

# Rutas winget conocidas (build gyan). NOTA: el hash de paquete de winget es
# "8wekyb3d8bbwe" (el código original tenía el typo "8wekypt3d8bbwe").
_WINGET_GLOBS = [
    r"C:\Users\DELL\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg*"
    r"\ffmpeg-*\bin\ffmpeg.exe",
    os.path.join(os.path.expanduser("~"),
                 r"AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg*"
                 r"\ffmpeg-*\bin\ffmpeg.exe"),
]


def localizar_ffmpeg() -> str | None:
    """Devuelve la ruta a ffmpeg.exe: PATH primero, luego rutas winget conocidas."""
    which = shutil.which("ffmpeg")
    if which:
        return which
    for patron in _WINGET_GLOBS:
        hits = sorted(glob.glob(patron), reverse=True)  # build más reciente primero
        if hits:
            return hits[0]
    return None


FFMPEG: str | None = localizar_ffmpeg()

BG, PANEL, TXT, DIM = "#0b0e17", "#12172a", "#e8ecf8", "#7c86a6"
ACENTO, ROJO, VERDE, AMBAR = "#7c5cff", "#ff4d6d", "#2ee6a8", "#ffb84d"

APP: dict = {"proc": None, "grabando": False, "t0": None, "out": None, "muerto": False}


def listar_audio() -> list[str]:
    """Nombres de dispositivos de audio para dshow."""
    if not FFMPEG:
        return []
    try:
        r = subprocess.run([FFMPEG, "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                           capture_output=True, text=True, timeout=20,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        texto = r.stderr
    except Exception:
        return []
    devs = []
    en_audio = False
    for line in texto.splitlines():
        if '"audio' in line.lower() and 'devices' in line.lower():
            en_audio = True
            continue
        if en_audio and '(audio' in line:
            nombre = line.split('"')[1] if '"' in line else None
            if nombre and not nombre.startswith(("@", "virtual")):
                devs.append(nombre)
    return devs


def comando_grabacion(monitor: tuple[int, int, int, int],
                      audio_dev: str | None, salida: str) -> list[str]:
    """Arquitectura OBS: source -> filter -> encoder -> muxer.

    Sincronización A/V: gdigrab y dshow son inputs independientes sin reloj
    común. Para alinearlos se usa `-use_wallclock_as_timestamps 1` en el input
    de audio, que estampa cada paquete dshow con el reloj de pared del sistema
    (la misma referencia temporal que usa gdigrab). El vídeo se fuerza a
    `-fps_mode cfr` para que x264 duplique/suelte frames según PTS y el muxer
    reciba una línea temporal uniforme. No se usa -async (obsoleto y pensado
    para transcodificación de archivos, no para captura en vivo).
    """
    if not FFMPEG:
        raise RuntimeError("ffmpeg no disponible")
    cmd = [FFMPEG, "-y",
           "-f", "gdigrab", "-framerate", str(CONFIG["fps"]),
           "-offset_x", str(monitor[0]), "-offset_y", str(monitor[1]),
           "-video_size", f"{monitor[2]}x{monitor[3]}",
           "-i", "desktop"]
    if audio_dev:
        # Reloj de pared en el input de audio = timestamps comparables con gdigrab
        cmd += ["-f", "dshow", "-use_wallclock_as_timestamps", "1",
                "-i", f"audio={audio_dev}"]
    cmd += ["-c:v", "libx264", "-preset", CONFIG["preset"], "-crf", str(CONFIG["crf"]),
            "-pix_fmt", "yuv420p", "-fps_mode", "cfr"]
    if audio_dev:
        cmd += ["-c:a", "aac", "-b:a", CONFIG["audio_bitrate"]]
    cmd += [salida]
    return cmd


def resolucion_pantalla() -> tuple[int, int, int, int]:
    import ctypes
    u = ctypes.windll.user32
    u.SetProcessDPIAware()
    return (0, 0, u.GetSystemMetrics(0), u.GetSystemMetrics(1))


def ruta_salida_unica() -> str:
    """aura-<fecha>.mp4; si existe, añade sufijo -1, -2… en vez de sobrescribir."""
    os.makedirs(CONFIG["salida"], exist_ok=True)
    base = os.path.join(CONFIG["salida"], time.strftime("aura-%Y%m%d-%H%M%S"))
    salida = base + ".mp4"
    n = 1
    while os.path.exists(salida):
        salida = f"{base}-{n}.mp4"
        n += 1
    return salida


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("◈ Aura Rec")
        root.configure(bg=BG)
        root.geometry("420x430")

        tk.Label(root, text="◈ Aura Rec", font=("Segoe UI", 20, "bold"),
                 bg=BG, fg=TXT).pack(anchor="w", padx=24, pady=(20, 0))
        tk.Label(root, text="grabadora de pantalla · ffmpeg · sin límite",
                 font=("Segoe UI", 9), bg=BG, fg=DIM).pack(anchor="w", padx=24)

        panel = tk.Frame(root, bg=PANEL, highlightbackground="#232a41",
                         highlightcolor="#232a41", highlightthickness=1)
        panel.pack(fill="x", padx=24, pady=14)

        tk.Label(panel, text="Calidad", font=("Segoe UI", 9, "bold"),
                 bg=PANEL, fg=DIM).pack(anchor="w", padx=14, pady=(10, 2))
        self.calidad = tk.StringVar(value="Alta (veryfast)")
        for txt, _preset, _crf in [("Máxima (medium)", "medium", 20),
                                   ("Alta (veryfast)", "veryfast", 23),
                                   ("Fluida (ultrafast)", "ultrafast", 28)]:
            tk.Radiobutton(panel, text=txt, variable=self.calidad, value=txt,
                           bg=PANEL, fg=TXT, selectcolor=BG,
                           activebackground=PANEL, font=("Segoe UI", 10),
                           command=lambda: self.set_calidad()).pack(anchor="w", padx=14)

        self.audio_var = tk.BooleanVar(value=CONFIG["con_audio"])
        self.audio_check = tk.Checkbutton(panel, text="Incluir micrófono",
                                          variable=self.audio_var, bg=PANEL, fg=TXT,
                                          selectcolor=BG, activebackground=PANEL,
                                          font=("Segoe UI", 10))
        self.audio_check.pack(anchor="w", padx=14, pady=(6, 4))

        self.status = tk.Label(root, text="● Listo", font=("Segoe UI", 11),
                               bg=BG, fg=VERDE, anchor="w")
        self.status.pack(fill="x", padx=24)

        self.btn = tk.Button(root, text="●  INICIAR GRABACIÓN", font=("Segoe UI", 14, "bold"),
                             bg=ACENTO, fg="white", activebackground="#8f75ff",
                             relief="flat", cursor="hand2", height=2,
                             state="disabled" if not FFMPEG else "normal",
                             command=self.toggle)
        self.btn.pack(fill="x", padx=24, pady=12)

        self.out_lbl = tk.Label(root, text=f"Salida: {CONFIG['salida']}",
                                font=("Segoe UI", 8), bg=BG, fg=DIM, wraplength=380)
        self.out_lbl.pack(padx=24)

        self.audio_devs = listar_audio() if (FFMPEG and CONFIG["con_audio"]) else []
        self.timer_lbl = tk.Label(root, text="", font=("Segoe UI", 14, "bold"),
                                  bg=BG, fg=ROJO)
        self.timer_lbl.pack()

        if not FFMPEG:
            self.status.config(
                text="✖ ffmpeg no encontrado. Instálalo con:\n  winget install Gyan.FFmpeg",
                fg=ROJO, justify="left")
        self._tick()

    def set_calidad(self) -> None:
        m = {"Máxima": ("medium", 20), "Alta": ("veryfast", 23), "Fluida": ("ultrafast", 28)}
        for k, (p, c) in m.items():
            if k in self.calidad.get():
                CONFIG["preset"], CONFIG["crf"] = p, c

    def toggle(self) -> None:
        if APP["grabando"]:
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        """Comprobaciones previas (ffmpeg, disco) y lanzamiento del proceso."""
        if not FFMPEG:
            return
        # Aviso de espacio en disco insuficiente (<1 GB) antes de iniciar
        try:
            libre = shutil.disk_usage(CONFIG["salida"]).free
        except Exception:
            libre = None
        if libre is not None and libre < CONFIG["min_disco_libre"]:
            self.status.config(
                text=f"✖ Espacio insuficiente en disco ({libre // 1_000_000} MB libres; "
                     f"se recomiendan ≥ 1 GB).", fg=ROJO)
            return

        salida = ruta_salida_unica()
        audio_dev = None
        if self.audio_var.get() and self.audio_devs:
            audio_dev = self.audio_devs[0]
            self.status.config(text=f"● Grabando con mic: {audio_dev[:40]}…", fg=ROJO)
        elif self.audio_var.get():
            self.status.config(text="● Grabando sin micrófono (no detectado)", fg=ROJO)
        else:
            self.status.config(text="● Grabando pantalla…", fg=ROJO)
        try:
            cmd = comando_grabacion(resolucion_pantalla(), audio_dev, salida)
            APP["proc"] = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                           stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL,
                                           creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            self.status.config(text=f"✖ No se pudo iniciar ffmpeg: {e}", fg=ROJO)
            return
        APP["grabando"] = True
        APP["muerto"] = False
        APP["t0"] = time.time()
        APP["out"] = salida
        self.btn.config(text="■  DETENER Y GUARDAR", bg=ROJO)

    def stop(self) -> None:
        """Cierre limpio: 'q' por stdin → timeout → terminate → kill.

        El 'q' permite a ffmpeg escribir el índice moov del mp4 (archivo válido);
        el fallback evita dejar el proceso colgado o el archivo corrupto.
        """
        proc = APP["proc"]
        if proc is not None:
            murio_solo = proc.poll() is not None
            if not murio_solo:
                try:
                    proc.stdin.write(b"q")
                    proc.stdin.flush()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=CONFIG["stop_timeout"])
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        proc.kill()
            elif murio_solo and not APP["muerto"]:
                APP["muerto"] = True
        fallo = APP["muerto"] or (proc is not None and proc.poll() not in (None, 0))
        APP["grabando"] = False
        APP["proc"] = None
        self.btn.config(text="●  INICIAR GRABACIÓN", bg=ACENTO)
        if fallo:
            self.status.config(text="✖ ffmpeg terminó inesperadamente "
                                    "(¿equipo bloqueado?). Revisa el archivo.", fg=ROJO)
        else:
            self.status.config(text="✔ Guardado: " + (APP["out"] or ""), fg=VERDE)
        self.timer_lbl.config(text="")

    def _tick(self) -> None:
        """Cronómetro, tamaño estimado en vivo y vigilancia del proceso."""
        if APP["grabando"]:
            proc = APP["proc"]
            # ffmpeg murió solo (p. ej. pantalla bloqueada / dispositivo perdido)
            if proc is not None and proc.poll() is not None:
                APP["muerto"] = True
                self.stop()
            else:
                seg = int(time.time() - (APP["t0"] or time.time()))
                txt = f"● REC {seg//60}:{seg%60:02d}"
                # Tamaño estimado en vivo a partir del crecimiento del archivo
                try:
                    peso = os.path.getsize(APP["out"])
                    if peso > 0 and seg > 0:
                        kbps = peso * 8 / seg / 1000
                        txt += f"  ·  {peso/1_000_000:.1f} MB ({kbps:.0f} kb/s)"
                except OSError:
                    pass
                self.timer_lbl.config(text=txt)
        self.root.after(500, self._tick)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
