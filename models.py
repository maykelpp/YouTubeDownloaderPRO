#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modelos de base de datos (SQLAlchemy).

Tablas:
- users
- email_verifications
- login_codes
- support_tickets
- download_stats  (reemplaza la antigua tabla de estadísticas de forma compatible)
"""
import datetime

from extensions import db


def utcnow():
    return datetime.datetime.utcnow()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    email_verifications = db.relationship(
        "EmailVerification", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    login_codes = db.relationship(
        "LoginCode", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def to_public_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "email_verified": self.email_verified,
            "is_admin": self.is_admin,
        }


class EmailVerification(db.Model):
    __tablename__ = "email_verifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(255), nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    @property
    def is_expired(self):
        return utcnow() > self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None


class LoginCode(db.Model):
    __tablename__ = "login_codes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    code_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    @property
    def is_expired(self):
        return utcnow() > self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None


class SupportTicket(db.Model):
    __tablename__ = "support_tickets"

    STATUSES = ("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED")
    ISSUE_TYPES = (
        "Error de descarga",
        "Error de audio",
        "Error de vídeo",
        "Error de login",
        "Problema con la cuenta",
        "Error de interfaz",
        "Bug",
        "Otro",
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    issue_type = db.Column(db.String(60), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    related_url = db.Column(db.String(500), nullable=True)
    video_id = db.Column(db.String(64), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    questionnaire = db.Column(db.Text, nullable=True)  # JSON serializado
    status = db.Column(db.String(20), default="OPEN", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class DownloadStat(db.Model):
    __tablename__ = "download_stats"

    id = db.Column(db.Integer, primary_key=True)
    format_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)


class UserActivity(db.Model):
    """
    Registra búsquedas y descargas (con user_id nulo si es anónimo).
    Se usa para: (1) variar el feed en cada visita y (2) construir el feed
    "Para ti" de usuarios que iniciaron sesión, a partir de su historial
    reciente real (sin inventar preferencias).
    """
    __tablename__ = "user_activity"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    kind = db.Column(db.String(20), nullable=False)  # 'search' | 'download'
    # OJO: NO se llama "query" — ese nombre choca con la propiedad especial
    # Model.query que usa Flask-SQLAlchemy para hacer consultas (causaba
    # AttributeError: 'InstrumentedAttribute' object has no attribute 'filter_by').
    search_query = db.Column(db.String(200), nullable=True)
    video_id = db.Column(db.String(64), nullable=True)
    video_title = db.Column(db.String(300), nullable=True)
    uploader = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
