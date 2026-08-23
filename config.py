#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuración centralizada de la aplicación.
TODO se lee desde variables de entorno. Nunca hardcodear secretos aquí.
"""
import os

# Carga variables desde un archivo .env si existe (desarrollo local,
# Termux, etc.). En Render/producción las variables ya vienen inyectadas
# por la plataforma, así que esto no hace nada si no hay .env.
from dotenv import load_dotenv
load_dotenv()


def _bool_env(name, default="false"):
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


class Config:
    # --- Núcleo Flask ---
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        # Nunca usar una clave predecible en producción. Si falta, generamos una
        # aleatoria de proceso (las sesiones no sobreviven a un reinicio), y avisamos.
        import secrets as _secrets
        SECRET_KEY = _secrets.token_hex(32)
        _MISSING_SECRET_KEY = True
    else:
        _MISSING_SECRET_KEY = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool_env("SESSION_COOKIE_SECURE", "true")
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 7  # 7 días

    # --- Base de datos ---
    # Se usa una carpeta 'instance/' dentro del propio proyecto en vez de
    # /tmp: en algunos entornos (p. ej. Termux/Android, o Render sin
    # permisos en /tmp) escribir en /tmp falla con PermissionError.
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    _INSTANCE_DIR = os.path.join(_BASE_DIR, "instance")
    _DEFAULT_DB_PATH = os.path.join(_INSTANCE_DIR, "app.db")

    DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_DEFAULT_DB_PATH}")
    # Render/Heroku a veces entregan postgres:// en vez de postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Descargas ---
    DOWNLOAD_FOLDER = os.environ.get("DOWNLOAD_FOLDER", os.path.join(_BASE_DIR, "downloads"))
    MAX_DOWNLOAD_AGE_SECONDS = int(os.environ.get("MAX_DOWNLOAD_AGE_SECONDS", 3600))

    # --- SMTP / correo ---
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", SMTP_USERNAME)
    SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "dcpiurl@gmail.com")
    MAIL_ENABLED = bool(SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD)

    # --- Cuenta administrativa inicial ---
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

    # --- Verificación / 2FA ---
    EMAIL_VERIFICATION_EXPIRE_MINUTES = int(os.environ.get("EMAIL_VERIFICATION_EXPIRE_MINUTES", 30))
    LOGIN_CODE_EXPIRE_MINUTES = int(os.environ.get("LOGIN_CODE_EXPIRE_MINUTES", 10))
    LOGIN_CODE_MAX_ATTEMPTS = int(os.environ.get("LOGIN_CODE_MAX_ATTEMPTS", 5))
    LOGIN_CODE_RESEND_COOLDOWN_SECONDS = int(os.environ.get("LOGIN_CODE_RESEND_COOLDOWN_SECONDS", 60))

    # --- Keepalive ---
    ENABLE_KEEPALIVE = _bool_env("ENABLE_KEEPALIVE", "false")
    KEEPALIVE_URL = os.environ.get("KEEPALIVE_URL", "")
    KEEPALIVE_INTERVAL = int(os.environ.get("KEEPALIVE_INTERVAL", 30))

    # --- Rate limiting ---
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

    # --- Entorno ---
    ENV = os.environ.get("FLASK_ENV", "production")
    DEBUG = _bool_env("FLASK_DEBUG", "false")
