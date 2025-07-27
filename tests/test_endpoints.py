from fastapi.testclient import TestClient

from app.main import app, sup_util

client = TestClient(app)


def test_accepts_connections_ready():
    # Ensure no active WebSocket connection
    sup_util.websocket_connected = False

    response = client.get("/acceptsConnections")
    expected_status_code = 200
    assert response.status_code == expected_status_code
    assert response.json() == {"status": "ready"}
