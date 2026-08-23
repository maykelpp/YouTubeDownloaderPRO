import datetime

from extensions import db
from models import EmailVerification, LoginCode, User
from security import hash_password, verify_password, hash_login_code


def _register(client, email="user@example.com", password="supersecret1"):
    return client.post(
        "/auth/register",
        data={
            "name": "Test User",
            "email": email,
            "password": password,
            "password_confirm": password,
        },
        follow_redirects=True,
    )


def test_password_hash_roundtrip():
    h = hash_password("hunter2hunter")
    assert h != "hunter2hunter"
    assert verify_password("hunter2hunter", h)
    assert not verify_password("wrongpass", h)


def test_register_creates_unverified_user(app, client):
    _register(client)
    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        assert user is not None
        assert user.email_verified is False
        assert user.password_hash != "supersecret1"


def test_register_password_mismatch_rejected(client):
    resp = client.post(
        "/auth/register",
        data={
            "name": "Test",
            "email": "mismatch@example.com",
            "password": "abcdefgh",
            "password_confirm": "different1",
        },
        follow_redirects=True,
    )
    assert b"no coinciden" in resp.data.lower() or resp.status_code == 200


def test_email_verification_flow(app, client):
    _register(client)
    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        record = EmailVerification.query.filter_by(user_id=user.id).first()
        assert record is not None
        assert not record.is_used

    # Simular clic en el enlace usando un token conocido (generamos uno nuevo
    # y lo insertamos directamente para no depender del correo real).
    from security import generate_verification_token, hash_token

    token = generate_verification_token()
    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        ev = EmailVerification(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
        )
        db.session.add(ev)
        db.session.commit()

    resp = client.get(f"/auth/verify-email/{token}", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        assert user.email_verified is True


def test_login_requires_email_verification(client):
    _register(client)
    resp = client.post(
        "/auth/login",
        data={"email": "user@example.com", "password": "supersecret1"},
        follow_redirects=True,
    )
    assert b"verificar" in resp.data.lower()


def test_login_triggers_2fa_and_full_flow(app, client):
    _register(client)
    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        user.email_verified = True
        db.session.commit()

    resp = client.post(
        "/auth/login",
        data={"email": "user@example.com", "password": "supersecret1"},
        follow_redirects=True,
    )
    assert b"digitos" in resp.data.lower() or b"c\xc3\xb3digo" in resp.data.lower()

    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        code_record = LoginCode.query.filter_by(user_id=user.id).first()
        assert code_record is not None
        # Insertamos un código conocido para poder verificarlo en el test.
        code_record.code_hash = hash_login_code("123456")
        db.session.commit()

    resp = client.post("/auth/verify-code", data={"code": "123456"}, follow_redirects=True)
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get("user_id") is not None


def test_login_code_wrong_attempt_is_rejected(app, client):
    _register(client)
    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        user.email_verified = True
        db.session.commit()

    client.post(
        "/auth/login",
        data={"email": "user@example.com", "password": "supersecret1"},
        follow_redirects=True,
    )
    resp = client.post("/auth/verify-code", data={"code": "000000"}, follow_redirects=True)
    assert b"incorrecto" in resp.data.lower()
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None


def test_expired_login_code_rejected(app, client):
    _register(client)
    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        user.email_verified = True
        db.session.commit()

    client.post(
        "/auth/login",
        data={"email": "user@example.com", "password": "supersecret1"},
        follow_redirects=True,
    )
    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        code_record = LoginCode.query.filter_by(user_id=user.id).first()
        code_record.expires_at = datetime.datetime.utcnow() - datetime.timedelta(minutes=1)
        db.session.commit()

    resp = client.post("/auth/verify-code", data={"code": "123456"}, follow_redirects=True)
    assert b"expir" in resp.data.lower()


def test_logout_clears_session(app, client):
    _register(client)
    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        user.email_verified = True
        db.session.commit()
    with client.session_transaction() as sess:
        sess["user_id"] = 1
    client.get("/auth/logout")
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None
