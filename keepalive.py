#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ping opcional para mantener la app activa en planes gratuitos que lo
permitan. Desactivado por defecto. Se activa con ENABLE_KEEPALIVE=true.

No es agresivo: un único hilo en segundo plano que hace una petición GET
cada KEEPALIVE_INTERVAL segundos (por defecto 30s) a KEEPALIVE_URL, y se
detiene solo si el proceso termina. No genera tráfico si está desactivado.
"""
import logging
import threading
import time

import urllib.request

logger = logging.getLogger("keepalive")


def start_keepalive(app):
    cfg = app.config
    if not cfg.get("ENABLE_KEEPALIVE"):
        return
    url = cfg.get("KEEPALIVE_URL")
    if not url:
        logger.warning("ENABLE_KEEPALIVE=true pero KEEPALIVE_URL no está configurado; keepalive no iniciado.")
        return

    interval = max(cfg.get("KEEPALIVE_INTERVAL", 30), 15)  # mínimo 15s para evitar tráfico agresivo

    def _loop():
        while True:
            try:
                urllib.request.urlopen(url, timeout=10)
            except Exception as exc:
                logger.debug("Keepalive ping falló: %s", exc)
            time.sleep(interval)

    thread = threading.Thread(target=_loop, daemon=True, name="keepalive")
    thread.start()
    logger.info("Keepalive iniciado: %s cada %ss", url, interval)
