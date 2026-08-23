#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Envío de correos vía SMTP (configurable por variables de entorno).

IMPORTANTE:
- Nunca se registran (logs) contraseñas ni códigos 2FA.
- Si SMTP no está configurado, las funciones devuelven False en vez de
  lanzar una excepción que rompa el flujo de registro/login.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

logger = logging.getLogger("mailer")


def _send(to_email: str, subject: str, html_body: str, text_body: str) -> bool:
    cfg = current_app.config
    if not cfg.get("MAIL_ENABLED"):
        logger.warning("SMTP no configurado: correo a %s NO enviado (%s)", to_email, subject)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["MAIL_FROM"]
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if cfg["SMTP_PORT"] == 465:
            server = smtplib.SMTP_SSL(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=15)
        else:
            server = smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=15)
            server.starttls()
        try:
            server.login(cfg["SMTP_USERNAME"], cfg["SMTP_PASSWORD"])
            server.sendmail(cfg["MAIL_FROM"], [to_email], msg.as_string())
        finally:
            server.quit()
        logger.info("Correo enviado a %s (%s)", to_email, subject)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error(
            "SMTP: autenticación rechazada para %s. La contraseña de aplicación "
            "es incorrecta o fue revocada. Genera una nueva en "
            "https://myaccount.google.com/apppasswords", cfg.get("SMTP_USERNAME")
        )
        return False
    except (TimeoutError, OSError) as exc:
        logger.error(
            "SMTP: timeout/error de conexión a %s:%s (%s). Es probable que la red "
            "esté bloqueando el puerto SMTP saliente (frecuente en datos móviles). "
            "Prueba con WiFi o corre 'python test_smtp.py' para diagnosticar.",
            cfg.get("SMTP_HOST"), cfg.get("SMTP_PORT"), exc
        )
        return False
    except Exception:
        # Nunca exponer detalles del error SMTP al usuario final.
        logger.exception("Error enviando correo a %s", to_email)
        return False


def send_verification_email(to_email: str, name: str, verify_url: str, expire_minutes: int) -> bool:
    subject = "Verifica tu correo - YouTube Downloader PRO"
    text = (
        f"Hola {name},\n\n"
        f"Para activar tu cuenta, abre este enlace (expira en {expire_minutes} minutos):\n"
        f"{verify_url}\n\n"
        "Si no creaste esta cuenta, ignora este mensaje."
    )
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
      <h2 style="color:#10b981">Verifica tu correo</h2>
      <p>Hola {name},</p>
      <p>Para activar tu cuenta en <strong>YouTube Downloader PRO</strong> haz clic en el
      siguiente botón (expira en {expire_minutes} minutos):</p>
      <p><a href="{verify_url}" style="background:#10b981;color:#fff;padding:12px 24px;
      border-radius:8px;text-decoration:none;display:inline-block">Verificar mi correo</a></p>
      <p style="color:#888;font-size:13px">Si no creaste esta cuenta, ignora este mensaje.</p>
    </div>
    """
    return _send(to_email, subject, html, text)


def send_login_code_email(to_email: str, name: str, code: str, expire_minutes: int) -> bool:
    subject = "Tu código de verificación - YouTube Downloader PRO"
    text = (
        f"Hola {name},\n\n"
        f"Tu código de verificación es: {code}\n"
        f"Expira en {expire_minutes} minutos. No lo compartas con nadie."
    )
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
      <h2 style="color:#10b981">Verifica tu identidad</h2>
      <p>Hola {name},</p>
      <p>Tu código de verificación es:</p>
      <p style="font-size:32px;font-weight:bold;letter-spacing:6px">{code}</p>
      <p style="color:#888;font-size:13px">Expira en {expire_minutes} minutos. No lo compartas con nadie.</p>
    </div>
    """
    # El código NUNCA se registra en logs; solo se envía por correo.
    return _send(to_email, subject, html, text)


def send_support_ticket_email(support_email: str, ticket) -> bool:
    subject = f"[Soporte #{ticket.id}] {ticket.issue_type} - {ticket.title}"
    text = (
        f"Nuevo ticket de soporte\n\n"
        f"Nombre: {ticket.name}\n"
        f"Correo: {ticket.email}\n"
        f"Tipo: {ticket.issue_type}\n"
        f"Título: {ticket.title}\n"
        f"Descripción: {ticket.description}\n"
        f"URL relacionada: {ticket.related_url or '-'}\n"
        f"Video ID: {ticket.video_id or '-'}\n"
        f"Mensaje de error: {ticket.error_message or '-'}\n"
        f"Estado: {ticket.status}\n"
    )
    html = f"<pre style='font-family:sans-serif;white-space:pre-wrap'>{text}</pre>"
    return _send(support_email, subject, html, text)
