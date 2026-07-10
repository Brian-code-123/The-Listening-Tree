"""
Mermaid sequence diagram:
sequenceDiagram
    participant Tester
    participant API
    participant STT as Speech Layer
    participant Game as Quiz Engine
    Tester->>API: register/login user session
    Tester->>API: POST /transcribe with WAV payload
    API->>STT: recognize_google(audio, lang)
    STT-->>API: transcription text
    API-->>Tester: transcribe JSON
    Tester->>API: POST /get_response with play game/answer
    API->>Game: update game state and score
    API-->>Tester: game progress responses
"""

import types
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import run
from run import app


pytestmark = pytest.mark.integration


def _new_user_email() -> str:
    return f"coreext_{uuid.uuid4().hex[:10]}@example.com"


def _seed_verification_code(email: str, code: str = "123456") -> str:
    conn = run.get_db()
    c = conn.cursor()
    ts = datetime.now()
    expires_at = (ts + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
    run.db_execute(
        c,
        "INSERT INTO email_verifications (email, code, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (email, code, expires_at, ts.strftime('%Y-%m-%d %H:%M:%S')),
    )
    conn.commit()
    conn.close()
    return code


def _login_user(client: TestClient, email: str, password: str) -> None:
    code = _seed_verification_code(email)
    register_resp = client.post(
        '/register',
        data={
            'email': email,
            'password': password,
            'confirm_password': password,
            'verification_code': code,
        },
        follow_redirects=False,
    )
    assert register_resp.status_code == 303

    login_resp = client.post(
        '/login',
        data={'email': email, 'password': password},
        follow_redirects=False,
    )
    assert login_resp.status_code == 303

    session_cookie = login_resp.cookies.get('lt_session') or client.cookies.get('lt_session')
    assert session_cookie
    client.cookies.set('lt_session', session_cookie)


def test_voice_transcribe_endpoint_with_mocked_stt(monkeypatch):
    class FakeAudioFile:
        def __init__(self, _stream):
            pass

        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeRecognizer:
        def record(self, _source):
            return b'audio-bytes'

        def recognize_google(self, _audio_data, language='en-US'):
            assert language in ('en-US', 'zh-HK')
            return 'hello companion'

    fake_sr = types.SimpleNamespace(
        Recognizer=FakeRecognizer,
        AudioFile=FakeAudioFile,
        UnknownValueError=Exception,
        RequestError=Exception,
    )
    monkeypatch.setattr(run, 'sr', fake_sr)

    email = _new_user_email()
    password = 'TestPass123!'

    with TestClient(app) as client:
        _login_user(client, email, password)

        resp = client.post(
            '/transcribe',
            files={'audio': ('voice.wav', b'RIFFFAKEWAV', 'audio/wav')},
            data={'lang': 'en-US'},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload['text'] == 'hello companion'
        assert payload['engine'] == 'google-web-speech'


def test_cognitive_game_command_flow():
    email = _new_user_email()
    password = 'TestPass123!'

    with TestClient(app) as client:
        _login_user(client, email, password)

        start_resp = client.post('/get_response', data={'msg': 'play game'})
        assert start_resp.status_code == 200
        assert "Let's play" in start_resp.json()['response']

        answer_resp = client.post('/get_response', data={'msg': 'answer paris'})
        assert answer_resp.status_code == 200
        assert 'Correct! Score: 1' in answer_resp.json()['response']

        exit_resp = client.post('/get_response', data={'msg': 'exit game'})
        assert exit_resp.status_code == 200
        assert 'Game stopped' in exit_resp.json()['response']


def test_ai_chat_response_with_mocked_model(monkeypatch):
    async def fake_call_ai(user_input: str, user_id: int, lang: str = 'en'):
        assert user_input
        assert user_id
        assert lang in ('en', 'zh-HK')
        return 'Mock AI response for testing.'

    monkeypatch.setattr(run, 'call_ai', fake_call_ai)

    email = _new_user_email()
    password = 'TestPass123!'

    with TestClient(app) as client:
        _login_user(client, email, password)
        chat_resp = client.post('/get_response', data={'msg': 'tell me a warm story'})

        assert chat_resp.status_code == 200
        assert chat_resp.json()['response'] == 'Mock AI response for testing.'
