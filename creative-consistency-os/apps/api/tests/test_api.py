def create_project(client, title="First World"):
    response = client.post("/api/v1/projects", json={"title": title})
    assert response.status_code == 201
    return response.json()


def world_builder_payload():
    return {
        "setup_mode": "guided",
        "selected_genres": ["isekai", "noble_lady", "mystery"],
        "genre_weights": {"isekai": 90, "noble_lady": 70, "mystery": 35},
        "custom_genres": [{"name": "旅と群像劇", "weight": 55}],
        "section_modes": {
            "geography": "auto",
            "society": "manual",
            "language": "auto",
            "culture": "manual",
        },
        "section_notes": {
            "geography": "大陸横断の旅を重視。",
            "culture": "地域差を強く出す。",
        },
        "status": "configured",
    }


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_list_and_get_project(client):
    payload = create_project(client)
    assert payload["title"] == "First World"
    assert payload["schema_version"] == 2

    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = client.get(f"/api/v1/projects/{payload['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == payload["id"]


def test_rejects_blank_title(client):
    response = client.post("/api/v1/projects", json={"title": ""})
    assert response.status_code == 422


def test_world_builder_catalog_contains_all_initial_routes(client):
    response = client.get("/api/v1/catalog/world-builder")
    assert response.status_code == 200
    payload = response.json()
    genre_keys = {item["key"] for item in payload["genres"]}
    assert {"isekai", "noble_lady", "palace", "romcom", "mystery", "sf", "undecided"} <= genre_keys
    assert {item["key"] for item in payload["setup_modes"]} == {"quick", "guided", "full", "blank", "import"}
    assert {"language", "culture", "geography"} <= {item["key"] for item in payload["world_dna_sections"]}


def test_save_and_get_world_builder_profile(client):
    project = create_project(client)
    response = client.put(f"/api/v1/projects/{project['id']}/world-builder", json=world_builder_payload())
    assert response.status_code == 200
    profile = response.json()
    assert profile["setup_mode"] == "guided"
    assert profile["selected_genres"] == ["isekai", "noble_lady", "mystery"]
    assert profile["section_modes"]["society"] == "manual"
    assert profile["section_modes"]["economy"] == "auto"
    assert profile["recommendations"]["society"]["priority"] == "high"

    fetched = client.get(f"/api/v1/projects/{project['id']}/world-builder")
    assert fetched.status_code == 200
    assert fetched.json()["custom_genres"][0]["name"] == "旅と群像劇"


def test_world_builder_profile_can_be_updated(client):
    project = create_project(client)
    first = world_builder_payload()
    assert client.put(f"/api/v1/projects/{project['id']}/world-builder", json=first).status_code == 200

    second = world_builder_payload()
    second["setup_mode"] = "blank"
    second["section_modes"] = {"geography": "manual"}
    updated = client.put(f"/api/v1/projects/{project['id']}/world-builder", json=second)
    assert updated.status_code == 200
    assert updated.json()["section_modes"]["geography"] == "manual"
    assert updated.json()["section_modes"]["society"] == "skip"


def test_rejects_unknown_genre_and_bad_weight_mapping(client):
    project = create_project(client)

    bad_genre = world_builder_payload()
    bad_genre["selected_genres"] = ["isekai", "unknown"]
    bad_genre["genre_weights"] = {"isekai": 50, "unknown": 50}
    response = client.put(f"/api/v1/projects/{project['id']}/world-builder", json=bad_genre)
    assert response.status_code == 422

    bad_weights = world_builder_payload()
    bad_weights["genre_weights"] = {"isekai": 90}
    response = client.put(f"/api/v1/projects/{project['id']}/world-builder", json=bad_weights)
    assert response.status_code == 422


def test_import_mode_requires_format(client):
    project = create_project(client)
    payload = world_builder_payload()
    payload["setup_mode"] = "import"
    payload["import_format"] = None
    response = client.put(f"/api/v1/projects/{project['id']}/world-builder", json=payload)
    assert response.status_code == 422

    payload["import_format"] = "docx"
    payload["import_notes"] = "既存の設定資料から開始する。"
    response = client.put(f"/api/v1/projects/{project['id']}/world-builder", json=payload)
    assert response.status_code == 200
    assert response.json()["import_format"] == "docx"
