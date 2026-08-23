#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prueba de SMTP independiente de Flask.

Uso:
    python test_smtp.py tu-correo-de-prueba@gmail.com

Lee las mismas variables que la app (SMTP_HOST, SMTP_PORT, SMTP_USERNAME,
SMTP_PASSWORD, MAIL_FROM) desde tu archivo .env, e intenta conectar y
enviar un correo de prueba, mostrando en pantalla exactamente en qué paso
falla (conexión, TLS, login o envío). Así distinguimos:

- Si se cuelga en "Conectando..." varios segundos y luego falla con
  timeout -> tu red/operador está bloqueando el puerto SMTP saliente
  (común en datos móviles). Prueba con WiFi, o cambia SMTP_PORT a 465.
- Si falla en "Autenticando..." con error 535 -> la contraseña de
  aplicación es incorrecta o fue revocada. Genera una nueva en
  https://myaccount.google.com/apppasswords
- Si todo dice OK pero el correo no llega -> revisa la carpeta de SPAM.
"""
import os
import smtplib
import sys
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
MAIL_FROM = os.environ.get("MAIL_FROM", SMTP_USERNAME)


def main():
    to_email = sys.argv[1] if len(sys.argv) > 1 else SMTP_USERNAME

    print("=== Diagnóstico SMTP ===")
    print(f"SMTP_HOST     = {SMTP_HOST!r}")
    print(f"SMTP_PORT     = {SMTP_PORT!r}")
    print(f"SMTP_USERNAME = {SMTP_USERNAME!r}")
    print(f"SMTP_PASSWORD = {'*' * len(SMTP_PASSWORD) if SMTP_PASSWORD else '(vacío)'}")
    print(f"MAIL_FROM     = {MAIL_FROM!r}")
    print(f"Enviando correo de prueba a: {to_email}")
    print()

    if not (SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD):
        print("❌ Faltan variables SMTP_HOST / SMTP_USERNAME / SMTP_PASSWORD en tu .env")
        return

    try:
        print("1) Conectando a", SMTP_HOST, "puerto", SMTP_PORT, "...")
        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
            server.set_debuglevel(0)
            print("2) Iniciando TLS (STARTTLS)...")
            server.starttls()
        print("   ✅ Conexión OK")

        print("3) Autenticando...")
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        print("   ✅ Login OK")

        print("4) Enviando correo de prueba...")
        msg = MIMEText("Este es un correo de prueba de YouTube Downloader PRO.", "plain", "utf-8")
        msg["Subject"] = "Prueba SMTP - YouTube Downloader PRO"
        msg["From"] = MAIL_FROM
        msg["To"] = to_email
        server.sendmail(MAIL_FROM, [to_email], msg.as_string())
        server.quit()

        print("   ✅ Correo enviado sin errores.")
        print()
        print("Si aun así no te llega, revisa la carpeta de SPAM/Promociones de", to_email)

    except smtplib.SMTPAuthenticationError as e:
        print(f"   ❌ Error de autenticación (535): {e}")
        print("   -> La contraseña de aplicación es incorrecta, expiró o fue revocada.")
        print("   -> Genera una nueva en https://myaccount.google.com/apppasswords")
    except (TimeoutError, OSError) as e:
        print(f"   ❌ Error de conexión/timeout: {e}")
        print("   -> Es muy probable que tu red (datos móviles / Termux) esté bloqueando")
        print("      el puerto saliente", SMTP_PORT, ". Prueba con WiFi, o cambia SMTP_PORT=465")
        print("      en tu .env (usa SMTP_SSL directo en vez de STARTTLS).")
    except Exception as e:
        print(f"   ❌ Error inesperado: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
