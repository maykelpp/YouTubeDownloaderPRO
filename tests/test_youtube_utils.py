from unittest.mock import MagicMock, patch

import pytest

import youtube_utils as yu
from security import safe_filename


def test_safe_filename_blocks_path_traversal():
    assert safe_filename("../../etc/passwd") == "etc_passwd" or "/" not in safe_filename(
        "../../etc/passwd"
    )
    assert ".." not in safe_filename("../secret.txt")
    assert safe_filename("") == "download"


def test_classify_error_bot_check():
    err = Exception("ERROR: Sign in to confirm you're not a bot")
    assert yu._classify_error(err) == yu.ERROR_BOT_CHECK


def test_classify_error_403():
    err = Exception("HTTP Error 403: Forbidden")
    assert yu._classify_error(err) == yu.ERROR_FORBIDDEN


def test_classify_error_unavailable():
    err = Exception("Video unavailable")
    assert yu._classify_error(err) == yu.ERROR_UNAVAILABLE


def test_classify_error_generic_fallback():
    err = Exception("some totally unexpected failure")
    assert yu._classify_error(err) == yu.ERROR_GENERIC


@patch("youtube_utils.yt_dlp.YoutubeDL")
def test_get_video_info_success(mock_ydl_cls):
    mock_ydl = MagicMock()
    mock_ydl.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {
        "id": "abc123",
        "title": "Video de prueba",
        "uploader": "Canal X",
        "duration": 120,
        "view_count": 1000,
        "like_count": 50,
        "upload_date": "20240101",
        "thumbnail": "http://example.com/thumb.jpg",
        "description": "desc",
        "formats": [{"format_id": "251"}, {"format_id": "137"}],
    }
    mock_ydl_cls.return_value = mock_ydl

    result = yu.get_video_info("abc123")
    assert result["success"] is True
    assert result["title"] == "Video de prueba"
    assert result["formats"] == 2


@patch("youtube_utils.yt_dlp.YoutubeDL")
def test_get_video_info_bot_check_does_not_crash(mock_ydl_cls):
    mock_ydl = MagicMock()
    mock_ydl.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.side_effect = Exception("Sign in to confirm you're not a bot")
    mock_ydl_cls.return_value = mock_ydl

    result = yu.get_video_info("abc123")
    assert result["success"] is False
    assert result["error"] == yu.ERROR_BOT_CHECK


def test_video_info_and_download_are_independent(monkeypatch):
    """
    video_info = OK y download = NO DISPONIBLE debe ser un estado válido:
    ambas funciones son independientes entre sí.
    """
    monkeypatch.setattr(yu, "ffmpeg_is_available", lambda: True)

    def fake_run_download(target, opts):
        raise Exception("HTTP Error 403: Forbidden")

    monkeypatch.setattr(yu, "_run_download", fake_run_download)

    result = yu.download_media("abc123", "titulo", "video", "/tmp/does_not_matter")
    assert result["success"] is False
    assert result["error"] == yu.ERROR_FORBIDDEN


def test_download_video_does_not_retry_infinitely(monkeypatch, tmp_path):
    """No debe intentar más de 2 veces (selector primario + 1 respaldo)."""
    monkeypatch.setattr(yu, "ffmpeg_is_available", lambda: True)
    call_count = {"n": 0}

    def fake_run_download(target, opts):
        call_count["n"] += 1
        raise Exception("HTTP Error 403: Forbidden")

    monkeypatch.setattr(yu, "_run_download", fake_run_download)

    result = yu._download_video("https://youtube.com/watch?v=x", str(tmp_path / "out"), str(tmp_path))
    assert result["success"] is False
    assert call_count["n"] == 2  # exactamente 2 intentos, nunca un bucle infinito


def test_download_video_stops_immediately_on_bot_check(monkeypatch, tmp_path):
    """Un error no recuperable (bot-check) no debe generar un segundo intento."""
    monkeypatch.setattr(yu, "ffmpeg_is_available", lambda: True)
    call_count = {"n": 0}

    def fake_run_download(target, opts):
        call_count["n"] += 1
        raise Exception("Sign in to confirm you're not a bot")

    monkeypatch.setattr(yu, "_run_download", fake_run_download)

    result = yu._download_video("https://youtube.com/watch?v=x", str(tmp_path / "out"), str(tmp_path))
    assert result["success"] is False
    assert call_count["n"] == 1


def test_download_media_missing_ffmpeg(monkeypatch):
    monkeypatch.setattr(yu, "ffmpeg_is_available", lambda: False)
    result = yu.download_media("abc123", "titulo", "audio", "/tmp/does_not_matter")
    assert result["success"] is False
    assert result["error"] == yu.ERROR_FFMPEG_MISSING


@patch("youtube_utils.yt_dlp.YoutubeDL")
def test_search_youtube(mock_ydl_cls):
    mock_ydl = MagicMock()
    mock_ydl.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {
        "entries": [
            {
                "id": "vid1",
                "title": "Canción 1",
                "uploader": "Artista",
                "duration": 200,
                "view_count": 500,
                "thumbnail": "http://example.com/1.jpg",
            }
        ]
    }
    mock_ydl_cls.return_value = mock_ydl

    result = yu.search_youtube("test query")
    assert "videos" in result
    assert result["videos"][0]["id"] == "vid1"
