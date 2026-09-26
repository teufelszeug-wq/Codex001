from app.domain import SectionMode, SetupMode


GENRE_CATALOG = [
    {"key": "isekai", "label": "異世界", "description": "転生・転移・冒険・異世界社会。"},
    {"key": "noble_lady", "label": "令嬢", "description": "爵位・婚約・社交・家格を重視。"},
    {"key": "palace", "label": "後宮", "description": "宮廷・位階・派閥・儀礼を重視。"},
    {"key": "romcom", "label": "ラブコメ", "description": "恋愛・日常・学園・すれ違い。"},
    {"key": "mystery", "label": "ミステリー / 推理", "description": "時系列・証拠・知識状態・伏線を重視。"},
    {"key": "sf", "label": "SF", "description": "科学仮定・技術・因果・時間を重視。"},
    {"key": "fantasy", "label": "ファンタジー", "description": "魔法・神話・世界文化を広く扱う。"},
    {"key": "romance", "label": "恋愛", "description": "人物関係と感情変化を中心に扱う。"},
    {"key": "contemporary", "label": "現代", "description": "現代社会・生活・制度を中心に扱う。"},
    {"key": "horror", "label": "ホラー", "description": "恐怖・禁忌・怪異・閉鎖環境など。"},
    {"key": "historical", "label": "歴史", "description": "時代制度・文化・技術・暦を重視。"},
    {"key": "adventure", "label": "冒険", "description": "旅程・地理・探索・目的達成を重視。"},
    {"key": "undecided", "label": "ジャンル未定", "description": "あとからジャンルを決めたい場合。"},
]

SETUP_MODES = [
    {"key": SetupMode.QUICK.value, "label": "クイック", "description": "最低限の設定から早く始める。"},
    {"key": SetupMode.GUIDED.value, "label": "ガイド付き", "description": "質問に答えながら段階的に構築する。"},
    {"key": SetupMode.FULL.value, "label": "フル編集", "description": "全項目を自分で調整する。"},
    {"key": SetupMode.BLANK.value, "label": "空白から開始", "description": "自動生成を使わず空の世界から始める。"},
    {"key": SetupMode.IMPORT.value, "label": "既存設定を取り込む", "description": "既存原稿・設定資料を起点にする。"},
]

WORLD_DNA_SECTIONS = [
    {"key": "geography", "label": "地理", "description": "大陸・地域・都市・移動距離。"},
    {"key": "society", "label": "社会", "description": "政治・身分・法・組織・権限。"},
    {"key": "economy", "label": "経済", "description": "通貨・物価・交易・資源。"},
    {"key": "technology", "label": "技術", "description": "文明水準・交通・通信・産業。"},
    {"key": "magic", "label": "魔法 / 超常", "description": "魔法体系・代償・制約・普及度。"},
    {"key": "religion", "label": "宗教 / 神話", "description": "信仰・神話・儀礼・禁忌。"},
    {"key": "calendar", "label": "暦 / 時間", "description": "暦・季節・祭日・時刻体系。"},
    {"key": "language", "label": "言語", "description": "M2では方針とメモを保存。詳細設計はM2.5。", "detail_milestone": "M2.5"},
    {"key": "culture", "label": "文化", "description": "M2では方針とメモを保存。詳細設計はM2.5。", "detail_milestone": "M2.5"},
]

IMPORT_FORMATS = [
    {"key": "plain_text", "label": "TXT / プレーンテキスト"},
    {"key": "markdown", "label": "Markdown"},
    {"key": "docx", "label": "DOCX"},
    {"key": "epub", "label": "EPUB"},
    {"key": "other", "label": "その他"},
]

SECTION_MODES = [
    {"key": SectionMode.AUTO.value, "label": "AUTO", "description": "システム提案を使い、作者が承認する。"},
    {"key": SectionMode.MANUAL.value, "label": "MANUAL", "description": "作者が自分で設定する。"},
    {"key": SectionMode.SKIP.value, "label": "SKIP", "description": "今は設定しない。"},
]

_BASE = {section["key"]: 50 for section in WORLD_DNA_SECTIONS}

_GENRE_INFLUENCE = {
    "isekai": {**_BASE, "geography": 80, "society": 70, "economy": 65, "technology": 60, "magic": 90, "language": 75, "culture": 80},
    "noble_lady": {**_BASE, "society": 95, "economy": 60, "calendar": 70, "language": 75, "culture": 90},
    "palace": {**_BASE, "society": 95, "religion": 65, "calendar": 80, "language": 75, "culture": 95},
    "romcom": {**_BASE, "society": 70, "calendar": 85, "language": 50, "culture": 65},
    "mystery": {**_BASE, "geography": 60, "society": 70, "technology": 60, "calendar": 95},
    "sf": {**_BASE, "geography": 65, "society": 75, "economy": 65, "technology": 95, "magic": 20, "calendar": 80, "language": 60, "culture": 65},
    "fantasy": {**_BASE, "geography": 85, "society": 65, "magic": 95, "religion": 75, "language": 75, "culture": 85},
    "romance": {**_BASE, "society": 80, "calendar": 75, "language": 55, "culture": 65},
    "contemporary": {**_BASE, "society": 70, "economy": 60, "technology": 75, "calendar": 80},
    "horror": {**_BASE, "geography": 60, "society": 60, "religion": 70, "calendar": 65, "culture": 70},
    "historical": {**_BASE, "geography": 70, "society": 90, "economy": 75, "technology": 75, "religion": 80, "calendar": 90, "language": 80, "culture": 95},
    "adventure": {**_BASE, "geography": 95, "society": 50, "economy": 50, "technology": 50, "magic": 55, "calendar": 60, "culture": 60},
    "undecided": _BASE,
}


def get_world_builder_catalog() -> dict[str, object]:
    return {
        "genres": GENRE_CATALOG,
        "setup_modes": SETUP_MODES,
        "section_modes": SECTION_MODES,
        "world_dna_sections": WORLD_DNA_SECTIONS,
        "import_formats": IMPORT_FORMATS,
        "catalog_version": 1,
    }


def build_recommendations(
    selected_genres: list[str],
    genre_weights: dict[str, int],
    custom_genres: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    custom_weight = sum(int(item.get("weight", 50)) for item in custom_genres)
    total_weight = sum(genre_weights.get(key, 0) for key in selected_genres) + custom_weight
    recommendations: dict[str, dict[str, object]] = {}

    for section in WORLD_DNA_SECTIONS:
        section_key = section["key"]
        if total_weight <= 0:
            score = 50
        else:
            numerator = custom_weight * 50
            for genre in selected_genres:
                influence = _GENRE_INFLUENCE.get(genre, _BASE)[section_key]
                numerator += genre_weights.get(genre, 0) * influence
            score = round(numerator / total_weight)

        priority = "high" if score >= 70 else "standard" if score >= 45 else "light"
        recommendations[section_key] = {
            "score": score,
            "priority": priority,
            "reason": "選択したジャンル構成から算出した初期優先度。作者が自由に変更できます。",
        }

    return recommendations
