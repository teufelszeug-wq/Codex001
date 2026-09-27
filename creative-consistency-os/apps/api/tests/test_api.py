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


def language_culture_payload():
    return {
        "languages": [
            {
                "id": "lang-north",
                "name": "北方共通語",
                "role": "common",
                "regions": ["北部王国", "交易都市"],
                "inspirations": [
                    {"source": "nordic_like", "weight": 60},
                    {"source": "custom:霧の多い沿岸文化", "weight": 40},
                ],
                "parent_language_id": None,
                "era_label": "現代語",
                "phonology": {
                    "onsets": ["k", "v", "r", "s", "h"],
                    "nuclei": ["a", "e", "i", "o"],
                    "codas": ["", "n", "r"],
                    "forbidden_sequences": ["kkk"],
                    "syllables_min": 2,
                    "syllables_max": 3,
                    "separator": "",
                    "capitalize": True,
                },
                "naming": {
                    "prefixes": {"person": [""], "place": [""], "item": [""], "title": ["Ar"]},
                    "suffixes": {"person": ["a", "en"], "place": ["vik", "heim"], "item": [""], "title": ["ar"]},
                    "notes": "人名は短め。",
                },
                "script": {"name": "北方文字", "type": "alphabetic", "direction": "ltr", "notes": ""},
                "notes": "交易で広く通じる。",
            },
            {
                "id": "lang-old",
                "name": "古層典礼語",
                "role": "sacred",
                "regions": ["神殿"],
                "inspirations": [{"source": "old_japanese_inspired", "weight": 35}, {"source": "custom", "weight": 65}],
                "parent_language_id": None,
                "phonology": {
                    "onsets": ["m", "n", "y"],
                    "nuclei": ["a", "i", "u"],
                    "codas": [""],
                    "syllables_min": 2,
                    "syllables_max": 4,
                },
                "naming": {"prefixes": {}, "suffixes": {}, "notes": ""},
                "script": {"name": "神殿刻字", "type": "syllabic", "direction": "vertical", "notes": ""},
                "notes": "",
            },
        ],
        "cultures": [
            {
                "id": "culture-north",
                "name": "北方沿岸文化",
                "regions": ["北部王国"],
                "language_ids": ["lang-north", "lang-old"],
                "tags": ["海運", "霧", "交易"],
                "institutions": ["港湾評議会"],
                "etiquette": "初対面では家名より港名を先に名乗る。",
                "taboos": ["航海前の火の貸し借り"],
                "festivals": ["冬至灯祭"],
                "material_culture": "木工と織物を重視。",
                "notes": "",
            }
        ],
        "contacts": [
            {
                "from_language_id": "lang-old",
                "to_language_id": "lang-north",
                "intensity": 55,
                "domains": ["religion", "scholarship"],
                "borrowing_policy": "adapt",
                "notes": "宗教語彙が借用される。",
            }
        ],
        "root_lexicon": [
            {
                "id": "root-mist",
                "language_id": "lang-north",
                "form": "hev",
                "meaning": "霧",
                "tags": ["weather", "place-name"],
                "origin": "native",
                "notes": "",
            }
        ],
        "display_policy": {
            "mode": "original_with_reading",
            "first_mention": "original_with_reading",
            "later_mentions": "translated",
            "ruby_policy": "project_choice",
            "notes": "",
        },
        "earth_term_policy": {
            "mode": "strict",
            "replacement_mode": "world_origin",
            "allowed_contexts": ["転生者の内心"],
            "notes": "異世界の地の文では地球由来固有名を避ける。",
        },
        "common_language_id": "lang-north",
        "status": "configured",
    }


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_list_and_get_project(client):
    payload = create_project(client)
    assert payload["title"] == "First World"
    assert payload["schema_version"] == 5

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


def test_language_culture_catalog_has_open_and_sensitive_inspiration_routes(client):
    response = client.get("/api/v1/catalog/language-culture")
    assert response.status_code == 200
    payload = response.json()
    inspiration_keys = {item["key"] for item in payload["inspirations"]}
    assert {"nordic_like", "ainu_inspired", "old_japanese_inspired", "speculative_jomon", "katakamuna_visual", "custom"} <= inspiration_keys
    assert {item["key"] for item in payload["earth_term_modes"]} == {"off", "warn", "strict"}


def test_save_get_language_culture_config_and_preview_names(client):
    project = create_project(client)
    payload = language_culture_payload()

    saved = client.put(f"/api/v1/projects/{project['id']}/language-culture", json=payload)
    assert saved.status_code == 200
    config = saved.json()
    assert config["common_language_id"] == "lang-north"
    assert config["languages"][0]["inspirations"][0]["source"] == "nordic_like"
    assert config["earth_term_policy"]["mode"] == "strict"
    assert config["cultures"][0]["language_ids"] == ["lang-north", "lang-old"]

    fetched = client.get(f"/api/v1/projects/{project['id']}/language-culture")
    assert fetched.status_code == 200
    assert fetched.json()["root_lexicon"][0]["meaning"] == "霧"

    first = client.post(
        f"/api/v1/projects/{project['id']}/language-culture/languages/lang-north/preview-names",
        json={"kind": "place", "count": 8, "seed": 42},
    )
    second = client.post(
        f"/api/v1/projects/{project['id']}/language-culture/languages/lang-north/preview-names",
        json={"kind": "place", "count": 8, "seed": 42},
    )
    assert first.status_code == 200
    assert first.json()["names"] == second.json()["names"]
    assert len(first.json()["names"]) == 8
    assert all(name.endswith(("vik", "heim")) for name in first.json()["names"])


def test_language_builder_rejects_unknown_references(client):
    project = create_project(client)
    payload = language_culture_payload()
    payload["cultures"][0]["language_ids"] = ["missing-language"]
    response = client.put(f"/api/v1/projects/{project['id']}/language-culture", json=payload)
    assert response.status_code == 422

    payload = language_culture_payload()
    payload["common_language_id"] = "missing-language"
    response = client.put(f"/api/v1/projects/{project['id']}/language-culture", json=payload)
    assert response.status_code == 422


def test_language_builder_rejects_invalid_parent_and_policy(client):
    project = create_project(client)
    payload = language_culture_payload()
    payload["languages"][0]["parent_language_id"] = "missing-language"
    response = client.put(f"/api/v1/projects/{project['id']}/language-culture", json=payload)
    assert response.status_code == 422

    payload = language_culture_payload()
    payload["earth_term_policy"]["mode"] = "auto-rewrite-without-approval"
    response = client.put(f"/api/v1/projects/{project['id']}/language-culture", json=payload)
    assert response.status_code == 422



def test_story_bible_requires_explicit_canon_transition(client):
    project = create_project(client)
    created = client.post(
        f"/api/v1/projects/{project['id']}/bible",
        json={
            "entity_type": "character",
            "canonical_name": "イレーネ",
            "summary": "第三区処理課に所属する令嬢。",
            "attributes": {"hair": "銀髪"},
            "canon_state": "INFERENCE",
            "source_type": "AI_EXTRACTION",
            "source_ref": "chapter-1",
        },
    )
    assert created.status_code == 201
    entity = created.json()
    assert entity["canon_state"] == "INFERENCE"

    direct = client.put(
        f"/api/v1/projects/{project['id']}/bible/{entity['id']}",
        json={"canon_state": "CANON"},
    )
    assert direct.status_code == 422

    promoted = client.post(
        f"/api/v1/projects/{project['id']}/bible/{entity['id']}/canon",
        json={"target_state": "CANON", "reason": "作者が設定資料と照合して承認"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["canon_state"] == "CANON"

    listed = client.get(f"/api/v1/projects/{project['id']}/bible")
    assert listed.status_code == 200
    assert listed.json()[0]["canonical_name"] == "イレーネ"


def test_writing_room_creates_revisions_only_when_text_changes(client):
    project = create_project(client)
    created = client.post(
        f"/api/v1/projects/{project['id']}/manuscripts",
        json={"title": "第一章", "content": "白い朝だった。", "order_index": 1, "status": "draft"},
    )
    assert created.status_code == 201
    document = created.json()
    assert document["current_revision"] == 1

    changed = client.put(
        f"/api/v1/projects/{project['id']}/manuscripts/{document['id']}",
        json={
            "title": "第一章",
            "content": "白い朝だった。鐘が鳴った。",
            "order_index": 1,
            "status": "draft",
            "reason": "autosave",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["current_revision"] == 2

    unchanged = client.put(
        f"/api/v1/projects/{project['id']}/manuscripts/{document['id']}",
        json={
            "title": "第一章",
            "content": "白い朝だった。鐘が鳴った。",
            "order_index": 1,
            "status": "draft",
            "reason": "autosave",
        },
    )
    assert unchanged.status_code == 200
    assert unchanged.json()["current_revision"] == 2

    revisions = client.get(
        f"/api/v1/projects/{project['id']}/manuscripts/{document['id']}/revisions"
    )
    assert revisions.status_code == 200
    assert [item["revision_no"] for item in revisions.json()] == [2, 1]

    old = revisions.json()[-1]
    restored = client.post(
        f"/api/v1/projects/{project['id']}/manuscripts/{document['id']}/revisions/{old['id']}/restore"
    )
    assert restored.status_code == 200
    assert restored.json()["content"] == "白い朝だった。"
    assert restored.json()["current_revision"] == 3


def test_timeline_requires_existing_bible_participants(client):
    project = create_project(client)
    character = client.post(
        f"/api/v1/projects/{project['id']}/bible",
        json={
            "entity_type": "character",
            "canonical_name": "リナ",
            "summary": "",
            "attributes": {},
            "canon_state": "PLAN",
            "source_type": "AUTHOR",
        },
    ).json()

    created = client.post(
        f"/api/v1/projects/{project['id']}/timeline",
        json={
            "title": "王都到着",
            "start_label": "第3日",
            "sort_key": 30,
            "description": "リナが王都へ到着する。",
            "participant_ids": [character["id"]],
            "canon_state": "PLAN",
            "source_type": "AUTHOR",
        },
    )
    assert created.status_code == 201
    assert created.json()["participant_ids"] == [character["id"]]

    missing = client.post(
        f"/api/v1/projects/{project['id']}/timeline",
        json={
            "title": "不正参照",
            "participant_ids": ["11111111-1111-1111-1111-111111111111"],
            "canon_state": "PLAN",
            "source_type": "AUTHOR",
        },
    )
    assert missing.status_code == 422



def test_entity_intelligence_alias_scan_and_candidate_promotion(client):
    project = create_project(client)
    heroine = client.post(
        f"/api/v1/projects/{project['id']}/bible",
        json={
            "entity_type": "character",
            "canonical_name": "イレーネ",
            "summary": "主人公",
            "attributes": {},
            "canon_state": "CANON",
            "source_type": "AUTHOR",
        },
    ).json()

    alias = client.post(
        f"/api/v1/projects/{project['id']}/bible/{heroine['id']}/aliases",
        json={"alias": "イレーネ嬢", "alias_type": "title"},
    )
    assert alias.status_code == 201
    assert alias.json()["normalized_alias"] == "イレーネ嬢"

    document = client.post(
        f"/api/v1/projects/{project['id']}/manuscripts",
        json={
            "title": "第一章",
            "content": "イレーネはフヴィートバウグルへ向かった。人々はイレーネ嬢と呼んだ。",
            "order_index": 1,
            "status": "draft",
        },
    ).json()

    refreshed = client.post(
        f"/api/v1/projects/{project['id']}/manuscripts/{document['id']}/mentions/refresh",
        json={"include_candidates": True},
    )
    assert refreshed.status_code == 200
    mentions = refreshed.json()
    assert any(item["mention_text"] == "イレーネ" and item["entity_id"] == heroine["id"] for item in mentions)
    assert any(item["mention_text"] == "イレーネ嬢" and item["entity_id"] == heroine["id"] for item in mentions)

    unresolved = next(item for item in mentions if item["mention_text"] == "フヴィートバウグル")
    assert unresolved["resolver_state"] == "unresolved"

    created = client.post(
        f"/api/v1/projects/{project['id']}/mentions/{unresolved['id']}/create-entity",
        json={"entity_type": "place", "summary": "本文から抽出した候補。"},
    )
    assert created.status_code == 201
    assert created.json()["canonical_name"] == "フヴィートバウグル"
    assert created.json()["canon_state"] == "INFERENCE"
    assert created.json()["source_type"] == "MANUSCRIPT"

    linked = client.get(
        f"/api/v1/projects/{project['id']}/manuscripts/{document['id']}/mentions"
    )
    resolved_candidate = next(item for item in linked.json() if item["id"] == unresolved["id"])
    assert resolved_candidate["resolver_state"] == "resolved"
    assert resolved_candidate["entity_id"] == created.json()["id"]


def test_entity_reference_resolution_can_report_ambiguity(client):
    project = create_project(client)
    entities = []
    for name in ("第一王女", "第二王女"):
        entities.append(
            client.post(
                f"/api/v1/projects/{project['id']}/bible",
                json={
                    "entity_type": "character",
                    "canonical_name": name,
                    "summary": "",
                    "attributes": {},
                    "canon_state": "CANON",
                    "source_type": "AUTHOR",
                },
            ).json()
        )

    for entity in entities:
        response = client.post(
            f"/api/v1/projects/{project['id']}/bible/{entity['id']}/aliases",
            json={"alias": "姫", "alias_type": "title"},
        )
        assert response.status_code == 201

    resolved = client.get(
        f"/api/v1/projects/{project['id']}/entity-intelligence/resolve",
        params={"text": "姫"},
    )
    assert resolved.status_code == 200
    payload = resolved.json()
    assert payload["resolver_state"] == "ambiguous"
    assert set(payload["candidate_ids"]) == {item["id"] for item in entities}


def test_entity_relations_validate_graph_edges(client):
    project = create_project(client)
    source = client.post(
        f"/api/v1/projects/{project['id']}/bible",
        json={
            "entity_type": "character",
            "canonical_name": "主人公",
            "summary": "",
            "attributes": {},
            "canon_state": "CANON",
            "source_type": "AUTHOR",
        },
    ).json()
    target = client.post(
        f"/api/v1/projects/{project['id']}/bible",
        json={
            "entity_type": "organization",
            "canonical_name": "魔法学院",
            "summary": "",
            "attributes": {},
            "canon_state": "CANON",
            "source_type": "AUTHOR",
        },
    ).json()

    relation = client.post(
        f"/api/v1/projects/{project['id']}/relations",
        json={
            "source_entity_id": source["id"],
            "target_entity_id": target["id"],
            "relation_type": "member_of",
            "label": "在籍",
            "canon_state": "PLAN",
            "source_type": "AUTHOR",
            "attributes": {"since": "第一章"},
        },
    )
    assert relation.status_code == 201
    assert relation.json()["relation_type"] == "member_of"

    listed = client.get(f"/api/v1/projects/{project['id']}/relations")
    assert listed.status_code == 200
    assert listed.json()[0]["target_entity_id"] == target["id"]

    self_edge = client.post(
        f"/api/v1/projects/{project['id']}/relations",
        json={
            "source_entity_id": source["id"],
            "target_entity_id": source["id"],
            "relation_type": "friend",
            "canon_state": "PLAN",
            "source_type": "AUTHOR",
        },
    )
    assert self_edge.status_code == 422
