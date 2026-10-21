"""
Automatic animal (variant) picks for a name -- used by the website preview
and offered to the dashboard, so the preview the parent sees and the book
that gets printed choose the same animals.

The rule:
  * Each letter's case follows the print book: uppercase for the first
    letter and the first letter after a hyphen, lowercase otherwise.
  * The 1st time a letter appears it gets variant 1, the 2nd time variant 2,
    and so on (counted per letter, ignoring case -- "А" and "а" are the
    same animal family, so "Ананд" gets a-1 then a-2).
  * If that variant has no complete art for this gender and case (meet
    spread, give spread in either case, garland letter, night letter,
    caption row), the highest complete variant below it is used; failing
    that, the lowest complete one.
  * Letters with no art at all are reported as unsupported.
"""

import os
import re

# Same table as the dashboard's CYRILLIC_MAP.
CYRILLIC_MAP = {
    'А': 'a', 'Б': 'b', 'В': 'v', 'Г': 'g', 'Д': 'd', 'Е': 'ye', 'Ё': 'yo', 'Ж': 'j', 'З': 'z',
    'И': 'i', 'Й': 'iy', 'К': 'k', 'Л': 'l', 'М': 'm', 'Н': 'n', 'О': 'o', 'Ө': 'q', 'П': 'p',
    'Р': 'r', 'С': 's', 'Т': 't', 'У': 'u', 'Ү': 'w', 'Ф': 'f', 'Х': 'kh', 'Ц': 'ts', 'Ч': 'ch',
    'Ш': 'sh', 'Щ': 'sch', 'Ь': ',', 'Э': 'e', 'Ю': 'yu', 'Я': 'ya',
}

_inventory_cache = {}


def _inventory(asset_root, caption_keys):
    """Which (key, gender, case, variant) combinations have complete art."""
    cache_key = (asset_root, len(caption_keys))
    if cache_key in _inventory_cache:
        return _inventory_cache[cache_key]
    spreads = set(os.listdir(os.path.join(asset_root, "spreads")))
    letters = set(os.listdir(os.path.join(asset_root, "letters")))
    night = set(os.listdir(os.path.join(asset_root, "letters_night")))
    complete = set()
    for f in spreads:
        m = re.match(r"spread-(.+?)-(\d+)-meet-(boy|girl)\.pdf$", f)
        if not m:
            continue
        key, variant, gender = m.group(1), m.group(2), m.group(3)
        if (key, variant, gender) not in caption_keys:
            continue
        for case in ("u", "l"):
            other = "l" if case == "u" else "u"
            has_give = (f"spread-{key}-{case}-{variant}-give-{gender}.pdf" in spreads
                        or f"spread-{key}-{other}-{variant}-give-{gender}.pdf" in spreads)
            png = f"{key}-{case}-{variant}.png"
            if has_give and png in letters and png in night:
                complete.add((key, gender, case, int(variant)))
    _inventory_cache[cache_key] = complete
    return complete


def parse_name(name):
    """[(char, key or None, case)] plus '-' entries, mirroring the dashboard."""
    tokens = []
    start = True
    for ch in name.strip():
        if ch == "-":
            tokens.append(("-", "-", None))
            start = True
            continue
        if ch.isspace():
            continue
        up = ch.upper()
        tokens.append((up, CYRILLIC_MAP.get(up), "u" if start else "l"))
        start = False
    return tokens


def pick_variants(name, gender, asset_root, caption_keys):
    """
    Returns (letter_variants, unsupported) where letter_variants is the list
    the book generator takes ([{"key","case","variant"}...], dashes as
    {"key":"-","case":None,"variant":None}) and unsupported lists any
    characters with no art (empty when the whole name can be built).
    """
    complete = _inventory(asset_root, caption_keys)
    seen = {}
    out, unsupported = [], []
    for ch, key, case in parse_name(name):
        if key == "-":
            out.append({"key": "-", "case": None, "variant": None})
            continue
        options = sorted(v for (k, g, c, v) in complete if k == key and g == gender and c == case) if key else []
        if not options:
            unsupported.append(ch)
            continue
        seen[key] = seen.get(key, 0) + 1
        want = seen[key]
        below = [v for v in options if v <= want]
        variant = below[-1] if below else options[0]
        out.append({"key": key, "case": case, "variant": str(variant)})
    return out, unsupported


def caption_keys_from(caption_data):
    """caption_data is letters.load_caption_data(...) -> {(key, variant, gender): row}."""
    return set(caption_data.keys())
