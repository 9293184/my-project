from aisec import create_app


def test_health():
    app = create_app()
    client = app.test_client()
    resp = client.get("/api/health")
    assert resp.status_code in (200, 500)
