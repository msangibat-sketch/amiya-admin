"""
Website preview: builds only the pages a parent sees before ordering
(cover, hello, dedication, the two story spreads, the first two letters,
farewell) at screen quality, with a watermark. Nothing is saved or
uploaded and no Heyzine book is made -- the caller deletes work_dir.

The pages come from the same assembly code as the real book, and the
animals come from autopick, so the preview matches what gets printed.
"""

import base64
import io
import os

import fitz
from PIL import Image, ImageDraw, ImageFont

from .autopick import pick_variants, caption_keys_from
from .letters import build_letter_sequence, load_caption_data, SPREAD_W_MM, SPREAD_H_MM
from .hello import build_hello_test
from .spread2_dedication import build_spread2
from .spread3_intro import build_spread3
from .spread4_gathering import build_spread4
from .farewell import build_farewell
from .cover import build_digital_cover_page, calc_total_pages
from .stitch import normalize_name_case

PREVIEW_LETTERS = 2
SPREAD_PX = 1400          # width of a spread image; deliberately screen-only
COVER_PX = 700            # the cover is a single page
JPEG_QUALITY = 72
WATERMARK = "Миний нэр · preview"

_caption_cache = {}


class UnsupportedLetters(Exception):
    def __init__(self, letters):
        super().__init__("no art for: " + "".join(letters))
        self.letters = letters


def _caption_keys(asset_root):
    if asset_root not in _caption_cache:
        data = load_caption_data(os.path.join(asset_root, "caption_text.xlsx"))
        _caption_cache[asset_root] = caption_keys_from(data)
    return _caption_cache[asset_root]


def _render(pdf_path, width_px):
    doc = fitz.open(pdf_path)
    page = doc[0]
    zoom = width_px / page.rect.width
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()
    return img


_watermark_cache = {}


def _watermark(img, font_path):
    """Faint diagonal text tiled across the whole page (overlay cached per size)."""
    w, h = img.size
    tile = _watermark_cache.get((w, h))
    if tile is None:
        tile = _make_watermark(w, h, font_path)
        _watermark_cache[(w, h)] = tile
    out = img.convert("RGBA")
    out.alpha_composite(tile)
    return out.convert("RGB")


def _make_watermark(w, h, font_path):
    size = max(18, w // 28)
    font = ImageFont.truetype(font_path, size)
    tile = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    step_x, step_y = size * 14, size * 5
    for row, y in enumerate(range(0, h * 2, step_y)):
        offset = (row % 2) * step_x // 2
        for x in range(-step_x, w * 2, step_x):
            d.text((x + offset, y), WATERMARK, font=font, fill=(255, 255, 255, 70),
                   stroke_width=1, stroke_fill=(90, 60, 40, 40))
    tile = tile.rotate(24, resample=Image.BICUBIC)
    return tile.crop((w // 2, h // 2, w // 2 + w, h // 2 + h))


def _jpeg_data_url(img):
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _save_photo(photo_bytes, path):
    img = Image.open(io.BytesIO(photo_bytes))
    img = img.convert("RGB")
    img.thumbnail((1600, 1600))
    img.save(path, format="JPEG", quality=90)


def build_preview(asset_root, child_name, gender, dedication_text, photo_bytes, work_dir):
    """
    Returns {
      "pages":   [{"kind": "cover"|"hello"|..., "image": "data:image/jpeg;base64,..."}],
      "locked_letters": ["Э", "н", ...]   remaining letters, in order (no dashes),
      "total_pages": N,                  same count the cover/spine code uses,
      "letter_variants": [...]           the automatic picks, to save with the order
    }
    Raises UnsupportedLetters if the name has a letter with no art.
    """
    os.makedirs(work_dir, exist_ok=True)
    name = normalize_name_case(child_name.strip())
    letter_variants, unsupported = pick_variants(name, gender, asset_root, _caption_keys(asset_root))
    if unsupported:
        raise UnsupportedLetters(unsupported)

    spreads = os.path.join(asset_root, "spreads")
    font_path = os.path.join(asset_root, "fonts", "Nunito-Custom450.ttf")
    photo_path = os.path.join(work_dir, "photo.jpg")
    _save_photo(photo_bytes, photo_path)

    def p(n):
        return os.path.join(work_dir, n)

    build_digital_cover_page(name, gender, asset_root, target_w_mm=SPREAD_W_MM / 2,
                             target_h_mm=SPREAD_H_MM, out_path=p("cover.pdf"), dpi=100,
                             source_dpi=110)
    build_hello_test(os.path.join(spreads, f"hello_{gender}.pdf"), name, p("hello.pdf"))
    build_spread2(os.path.join(spreads, "dedication.pdf"), photo_path, dedication_text, p("dedication.pdf"))
    build_spread3(os.path.join(spreads, f"intro_{gender}.pdf"), gender, p("intro.pdf"))
    build_spread4(os.path.join(spreads, f"gathering_{gender}.pdf"), p("gathering.pdf"), gender)
    letter_pages = build_letter_sequence(asset_root, letter_variants, gender, p("letters"),
                                         max_letters=PREVIEW_LETTERS)
    build_farewell(os.path.join(spreads, f"farewell_{gender}.pdf"), name, gender, p("farewell.pdf"))

    order = [("cover", p("cover.pdf"), COVER_PX), ("hello", p("hello.pdf"), SPREAD_PX),
             ("dedication", p("dedication.pdf"), SPREAD_PX), ("intro", p("intro.pdf"), SPREAD_PX),
             ("gathering", p("gathering.pdf"), SPREAD_PX)]
    order += [("letter", path, SPREAD_PX) for path in letter_pages]
    order.append(("farewell", p("farewell.pdf"), SPREAD_PX))

    pages = [{"kind": kind, "image": _jpeg_data_url(_watermark(_render(path, px), font_path))}
             for kind, path, px in order]

    letters_only = [lv for lv in letter_variants if lv["key"] != "-"]
    name_letters = [ch for ch in name if ch != "-" and not ch.isspace()]
    return {
        "pages": pages,
        "locked_letters": name_letters[PREVIEW_LETTERS:],
        "total_pages": calc_total_pages(len(letters_only)),
        "letter_variants": letter_variants,
    }


def warm_up(asset_root):
    """Fills the caches a preview needs (captions, blank covers, watermark
    overlays) so the first real preview is as fast as later ones."""
    from .cover import _cover_template_image
    _caption_keys(asset_root)
    font_path = os.path.join(asset_root, "fonts", "Nunito-Custom450.ttf")
    for gender in ("boy", "girl"):
        _cover_template_image(os.path.join(asset_root, "covers", f"{gender}_cover.pdf"), 110)
        hello = _render(os.path.join(asset_root, "spreads", f"hello_{gender}.pdf"), SPREAD_PX)
        _watermark(hello, font_path)
