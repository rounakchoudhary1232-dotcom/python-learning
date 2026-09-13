from uuid import uuid4
from fastapi.testclient import TestClient
import pytest
from app.main import app
from app.services.ai import get_ai_service

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

def register(client: TestClient, email: str) -> dict:
    return client.post('/api/v1/auth/register', json={'email': email, 'password': 'secure-password-123', 'display_name': 'Tester'}).json()

def unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}@example.com"

def test_authentication_and_user_scoped_memory(client: TestClient) -> None:
    register(client, unique_email('one'))
    assert client.post('/api/v1/memories', json={'content': 'I prefer concise summaries'}).status_code == 201
    assert len(client.get('/api/v1/memories').json()) == 1
    client.post('/api/v1/auth/logout')
    register(client, unique_email('two'))
    assert client.get('/api/v1/memories').json() == []

def test_missions_create_a_plan_and_pending_approval(client: TestClient) -> None:
    register(client, unique_email('mission'))
    response = client.post('/api/v1/missions', json={'title': 'Interview preparation', 'objective': 'Prepare for a Python interview'})
    assert response.status_code == 201
    assert len(response.json()['steps']) == 4
    assert response.json()['approval']['status'] == 'pending'

def test_security_analysis_requires_authorization(client: TestClient) -> None:
    register(client, unique_email('security'))
    response = client.post('/api/v1/security/analyze', json={'target': 'https://example.com', 'authorized': False})
    assert response.status_code == 403

def test_protected_endpoint_rejects_anonymous_client(client: TestClient) -> None:
    assert client.get('/api/v1/conversations').status_code == 401

def test_invalid_password_is_rejected(client: TestClient) -> None:
    email = unique_email('login')
    register(client, email)
    client.post('/api/v1/auth/logout')
    assert client.post('/api/v1/auth/login', json={'email': email, 'password': 'wrong-password'}).status_code == 401

def test_conversation_persists_messages_without_exposing_provider_secret(client: TestClient) -> None:
    class StubProvider:
        def respond(self, messages):
            assert messages[-1].content == 'Hello ULTRON'
            return 'Hello from the configured provider.'

    app.dependency_overrides[get_ai_service] = lambda: StubProvider()
    try:
        assert client.post('/api/v1/auth/register', json={'email': unique_email('chat'), 'password': 'secure-password-123', 'display_name': 'Chat User'}).status_code == 201
        conversation = client.post('/api/v1/conversations', json={'title': 'Provider test'}).json()
        response = client.post(f"/api/v1/conversations/{conversation['id']}/messages", json={'content': 'Hello ULTRON'})
        assert response.status_code == 201
        assert response.json()['assistant_message']['content'] == 'Hello from the configured provider.'
        assert 'key' not in str(response.json()).lower()
        history = client.get(f"/api/v1/conversations/{conversation['id']}/messages").json()
        assert [message['role'] for message in history] == ['user', 'assistant']
    finally:
        app.dependency_overrides.clear()
