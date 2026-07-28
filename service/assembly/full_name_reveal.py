import fitz
from PIL import Image
import numpy as np

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


def solve_height(letters_aspect_upsize, count_for_sizing):
    for candidate in [x / 10 for x in range(int(MAX_TOTAL_H_MM * 10), int(MIN_TOTAL_H_MM * 10) - 1, -1)]:
        gap = BASE_GAP_MM * (candidate / MAX_TOTAL_H_MM)
        total_w = sum((candidate * UPSIZE_MULT if up else candidate) * aspect
                      for aspect, up in letters_aspect_upsize) + (count_for_sizing - 1) * gap
        if total_w <= ZONE_W_MM:
            return candidate, gap
    return MIN_TOTAL_H_MM, BASE_GAP_MM * (MIN_TOTAL_H_MM / MAX_TOTAL_H_MM)


def build_full_name_reveal(spread_path, name_sequence, out_path):
    # filter out dash markers for the actual rendered letters, keep upsize flags aligned
    upsize_flags_full = mark_upsize_flags(name_sequence)
    letters = [(item, up) for item, up in zip(name_sequence, upsize_flags_full) if item != "-"]

    analyzed = []
    for (key, case, variant, path), up in letters:
        cropped, aspect = analyze_letter(path)
        analyzed.append((key, case, cropped, aspect, up))

    n = len(analyzed)
    sizing_n = max(n, REFERENCE_SLOTS)
    letters_for_sizing = [(a, up) for (_, _, _, a, up) in analyzed]
    if n < REFERENCE_SLOTS:
        avg_aspect = sum(a for (a, up) in letters_for_sizing) / len(letters_for_sizing)
        letters_for_sizing += [(avg_aspect, False)] * (REFERENCE_SLOTS - n)

    H, gap_mm = solve_height(letters_for_sizing, sizing_n)

    # compute each rendered letter's width, then center the whole group in ZONE_W_MM
    widths = []
    for (key, case, cropped, aspect, up) in analyzed:
        h_mm = H * UPSIZE_MULT if up else H
        w_mm = h_mm * aspect
        widths.append((h_mm, w_mm))
    total_w_mm = sum(w for (h, w) in widths) + gap_mm * (n - 1)
    x_cursor = ZONE_X0_MM + (ZONE_W_MM - total_w_mm) / 2

    baseline_y_mm = ZONE_Y0_MM + BASELINE_FRACTION * ZONE_H_MM

    doc = fitz.open(spread_path)
    page = doc[0]
    for (key, case, cropped, aspect, up), (h_mm, w_mm) in zip(analyzed, widths):
        top_y_mm = baseline_y_mm - h_mm
        rect = fitz.Rect(x_cursor * MM_TO_PT, top_y_mm * MM_TO_PT,
                          (x_cursor + w_mm) * MM_TO_PT, baseline_y_mm * MM_TO_PT)
        tmp_path = f"/tmp/_reveal_{key}_{case}.png"
        cropped.save(tmp_path)
        page.insert_image(rect, filename=tmp_path)
        x_cursor += w_mm + gap_mm

    doc.save(out_path)
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
