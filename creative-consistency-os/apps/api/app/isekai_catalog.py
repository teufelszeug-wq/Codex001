from __future__ import annotations

ISEKAI_CATEGORIES: dict[str, dict[str, str]] = {
    "geo_origin_food_drink": {
        "label": "地球の地名・産地由来",
        "description": "地球上の地名・産地・都市名をそのまま含む食品・飲料名。",
    },
    "earth_culture_food": {
        "label": "地球文化由来の料理名",
        "description": "地球上の歴史・地域・人名・料理文化に強く結びつく名称。",
    },
    "modern_technology": {
        "label": "現代技術語",
        "description": "スマートフォン、インターネット等の現代地球技術を前提にする語。",
    },
    "modern_institution": {
        "label": "現代制度・生活語",
        "description": "現代社会の制度・店舗・職業文化を前提にする語。",
    },
    "earth_currency": {
        "label": "地球通貨",
        "description": "円・ドル等、現実世界の通貨単位。",
    },
    "modern_measurement": {
        "label": "現代計量体系",
        "description": "メートル法・摂氏など、世界設定上の採否を意識したい計量語。",
    },
}

EARTH_TERM_CATALOG: list[dict[str, str]] = [
    {"term": "じゃがいも", "category": "geo_origin_food_drink", "concept_key": "tuber_potato", "generic_replacement": "芋"},
    {"term": "ジャガイモ", "category": "geo_origin_food_drink", "concept_key": "tuber_potato", "generic_replacement": "芋"},
    {"term": "ウインナー", "category": "geo_origin_food_drink", "concept_key": "sausage", "generic_replacement": "細い腸詰め"},
    {"term": "フランクフルト", "category": "geo_origin_food_drink", "concept_key": "sausage", "generic_replacement": "太い腸詰め"},
    {"term": "ハンバーグ", "category": "geo_origin_food_drink", "concept_key": "minced_meat_patty", "generic_replacement": "挽肉焼き"},
    {"term": "ダージリン", "category": "geo_origin_food_drink", "concept_key": "highland_black_tea", "generic_replacement": "高地産紅茶"},
    {"term": "セイロン", "category": "geo_origin_food_drink", "concept_key": "island_black_tea", "generic_replacement": "島産紅茶"},
    {"term": "アッサム", "category": "geo_origin_food_drink", "concept_key": "strong_black_tea", "generic_replacement": "濃厚紅茶"},
    {"term": "キリマンジャロ", "category": "geo_origin_food_drink", "concept_key": "highland_coffee", "generic_replacement": "高地産珈琲"},
    {"term": "モカ", "category": "geo_origin_food_drink", "concept_key": "port_coffee", "generic_replacement": "香りの強い珈琲"},
    {"term": "マンデリン", "category": "geo_origin_food_drink", "concept_key": "earthy_coffee", "generic_replacement": "深煎り珈琲"},
    {"term": "シャンパン", "category": "geo_origin_food_drink", "concept_key": "sparkling_wine", "generic_replacement": "発泡葡萄酒"},
    {"term": "コニャック", "category": "geo_origin_food_drink", "concept_key": "grape_brandy", "generic_replacement": "葡萄蒸留酒"},
    {"term": "ボルドー", "category": "geo_origin_food_drink", "concept_key": "red_wine", "generic_replacement": "赤葡萄酒"},
    {"term": "ブルゴーニュ", "category": "geo_origin_food_drink", "concept_key": "wine", "generic_replacement": "葡萄酒"},
    {"term": "サンドイッチ", "category": "earth_culture_food", "concept_key": "filled_bread", "generic_replacement": "具挟みパン"},
    {"term": "ナポリタン", "category": "earth_culture_food", "concept_key": "tomato_pasta", "generic_replacement": "トマト炒め麺"},
    {"term": "カレー", "category": "earth_culture_food", "concept_key": "spiced_stew", "generic_replacement": "香辛料煮込み"},
    {"term": "スマホ", "category": "modern_technology", "concept_key": "smartphone", "generic_replacement": "携帯通信端末"},
    {"term": "スマートフォン", "category": "modern_technology", "concept_key": "smartphone", "generic_replacement": "携帯通信端末"},
    {"term": "インターネット", "category": "modern_technology", "concept_key": "internet", "generic_replacement": "遠隔情報網"},
    {"term": "SNS", "category": "modern_technology", "concept_key": "social_network", "generic_replacement": "交流通信網"},
    {"term": "コンビニ", "category": "modern_institution", "concept_key": "convenience_store", "generic_replacement": "雑貨店"},
    {"term": "サラリーマン", "category": "modern_institution", "concept_key": "salaried_worker", "generic_replacement": "勤め人"},
    {"term": "株式会社", "category": "modern_institution", "concept_key": "joint_stock_company", "generic_replacement": "商会"},
    {"term": "ドル", "category": "earth_currency", "concept_key": "currency", "generic_replacement": "貨幣"},
    {"term": "円", "category": "earth_currency", "concept_key": "currency", "generic_replacement": "貨幣"},
    {"term": "キロメートル", "category": "modern_measurement", "concept_key": "distance_unit", "generic_replacement": "長距離単位"},
    {"term": "メートル", "category": "modern_measurement", "concept_key": "distance_unit", "generic_replacement": "長さ単位"},
    {"term": "キログラム", "category": "modern_measurement", "concept_key": "mass_unit", "generic_replacement": "重量単位"},
    {"term": "摂氏", "category": "modern_measurement", "concept_key": "temperature_scale", "generic_replacement": "温度尺度"},
]

STRICTNESS_TO_SEVERITY = {
    "soft": "hint",
    "standard": "warning",
    "strict": "error",
}

ISEKAI_STRICTNESS = ["soft", "standard", "strict"]
ISEKAI_STATUS = {"draft", "configured"}


def default_isekai_config() -> dict[str, object]:
    return {
        "enabled": False,
        "strictness": "standard",
        "enabled_categories": {key: True for key in ISEKAI_CATEGORIES},
        "allow_terms": [],
        "custom_terms": [],
        "replacements": [],
        "require_world_mapping": False,
        "travel_routes": [],
        "magic_policy": {
            "enabled": False,
            "require_cost": True,
            "allowed_cost_types": [],
            "costless_tiers": [],
        },
        "economy_policy": {
            "enabled": False,
            "currencies": [],
            "price_bands": [],
        },
        "healing_policy": {
            "enabled": False,
            "resurrection_allowed": False,
            "limb_regrowth_allowed": False,
        },
        "status": "draft",
    }
