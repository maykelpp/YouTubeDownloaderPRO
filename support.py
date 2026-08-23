#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Blueprint de soporte / reporte de bugs.

Reemplaza la antigua sección "Ayuda" (que mostraba un número de teléfono)
por un formulario de soporte con cuestionario dinámico. El reporte se
guarda en la base de datos y se envía por correo a SUPPORT_EMAIL.

Nunca se solicitan contraseñas, tokens ni cookies de YouTube.
"""
import json

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from extensions import db, limiter
from mailer import send_support_ticket_email
from models import SupportTicket
from security import is_valid_email

support_bp = Blueprint("support", __name__, url_prefix="/support")

QUESTIONNAIRE = [
    {"key": "intent", "question": "¿Qué estabas intentando hacer?"},
    {"key": "what_happened", "question": "¿Qué ocurrió?"},
    {"key": "expected", "question": "¿Qué esperabas que ocurriera?"},
    {"key": "always_happens", "question": "¿Ocurre siempre?"},
    {"key": "device", "question": "¿Qué dispositivo/navegador utilizas?"},
    {"key": "error_shown", "question": "¿Qué mensaje de error apareció?"},
    {"key": "extra_info", "question": "¿Quieres adjuntar información adicional?"},
]


@support_bp.route("/", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def support_form():
    if request.method == "GET":
        return render_template(
            "support.html", issue_types=SupportTicket.ISSUE_TYPES, questionnaire=QUESTIONNAIRE
        )

    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    issue_type = (request.form.get("issue_type") or "").strip()
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    related_url = (request.form.get("related_url") or "").strip() or None
    video_id = (request.form.get("video_id") or "").strip() or None
    error_message = (request.form.get("error_message") or "").strip() or None

    errors = []
    if not name:
        errors.append("El nombre es obligatorio.")
    if not is_valid_email(email):
        errors.append("El correo no es válido.")
    if issue_type not in SupportTicket.ISSUE_TYPES:
        errors.append("Selecciona un tipo de problema válido.")
    if not title:
        errors.append("El título es obligatorio.")
    if not description:
        errors.append("La descripción es obligatoria.")

    if errors:
        for e in errors:
            flash(e, "error")
        return render_template(
            "support.html",
            issue_types=SupportTicket.ISSUE_TYPES,
            questionnaire=QUESTIONNAIRE,
            form=request.form,
        )

    answers = {q["key"]: (request.form.get(f"q_{q['key']}") or "").strip() for q in QUESTIONNAIRE}

    ticket = SupportTicket(
        name=name,
        email=email,
        issue_type=issue_type,
        title=title,
        description=description,
        related_url=related_url,
        video_id=video_id,
        error_message=error_message,
        questionnaire=json.dumps(answers, ensure_ascii=False),
        status="OPEN",
    )
    db.session.add(ticket)
    db.session.commit()

    send_support_ticket_email(current_app.config["SUPPORT_EMAIL"], ticket)

    flash("¡Gracias! Tu reporte fue enviado. Te contactaremos por correo.", "success")
    return redirect(url_for("support.support_form"))
