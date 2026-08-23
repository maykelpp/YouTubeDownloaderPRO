# 🎵 YouTube Downloader PRO

Aplicación web Flask/Python (yt-dlp + FFmpeg) para descargar audio/vídeo de
YouTube, con cuentas de usuario, verificación por correo, segundo factor
(2FA) por email, soporte con cuestionario dinámico, y lista para
producción en **Render** + **GitHub**.

---

## 📁 Estructura del proyecto

```
YouTubeDownloaderPRO-main/
├── app.py                  # Flask app factory + rutas
├── config.py                # Configuración desde variables de entorno
├── extensions.py            # Instancias compartidas (db, limiter)
├── models.py                 # users, email_verifications, login_codes, support_tickets, download_stats
├── database.py               # init_db(), get_stats(), cuenta admin inicial
├── security.py                # hashing, tokens, códigos 2FA, nombres de archivo seguros
├── mailer.py                   # Envío SMTP (verificación, 2FA, soporte)
├── auth.py                     # Blueprint: registro, login, 2FA, logout, cuenta
├── support.py                   # Blueprint: formulario de soporte
├── youtube_utils.py             # yt-dlp + FFmpeg (selección dinámica de formatos)
├── keepalive.py                  # Ping opcional configurable
├── templates/
│   ├── index.html            # Interfaz principal de descarga (diseño original)
│   ├── _layout.html          # Layout compartido para auth/soporte
│   ├── login.html / register.html / verify_code.html / account.html / support.html
├── tests/                      # pytest (yt-dlp mockeado, sin depender de YouTube)
├── requirements.txt
├── requirements-dev.txt
├── render.yaml
├── Procfile
├── .gitignore
├── .env.example
└── app.py.bak                  # Backup del app.py original antes de los cambios
```

---

## 🆕 Qué cambió respecto al proyecto original

1. **Descargas de YouTube corregidas**: selección dinámica de formatos (nunca
   IDs fijos como `18`/`140`, nunca se fuerza el cliente `android_vr`). Si
   YouTube no entrega streams (bloqueo temporal / "Sign in to confirm
   you're not a bot"), se detecta **una sola vez** y se devuelve un mensaje
   claro — no se repiten intentos idénticos. `video_info` y `download` son
   operaciones independientes (una puede funcionar sin la otra).
2. **Audio → MP3** con metadata (título, artista/canal, álbum, fecha) y
   portada incrustada; limpieza de temporales.
3. **Cuentas de usuario**: registro con hashing seguro (nunca texto plano),
   verificación de correo por token con expiración, y **2FA por email con
   código de 6 dígitos** (expira, límite de intentos, invalidación tras
   uso, cooldown de reenvío, nunca en logs).
4. **Soporte**: se eliminó la sección con el número de teléfono; ahora hay
   un formulario de "Soporte" con cuestionario dinámico que crea un ticket
   en la base de datos y lo envía por correo a `dcpiurl@gmail.com`.
5. **Preparado para Render + GitHub**: `render.yaml`, `Procfile`,
   `.gitignore`, `.env.example`, `gunicorn` como servidor de producción
   (nunca `app.run()`), endpoint `/health`, keepalive opcional y
   configurable.
6. **Seguridad**: CSRF en formularios, rate limiting en login/2FA/soporte,
   protección contra path traversal en `/download/<archivo>`, nombres de
   archivo saneados, errores nunca exponen tracebacks al usuario.

---

## 💻 Instalación local

```bash
git clone https://github.com/tu-usuario/YouTubeDownloaderPRO.git
cd YouTubeDownloaderPRO-main

python -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate

pip install -r requirements-dev.txt   # incluye requirements.txt + pytest

# FFmpeg (necesario para audio/vídeo)
sudo apt-get install ffmpeg     # Ubuntu/Debian
brew install ffmpeg             # macOS

cp .env.example .env
# Edita .env con tus valores (ver sección siguiente)

python app.py
```

La app estará en `http://localhost:8080` (o el `PORT` que definas).

---

## 🔧 Variables de entorno

Copia `.env.example` a `.env` y completa:

| Variable | Descripción |
|---|---|
| `SECRET_KEY` | Clave para firmar sesiones. Genera una con `python -c "import secrets;print(secrets.token_hex(32))"` |
| `DATABASE_URL` | `sqlite:////tmp/app.db` por defecto (efímero en Render) o una URL de PostgreSQL para persistencia real |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `MAIL_FROM` | Credenciales SMTP para enviar correos de verificación/2FA/soporte |
| `SUPPORT_EMAIL` | Correo que recibe los tickets de soporte (`dcpiurl@gmail.com` por defecto) |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Si se configuran, se crea/asegura una cuenta administrativa al iniciar |
| `ENABLE_KEEPALIVE`, `KEEPALIVE_URL`, `KEEPALIVE_INTERVAL` | Ping opcional para mantener la app activa (desactivado por defecto) |

**Nunca subas `.env` a GitHub** — ya está excluido en `.gitignore`.

### Configurar Gmail como SMTP (remitente `dcpiurl@gmail.com`)

1. Activa la verificación en 2 pasos en la cuenta de Gmail.
2. Genera una **contraseña de aplicación** en
   `https://myaccount.google.com/apppasswords`.
3. Usa esa contraseña (no la contraseña normal de Gmail) como
   `SMTP_PASSWORD`, con `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`,
   `SMTP_USERNAME=dcpiurl@gmail.com`, `MAIL_FROM=dcpiurl@gmail.com`.
4. Nunca escribas esta contraseña en ningún archivo del repositorio —
   solo como variable de entorno (local en `.env`, en Render como
   Environment Variable).

---

## 🧪 Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Los tests **no dependen de YouTube real** — `yt-dlp` está mockeado. Cubren:
registro, hashing de contraseña, verificación de correo, código de 6
dígitos (correcto/incorrecto/expirado), logout, soporte, `/health`,
selección de formato y detección de errores de yt-dlp (bot-check, 403,
vídeo no disponible), y que la descarga **nunca reintenta más de 2 veces**.

> Nota: en este entorno de generación no tuve acceso a red para instalar
> las dependencias y ejecutar `pytest` de forma end-to-end — sí verifiqué
> que los 16 archivos Python compilan sin errores de sintaxis (`python -m
> py_compile`). Ejecuta la suite localmente o en el build de GitHub
> Actions/Render antes de desplegar a producción, para confirmar con las
> dependencias reales instaladas.

---

## 🚀 Deploy en GitHub + Render

### 1. Crear el repositorio en GitHub
```bash
cd YouTubeDownloaderPRO-main
git init
git add .
git commit -m "YouTube Downloader PRO: auth, 2FA, soporte, listo para Render"
git branch -M main
git remote add origin https://github.com/tu-usuario/YouTubeDownloaderPRO.git
git push -u origin main
```
`.gitignore` ya excluye `.env`, bases de datos locales, `__pycache__`,
descargas temporales y cualquier archivo con "secret/credential/token/
cookie" en el nombre. **Verifica antes de tu primer push que no haya
credenciales reales en ningún archivo versionado.**

### 2. Crear el servicio en Render
1. Entra a [render.com](https://render.com) → **New +** → **Web Service**.
2. Conecta tu repositorio de GitHub.
3. Render detecta `render.yaml` automáticamente (Blueprint).
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
   - **Health Check Path**: `/health`

### 3. Configurar las Environment Variables en Render
En el dashboard del servicio → **Environment**, añade (Render puede
generar `SECRET_KEY` automáticamente si usas el Blueprint):

```
SECRET_KEY=          (generar aleatorio, o dejar que Render lo genere)
DATABASE_URL=        (sqlite:////tmp/app.db o tu URL de PostgreSQL)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=dcpiurl@gmail.com
SMTP_PASSWORD=       (contraseña de aplicación de Gmail, NUNCA la real)
MAIL_FROM=dcpiurl@gmail.com
SUPPORT_EMAIL=dcpiurl@gmail.com
ADMIN_EMAIL=jaramillomaykel9@gmail.com
ADMIN_PASSWORD=      (elige una contraseña fuerte, se guarda con hash)
ENABLE_KEEPALIVE=false
SESSION_COOKIE_SECURE=true
```

> `DATABASE_URL` con SQLite en `/tmp` es **efímera** en el plan gratuito de
> Render (se pierde en cada redeploy). Para conservar usuarios/tickets
> entre despliegues, crea una base de datos PostgreSQL en Render y usa su
> `DATABASE_URL` (instala también `psycopg2-binary`, ya viene comentado en
> `requirements.txt`).

### 4. Deploy
Click **Create Web Service**. El primer build tarda 5-10 minutos. Tu app
quedará en `https://tu-app.onrender.com`.

---

## ✅ Cómo probar cada funcionalidad

**Registro**: ve a `/auth/register`, crea una cuenta. Revisa el correo
configurado en `SMTP_USERNAME`/`MAIL_FROM` (o el buzón del email que
registraste) para el enlace de verificación.

**2FA**: tras verificar el correo, inicia sesión en `/auth/login`. Te
pedirá un código de 6 dígitos enviado por correo (`/auth/verify-code`).
El código expira, tiene intentos limitados y se puede reenviar con
cooldown.

**Descargas**: busca un video desde la página principal y prueba "Audio"
y "Video". Si YouTube bloquea temporalmente el stream, verás el mensaje
claro *"YouTube no proporcionó un stream descargable para este vídeo en
este momento"* en vez de un error genérico o un traceback.

**Soporte**: ve a `/support/`, completa el formulario y el cuestionario
dinámico. Se guarda un ticket en la base de datos y se envía copia a
`SUPPORT_EMAIL`.

**Salud del servicio**: `GET /health` → `{"status": "ok"}`.

---

## 🐛 Solución de problemas

- **"yt-dlp no encuentra streams"**: puede ser un bloqueo temporal de
  YouTube. La app ya no reintenta infinitamente ni oculta el error —
  espera unos minutos y vuelve a intentar.
- **"FFmpeg no está instalado"**: instala FFmpeg en el entorno de
  ejecución (en Render, el buildpack de Python no lo trae por defecto —
  puede requerir un `Dockerfile` o un buildpack con FFmpeg si el plan
  gratuito no lo incluye).
- **No llegan los correos**: revisa `SMTP_HOST/PORT/USERNAME/PASSWORD` y
  que sea una contraseña de aplicación de Gmail, no la contraseña normal.
- **Sesiones se cierran solas en Render**: si no configuraste
  `SECRET_KEY`, la app genera una temporal en cada arranque y las
  sesiones se invalidan en cada redeploy/reinicio — configura
  `SECRET_KEY` fija en las Environment Variables.
