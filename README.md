# 🎵 YouTube Downloader PRO

## Descarga videos y música de YouTube - 100% GRATIS

### 🌟 Características
- ✅ 100% Gratuito - Sin límites, sin registro
- 🎵 Descarga audio en MP3 320kbps
- 🎬 Descarga videos en HD/Full HD
- 📊 Información completa de videos
- 📈 Estadísticas en tiempo real
- 🎨 Diseño moderno verde oscuro
- 📱 Responsive - Compatible con móviles

---

## 📁 Estructura del Proyecto

```
youtube-downloader-pro/
├── app.py                    # Servidor Flask principal
├── youtube_utils.py          # Funciones de YouTube
├── database.py              # Gestión de base de datos
├── requirements.txt         # Dependencias Python
├── render.yaml             # Configuración Render.com
├── README.md               # Este archivo
└── templates/
    └── index.html          # Interfaz web completa
```

---

## 🚀 Deploy en Render.com (GRATIS)

### Paso 1: Preparar el código
1. Crea una cuenta en [GitHub](https://github.com) (gratis)
2. Crea un nuevo repositorio público
3. Sube todos los archivos del proyecto

### Paso 2: Conectar con Render
1. Crea una cuenta en [Render.com](https://render.com) (gratis)
2. Click en "New +" → "Web Service"
3. Conecta tu repositorio de GitHub
4. Render detectará automáticamente el `render.yaml`

### Paso 3: Configurar (Automático)
- **Build Command**: Se instala automáticamente desde `render.yaml`
- **Start Command**: `gunicorn app:app` (ya configurado)
- **Puerto**: Dinámico (variable `$PORT`)

### Paso 4: Deploy
- Click en "Create Web Service"
- Espera 5-10 minutos para el primer deploy
- Tu app estará en: `https://tu-app.onrender.com`

---

## 💻 Instalación Local

### Requisitos previos
- Python 3.11+
- ffmpeg instalado
- yt-dlp

### Instalación

```bash
# Clonar el repositorio
git clone https://github.com/tu-usuario/youtube-downloader-pro.git
cd youtube-downloader-pro

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Instalar ffmpeg (Ubuntu/Debian)
sudo apt-get install ffmpeg

# Instalar ffmpeg (macOS)
brew install ffmpeg

# Instalar ffmpeg (Windows)
# Descargar desde: https://ffmpeg.org/download.html

# Ejecutar la aplicación
python app.py
```

La aplicación estará disponible en: `http://localhost:10000`

---

## 🔧 Configuración

### Variables de Entorno (Opcional)

```bash
# Puerto (por defecto: 10000)
export PORT=10000

# Carpeta de descargas (por defecto: /tmp/youtube_downloads)
# Puedes modificarlo en app.py si lo necesitas
```

---

## 📦 Dependencias

- **Flask 3.0.0**: Framework web
- **yt-dlp 2024.10.7**: Descargador de YouTube
- **gunicorn 21.2.0**: Servidor WSGI para producción

---

## 🎨 Personalización

### Cambiar colores
Edita `templates/index.html` y modifica las variables CSS:
```css
/* Color principal (verde) */
#10b981

/* Color secundario (azul) */
#3b82f6
```

### Cambiar puerto
Modifica `app.py`:
```python
port = int(os.environ.get("PORT", TU_PUERTO))
```

---

## 🐛 Solución de Problemas

### Error: "yt-dlp not found"
```bash
pip install --upgrade yt-dlp
```

### Error: "ffmpeg not found"
Instala ffmpeg según tu sistema operativo (ver sección de instalación)

### Error: Base de datos
La base de datos se crea automáticamente en `/tmp/stats.db`

### Descargas no funcionan en Render
Render usa almacenamiento efímero. Los archivos en `/tmp` se borran periódicamente.
Esto es normal y esperado para el plan gratuito.

---

## 📊 Estadísticas

El sistema registra:
- Total de descargas
- Descargas del día
- Tipo de descarga (audio/video)
- Títulos descargados

---

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama (`git checkout -b feature/nueva-caracteristica`)
3. Commit cambios (`git commit -m 'Agregar nueva característica'`)
4. Push a la rama (`git push origin feature/nueva-caracteristica`)
5. Abre un Pull Request

---

## 📱 Contacto

- WhatsApp: +593 979611678
- Email: tu-email@ejemplo.com

---

## ⚖️ Licencia

Este proyecto es de código abierto y está disponible bajo la licencia MIT.

---

## 💚 Donaciones

Si este proyecto te ayuda, considera apoyarlo:
- ☕ Invitarme un café
- ⭐ Dar una estrella en GitHub
- 📢 Compartir con amigos

---

## 🎉 Características Futuras

- [ ] Descargar playlists completas
- [ ] Selector de calidad de video
- [ ] Subtítulos automáticos
- [ ] Historial de descargas
- [ ] Modo oscuro/claro
- [ ] Soporte para más plataformas

---

**Hecho con 💚 para la comunidad**
