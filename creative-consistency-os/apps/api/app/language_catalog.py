INSPIRATION_CATALOG = [
    {"key": "english_like", "label": "英語圏風", "category": "modern", "note": "語感の着想用。実在言語の再現を強制しません。"},
    {"key": "germanic_like", "label": "ゲルマン諸語風", "category": "family", "note": "子音群や複合語などの着想用。"},
    {"key": "nordic_like", "label": "北欧諸語風", "category": "family", "note": "北欧系の音感・命名の着想用。"},
    {"key": "romance_like", "label": "ロマンス諸語風", "category": "family", "note": "母音と語尾の流れの着想用。"},
    {"key": "slavic_like", "label": "スラヴ諸語風", "category": "family", "note": "子音・語尾・屈折感の着想用。"},
    {"key": "celtic_like", "label": "ケルト諸語風", "category": "family", "note": "音形・地名の着想用。"},
    {"key": "japanese_like", "label": "日本語風", "category": "modern", "note": "音節・名前・語形成の着想用。"},
    {"key": "sinitic_like", "label": "漢語圏風", "category": "family", "note": "音節・複合語・表記文化の着想用。"},
    {"key": "indic_like", "label": "インド諸語風", "category": "family", "note": "音感・語形成・名称体系の着想用。"},
    {"key": "ainu_inspired", "label": "アイヌ語着想", "category": "historical-cultural", "note": "敬意ある創作上の着想として扱い、実在言語そのものとは区別します。"},
    {"key": "old_japanese_inspired", "label": "上代日本語着想", "category": "historical", "note": "歴史言語の着想用。創作語と史実の語を区別します。"},
    {"key": "speculative_jomon", "label": "縄文イメージ創作", "category": "speculative", "note": "再構成言語とは扱わず、完全な創作音体系として扱います。"},
    {"key": "katakamuna_visual", "label": "カタカムナ視覚着想", "category": "fantasy", "note": "古代言語の史実認定ではなく、創作上の視覚・記号着想として扱います。"},
    {"key": "custom", "label": "完全カスタム", "category": "custom", "note": "自由入力の着想源を使用します。"},
]

LANGUAGE_ROLES = [
    {"key": "common", "label": "共通語"},
    {"key": "regional", "label": "地域語"},
    {"key": "trade", "label": "交易語"},
    {"key": "court", "label": "宮廷語"},
    {"key": "sacred", "label": "典礼・宗教語"},
    {"key": "scholarly", "label": "学術語"},
    {"key": "historical", "label": "古語・祖語"},
    {"key": "other", "label": "その他"},
]

WRITING_DIRECTIONS = [
    {"key": "ltr", "label": "左→右"},
    {"key": "rtl", "label": "右→左"},
    {"key": "vertical", "label": "縦書き"},
    {"key": "boustrophedon", "label": "牛耕式"},
    {"key": "custom", "label": "カスタム"},
]

DISPLAY_MODES = [
    {"key": "translated", "label": "読者向け翻訳を優先"},
    {"key": "original_with_reading", "label": "原語＋読みを併記"},
    {"key": "mixed", "label": "場面ごとに混在"},
    {"key": "custom", "label": "カスタム"},
]

EARTH_TERM_MODES = [
    {"key": "off", "label": "OFF"},
    {"key": "warn", "label": "警告"},
    {"key": "strict", "label": "厳格"},
]

REPLACEMENT_MODES = [
    {"key": "descriptive", "label": "一般説明語へ置換"},
    {"key": "world_origin", "label": "世界内の産地・固有名へ置換"},
    {"key": "both", "label": "両方提案"},
    {"key": "custom", "label": "カスタム"},
]

CONTACT_DOMAINS = [
    {"key": "trade", "label": "交易"},
    {"key": "religion", "label": "宗教"},
    {"key": "conquest", "label": "征服・支配"},
    {"key": "migration", "label": "移住"},
    {"key": "scholarship", "label": "学術"},
    {"key": "diplomacy", "label": "外交"},
    {"key": "popular_culture", "label": "大衆文化"},
    {"key": "technology", "label": "技術"},
]


def get_language_culture_catalog() -> dict[str, object]:
    return {
        "inspirations": INSPIRATION_CATALOG,
        "language_roles": LANGUAGE_ROLES,
        "writing_directions": WRITING_DIRECTIONS,
        "display_modes": DISPLAY_MODES,
        "earth_term_modes": EARTH_TERM_MODES,
        "replacement_modes": REPLACEMENT_MODES,
        "contact_domains": CONTACT_DOMAINS,
        "catalog_version": 1,
    }
