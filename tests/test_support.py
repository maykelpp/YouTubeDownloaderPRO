from models import SupportTicket


def test_support_ticket_created(app, client):
    resp = client.post(
        "/support/",
        data={
            "name": "Ana",
            "email": "ana@example.com",
            "issue_type": "Error de descarga",
            "title": "No descarga el audio",
            "description": "El botón de audio se queda cargando.",
            "related_url": "",
            "video_id": "",
            "error_message": "",
            "q_intent": "Descargar una canción",
            "q_what_happened": "No pasó nada",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        ticket = SupportTicket.query.filter_by(email="ana@example.com").first()
        assert ticket is not None
        assert ticket.status == "OPEN"
        assert ticket.issue_type == "Error de descarga"


def test_support_ticket_requires_fields(client):
    resp = client.post("/support/", data={"name": "", "email": "bad"}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"obligatorio" in resp.data.lower() or b"v\xc3\xa1lido" in resp.data.lower()
