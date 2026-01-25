import os
import pytest

# Set environment variables for testing before importing the app
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SECRET_KEY'] = 'test-secret'

from backend.app import app, db


@pytest.fixture
def client():
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'
    })
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client

def test_app_initialization(client):
    """Basic smoke test to ensure the app starts and returns 200 on health check."""
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.get_json() == {'status': 'healthy', 'service': 'riparr'}

def test_index_page(client):
    """Ensure the index page is accessible."""
    response = client.get('/')
    assert response.status_code == 200

def test_api_requests_no_auth(client):
    """Ensure protected API routes return 401 or redirect to login."""
    response = client.get('/api/requests')
    # flask-login returns 401 for @login_required if no login_view is set, 
    # but app.py sets login_view = 'login', which might cause a redirect if hit via browser
    # or return 401 if it's an API request.
    assert response.status_code in [401, 302]
