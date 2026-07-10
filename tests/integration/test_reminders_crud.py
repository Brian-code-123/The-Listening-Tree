"""
Mermaid sequence diagram:
sequenceDiagram
    participant Tester
    participant API
    participant DB
    Tester->>API: register/login and send reminder commands
    API->>DB: insert reminder row
    API->>DB: select reminder rows
    API->>DB: update reminder is_active flag
    API->>DB: delete reminder row
    API-->>Tester: CRUD confirmations
"""

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import run
from run import app


pytestmark = pytest.mark.integration


def _new_user_email() -> str:
    return f"integration_{uuid.uuid4().hex[:10]}@example.com"


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


def test_reminders_crud_flow():
    email = _new_user_email()
    password = 'TestPass123!'
    label = f'take medicine {uuid.uuid4().hex[:6]}'
    time = '09:30'

    with TestClient(app) as client:
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

        create_resp = client.post('/get_response', data={'msg': f'set reminder {label} {time}'})
        assert create_resp.status_code == 200
        assert 'Reminder set' in create_resp.json()['response']

        read_resp = client.get('/get_reminders')
        assert read_resp.status_code == 200
        reminders = read_resp.json()['reminders']
        assert any(r['label'] == label and r['active'] is True for r in reminders)

        update_resp = client.post('/deactivate_reminder', data={'label': label})
        assert update_resp.status_code == 200
        assert update_resp.json()['success'] is True

        updated_resp = client.get('/get_reminders')
        assert updated_resp.status_code == 200
        updated_reminders = updated_resp.json()['reminders']
        assert any(r['label'] == label and r['active'] is False for r in updated_reminders)

        delete_resp = client.post('/get_response', data={'msg': f'delete reminder {label}'})
        assert delete_resp.status_code == 200
        assert 'Deleted reminder' in delete_resp.json()['response']

        final_resp = client.get('/get_reminders')
        assert final_resp.status_code == 200
        final_reminders = final_resp.json()['reminders']
        assert not any(r['label'] == label for r in final_reminders)