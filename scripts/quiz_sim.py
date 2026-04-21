from fastapi.testclient import TestClient
import run


def _new_user_email():
    import uuid
    return f"test+{uuid.uuid4().hex[:8]}@example.com"


def sim_quiz():
    email = _new_user_email()
    password = "TestPass123!"
    with TestClient(run.app) as client:
        # register
        r = client.post('/register', data={'email': email, 'password': password, 'confirm_password': password})
        print('register:', r.status_code)
        # login
        r = client.post('/login', data={'email': email, 'password': password})
        print('login:', r.status_code)
        sess = r.cookies.get('lt_session') or client.cookies.get('lt_session')
        client.cookies.set('lt_session', sess)

        r = client.post('/get_response', data={'msg': 'play game'})
        print('start resp:', r.json())

        # answer first question correctly
        first_answer = 'paris'
        r = client.post('/get_response', data={'msg': first_answer})
        print('first answer resp:', r.json())

        # answer second question incorrectly
        second_wrong = 'yellow'
        r = client.post('/get_response', data={'msg': second_wrong})
        print('second (wrong) resp:', r.json())

        # answer third question (should be next question) with a sample answer
        r = client.post('/get_response', data={'msg': 'watermelon'})
        print('third answer resp:', r.json())

if __name__ == '__main__':
    sim_quiz()
