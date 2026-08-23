#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilidades de seguridad: hashing de contraseñas, generación y hashing de
tokens/códigos, y saneamiento de nombres de archivo.

Regla de oro: NUNCA almacenar contraseñas, tokens de verificación o códigos
2FA en texto plano. Todo se guarda con hash (Werkzeug/PBKDF2-SHA256, o
SHA-256 para los códigos cortos de un solo uso).
"""
import hashlib
import re
import secrets

from werkzeug.security import generate_password_hash, check_password_hash


# ---------- Contraseñas ----------
def hash_password(password: str) -> str:
    return generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return check_password_hash(password_hash, password)
    except (ValueError, TypeError):
        return False


def password_is_strong_enough(password: str) -> bool:
    return isinstance(password, str) and len(password) >= 8


# ---------- Tokens de verificación de correo ----------
def generate_verification_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    # Los tokens son largos y aleatorios (alta entropía): SHA-256 es suficiente
    # y permite una búsqueda determinista en la base de datos.
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------- Códigos 2FA de 6 dígitos ----------
def generate_login_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(6))


def hash_login_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def codes_match(candidate: str, code_hash: str) -> bool:
    if not candidate or not re.fullmatch(r"\d{6}", candidate):
        return False
    return secrets.compare_digest(hash_login_code(candidate), code_hash)


# ---------- Validación de email ----------
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str) -> bool:
    return bool(email) and bool(_EMAIL_RE.match(email.strip())) and len(email) <= 255


# ---------- Nombres de archivo seguros ----------
_UNSAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9._\- ]+")


def safe_filename(name: str, fallback: str = "download") -> str:
    """
    Genera un nombre de archivo seguro:
    - elimina separadores de ruta y caracteres de control
    - previene path traversal (../, rutas absolutas)
    - limita la longitud
    """
    if not name:
        return fallback
    name = name.replace("\\", "/").split("/")[-1]  # descarta cualquier ruta
    name = name.replace("..", "")
    name = _UNSAFE_CHARS_RE.sub("_", name).strip(" .")
    if not name:
        return fallback
    return name[:150]
