"""
Book editions: the classic book and the New Year special edition.

The New Year art lives in the same asset zip, in its own folder that mirrors
the classic layout:

    amiya-assets/
    ├── spreads/ letters/ letters_night/ fonts/ covers/ caption_text.xlsx   (classic)
    └── newyear/
        ├── spreads/        any spread that looks different in the New Year
        │                   edition, under the SAME filename as the classic one
        ├── letters/ ...    (optional -- only if those differ too)
        └── covers/ (or cover/) boy_cover_blue.pdf, boy_cover_green.pdf, boy_cover_red.pdf,
                            girl_cover_blue.pdf, girl_cover_green.pdf, girl_cover_red.pdf

For each New Year color this module builds a complete asset folder made of
links: every classic file, with the New Year version swapped in wherever one
exists, and covers/{gender}_cover.pdf pointing at that color's cover. The
rest of the code then works exactly as before -- it is just handed a
different asset folder. The three colors share the same inside pages.

A file missing from newyear/ falls back to the classic version. The startup
log lists which classic spreads have no New Year version, so a forgotten
file shows up there instead of in a printed book.
"""

import os
import threading

CLASSIC = "classic"
NEW_YEAR = "new_year"
EDITIONS = (CLASSIC, NEW_YEAR)
COVER_COLORS = ("blue", "green", "red")
OVERLAY_DIR = "newyear"

# Per-edition look. hello_layout: size, position and color of the
# "Сайн уу, <name>!" greeting on the hello page (see hello.NEWYEAR_LAYOUT).
def _styles():
    from .hello import NEWYEAR_LAYOUT
    return {NEW_YEAR: {"hello_layout": NEWYEAR_LAYOUT}}

_built = {}
_lock = threading.Lock()


class EditionError(ValueError):
    pass


def normalize(edition, cover_color):
    """Checks an order's edition/color and returns the clean pair.
    Classic orders ignore any color; New Year orders must have one."""
    edition = (edition or CLASSIC).strip().lower().replace("-", "_")
    if edition not in EDITIONS:
        raise EditionError(f"edition must be one of {', '.join(EDITIONS)}")
    if edition == CLASSIC:
        return CLASSIC, None
    color = (cover_color or "").strip().lower()
    if color not in COVER_COLORS:
        raise EditionError(f"a New Year order needs cover_color: {', '.join(COVER_COLORS)}")
    return NEW_YEAR, color


def asset_root_for(asset_root, edition=CLASSIC, cover_color=None, editions_root=None):
    """The asset folder to build this order's book from."""
    edition, color = normalize(edition, cover_color)
    if edition == CLASSIC:
        return asset_root
    overlay = os.path.join(asset_root, OVERLAY_DIR)
    if not os.path.isdir(overlay):
        raise FileNotFoundError(f"New Year art folder not found: {overlay}")
    editions_root = editions_root or os.environ.get("EDITIONS_ROOT", "/app/editions")
    key = (asset_root, color, editions_root)
    with _lock:
        if key not in _built:
            _built[key] = _build(asset_root, overlay, color, os.path.join(editions_root, f"new_year_{color}"))
        return _built[key]


def style_for(asset_root):
    """The edition style for an asset folder returned by asset_root_for
    (empty for classic)."""
    for root in _built.values():
        if os.path.realpath(root) == os.path.realpath(asset_root):
            return _styles()[NEW_YEAR]
    return {}


def _link(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.lexists(dst):
        os.remove(dst)
    os.symlink(src, dst)


def _page_size(path):
    import fitz
    with fitz.open(path) as doc:
        r = doc[0].rect
        return r.width, r.height


def _size_mismatch(src, classic):
    """The classic page size (points) if src is a PDF of a different size, else None."""
    if not (src.lower().endswith(".pdf") and os.path.exists(classic)):
        return None
    sw, sh = _page_size(src)
    cw, ch = _page_size(classic)
    tolerance = 72 / 25.4  # 1 mm
    if abs(sw - cw) <= tolerance and abs(sh - ch) <= tolerance:
        return None
    return cw, ch


def _scaled_copy(src, dst, size):
    import fitz
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.lexists(dst):
        os.remove(dst)
    out = fitz.open()
    with fitz.open(src) as s:
        for i in range(len(s)):
            page = out.new_page(width=size[0], height=size[1])
            page.show_pdf_page(page.rect, s, i, keep_proportion=False)
    out.save(dst)
    out.close()


def _build(asset_root, overlay, color, out_root):
    import shutil
    shutil.rmtree(out_root, ignore_errors=True)
    os.makedirs(out_root)

    # 1. every classic file
    for dirpath, dirnames, filenames in os.walk(asset_root):
        rel = os.path.relpath(dirpath, asset_root)
        if rel == OVERLAY_DIR or rel.startswith(OVERLAY_DIR + os.sep):
            continue
        for f in filenames:
            _link(os.path.join(dirpath, f), os.path.join(out_root, rel, f))

    # 2. New Year versions on top (same filenames). A New Year PDF exported
    #    at a different size than the classic page it replaces (e.g. double
    #    size) would put the photo/text in the wrong place, since the layout
    #    code works in fixed millimetres -- so it is scaled to the classic
    #    page size instead of linked.
    for dirpath, _, filenames in os.walk(overlay):
        rel = os.path.relpath(dirpath, overlay)
        for f in filenames:
            src = os.path.join(dirpath, f)
            dst = os.path.join(out_root, rel, f)
            classic = os.path.join(asset_root, rel, f)
            size = _size_mismatch(src, classic)
            if size:
                _scaled_copy(src, dst, size)
                print(f"[editions] {OVERLAY_DIR}/{rel}/{f} is a different size than the classic page "
                      f"-- scaled to {size[0] / 72 * 25.4:.0f}x{size[1] / 72 * 25.4:.0f}mm")
            else:
                _link(src, dst)

    # 3. this color's covers become the ones the cover code looks for
    for gender in ("boy", "girl"):
        src = _ny_cover(overlay, gender, color)
        if src:
            _link(src, os.path.join(out_root, "covers", f"{gender}_cover.pdf"))
        else:
            # never fall back to the classic cover -- a wrong cover is worse
            # than a clear error
            dst = os.path.join(out_root, "covers", f"{gender}_cover.pdf")
            if os.path.lexists(dst):
                os.remove(dst)
    return out_root


def _ny_cover(overlay, gender, color):
    """The New Year cover file -- the folder may be named covers/ or cover/."""
    for folder in ("covers", "cover"):
        p = os.path.join(overlay, folder, f"{gender}_cover_{color}.pdf")
        if os.path.exists(p):
            return p
    return None


def report(asset_root):
    """Startup log lines: which New Year files are present or missing."""
    overlay = os.path.join(asset_root, OVERLAY_DIR)
    if not os.path.isdir(overlay):
        return [f"  [--] {OVERLAY_DIR}/ -- not in this asset zip (New Year orders will fail)"]
    lines = []
    for gender in ("girl", "boy"):
        for color in COVER_COLORS:
            f = f"{gender}_cover_{color}.pdf"
            ok = _ny_cover(overlay, gender, color) is not None
            lines.append(f"  [{'OK' if ok else 'MISSING'}] {OVERLAY_DIR}/covers/{f}")
    for sub in ("spreads", "letters", "letters_night"):
        classic = set(os.listdir(os.path.join(asset_root, sub))) if os.path.isdir(os.path.join(asset_root, sub)) else set()
        ny_dir = os.path.join(overlay, sub)
        ny = set(os.listdir(ny_dir)) if os.path.isdir(ny_dir) else set()
        if not ny:
            if sub == "spreads":
                lines.append(f"  [MISSING] {OVERLAY_DIR}/spreads/ -- New Year books would use classic pages")
            continue
        unknown = sorted(ny - classic)
        lines.append(f"  [OK] {OVERLAY_DIR}/{sub}/ -- {len(ny & classic)} of {len(classic)} files have a New Year version")
        for f in unknown:
            lines.append(f"  [CHECK NAME] {OVERLAY_DIR}/{sub}/{f} -- no classic file with this name, so it is never used")
        for f in sorted(ny & classic):
            try:
                if _size_mismatch(os.path.join(ny_dir, f), os.path.join(asset_root, sub, f)):
                    lines.append(f"  [SIZE] {OVERLAY_DIR}/{sub}/{f} -- different size than classic, scaled automatically")
            except Exception as e:
                lines.append(f"  [ERROR] {OVERLAY_DIR}/{sub}/{f} -- could not open: {e!r}")
        if sub == "spreads":
            fixed = sorted(f for f in classic - ny if not f.startswith("spread-"))
            letter_spreads = [f for f in classic - ny if f.startswith("spread-")]
            for f in fixed:
                lines.append(f"  [classic used] spreads/{f}")
            if letter_spreads:
                lines.append(f"  [classic used] {len(letter_spreads)} letter spreads (spread-*.pdf)")
    return lines
