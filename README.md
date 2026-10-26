# 🎬 Aura Rec

Grabadora de pantalla minimalista para Windows, inspirada en la arquitectura de
**OBS Studio** (fuente → codificador → muxer) pero reducida a lo esencial:
**un botón, sin límite de duración, mp4 de calidad**.

Parte del patrón "estudiar una app famosa y construir tu versión" (caso #4 de la
investigación REA, como [rec-rs](https://github.com/michaelshimeles/rec-rs) estudió OBS).

## Uso

**Doble clic en `IniciarAuraRec.bat`** → elige calidad (Máxima/Alta/Fluida),
marca "Incluir micrófono" si quieres narración → **● INICIAR GRABACIÓN** →
**■ DETENER Y GUARDAR**.

El mp4 queda en `~/Videos/AuraRec/aura-<fecha>.mp4` (nombrado por fecha/hora);
si el nombre ya existe, se añade sufijo `-1`, `-2`… en lugar de sobrescribir.

Durante la grabación el cronómetro muestra también el tamaño actual y el bitrate
medido (ej. `● REC 1:23 · 14.2 MB (1370 kb/s)`).

## Arquitectura (lo aprendido de OBS)

| OBS | Aura Rec |
|---|---|
| Fuente: captura de pantalla | `gdigrab` (GDI del sistema, sin drivers) |
| Fuente: micrófono | `dshow` (dispositivo detectado automáticamente) |
| Codificador | `libx264` con presets ultrafast/veryfast/medium |
| Muxer | mp4 (H.264 + AAC 128k) |
| Término "replay buffer" | futuro: grabación circular permanente |

Captura verificada: 1795 kb/s a 30 fps en pantalla 1080p con `ultrafast`.

### Sincronización A/V

gdigrab (vídeo) y dshow (audio) son entradas independientes sin reloj común. La
app estampa los paquetes de audio con el reloj de pared del sistema
(`-use_wallclock_as_timestamps 1` en el input dshow) —la misma referencia
temporal que usa gdigrab— y fuerza vídeo a frame-rate constante
(`-fps_mode cfr`) para que el muxer reciba líneas temporales comparables.
No se usa `-async`: es un flag obsoleto pensado para transcodificar archivos,
no para captura en vivo.

## Requisitos

- Windows 10/11
- [ffmpeg](https://www.gyan.dev/ffmpeg/builds/) — se busca primero en el PATH y
  luego en las rutas de instalación de winget (`Gyan.FFmpeg`); si no se
  encuentra, la GUI lo indica con instrucciones en lugar de fallar.
- Python 3.10+ con tkinter (incluido en el instalador oficial)

**Sin dependencias pip** — el app solo orquesta ffmpeg.

## Robustez y límites

- **Cierre limpio**: Detener envía `q` por stdin a ffmpeg (escribe el índice del
  mp4, archivo siempre válido); tras 8 s de gracia hace `terminate` y luego
  `kill` como último recurso.
- **Muerte del proceso**: si ffmpeg muere solo (p. ej. sesión bloqueada, mic
  desconectado), la UI lo detecta en <1 s, informa y restaura el botón.
- **Disco**: no inicia la grabación si hay menos de **1 GB** libres en la unidad
  de destino (configurable en `CONFIG["min_disco_libre"]`).
- **Límites conocidos**: gdigrab no captura pantallas bloqueadas ni contenido
  protegido por DRM (se ve negro); en multi-monitor solo se graba el monitor
  principal (0,0).

## Solución de problemas

- **Video con saltos** → baja la calidad a "Fluida (ultrafast)" o el fps a 20
- **Sin audio** → marca "Incluir micrófono"; si dice "no detectado", tu dispositivo
  no aparece en dshow (revisa Configuración > Privacidad > Micrófono)
- **"ffmpeg terminó inesperadamente"** → normalmente la sesión estaba bloqueada
  o el micrófono se desconectó; el archivo hasta ese instante suele ser válido
- **Desincronización A/V** → no debería ocurrir (ver sección anterior); si pasa,
  prueba a bajar el fps o desactivar el micrófono para aislar la causa
