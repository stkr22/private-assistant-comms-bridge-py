from fastapi.testclient import TestClient

from private_assistant_comms_bridge.main import app, sup_util

client = TestClient(app)


def test_accepts_connections_ready():
    # Ensure no active WebSocket connection
    sup_util.websocket_connected = False

    response = client.get("/acceptsConnections")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
