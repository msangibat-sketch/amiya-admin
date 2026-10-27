"""
Shared measuring + drawing for the hanging letter PNGs (day garland on the
give spreads, and the night full-name reveal).

Every letter PNG is a thread with the illustrated letter (the "glyph") at the
bottom. Thread length, canvas size and resolution differ from file to file
(the glyph is anywhere from ~15% to ~25% of the image height), and a letter's
day and night files are trimmed differently. So nothing here sizes by the
whole image:

  * SIZE is set by the glyph's height -- every lowercase glyph comes out the
    same height, every capital glyph the same (larger) height.
  * SPACING uses the glyph's width, not the image's.
  * The THREAD is extended upward by repeating one of its own pixel rows, so
    it always runs off the top edge of the page however small the letters
    get and however short the thread was drawn.
"""

import io
import math
from functools import lru_cache

import numpy as np
from PIL import Image

ALPHA_MIN = 10          # a pixel counts as "there" above this alpha
THREAD_MAX_FRAC = 0.08  # a row narrower than this share of the image width is thread, not glyph
GLYPH_RUN_FRAC = 0.01   # glyph starts at the first run of wide rows at least this tall (ignores specks)


class LetterArt:
    """A letter PNG cropped to its visible pixels, with its glyph and thread measured.
    All measurements are in pixels of `image`."""

    def __init__(self, image, glyph_top, gx0, gx1, has_thread, repeat_row):
        self.image = image
        self.w, self.h = image.size
        self.glyph_top = glyph_top          # first row of the glyph (rows above are thread)
        self.gx0, self.gx1 = gx0, gx1       # glyph's left/right edge
        self.glyph_w = gx1 - gx0
        self.glyph_h = self.h - glyph_top
        self.aspect = self.glyph_w / self.glyph_h   # GLYPH width / GLYPH height
        self.has_thread = has_thread
        self.repeat_row = repeat_row        # a clean thread row, repeated to lengthen the thread


@lru_cache(maxsize=512)
def load_letter_art(path):
    im = Image.open(path).convert("RGBA")
    alpha = np.array(im)[:, :, 3]
    rows = np.where(alpha.max(axis=1) > ALPHA_MIN)[0]
    cols = np.where(alpha.max(axis=0) > ALPHA_MIN)[0]
    im = im.crop((int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1))
    on = np.array(im)[:, :, 3] > ALPHA_MIN
    h, w = on.shape

    # Horizontal span of each row (left-most to right-most visible pixel)
    any_on = on.any(axis=1)
    left = np.argmax(on, axis=1)
    right = w - 1 - np.argmax(on[:, ::-1], axis=1)
    span = np.where(any_on, right - left + 1, 0)

    wide = span > max(3, w * THREAD_MAX_FRAC)
    run = max(2, round(h * GLYPH_RUN_FRAC))
    glyph_top = 0
    if not wide[0]:
        glyph_top = h - 1
        for y in range(h - run + 1):
            if wide[y:y + run].all():
                glyph_top = y
                break

    gcols = np.where(on[glyph_top:].any(axis=0))[0]
    gx0, gx1 = int(gcols[0]), int(gcols[-1]) + 1

    has_thread = glyph_top >= run
    # a row a quarter of the way down the thread: clear of a tapered tip at the top
    repeat_row = int(glyph_top * 0.25) if has_thread else 0
    return LetterArt(im, glyph_top, gx0, gx1, has_thread, repeat_row)


def _insert(page, image, x0_mm, y0_mm, x1_mm, y1_mm, mm_to_pt):
    import fitz
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    page.insert_image(fitz.Rect(x0_mm * mm_to_pt, y0_mm * mm_to_pt,
                                x1_mm * mm_to_pt, y1_mm * mm_to_pt),
                      stream=buf.getvalue())


def draw_hanging_letter(page, art, x_mm, glyph_h_mm, baseline_y_mm, thread_top_y_mm, mm_to_pt):
    """Draw `art` so its glyph is `glyph_h_mm` tall, its glyph's left edge at
    `x_mm` and its bottom on `baseline_y_mm`. If its thread would end below
    `thread_top_y_mm`, the thread is lengthened to reach it."""
    mm_per_px = glyph_h_mm / art.glyph_h
    image, img_h = art.image, art.h

    if art.has_thread and baseline_y_mm - img_h * mm_per_px > thread_top_y_mm:
        r = art.repeat_row
        below = art.image.crop((0, r, art.w, art.h))
        extra = math.ceil((baseline_y_mm - thread_top_y_mm) / mm_per_px) - below.height + 1
        thread_row = art.image.crop((0, r, art.w, r + 1)).resize((art.w, extra), Image.NEAREST)
        image = Image.new("RGBA", (art.w, extra + below.height))
        image.paste(thread_row, (0, 0))
        image.paste(below, (0, extra))
        img_h = image.height

    left_mm = x_mm - art.gx0 * mm_per_px
    _insert(page, image,
            left_mm, baseline_y_mm - img_h * mm_per_px,
            left_mm + art.w * mm_per_px, baseline_y_mm,
            mm_to_pt)


def draw_centered_piece(page, art, x_mm, w_mm, h_mm, center_y_mm, mm_to_pt):
    """Draw a thread-less piece (the dash) in a box centred on `center_y_mm`."""
    _insert(page, art.image,
            x_mm, center_y_mm - h_mm / 2,
            x_mm + w_mm, center_y_mm + h_mm / 2,
            mm_to_pt)
