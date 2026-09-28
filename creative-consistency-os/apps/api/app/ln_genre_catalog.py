from __future__ import annotations

PACK_KEYS = ("noble_lady", "palace_harem", "romcom")
LN_STATUS = {"draft", "configured"}

DEFAULT_NOBLE_POLICY: dict[str, object] = {
    "rank_order": [
        "commoner",
        "knight",
        "baron",
        "viscount",
        "count",
        "marquess",
        "duke",
        "royal",
    ],
    "rank_title_map": {},
    "address_rules": [],
    "allow_multiple_active_engagements": False,
    "engagement_relation_types": ["engaged_to", "betrothed_to"],
}

DEFAULT_PALACE_POLICY: dict[str, object] = {
    "rank_order": [
        "attendant",
        "court_lady",
        "consort",
        "noble_consort",
        "imperial_consort",
        "empress",
    ],
    "restricted_areas": [],
    "information_rules": [],
    "ritual_sequences": [],
}

DEFAULT_ROMCOM_POLICY: dict[str, object] = {
    "stages": [
        "stranger",
        "acquaintance",
        "friend",
        "close_friend",
        "mutual_interest",
        "dating",
        "engaged",
    ],
    "max_stage_jump": 1,
    "allow_regression": True,
    "require_reason_for_large_jump": True,
    "unresolved_misunderstanding_severity": "info",
}


def default_ln_genre_config() -> dict[str, object]:
    return {
        "enabled_packs": {key: False for key in PACK_KEYS},
        "noble_lady": dict(DEFAULT_NOBLE_POLICY),
        "palace_harem": dict(DEFAULT_PALACE_POLICY),
        "romcom": dict(DEFAULT_ROMCOM_POLICY),
        "status": "draft",
    }


def catalog_payload() -> dict[str, object]:
    return {
        "packs": [
            {
                "key": "noble_lady",
                "label": "令嬢 / 貴族社会",
                "description": "爵位・家・婚約・呼称・礼法の整合性。",
            },
            {
                "key": "palace_harem",
                "label": "後宮 / 宮廷",
                "description": "位階・派閥・立入権限・情報権限・儀礼順序。",
            },
            {
                "key": "romcom",
                "label": "ラブコメ",
                "description": "関係段階・予定衝突・誤解ライフサイクル。",
            },
        ],
        "attribute_contracts": {
            "noble_character": {
                "entity_type": "character",
                "attributes.ln_noble": {
                    "house_entity_id": "optional Bible entity UUID",
                    "rank": "rank key",
                    "public_title": "optional title string",
                },
            },
            "noble_address_event": {
                "entity_type": "event",
                "attributes.ln_address": {
                    "speaker_entity_id": "Bible character UUID",
                    "target_entity_id": "Bible character UUID",
                    "used_address": "address string",
                },
            },
            "palace_character": {
                "entity_type": "character",
                "attributes.ln_palace": {
                    "rank": "rank key",
                    "faction_entity_id": "optional Bible faction/organization UUID",
                },
            },
            "palace_access_event": {
                "entity_type": "event",
                "attributes.ln_palace_access": {
                    "actor_entity_id": "Bible character UUID",
                    "place_entity_id": "Bible place UUID",
                },
            },
            "palace_information_event": {
                "entity_type": "event",
                "attributes.ln_information_access": {
                    "actor_entity_id": "Bible character UUID",
                    "fact_key": "information key",
                },
            },
            "palace_ritual_event": {
                "entity_type": "event",
                "attributes.ln_ritual": {
                    "ritual_key": "ritual identifier",
                    "step_key": "step identifier",
                    "sequence_index": "integer order",
                },
            },
            "romcom_transition_event": {
                "entity_type": "event",
                "attributes.ln_relationship_transition": {
                    "source_entity_id": "Bible character UUID",
                    "target_entity_id": "Bible character UUID",
                    "from_stage": "stage key",
                    "to_stage": "stage key",
                    "reason": "optional string",
                },
            },
            "romcom_schedule_event": {
                "entity_type": "event",
                "attributes.ln_schedule": {
                    "participant_ids": "Bible character UUID[]",
                    "day_key": "date/day bucket",
                    "start_minute": "integer minute",
                    "end_minute": "integer minute",
                },
            },
            "romcom_misunderstanding_event": {
                "entity_type": "event",
                "attributes.ln_misunderstanding": {
                    "misunderstanding_id": "stable id",
                    "action": "open or resolve",
                    "sequence_index": "integer order",
                },
            },
        },
        "defaults": default_ln_genre_config(),
        "pack_version": 1,
    }
