#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instancias compartidas de extensiones Flask.
Se crean aquí (sin app) y se inicializan con init_app() en app.py
para evitar imports circulares entre módulos.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()

limiter = Limiter(key_func=get_remote_address)
