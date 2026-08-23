#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integración con yt-dlp + FFmpeg.

Principios (ver especificación del proyecto):
- Selección DINÁMICA de formatos. Nunca se asume que un format_id fijo
  (p.ej. "18" o "140") exista o funcione.
- No se fuerza el cliente "android_vr" ni ningún cliente en particular.
- video_info y download son operaciones independientes: video_info puede
  tener éxito aunque la descarga no esté disponible en ese momento.
- Si YouTube no entrega streams (bloqueo temporal, "Sign in to confirm
  you're not a bot", etc.) se detecta el error UNA vez y se devuelve un
  mensaje claro. No se reintenta la misma solicitud varias veces.
- Nunca se devuelve un traceback al usuario; los detalles técnicos van al
  log del servidor.
"""
import logging
import os
import random
import shutil
import uuid

import yt_dlp

from security import safe_filename

logger = logging.getLogger("youtube_utils")

YOUTUBE_WATCH_URL = "https://www.youtube.com/watch?v={video_id}"

# Mensajes de error "amigables" — nunca exponemos tracebacks al cliente.
ERROR_BOT_CHECK = "YouTube no proporcionó un stream descargable para este vídeo en este momento."
ERROR_NO_STREAMS = "YouTube no proporcionó un stream descargable para este vídeo en este momento."
ERROR_FORBIDDEN = "El formato solicitado ya no está disponible (403). Inténtalo de nuevo más tarde."
ERROR_INVALID_URL = "El enlace o ID de vídeo no es válido."
ERROR_UNAVAILABLE = "Este vídeo no está disponible (privado, eliminado o restringido)."
ERROR_FFMPEG_MISSING = "El servidor no tiene FFmpeg instalado. Contacta a soporte."
ERROR_GENERIC = "No se pudo completar la descarga. Inténtalo de nuevo más tarde."
ERROR_FILE_NOT_FOUND = "La descarga se procesó pero el archivo final no se encontró."


def _base_ydl_opts():
    """
    Opciones base y neutrales para yt-dlp. No fuerza UN cliente concreto:
    se ofrece una LISTA de clientes para que yt-dlp elija dinámicamente
    cuál funciona para cada vídeo. No usa cookies y no fija format_ids.

    Nota sobre el 403 Forbidden: desde 2024-2025 YouTube exige un
    "PO token" para muchos streams del cliente 'web' (el usado por
    defecto). Los clientes 'android' e 'ios' normalmente no lo requieren,
    por eso se incluyen como alternativas. Esto sigue siendo selección
    dinámica: no se fija un único cliente como 'android_vr'.
    """
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": False,
        "socket_timeout": 20,
        "retries": 5,
        "fragment_retries": 5,
        "extractor_retries": 3,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        },
        "extractor_args": {
            "youtube": {
                # Lista, no un único cliente forzado: yt-dlp prueba en
                # orden hasta que uno entregue streams válidos.
                "player_client": ["android", "web", "ios"],
            }
        },
    }


def ffmpeg_is_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _classify_error(exc: Exception) -> str:
    """Convierte una excepción de yt-dlp en un mensaje claro para el usuario."""
    message = str(exc).lower()

    if "sign in to confirm" in message or "not a bot" in message:
        return ERROR_BOT_CHECK
    if "403" in message or "forbidden" in message:
        return ERROR_FORBIDDEN
    if "video unavailable" in message or "private video" in message or "removed" in message:
        return ERROR_UNAVAILABLE
    if "requested format is not available" in message or "no video formats" in message:
        return ERROR_NO_STREAMS
    if "unsupported url" in message or "is not a valid url" in message:
        return ERROR_INVALID_URL
    return ERROR_GENERIC


def _extract_video_id(video_id_or_url: str):
    if not video_id_or_url:
        return None
    v = video_id_or_url.strip()
    if v.startswith("http://") or v.startswith("https://"):
        return v  # yt-dlp acepta la URL completa igualmente
    return YOUTUBE_WATCH_URL.format(video_id=v)


# ---------------------------------------------------------------------------
# Búsqueda (con paginación tipo "cargar más")
# ---------------------------------------------------------------------------
def search_youtube(query: str, max_results: int = 12, offset: int = 0):
    """
    offset permite "cargar más": se piden offset+max_results resultados a
    yt-dlp y se devuelven solo los que están después de offset. No es
    paginación nativa de YouTube (ytsearch no la expone), pero es
    suficiente para un botón "Cargar más" / scroll infinito.
    """
    opts = _base_ydl_opts()
    opts["extract_flat"] = "in_playlist"
    total_needed = offset + max_results
    search_expr = f"ytsearch{total_needed}:{query}"

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(search_expr, download=False)
    except Exception as exc:
        logger.warning("Error buscando '%s': %s", query, exc)
        return {"error": "No se pudo completar la búsqueda en YouTube. Inténtalo de nuevo."}

    entries = (info or {}).get("entries") or []
    videos = [_entry_to_video(e) for e in entries if e]
    videos = [v for v in videos if v]
    page = videos[offset:offset + max_results]
    return {"videos": page, "has_more": len(videos) > offset + max_results}


def _entry_to_video(e):
    if not e:
        return None
    return {
        "id": e.get("id"),
        "title": e.get("title") or "Sin título",
        "uploader": e.get("uploader") or e.get("channel") or "Desconocido",
        "duration": e.get("duration") or 0,
        "view_count": e.get("view_count") or 0,
        "thumbnail": e.get("thumbnail") or (e.get("thumbnails") or [{}])[-1].get("url", ""),
    }


# ---------------------------------------------------------------------------
# Feed de inicio (aleatorio, distinto en cada visita) y feed "Para ti"
# ---------------------------------------------------------------------------
_FEED_QUERY_POOL = [
    "música 2026", "reggaeton 2026", "pop en español", "rock clásico",
    "lofi para estudiar", "bad bunny", "top hits 2026", "musica romantica",
    "trap latino", "salsa mix", "electronic music mix", "indie music 2026",
    "cumbia mix", "k-pop 2026", "hip hop 2026", "musica para trabajar",
]


def get_random_feed(max_results: int = 16):
    """
    Feed de inicio: elige uno o dos temas al azar de un pool variado y
    mezcla los resultados, para que no sea siempre el mismo listado.
    """
    picks = random.sample(_FEED_QUERY_POOL, k=min(2, len(_FEED_QUERY_POOL)))
    all_videos = []
    seen_ids = set()
    for q in picks:
        result = search_youtube(q, max_results=max_results)
        for v in result.get("videos", []):
            if v["id"] and v["id"] not in seen_ids:
                seen_ids.add(v["id"])
                all_videos.append(v)
    random.shuffle(all_videos)
    return {"videos": all_videos[:max_results], "has_more": True}


def get_personalized_feed(recent_queries, recent_titles, max_results: int = 16):
    """
    Feed "Para ti": reutiliza búsquedas/descargas recientes REALES del
    usuario (recent_queries, recent_titles) para pedir contenido
    relacionado. Si no hay historial suficiente, el llamador debe usar
    get_random_feed() como respaldo.
    """
    terms = [t for t in (recent_queries + recent_titles) if t][:4]
    if not terms:
        return {"videos": [], "has_more": False}

    all_videos = []
    seen_ids = set()
    for term in terms:
        result = search_youtube(term, max_results=8)
        for v in result.get("videos", []):
            if v["id"] and v["id"] not in seen_ids:
                seen_ids.add(v["id"])
                all_videos.append(v)
    random.shuffle(all_videos)
    return {"videos": all_videos[:max_results], "has_more": True}


# ---------------------------------------------------------------------------
# Información del vídeo (independiente de la descarga)
# ---------------------------------------------------------------------------
def get_video_info(video_id: str):
    target = _extract_video_id(video_id)
    if not target:
        return {"success": False, "error": ERROR_INVALID_URL}

    opts = _base_ydl_opts()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(target, download=False)
    except Exception as exc:
        logger.warning("Error obteniendo info de %s: %s", video_id, exc)
        return {"success": False, "error": _classify_error(exc)}

    if not info:
        return {"success": False, "error": ERROR_UNAVAILABLE}

    formats = info.get("formats") or []
    subtitles = sorted(set((info.get("subtitles") or {}).keys()))
    auto_captions = sorted(set((info.get("automatic_captions") or {}).keys()))
    return {
        "success": True,
        "id": info.get("id"),
        "title": info.get("title") or "Sin título",
        "uploader": info.get("uploader") or info.get("channel") or "Desconocido",
        "duration": info.get("duration") or 0,
        "view_count": info.get("view_count") or 0,
        "like_count": info.get("like_count") or 0,
        "upload_date": info.get("upload_date") or "",
        "thumbnail": info.get("thumbnail") or "",
        "description": (info.get("description") or "")[:2000],
        "formats": len(formats),
        # Idiomas con subtítulos reales (subtitles) o autogenerados
        # (automatic_captions). El frontend usa esto para mostrar/ocultar
        # la opción "Incluir subtítulos".
        "has_subtitles": bool(subtitles or auto_captions),
        "subtitle_langs": subtitles[:8],
        "auto_caption_langs": auto_captions[:8],
    }


# ---------------------------------------------------------------------------
# Descarga (independiente de video_info)
# ---------------------------------------------------------------------------
def _run_download(target: str, ydl_opts: dict):
    """Ejecuta yt-dlp UNA sola vez con las opciones dadas."""
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(target, download=True)
        return info, ydl.prepare_filename(info)


def _subtitle_opts(with_subtitles: bool, sub_lang: str = None):
    """
    Opciones comunes para pedir subtítulos SINCRONIZADOS (no traducción
    aparte): prioriza subtítulos manuales del idioma pedido y cae a los
    autogenerados por YouTube si no hay manuales. No descarga TODOS los
    idiomas (evita tráfico innecesario).
    """
    if not with_subtitles:
        return {}
    langs = [sub_lang] if sub_lang else ["es", "es-ES", "es-419", "en"]
    return {
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": langs,
        "subtitlesformat": "srt/vtt",
    }


def _download_audio(target: str, out_base: str, download_folder: str, with_subtitles: bool = False,
                     sub_lang: str = None, progress_hook=None):
    """
    Estrategia de audio:
    1. Preferir una pista de audio directa de buena calidad ('bestaudio').
    2. Si no hay audio directo, yt-dlp cae automáticamente a un formato
       audiovisual que contenga audio: se pide el más pequeño razonable
       para minimizar transferencia ('worst[ext=mp4]' como último recurso
       vive dentro del propio selector, sin fijar IDs).
    3. Extraer MP3 con FFmpeg, incrustar metadata y portada.
    4. Si with_subtitles=True, además se descarga el subtítulo
       SINCRONIZADO del vídeo como archivo .srt independiente (un MP3 no
       puede llevar una pista de subtítulos embebida, por eso se entrega
       aparte, con la misma sincronía que el vídeo original).
    progress_hook (opcional): callback de yt-dlp que recibe el progreso
    REAL de la descarga (bytes descargados/total), usado para la barra de
    progreso del frontend.
    """
    if not ffmpeg_is_available():
        return {"success": False, "error": ERROR_FFMPEG_MISSING}

    # Selector dinámico: mejor audio disponible; si no existe pista de solo
    # audio, usa el mejor audio+video combinado (nunca un ID fijo).
    format_selector = "bestaudio/best"

    opts = _base_ydl_opts()
    opts.update(
        {
            "format": format_selector,
            "outtmpl": out_base + ".%(ext)s",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
                {"key": "FFmpegMetadata", "add_metadata": True},
                {"key": "EmbedThumbnail"},
            ],
            "writethumbnail": True,
            "postprocessor_args": {},
        }
    )
    opts.update(_subtitle_opts(with_subtitles, sub_lang))
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    try:
        info, _prepared = _run_download(target, opts)
    except Exception as exc:
        logger.warning("Fallo en descarga de audio: %s", exc)
        return {"success": False, "error": _classify_error(exc)}

    final_path = out_base + ".mp3"
    if not os.path.exists(final_path):
        logger.error("Archivo mp3 esperado no encontrado: %s", final_path)
        return {"success": False, "error": ERROR_FILE_NOT_FOUND}

    subtitle_path = _find_subtitle_file(out_base) if with_subtitles else None
    return {"success": True, "path": final_path, "info": info, "subtitle_path": subtitle_path}


def _download_video(target: str, out_base: str, download_folder: str, with_subtitles: bool = False,
                     sub_lang: str = None, progress_hook=None):
    """
    Estrategia de vídeo:
    - Preferir MP4.
    - Si vídeo y audio están en streams separados, yt-dlp los descarga y
      los une con FFmpeg automáticamente (merge_output_format).
    - Selección dinámica de "la mejor calidad razonable disponible": se
      limita a <=1080p para evitar archivos excesivos, pero SIN fijar
      ningún format_id — el selector deja que yt-dlp elija entre lo que
      exista realmente para ese vídeo.
    - Si un formato falla con 403, se reintenta UNA vez con un selector
      más permisivo (nunca en bucle infinito).
    - Si with_subtitles=True, se incrustan los subtítulos SINCRONIZADOS
      como pista de subtítulos dentro del propio MP4 (soft-subs,
      activables/desactivables en el reproductor), usando el
      postprocesador nativo de yt-dlp (FFmpegEmbedSubtitle).
    progress_hook (opcional): callback de yt-dlp con el progreso REAL de
    la descarga, usado para la barra de progreso del frontend.
    """
    if not ffmpeg_is_available():
        return {"success": False, "error": ERROR_FFMPEG_MISSING}

    postprocessors = [{"key": "FFmpegMetadata", "add_metadata": True}]
    if with_subtitles:
        postprocessors.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})

    opts = _base_ydl_opts()
    opts.update(
        {
            "outtmpl": out_base + ".%(ext)s",
            "merge_output_format": "mp4",
            "postprocessors": postprocessors,
        }
    )
    opts.update(_subtitle_opts(with_subtitles, sub_lang))
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    # Selector primario: mp4 combinado hasta 1080p, o el mejor disponible.
    primary_selector = (
        "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/"
        "best[ext=mp4][height<=1080]/best[height<=1080]/best"
    )
    # Selector de respaldo (más permisivo), usado SOLO si el primero falla
    # por un error recuperable como 403. No es un format_id fijo: sigue
    # siendo una expresión de selección dinámica.
    fallback_selector = "best"

    attempts = [primary_selector, fallback_selector]
    last_error = None
    info = None

    for i, selector in enumerate(attempts):
        opts["format"] = selector
        try:
            info, _prepared = _run_download(target, opts)
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            message = str(exc).lower()
            recoverable = "403" in message or "forbidden" in message or "requested format" in message
            logger.warning("Intento %d de descarga de vídeo falló: %s", i + 1, exc)
            if not recoverable:
                # Error no recuperable (p. ej. bot-check): no repetir intentos idénticos.
                break
            # Si es recoverable, probamos el siguiente selector (máx. 2 intentos totales).
            continue

    if last_error is not None:
        return {"success": False, "error": _classify_error(last_error)}

    final_path = out_base + ".mp4"
    if not os.path.exists(final_path):
        # yt-dlp puede haber dejado la extensión original si no hubo remux.
        for ext in ("mkv", "webm"):
            alt = f"{out_base}.{ext}"
            if os.path.exists(alt):
                final_path = alt
                break

    if not os.path.exists(final_path):
        logger.error("Archivo de vídeo esperado no encontrado: %s", final_path)
        return {"success": False, "error": ERROR_FILE_NOT_FOUND}

    return {"success": True, "path": final_path, "info": info}


def _find_subtitle_file(out_base: str):
    """Busca el .srt/.vtt generado por yt-dlp junto al out_base dado."""
    folder = os.path.dirname(out_base)
    prefix = os.path.basename(out_base)
    try:
        for fname in os.listdir(folder):
            if fname.startswith(prefix) and fname.endswith((".srt", ".vtt")):
                return os.path.join(folder, fname)
    except FileNotFoundError:
        pass
    return None


def download_media(video_id: str, video_title: str, format_type: str, download_folder: str,
                    with_subtitles: bool = False, sub_lang: str = None, progress_hook=None):
    """
    Descarga audio o vídeo. Devuelve siempre un dict JSON-serializable:
    {'success': True, 'filename': ..., 'subtitle_filename': <opcional>}
    o {'success': False, 'error': ...}. Nunca lanza excepciones hacia el
    llamador ni expone tracebacks.
    progress_hook (opcional): callback de yt-dlp con el progreso REAL,
    usado para alimentar la barra de progreso del frontend vía jobs.py.
    """
    target = _extract_video_id(video_id)
    if not target:
        return {"success": False, "error": ERROR_INVALID_URL}

    os.makedirs(download_folder, exist_ok=True)
    unique_name = safe_filename(video_title or video_id, fallback=video_id or "video")
    out_base = os.path.join(download_folder, f"{unique_name}-{uuid.uuid4().hex[:8]}")

    try:
        if format_type == "audio":
            result = _download_audio(target, out_base, download_folder, with_subtitles, sub_lang, progress_hook)
        elif format_type == "video":
            result = _download_video(target, out_base, download_folder, with_subtitles, sub_lang, progress_hook)
        else:
            return {"success": False, "error": "Tipo de formato no soportado."}
    except Exception:
        # Red de seguridad final: nunca dejar escapar un traceback.
        logger.exception("Error inesperado descargando %s (%s)", video_id, format_type)
        return {"success": False, "error": ERROR_GENERIC}
    finally:
        _cleanup_leftovers(out_base)

    if not result.get("success"):
        return result

    final_path = result["path"]
    filename = os.path.basename(final_path)
    response = {"success": True, "filename": filename}

    subtitle_path = result.get("subtitle_path")
    if subtitle_path and os.path.exists(subtitle_path):
        response["subtitle_filename"] = os.path.basename(subtitle_path)

    return response


def _cleanup_leftovers(out_base: str):
    """Elimina archivos temporales (thumbnails descargados, .part, etc.).
    Conserva el archivo final (mp3/mp4/mkv/webm) y, si existe, el
    subtítulo (.srt/.vtt) — este último se limpia después de que
    download_media() ya devolvió su nombre al llamador, vía
    /download/<archivo>."""
    folder = os.path.dirname(out_base)
    prefix = os.path.basename(out_base)
    try:
        for fname in os.listdir(folder):
            if not fname.startswith(prefix):
                continue
            if fname.endswith((".mp3", ".mp4", ".mkv", ".webm", ".srt", ".vtt")):
                continue  # es el archivo final, no un temporal
            try:
                os.remove(os.path.join(folder, fname))
            except OSError:
                pass
    except FileNotFoundError:
        pass
