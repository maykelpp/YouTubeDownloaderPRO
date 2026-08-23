#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Blueprint de autenticación:
- Registro (nombre/email/contraseña + confirmación)
- Verificación de correo (token con expiración, un solo uso)
- Login (email + contraseña)
- Segundo factor por correo (código de 6 dígitos, expira, intentos limitados,
  invalidación tras uso, cooldown de reenvío, nunca en logs)
- Logout
- Página "Mi cuenta"

Notas de seguridad:
- Las contraseñas se guardan con hash (nunca en texto plano).
- Los tokens de verificación y los códigos 2FA se guardan con hash.
- Rate limiting en login y en verificación de código.
"""
import datetime
from functools import wraps

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from extensions import db, limiter
from models import EmailVerification, LoginCode, User
from mailer import send_login_code_email, send_verification_email
from security import (
    codes_match,
    generate_login_code,
    generate_verification_token,
    hash_login_code,
    hash_password,
    hash_token,
    is_valid_email,
    password_is_strong_enough,
    verify_password,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Debes iniciar sesión para acceder a esta página.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    password_confirm = request.form.get("password_confirm") or ""

    if not name or not is_valid_email(email):
        flash("Nombre o correo inválido.", "error")
        return render_template("register.html", name=name, email=email)

    if not password_is_strong_enough(password):
        flash("La contraseña debe tener al menos 8 caracteres.", "error")
        return render_template("register.html", name=name, email=email)

    if password != password_confirm:
        flash("Las contraseñas no coinciden.", "error")
        return render_template("register.html", name=name, email=email)

    if User.query.filter_by(email=email).first():
        flash("Ya existe una cuenta con ese correo.", "error")
        return render_template("register.html", name=name, email=email)

    user = User(name=name, email=email, password_hash=hash_password(password), email_verified=False)
    db.session.add(user)
    db.session.commit()

    _issue_and_send_verification_email(user)

    flash("Cuenta creada. Revisa tu correo para verificar tu cuenta.", "success")
    return redirect(url_for("auth.login"))


def _issue_and_send_verification_email(user: User):
    token = generate_verification_token()
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(
        minutes=current_app.config["EMAIL_VERIFICATION_EXPIRE_MINUTES"]
    )
    record = EmailVerification(user_id=user.id, token_hash=hash_token(token), expires_at=expires_at)
    db.session.add(record)
    db.session.commit()

    verify_url = url_for("auth.verify_email", token=token, _external=True)
    send_verification_email(
        user.email, user.name, verify_url, current_app.config["EMAIL_VERIFICATION_EXPIRE_MINUTES"]
    )


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    token_hash = hash_token(token)
    record = EmailVerification.query.filter_by(token_hash=token_hash).first()

    if not record or record.is_used or record.is_expired:
        flash("El enlace de verificación no es válido o ha expirado.", "error")
        return redirect(url_for("auth.login"))

    record.used_at = datetime.datetime.utcnow()
    user = db.session.get(User, record.user_id)
    if user:
        user.email_verified = True
    db.session.commit()

    flash("¡Correo verificado! Ya puedes iniciar sesión.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-verification", methods=["POST"])
@limiter.limit("3 per minute")
def resend_verification():
    email = (request.form.get("email") or "").strip().lower()
    user = User.query.filter_by(email=email).first()
    # Respuesta genérica: no revelar si el correo existe o no.
    if user and not user.email_verified:
        _issue_and_send_verification_email(user)
    flash("Si la cuenta existe y no está verificada, hemos enviado un nuevo correo.", "success")
    return redirect(url_for("auth.login"))


# ---------------------------------------------------------------------------
# Login (paso 1: email + contraseña)
# ---------------------------------------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not verify_password(password, user.password_hash):
        flash("Correo o contraseña incorrectos.", "error")
        return render_template("login.html", email=email)

    if not user.email_verified:
        flash("Debes verificar tu correo antes de iniciar sesión.", "error")
        return render_template("login.html", email=email, show_resend=True)

    _issue_and_send_login_code(user)
    session["pending_2fa_user_id"] = user.id
    return redirect(url_for("auth.verify_code"))


def _issue_and_send_login_code(user: User):
    code = generate_login_code()
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(
        minutes=current_app.config["LOGIN_CODE_EXPIRE_MINUTES"]
    )
    record = LoginCode(user_id=user.id, code_hash=hash_login_code(code), expires_at=expires_at)
    db.session.add(record)
    db.session.commit()
    # El código NUNCA se registra en logs (ver mailer.py).
    send_login_code_email(user.email, user.name, code, current_app.config["LOGIN_CODE_EXPIRE_MINUTES"])
    session["login_code_sent_at"] = datetime.datetime.utcnow().isoformat()


# ---------------------------------------------------------------------------
# Login (paso 2: código de 6 dígitos)
# ---------------------------------------------------------------------------
@auth_bp.route("/verify-code", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def verify_code():
    pending_user_id = session.get("pending_2fa_user_id")
    if not pending_user_id:
        return redirect(url_for("auth.login"))

    if request.method == "GET":
        return render_template("verify_code.html")

    code = (request.form.get("code") or "").strip()
    record = (
        LoginCode.query.filter_by(user_id=pending_user_id, used_at=None)
        .order_by(LoginCode.created_at.desc())
        .first()
    )

    if not record or record.is_expired:
        flash("El código expiró. Solicita uno nuevo.", "error")
        return render_template("verify_code.html")

    if record.attempts >= current_app.config["LOGIN_CODE_MAX_ATTEMPTS"]:
        flash("Demasiados intentos fallidos. Solicita un nuevo código.", "error")
        return render_template("verify_code.html")

    if not codes_match(code, record.code_hash):
        record.attempts += 1
        db.session.commit()
        flash("Código incorrecto.", "error")
        return render_template("verify_code.html")

    record.used_at = datetime.datetime.utcnow()
    db.session.commit()

    session.pop("pending_2fa_user_id", None)
    session.pop("login_code_sent_at", None)
    session.permanent = True
    session["user_id"] = pending_user_id

    flash("Sesión iniciada correctamente.", "success")
    return redirect(url_for("index"))


@auth_bp.route("/resend-code", methods=["POST"])
@limiter.limit("5 per minute")
def resend_code():
    pending_user_id = session.get("pending_2fa_user_id")
    if not pending_user_id:
        return redirect(url_for("auth.login"))

    cooldown = current_app.config["LOGIN_CODE_RESEND_COOLDOWN_SECONDS"]
    last_sent = session.get("login_code_sent_at")
    if last_sent:
        elapsed = (datetime.datetime.utcnow() - datetime.datetime.fromisoformat(last_sent)).total_seconds()
        if elapsed < cooldown:
            flash(f"Espera {int(cooldown - elapsed)}s antes de reenviar el código.", "error")
            return render_template("verify_code.html")

    user = db.session.get(User, pending_user_id)
    if user:
        _issue_and_send_login_code(user)
    flash("Nuevo código enviado.", "success")
    return render_template("verify_code.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "success")
    return redirect(url_for("index"))


@auth_bp.route("/account")
@login_required
def account():
    return render_template("account.html", user=current_user())
