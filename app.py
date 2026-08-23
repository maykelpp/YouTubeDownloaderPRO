#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import os

from flask import Flask, jsonify, request, render_template, send_file, session
from flask_wtf import CSRFProtect

from config import Config
from extensions import db, limiter
from database import init_db, get_stats, record_download
import youtube_utils
import jobs
from security import safe_filename
from auth import auth_bp, current_user, login_required
from support import support_bp
from models import UserActivity
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

csrf = CSRFProtect()


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    if getattr(config_object, "_MISSING_SECRET_KEY", False):
        logger.warning(
            "SECRET_KEY no está configurado. Se generó una clave temporal: "
            "las sesiones se invalidarán en cada reinicio. Configura SECRET_KEY en producción."
        )

    db.init_app(app)
    csrf.init_app(app)
    app.config["RATELIMIT_STORAGE_URI"] = app.config.get("RATELIMIT_STORAGE_URI", "memory://")
    limiter.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(support_bp)

    os.makedirs(app.config["DOWNLOAD_FOLDER"], exist_ok=True)

    # Si la BD es SQLite, aseguramos que la carpeta contenedora exista
    # (evita PermissionError/OperationalError en entornos como
    # Termux/Android donde /tmp no siempre es escribible, o donde una
    # ruta relativa en DATABASE_URL no resuelve como se espera).
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if db_uri.startswith("sqlite:///") and db_uri != "sqlite:///:memory:":
        db_path = db_uri[len("sqlite:///"):]  # puede quedar relativa o absoluta
        db_dir = os.path.dirname(db_path) or "."
        db_dir_abs = os.path.abspath(db_dir)
        try:
            os.makedirs(db_dir_abs, exist_ok=True)
        except OSError as exc:
            logger.warning(
                "No se pudo crear la carpeta de la base de datos '%s': %s", db_dir_abs, exc
            )
        logger.info("Base de datos SQLite: %s (carpeta: %s)", db_path, db_dir_abs)

    with app.app_context():
        init_db(app)

    _register_routes(app)
    _register_error_handlers(app)

    if app.config.get("ENABLE_KEEPALIVE"):
        from keepalive import start_keepalive

        start_keepalive(app)

    return app


def _register_routes(app):
    @app.context_processor
    def inject_user():
        return {"logged_in_user": current_user()}

    def _log_activity(kind, query=None, video_id=None, video_title=None, uploader=None):
        """Registra la actividad (best-effort). Nunca debe romper la
        respuesta al usuario si falla."""
        try:
            user = current_user()
            entry = UserActivity(
                user_id=user.id if user else None,
                kind=kind,
                search_query=(query or None),
                video_id=(video_id or None),
                video_title=(video_title or None),
                uploader=(uploader or None),
            )
            db.session.add(entry)
            db.session.commit()
        except Exception:
            logger.exception("No se pudo registrar actividad (%s)", kind)
            db.session.rollback()

    @app.route("/")
    def index():
        stats = get_stats()
        return render_template("index.html", stats=stats)

    @app.route("/api/search", methods=["POST"])
    @csrf.exempt
    def api_search():
        data = request.get_json(silent=True) or {}
        query = (data.get("query") or "").strip()
        offset = max(int(data.get("offset") or 0), 0)

        if not query:
            return jsonify({"error": "Query vacío"}), 400
        if len(query) > 200:
            return jsonify({"error": "Búsqueda demasiado larga"}), 400

        result = youtube_utils.search_youtube(query, offset=offset)

        if offset == 0 and not result.get("error"):
            _log_activity("search", query=query)

        return jsonify(result)

    @app.route("/api/feed")
    def api_feed():
        """Feed de inicio: aleatorio y distinto en cada visita (no repite
        siempre el mismo listado)."""
        result = youtube_utils.get_random_feed()
        return jsonify(result)

    @app.route("/api/feed/for-you")
    @login_required
    def api_feed_for_you():
        """Feed "Para ti": basado en el historial real reciente del
        usuario que inició sesión. Si no hay historial, usa el feed
        aleatorio como respaldo."""
        user = current_user()
        recent = (
            UserActivity.query.filter_by(user_id=user.id)
            .order_by(UserActivity.created_at.desc())
            .limit(15)
            .all()
        )
        recent_queries = [a.search_query for a in recent if a.kind == "search" and a.search_query]
        recent_titles = [a.video_title for a in recent if a.kind == "download" and a.video_title]

        result = youtube_utils.get_personalized_feed(recent_queries, recent_titles)
        if not result.get("videos"):
            result = youtube_utils.get_random_feed()
        return jsonify(result)

    @app.route("/api/video_info", methods=["POST"])
    @csrf.exempt
    def api_video_info():
        data = request.get_json(silent=True) or {}
        video_id = data.get("video_id")

        if not video_id:
            return jsonify({"success": False, "error": "Video ID faltante"}), 400

        result = youtube_utils.get_video_info(video_id)
        return jsonify({"success": result["success"], "info": result} if result["success"] else result)

    @app.route("/api/download", methods=["POST"])
    @csrf.exempt
    @limiter.limit("15 per minute")
    def api_download():
        """Descarga síncrona (sin barra de progreso). Se mantiene por
        compatibilidad; el frontend usa /api/download/start + /status."""
        data = request.get_json(silent=True) or {}
        video_id = data.get("video_id")
        video_title = data.get("video_title")
        uploader = data.get("uploader")
        format_type = data.get("format_type", "audio")
        with_subtitles = bool(data.get("with_subtitles", False))
        sub_lang = data.get("sub_lang") or None

        if not video_id or not video_title:
            return jsonify({"success": False, "error": "Parámetros faltantes"}), 400
        if format_type not in ("audio", "video"):
            return jsonify({"success": False, "error": "Tipo de formato no soportado"}), 400

        result = youtube_utils.download_media(
            video_id, video_title, format_type, app.config["DOWNLOAD_FOLDER"],
            with_subtitles=with_subtitles, sub_lang=sub_lang,
        )
        if result.get("success"):
            record_download(format_type)
            _log_activity("download", video_id=video_id, video_title=video_title, uploader=uploader)
        return jsonify(result)

    @app.route("/api/download/start", methods=["POST"])
    @csrf.exempt
    @limiter.limit("15 per minute")
    def api_download_start():
        """Inicia la descarga en un hilo en segundo plano y devuelve un
        job_id inmediatamente. El progreso REAL se consulta con
        GET /api/download/status/<job_id>."""
        data = request.get_json(silent=True) or {}
        video_id = data.get("video_id")
        video_title = data.get("video_title")
        uploader = data.get("uploader")
        format_type = data.get("format_type", "audio")
        with_subtitles = bool(data.get("with_subtitles", False))
        sub_lang = data.get("sub_lang") or None

        if not video_id or not video_title:
            return jsonify({"success": False, "error": "Parámetros faltantes"}), 400
        if format_type not in ("audio", "video"):
            return jsonify({"success": False, "error": "Tipo de formato no soportado"}), 400

        job_id = jobs.create_job()

        def _progress_hook(d):
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes") or 0
                percent = round(downloaded / total * 100, 1) if total else None
                jobs.update_job(
                    job_id,
                    status="downloading",
                    percent=percent,
                    speed=d.get("speed"),
                    eta=d.get("eta"),
                )
            elif status == "finished":
                # La descarga del stream terminó; falta postprocesar
                # (FFmpeg: extraer audio, unir video, incrustar subs...).
                jobs.update_job(job_id, status="processing", percent=95, speed=None, eta=None)

        def _worker():
            jobs.update_job(job_id, status="starting")
            with app.app_context():
                try:
                    result = youtube_utils.download_media(
                        video_id, video_title, format_type, app.config["DOWNLOAD_FOLDER"],
                        with_subtitles=with_subtitles, sub_lang=sub_lang,
                        progress_hook=_progress_hook,
                    )
                except Exception:
                    logger.exception("Error inesperado en job de descarga %s", job_id)
                    jobs.update_job(job_id, status="error", error=youtube_utils.ERROR_GENERIC)
                    return

                if result.get("success"):
                    try:
                        record_download(format_type)
                        _log_activity(
                            "download", video_id=video_id, video_title=video_title, uploader=uploader
                        )
                    except Exception:
                        logger.exception("No se pudo registrar la descarga %s", job_id)
                    jobs.update_job(job_id, status="done", percent=100, result=result)
                else:
                    jobs.update_job(job_id, status="error", error=result.get("error"))

        threading.Thread(target=_worker, daemon=True).start()
        return jsonify({"job_id": job_id})

    @app.route("/api/download/status/<job_id>")
    def api_download_status(job_id):
        job = jobs.get_job(job_id)
        if not job:
            return jsonify({"status": "not_found", "error": "Trabajo no encontrado o expirado"}), 404
        return jsonify(job)

    @app.route("/download/<path:filename>")
    def download_file(filename):
        # Protección contra path traversal: se sanea el nombre y se verifica
        # que el archivo resultante quede DENTRO de DOWNLOAD_FOLDER.
        safe_name = safe_filename(filename)
        download_folder = os.path.abspath(app.config["DOWNLOAD_FOLDER"])
        file_path = os.path.abspath(os.path.join(download_folder, safe_name))

        if not file_path.startswith(download_folder + os.sep):
            return "Archivo no encontrado", 404
        if not os.path.exists(file_path):
            return "Archivo no encontrado", 404

        return send_file(file_path, as_attachment=True, download_name=safe_name)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"}), 200


def _register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "No encontrado"}), 404

    @app.errorhandler(500)
    def server_error(e):
        # Nunca devolver el traceback al cliente; los detalles van al log.
        logger.exception("Error interno no controlado")
        return jsonify({"error": "Error interno del servidor. Inténtalo de nuevo más tarde."}), 500

    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify({"error": "Demasiadas solicitudes. Espera un momento e inténtalo de nuevo."}), 429


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    # Servidor de desarrollo únicamente. En producción se usa gunicorn
    # (ver Procfile / render.yaml): gunicorn app:app
    # Servidor de desarrollo únicamente. En producción se usa gunicorn
    # (ver Procfile / render.yaml): gunicorn app:app
    # threaded=True es necesario para que la barra de progreso funcione:
    # la descarga corre en un hilo en segundo plano mientras el navegador
    # consulta /api/download/status/<job_id> en paralelo.
    app.run(host="0.0.0.0", port=port, debug=app.config.get("DEBUG", False), threaded=True)
