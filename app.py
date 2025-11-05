#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import secrets
from flask import Flask, request, render_template, jsonify, send_file
from database import init_db, get_stats
from youtube_utils import get_video_info, search_youtube, download_media

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Configuración para Render.com
DOWNLOAD_FOLDER = os.path.join('/tmp', 'youtube_downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Inicializar base de datos
init_db()

# ===== RUTAS =====
@app.route("/")
def index():
    stats = get_stats()
    return render_template('index.html', stats=stats)

@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json()
    query = data.get('query', '')
    
    if not query:
        return jsonify({'error': 'Query vacío'}), 400
    
    result = search_youtube(query)
    return jsonify(result)

@app.route("/api/video_info", methods=["POST"])
def api_video_info():
    data = request.get_json()
    video_id = data.get('video_id')
    
    if not video_id:
        return jsonify({'success': False, 'error': 'Video ID faltante'}), 400
    
    result = get_video_info(video_id)
    return jsonify({'success': result['success'], 'info': result} if result['success'] else result)

@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.get_json()
    video_id = data.get('video_id')
    video_title = data.get('video_title')
    format_type = data.get('format_type', 'audio')
    
    if not video_id or not video_title:
        return jsonify({'success': False, 'error': 'Parámetros faltantes'}), 400
    
    result = download_media(video_id, video_title, format_type, DOWNLOAD_FOLDER)
    return jsonify(result)

@app.route("/download/<path:filename>")
def download_file(filename):
    try:
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=filename)
        return "Archivo no encontrado", 404
    except Exception as e:
        return str(e), 500

@app.route("/health")
def health():
    stats = get_stats()
    return jsonify({'status': 'ok', 'stats': stats}), 200

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))  # ← OJO: usa PORT del sistema
    app.run(host="0.0.0.0", port=port)
    
    print("\n" + "="*80)
    print(" "*10 + "🎵 YOUTUBE DOWNLOADER PRO - 100% GRATIS 💚")
    print("="*80)
    print(f"\n  🌐 Servidor: http://0.0.0.0:{port}")
    print(f"  📁 Descargas: {DOWNLOAD_FOLDER}")
    print("\n" + "="*80)
    print("  ✨ CARACTERÍSTICAS:")
    print("  💚 100% GRATIS - Sin límites, sin keys, sin registro")
    print("  🎵 Descarga de audio MP3 320kbps")
    print("  🎬 Descarga de videos en HD")
    print("  📊 Información completa de videos")
    print("\n  📱 WhatsApp: +593 979611678")
    print("="*80 + "\n")
    
    try:
        app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n\n  ⚠️  Servidor detenido")
