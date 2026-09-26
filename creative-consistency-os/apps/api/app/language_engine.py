import random


def _tokens(value: object, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return fallback
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return cleaned or fallback


def generate_names(language: dict[str, object], *, kind: str, count: int, seed: int) -> list[str]:
    phonology = language.get("phonology") if isinstance(language.get("phonology"), dict) else {}
    naming = language.get("naming") if isinstance(language.get("naming"), dict) else {}

    onsets = _tokens(phonology.get("onsets"), ["m", "n", "r", "s", "t", "k", "v", "l"])
    nuclei = _tokens(phonology.get("nuclei"), ["a", "e", "i", "o", "u"])
    codas = _tokens(phonology.get("codas"), ["", "", "n", "r", "s"])
    forbidden = _tokens(phonology.get("forbidden_sequences"), ["__never__"])

    minimum = max(1, min(6, int(phonology.get("syllables_min", 2))))
    maximum = max(minimum, min(8, int(phonology.get("syllables_max", 3))))
    separator = str(phonology.get("separator", ""))
    capitalize = bool(phonology.get("capitalize", True))

    suffix_map = naming.get("suffixes") if isinstance(naming.get("suffixes"), dict) else {}
    suffixes = _tokens(suffix_map.get(kind), [""])
    prefix_map = naming.get("prefixes") if isinstance(naming.get("prefixes"), dict) else {}
    prefixes = _tokens(prefix_map.get(kind), [""])

    rng = random.Random(seed)
    results: list[str] = []
    attempts = 0

    while len(results) < count and attempts < count * 40:
        attempts += 1
        syllable_count = rng.randint(minimum, maximum)
        parts = []
        for _ in range(syllable_count):
            parts.append(f"{rng.choice(onsets)}{rng.choice(nuclei)}{rng.choice(codas)}")
        name = f"{rng.choice(prefixes)}{separator.join(parts)}{rng.choice(suffixes)}"
        if capitalize and name:
            name = name[0].upper() + name[1:]
        if any(seq != "__never__" and seq in name for seq in forbidden):
            continue
        if name not in results:
            results.append(name)

    return results
