"""
Shared measuring + drawing for the hanging letter PNGs (day garland on the
give spreads, and the night full-name reveal).

Every letter PNG is a thread with the illustrated letter (the "glyph") at the
bottom. Thread length, canvas size and resolution differ from file to file
(the glyph is anywhere from ~15% to ~25% of the image height), and a letter's
day and night files are trimmed differently. So nothing here sizes by the
whole image:

  * SIZE is set by the letter's BODY height (see BODY_TRIM) -- every
    lowercase body comes out the same height, every capital the same
    (larger) height; ears, tails, б's top, у's tail etc. stick out.
  * SPACING uses the glyph's width, not the image's.
  * The THREAD is extended upward by repeating one of its own pixel rows, so
    it always runs off the top edge of the page however small the letters
    get and however short the thread was drawn.
"""

import io
import math
import os
from functools import lru_cache

import numpy as np
from PIL import Image

ALPHA_MIN = 10          # a pixel counts as "there" above this alpha
THREAD_MAX_FRAC = 0.08  # a row narrower than this share of the image width is thread, not glyph
GLYPH_RUN_FRAC = 0.01   # glyph starts at the first run of wide rows at least this tall (ignores specks)


# ---------------------------------------------------------------------
# Letter BODY: the part of a letter that has to match every other letter's
# size. By default the body is the whole glyph. For the letters below it's
# smaller, so the rest sticks out of the line instead of shrinking the
# letter:
#   * б -- the top stroke rises above the other letters
#   * у, ү, р -- the tail hangs below the line (and д, ц: their feet/hook)
#   * й, ё -- the mark/dots sit above
#   * animal extras -- ears, horns, antlers, crests, wings above; feet,
#     hooves, tails below
# Each entry: file name (no .png) -> (top, bottom), the share of the glyph's
# height that is NOT body at the top and at the bottom. The body's bottom
# sits on the baseline.
#
# Tailed letters (у, ү, р) are sized differently so they don't come out
# oversized: the whole letter (ears/horns excluded, tail included) is made
# TAILED_HEIGHT x an ordinary letter's height, with the tail still hanging
# below the baseline. Their tops end up a little smaller than other letters. Measured by eye from
# the art (Nov 2026); the day and night files of a letter share one entry.
# A NEW letter file that has something sticking out needs an entry here.
TAILED_HEIGHT = {"u": 1.3, "r": 1.3, "w": 1.5}   # ү needs more: its top came out too small

# Fine-tuning for single drawings that still look too big or small next to
# the others (e.g. a much chunkier animal). 0.9 = 10% smaller.
SIZE_TWEAK = {
    "u-l-1": 0.85,   # hippo у -- wide and chunky next to the slim horse у
    "ts-l-1": 0.85,  # red ц -- blocky, looked bigger than its neighbours
    "w-l-3": 0.85,   # grey ү -- much chunkier than the other ү
    "j-l-1": 0.85,   # ж -- wide, looked much bigger than other letters
}

# Tailed letters are hung so their top reaches this share of an ordinary
# letter's height (1.0 = level with the other letters' tops); the tail
# hangs below the line by whatever is left.
TAILED_TOP_REACH = 0.95
TAILED = set(TAILED_HEIGHT)

BODY_TRIM = {
    # б: bowl is the body, top stroke rises
    "b-l-1": (0.37, 0), "b-l-2": (0.36, 0),
    # р: bowl is the body, stem hangs below
    "r-l-1": (0.05, 0.40), "r-l-2": (0.13, 0.40),
    # у: arms are the body, tail hangs below
    "u-l-1": (0.16, 0.37), "u-l-2": (0.15, 0.34), "u-l-3": (0.03, 0.40),
    # ү: arms are the body, stem hangs below
    "w-l-1": (0.15, 0.40), "w-l-2": (0.13, 0.45), "w-l-3": (0.04, 0.48), "w-l-4": (0.03, 0.45),
    # д, ц: feet / hook hang below
    "d-l-1": (0.03, 0.17), "d-l-2": (0.22, 0.15),
    "ts-l-1": (0, 0.18), "ts-l-2": (0.18, 0.08),
    # й, ё: mark above
    "iy-l-1": (0.21, 0), "yo-l-1": (0.26, 0),
    # animal extras
    "a-l-2": (0.19, 0),            # giraffe horns
    "g-l-2": (0.10, 0),            # unicorn head
    "g-l-3": (0.03, 0.10),         # duck feet
    "k-l-1": (0.18, 0.02),         # koala ears
    "kh-l-3": (0.19, 0),           # antlers
    "l-l-1": (0.11, 0.03),         # dragon spikes, tail
    "m-l-2": (0.13, 0),            # cat ears
    "n-l-1": (0.03, 0.12),         # duck feet
    "o-l-1": (0, 0.08),            # penguin feet
    "o-l-5": (0.16, 0),            # bear ears
    "p-l-1": (0.08, 0),            # panda ears
    "q-l-2": (0.30, 0),            # bird head and crest
    "q-l-3": (0.28, 0),            # skunk tail
    "s-l-2": (0.20, 0),            # yak horns
    "sh-l-1": (0.24, 0),           # wings
    "t-l-2": (0.22, 0),            # bunny ears
    "yu-l-1": (0.32, 0),           # unicorn horn, ears, mane
    "z-l-1": (0.14, 0),            # bee wings
    "z-l-3": (0.05, 0.13),         # fish fins
    "j-l-1": (0.12, 0),            # antennae
}


def _trim_key(path):
    name = os.path.splitext(os.path.basename(path))[0]
    return name[len("letter-"):] if name.startswith("letter-") else name


class LetterArt:
    """A letter PNG cropped to its visible pixels, with its glyph and thread measured.
    All measurements are in pixels of `image`."""

    def __init__(self, image, glyph_top, gx0, gx1, has_thread, repeat_row, trim=(0, 0), tailed=0, size_tweak=1.0):
        self.image = image
        self.w, self.h = image.size
        self.glyph_top = glyph_top          # first row of the glyph (rows above are thread)
        self.gx0, self.gx1 = gx0, gx1       # glyph's left/right edge
        self.glyph_w = gx1 - gx0
        self.glyph_h = self.h - glyph_top
        # body: the part sized to match other letters (see BODY_TRIM); its
        # bottom sits on the baseline
        self.body_top = glyph_top + trim[0] * self.glyph_h
        self.body_bottom = self.h - trim[1] * self.glyph_h
        self.body_h = self.body_bottom - self.body_top
        if tailed:
            letter_h = self.h - self.body_top          # whole letter, extras on top excluded
            self.body_h = letter_h / tailed            # so the whole letter = that many x others
            # hang it so its top is TAILED_TOP_REACH of an ordinary letter
            # above the baseline (lifts it toward the top line)
            self.body_bottom = self.body_top + TAILED_TOP_REACH * self.body_h
        self.body_h /= size_tweak
        self.aspect = self.glyph_w / self.body_h    # GLYPH width / BODY height
        # how far the glyph reaches above the baseline, in body heights (>= 1)
        self.rise = (self.body_bottom - glyph_top) / self.body_h
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
    key = _trim_key(path)
    return LetterArt(im, glyph_top, gx0, gx1, has_thread, repeat_row,
                     BODY_TRIM.get(key, (0, 0)),
                     tailed=(TAILED_HEIGHT.get(key.split("-")[0], 0)
                             if "-l-" in key and key in BODY_TRIM else 0),
                     size_tweak=SIZE_TWEAK.get(key, 1.0))


def _insert(page, image, x0_mm, y0_mm, x1_mm, y1_mm, mm_to_pt):
    import fitz
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    page.insert_image(fitz.Rect(x0_mm * mm_to_pt, y0_mm * mm_to_pt,
                                x1_mm * mm_to_pt, y1_mm * mm_to_pt),
                      stream=buf.getvalue())


def draw_hanging_letter(page, art, x_mm, body_h_mm, baseline_y_mm, thread_top_y_mm, mm_to_pt):
    """Draw `art` so its BODY is `body_h_mm` tall, its glyph's left edge at
    `x_mm` and its body's bottom on `baseline_y_mm` (a tail or feet hang
    below it). If its thread would end below `thread_top_y_mm`, the thread
    is lengthened to reach it."""
    mm_per_px = body_h_mm / art.body_h
    image, img_h = art.image, art.h
    below_mm = (art.h - art.body_bottom) * mm_per_px   # part hanging under the baseline
    bottom_y_mm = baseline_y_mm + below_mm

    if art.has_thread and bottom_y_mm - img_h * mm_per_px > thread_top_y_mm:
        r = art.repeat_row
        below = art.image.crop((0, r, art.w, art.h))
        extra = math.ceil((bottom_y_mm - thread_top_y_mm) / mm_per_px) - below.height + 1
        thread_row = art.image.crop((0, r, art.w, r + 1)).resize((art.w, extra), Image.NEAREST)
        image = Image.new("RGBA", (art.w, extra + below.height))
        image.paste(thread_row, (0, 0))
        image.paste(below, (0, extra))
        img_h = image.height

    left_mm = x_mm - art.gx0 * mm_per_px
    _insert(page, image,
            left_mm, bottom_y_mm - img_h * mm_per_px,
            left_mm + art.w * mm_per_px, bottom_y_mm,
            mm_to_pt)


def draw_centered_piece(page, art, x_mm, w_mm, h_mm, center_y_mm, mm_to_pt):
    """Draw a thread-less piece (the dash) in a box centred on `center_y_mm`."""
    _insert(page, art.image,
            x_mm, center_y_mm - h_mm / 2,
            x_mm + w_mm, center_y_mm + h_mm / 2,
            mm_to_pt)
