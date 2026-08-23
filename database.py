#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Capa de compatibilidad de base de datos.

Antes el proyecto usaba una tabla de estadísticas "casera". Ahora usamos
SQLAlchemy (ver models.py) pero mantenemos las mismas funciones públicas
(init_db, get_stats) para no romper el resto de la aplicación, y añadimos
record_download() para registrar cada descarga completada.
"""
import datetime

from extensions import db
from models import DownloadStat, User
from security import hash_password


def init_db(app=None):
    """
    Crea todas las tablas si no existen y, si están configuradas las
    variables ADMIN_EMAIL / ADMIN_PASSWORD, crea (o adapta) la cuenta
    administrativa inicial. Debe llamarse dentro del contexto de la app
    (app.app_context()).
    """
    try:
        db.create_all()
    except Exception as exc:
        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "?") if app else "?"
        raise RuntimeError(
            "No se pudo crear/abrir la base de datos "
            f"(SQLALCHEMY_DATABASE_URI={db_uri!r}). "
            "Si usas SQLite, revisa que la carpeta contenedora exista y "
            "tenga permisos de escritura. Si definiste DATABASE_URL en tu "
            ".env con una ruta RELATIVA (p. ej. 'sqlite:///instance/app.db'), "
            "prueba quitando esa línea del .env para usar la ruta absoluta "
            "por defecto del proyecto, o usa una ruta absoluta explícita."
        ) from exc
    _ensure_admin_account(app)


def _ensure_admin_account(app):
    if app is None:
        return
    admin_email = app.config.get("ADMIN_EMAIL")
    admin_password = app.config.get("ADMIN_PASSWORD")
    if not admin_email or not admin_password:
        return  # No configurado: no se crea ninguna cuenta admin automáticamente.

    existing = User.query.filter_by(email=admin_email.lower().strip()).first()
    if existing:
        if not existing.is_admin:
            existing.is_admin = True
            db.session.commit()
        return

    admin = User(
        name="Administrador",
        email=admin_email.lower().strip(),
        password_hash=hash_password(admin_password),
        email_verified=True,
        is_admin=True,
    )
    db.session.add(admin)
    db.session.commit()


def record_download(format_type: str):
    stat = DownloadStat(format_type=format_type)
    db.session.add(stat)
    db.session.commit()


def get_stats():
    today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    total = DownloadStat.query.count()
    today = DownloadStat.query.filter(DownloadStat.created_at >= today_start).count()
    return {"total": total, "today": today}
