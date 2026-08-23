#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Registro en memoria de trabajos de descarga en curso, para poder mostrar
una barra de progreso REAL (no simulada) en el frontend.

Flujo:
1. POST /api/download/start crea un job_id y lanza la descarga en un hilo
   en segundo plano.
2. yt-dlp reporta avance real (bytes descargados / total) a través de un
   progress_hook, que actualiza este registro.
3. El frontend consulta GET /api/download/status/<job_id> cada ~700ms y
   actualiza la barra con el porcentaje real.

Limitación conocida: este registro vive en memoria de un solo proceso. Si
despliegas con gunicorn con más de 1 worker, cada worker tendría su propio
registro y el polling podría caer en otro worker que no conoce el job. Para
un solo proceso (como `python app.py` o `gunicorn -w 1`) funciona bien.
"""
import threading
import time
import uuid

_jobs = {}
_lock = threading.Lock()
_JOB_TTL_SECONDS = 15 * 60  # los jobs viejos se limpian solos


def create_job():
    job_id = uuid.uuid4().hex
    with _lock:
        _jobs[job_id] = {
            "status": "starting",   # starting | downloading | processing | done | error
            "percent": 0,
            "speed": None,
            "eta": None,
            "result": None,
            "error": None,
            "created_at": time.time(),
        }
    _cleanup_old_jobs()
    return job_id


def update_job(job_id, **kwargs):
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def get_job(job_id):
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def _cleanup_old_jobs():
    cutoff = time.time() - _JOB_TTL_SECONDS
    with _lock:
        stale = [jid for jid, j in _jobs.items() if j.get("created_at", 0) < cutoff]
        for jid in stale:
            _jobs.pop(jid, None)
