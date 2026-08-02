import fitz
from PIL import Image
import numpy as np
from .letters import measure_letter_only_ratio

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

REFERENCE_SLOTS = 10
UPSIZE_MULT = 1.8
BASELINE_FRACTION = 0.45  # "a bit above half" the zone height (was 0.4 on the per-letter pages)

MAX_TOTAL_H_MM = 400.0
MIN_TOTAL_H_MM = 40.0
BASE_GAP_MM = 6.0

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

DASH_SIZE_MULT = 0.6
DASH_MAX_WIDTH_MULT = 0.8
TYPICAL_LETTER_VISUAL_RATIO = 0.17
DASH_FILENAME = "hyphen-1-u.png"


def analyze_letter(path):
    im = Image.open(path).convert('RGBA')
    arr = np.array(im)
    alpha = arr[:, :, 3]
    rows_nz = np.where(alpha.max(axis=1) > 10)[0]
    top_row, bottom_row = int(rows_nz.min()), int(rows_nz.max())
    cols_nz = np.where(alpha.max(axis=0) > 10)[0]
    left_col, right_col = int(cols_nz.min()), int(cols_nz.max())
    cropped = im.crop((left_col, top_row, right_col + 1, bottom_row + 1))
    return cropped, cropped.width / cropped.height


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


def solve_height(letters_aspect_upsize, count_for_sizing, max_name_w_mm):
    for candidate in [x / 10 for x in range(int(MAX_TOTAL_H_MM * 10), int(MIN_TOTAL_H_MM * 10) - 1, -1)]:
        gap = BASE_GAP_MM * (candidate / MAX_TOTAL_H_MM)
        total_w = sum((candidate * UPSIZE_MULT if up else candidate) * aspect
                      for aspect, up in letters_aspect_upsize) + (count_for_sizing - 1) * gap
        if total_w <= max_name_w_mm:
            return candidate, gap
    return MIN_TOTAL_H_MM, BASE_GAP_MM * (MIN_TOTAL_H_MM / MAX_TOTAL_H_MM)


def build_full_name_reveal(spread_path, name_sequence, out_path, night_letters_dir=None):
    """
    name_sequence items are (key, case, variant, path) for real letters, or
    the literal string "-" for a dash. night_letters_dir, if given, is used
    to find the dash asset (this page is always a night scene).
    """
    upsize_flags_full = mark_upsize_flags(name_sequence)

    # build a unified list preserving order, tagging kind
    items = []
    for entry, up in zip(name_sequence, upsize_flags_full):
        if entry == "-":
            dash_path = None
            if night_letters_dir:
                candidate = f"{night_letters_dir}/{DASH_FILENAME}"
                import os
                if os.path.exists(candidate):
                    dash_path = candidate
            items.append(("-", None, None, dash_path, "dash", False))
        else:
            key, case, variant, path = entry
            items.append((key, case, variant, path, "letter", up))

    analyzed = []
    for key, case, variant, path, kind, up in items:
        cropped, aspect = analyze_letter(path)
        analyzed.append((key, case, cropped, aspect, up, kind))

    n = len(analyzed)
    sizing_n = max(n, REFERENCE_SLOTS)
    non_dash = [(a, up) for (_, _, _, a, up, kind) in analyzed if kind != "dash"]
    letters_for_sizing = list(non_dash)
    if len(letters_for_sizing) < REFERENCE_SLOTS:
        avg_aspect = sum(a for (a, up) in non_dash) / len(non_dash)
        letters_for_sizing += [(avg_aspect, False)] * (REFERENCE_SLOTS - len(letters_for_sizing))

    letter_ratios = [measure_letter_only_ratio(cropped) for (_, _, cropped, _, _, kind) in analyzed if kind != "dash"]
    actual_letter_ratio = sum(letter_ratios) / len(letter_ratios) if letter_ratios else TYPICAL_LETTER_VISUAL_RATIO

    n_real_letters = len(non_dash)
    target_frac = target_width_fraction(n_real_letters)
    target_w_mm = ZONE_W_MM * target_frac

    H, gap_mm = solve_height(letters_for_sizing, sizing_n, target_w_mm)
    letter_visual_h_mm = H * actual_letter_ratio

    widths = []
    for (key, case, cropped, aspect, up, kind) in analyzed:
        if kind == "dash":
            h_mm = letter_visual_h_mm * DASH_SIZE_MULT
            w_mm = h_mm * aspect
            max_w_mm = letter_visual_h_mm * DASH_MAX_WIDTH_MULT
            if w_mm > max_w_mm:
                scale = max_w_mm / w_mm
                h_mm *= scale
                w_mm = max_w_mm
        else:
            h_mm = H * UPSIZE_MULT if up else H
            w_mm = h_mm * aspect
        widths.append((h_mm, w_mm))

    total_w_mm = sum(w for (h, w) in widths) + gap_mm * (n - 1)

    # solve_height only ever caps from above (largest H that still fits under
    # target_w_mm). Short names, padded out to REFERENCE_SLOTS for sizing,
    # can undershoot that target considerably. If so, scale everything up
    # uniformly to actually reach it, rather than leaving the name looking
    # lost in a lot of empty space. Scaling H, gap, and every width by the
    # same factor preserves all relative proportions exactly.
    if total_w_mm < target_w_mm:
        scale = target_w_mm / total_w_mm
        H *= scale
        gap_mm *= scale
        letter_visual_h_mm *= scale
        widths = [(h * scale, w * scale) for (h, w) in widths]
        total_w_mm = target_w_mm

    x_cursor = ZONE_X0_MM + (ZONE_W_MM - total_w_mm) / 2

    baseline_y_mm = ZONE_Y0_MM + BASELINE_FRACTION * ZONE_H_MM
    center_y_mm = baseline_y_mm - letter_visual_h_mm / 2

    doc = fitz.open(spread_path)
    page = doc[0]
    for (key, case, cropped, aspect, up, kind), (h_mm, w_mm) in zip(analyzed, widths):
        if kind == "dash":
            top_y_mm = center_y_mm - h_mm / 2
            bottom_y_mm = center_y_mm + h_mm / 2
        else:
            top_y_mm = baseline_y_mm - h_mm
            bottom_y_mm = baseline_y_mm
        rect = fitz.Rect(x_cursor * MM_TO_PT, top_y_mm * MM_TO_PT,
                          (x_cursor + w_mm) * MM_TO_PT, bottom_y_mm * MM_TO_PT)
        tmp_path = f"/tmp/_reveal_{key}_{case}_{kind}.png"
        cropped.save(tmp_path)
        page.insert_image(rect, filename=tmp_path)
        x_cursor += w_mm + gap_mm

    doc.save(out_path)
    doc.close()
    print(f"Saved {out_path}: H={H:.1f}mm gap={gap_mm:.1f}mm total_w={total_w_mm:.1f}mm (zone={ZONE_W_MM:.1f}mm)")


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
