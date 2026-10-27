import os
import fitz
from .letter_art import load_letter_art, draw_hanging_letter, draw_centered_piece

MM_TO_PT = 72 / 25.4
BLEED_MM = 3.0
SPREAD_W_MM = 426.0  # full spread (two pages), trim width 420 + 6 bleed
SPREAD_H_MM = 216.0
MARGIN_MM = 30.0  # this spread uses a 30mm margin, not 20mm

ZONE_X0_MM = BLEED_MM + MARGIN_MM
ZONE_X1_MM = BLEED_MM + (SPREAD_W_MM - 2 * BLEED_MM) - MARGIN_MM
ZONE_Y0_MM = BLEED_MM + MARGIN_MM
ZONE_Y1_MM = BLEED_MM + (SPREAD_H_MM - 2 * BLEED_MM) - MARGIN_MM
ZONE_W_MM = ZONE_X1_MM - ZONE_X0_MM
ZONE_H_MM = ZONE_Y1_MM - ZONE_Y0_MM

BASELINE_FRACTION = 0.45  # "a bit above half" the zone height (was 0.4 on the per-letter pages)
THREAD_TOP_Y_MM = -1.0    # threads are drawn up to here: just past the top (bleed) edge

# All sizes below are relative to the LOWERCASE GLYPH height (the illustrated
# letter only, thread excluded) -- see letter_art.py for why.
UPSIZE_MULT = 1.8     # first letter / letter after a dash: glyph height = this x lowercase
GAP_MULT = 0.085      # space between letters = this x lowercase glyph height
DASH_SIZE_MULT = 0.6
DASH_MAX_WIDTH_MULT = 0.8
DASH_FILENAME = "hyphen-1-u.png"

# The order-form automation supports names of 5-10 letters (shorter/longer
# names are handled manually). Rather than a single fixed width target for
# every length, the name is meant to fill more of the zone as it gets
# longer: 55% of ZONE_W_MM at 5 letters, scaling up to 85% at 10 letters,
# interpolated linearly in between. Outside 5-10 it just clamps to the
# nearest endpoint rather than extrapolating.
WIDTH_FRACTION_AT_MIN_LETTERS = 0.55
WIDTH_FRACTION_AT_MAX_LETTERS = 0.85
MIN_AUTOMATED_LETTERS = 5
MAX_AUTOMATED_LETTERS = 10


def target_width_fraction(n_letters):
    if n_letters <= MIN_AUTOMATED_LETTERS:
        return WIDTH_FRACTION_AT_MIN_LETTERS
    if n_letters >= MAX_AUTOMATED_LETTERS:
        return WIDTH_FRACTION_AT_MAX_LETTERS
    t = (n_letters - MIN_AUTOMATED_LETTERS) / (MAX_AUTOMATED_LETTERS - MIN_AUTOMATED_LETTERS)
    return WIDTH_FRACTION_AT_MIN_LETTERS + t * (WIDTH_FRACTION_AT_MAX_LETTERS - WIDTH_FRACTION_AT_MIN_LETTERS)


def mark_upsize_flags(name_sequence):
    """First letter, and any letter immediately following a literal '-' entry
    in the sequence, gets the 1.8x upsize. name_sequence items are
    (key, case, variant, path) OR the literal string "-" for a dash."""
    flags = []
    prev_was_dash = False
    first = True
    for item in name_sequence:
        if item == "-":
            flags.append(None)  # dash isn't a rendered letter
            prev_was_dash = True
            continue
        flags.append(first or prev_was_dash)
        first = False
        prev_was_dash = False
    return flags


def _dash_path(night_letters_dir):
    """Night dash if there is one, else the day dash (it has no string anyway)."""
    if not night_letters_dir:
        return None
    for d in (night_letters_dir, os.path.join(os.path.dirname(night_letters_dir), "letters")):
        p = os.path.join(d, DASH_FILENAME)
        if os.path.exists(p):
            return p
    return None


def build_full_name_reveal(spread_path, name_sequence, out_path, night_letters_dir=None):
    """
    name_sequence items are (key, case, variant, path) for real letters, or
    the literal string "-" for a dash. night_letters_dir, if given, is used
    to find the dash asset (this page is always a night scene).

    Sizing: the name's total width is set to target_width_fraction() of the
    zone, solved directly from each letter's GLYPH width -- so every lowercase
    glyph ends up the same height and every capital glyph the same (larger)
    height, whatever thread length or canvas the PNG was exported with. If
    that would push the capitals above the top of the zone, everything is
    scaled down together instead.
    """
    upsize_flags = mark_upsize_flags(name_sequence)

    items = []  # (kind, art, upsize)
    dash_art = None
    for entry, up in zip(name_sequence, upsize_flags):
        if entry == "-":
            if dash_art is None:
                p = _dash_path(night_letters_dir)
                dash_art = load_letter_art(p) if p else False
            if dash_art:
                items.append(("dash", dash_art, False))
            else:
                print("[warning] no dash asset found -- leaving a gap in the name reveal")
                items.append(("gap", None, False))
        else:
            key, case, variant, path = entry
            items.append(("letter", load_letter_art(path), bool(up)))

    letters = [(art, up) for (kind, art, up) in items if kind == "letter"]
    n_real_letters = len(letters)
    target_w_mm = ZONE_W_MM * target_width_fraction(n_real_letters)

    # Total width in units of the lowercase glyph height g -- letters, dashes
    # (at their capped size) and every gap -- so the name lands exactly on target.
    units = 0.0
    for kind, art, up in items:
        if kind == "letter":
            units += (UPSIZE_MULT if up else 1.0) * art.aspect
        elif kind == "dash":
            units += min(DASH_SIZE_MULT * art.aspect, DASH_MAX_WIDTH_MULT)
        else:
            units += DASH_MAX_WIDTH_MULT
    units += GAP_MULT * max(0, len(items) - 1)
    g = target_w_mm / units

    baseline_y_mm = ZONE_Y0_MM + BASELINE_FRACTION * ZONE_H_MM
    tallest_mult = UPSIZE_MULT if any(up for _, up in letters) else 1.0
    g = min(g, (baseline_y_mm - ZONE_Y0_MM) / tallest_mult)  # capitals stay inside the zone
    gap_mm = GAP_MULT * g

    sizes = []  # (w_mm, h_mm) -- h is the GLYPH height for letters
    for kind, art, up in items:
        if kind == "letter":
            h_mm = g * (UPSIZE_MULT if up else 1.0)
            w_mm = h_mm * art.aspect
        elif kind == "dash":
            h_mm = g * DASH_SIZE_MULT
            w_mm = h_mm * art.aspect
            max_w_mm = g * DASH_MAX_WIDTH_MULT
            if w_mm > max_w_mm:
                h_mm *= max_w_mm / w_mm
                w_mm = max_w_mm
        else:
            h_mm, w_mm = 0.0, g * DASH_MAX_WIDTH_MULT
        sizes.append((w_mm, h_mm))

    total_w_mm = sum(w for w, _ in sizes) + gap_mm * (len(sizes) - 1)
    x_cursor = ZONE_X0_MM + (ZONE_W_MM - total_w_mm) / 2
    dash_center_y_mm = baseline_y_mm - g / 2

    doc = fitz.open(spread_path)
    page = doc[0]
    for (kind, art, up), (w_mm, h_mm) in zip(items, sizes):
        if kind == "letter":
            draw_hanging_letter(page, art, x_cursor, h_mm, baseline_y_mm, THREAD_TOP_Y_MM, MM_TO_PT)
        elif kind == "dash":
            draw_centered_piece(page, art, x_cursor, w_mm, h_mm, dash_center_y_mm, MM_TO_PT)
        x_cursor += w_mm + gap_mm

    doc.save(out_path)
    doc.close()
    print(f"Saved {out_path}: lowercase glyph={g:.1f}mm gap={gap_mm:.1f}mm "
          f"total_w={total_w_mm:.1f}mm (target={target_w_mm:.1f}mm, zone={ZONE_W_MM:.1f}mm)")


if __name__ == "__main__":
    import os
    os.chdir("/home/claude/amiyaa_test")

    NAME_5 = [
        ("a", "u", "1", "letters_v2/letter-a-u-1.png"),
        ("m", "l", "1", "letters_v2/letter-m-l-1.png"),
        ("i", "l", "2", "letters_v2/letter-i-l-2.png"),
        ("ya", "l", "1", "letters_v2/letter-ya-l-1.png"),
        ("a", "l", "2", "letters_v2/letter-a-l-2.png"),
    ]
    build_full_name_reveal("/mnt/user-data/uploads/Spread_-_Night_scene.pdf", NAME_5,
                            "/home/claude/amiyaa_test/full_name_reveal_test.pdf")

    # night scene -> white strings. Only 4 white-string letters are available
    # (a-u-1, m-l-1, i-l-2, ya-l-1); cycling those (skipping the missing
    # giraffe white-string) to build 7- and 10-letter stress tests.
    NIGHT_DIR = "letters_v2_night"
    A_U = ("a", "u", "1", f"{NIGHT_DIR}/letter-a-u-1.png")
    M_L = ("m", "l", "1", f"{NIGHT_DIR}/letter-m-l-1.png")
    I_L = ("i", "l", "2", f"{NIGHT_DIR}/letter-i-l-2.png")
    YA_L = ("ya", "l", "1", f"{NIGHT_DIR}/letter-ya-l-1.png")

    NAME_7 = [A_U, M_L, I_L, YA_L, M_L, I_L, YA_L]
    build_full_name_reveal("/mnt/user-data/uploads/Spread_-_Night_scene.pdf", NAME_7,
                            "/home/claude/amiyaa_test/full_name_reveal_7letters.pdf")

    NAME_10 = [A_U, M_L, I_L, YA_L, M_L, I_L, YA_L, M_L, I_L, YA_L]
    build_full_name_reveal("/mnt/user-data/uploads/Spread_-_Night_scene.pdf", NAME_10,
                            "/home/claude/amiyaa_test/full_name_reveal_10letters.pdf")
