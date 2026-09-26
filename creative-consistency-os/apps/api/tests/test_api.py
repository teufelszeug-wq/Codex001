def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_list_and_get_project(client):
    created = client.post("/api/v1/projects", json={"title": "First World"})
    assert created.status_code == 201
    payload = created.json()
    assert payload["title"] == "First World"
    assert payload["schema_version"] == 1

    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = client.get(f"/api/v1/projects/{payload['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == payload["id"]


def test_rejects_blank_title(client):
    response = client.post("/api/v1/projects", json={"title": ""})
    assert response.status_code == 422
