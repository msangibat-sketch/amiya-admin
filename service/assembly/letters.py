"""
Full "Амияа" (girl) assembly test: real spreads + accumulation garland +
real caption text, combined into one print-ready PDF.
"""

import fitz
from PIL import Image
import numpy as np
import openpyxl

MM_TO_PT = 72 / 25.4
BLEED_MM = 3.0
PAGE_TRIM_MM = 210.0
MARGIN_MM = 20.0
SPREAD_W_MM = 426.0
SPREAD_H_MM = 216.0

# ---- accumulation zone (left page only) ----
ZONE_X0_MM = BLEED_MM + MARGIN_MM
ZONE_Y0_MM = BLEED_MM + MARGIN_MM
ZONE_W_MM = PAGE_TRIM_MM - 2 * MARGIN_MM   # 170
ZONE_H_MM = PAGE_TRIM_MM - 2 * MARGIN_MM   # 170

MAX_TOTAL_H_MM = 400.0
MIN_TOTAL_H_MM = 60.0
BASE_GAP_MM = 6.0
BASELINE_FRACTION = 0.4
UPPERCASE_MULT = 1.8
REFERENCE_N = 5

# ---- text ----
FONT_PATH = "/home/claude/fonts/playpen/static/PlaypenSans-Regular.ttf"
FONT_SIZE = 18
LINEHEIGHT = 30 / 18
LEFT_TEXT_X0 = BLEED_MM + MARGIN_MM
LEFT_TEXT_X1 = BLEED_MM + PAGE_TRIM_MM - MARGIN_MM
RIGHT_TEXT_X0 = BLEED_MM + PAGE_TRIM_MM + MARGIN_MM
RIGHT_TEXT_X1 = BLEED_MM + PAGE_TRIM_MM + PAGE_TRIM_MM - MARGIN_MM
TEXT_TOP_Y0 = BLEED_MM + MARGIN_MM
TEXT_BOX_H_MM = 40

GENDER = "girl"  # test as girl

# Night-scene letters: (key, case, variant) -> True. Text goes white, and
# accumulation letters swap to their white-string variant on these pages.
# Both meet and give spreads for a night-scene animal are night (confirmed).
NIGHT_SET = {("a", "l", "2")}  # giraffe: applies to both its meet and give spread

TEXT_COLOR_DAY = (0.15, 0.1, 0.05)
TEXT_COLOR_NIGHT = (1, 1, 1)

# Alt (white-string) letter assets live here once provided; falls back to
# the normal brown-string version with a warning if not yet supplied.
NIGHT_LETTERS_DIR = "letters_v2_night"

NAME_SEQUENCE = [
    ("a",  "u", "1", "letters_v2/letter-a-u-1.png"),
    ("m",  "l", "1", "letters_v2/letter-m-l-1.png"),
    ("i",  "l", "2", "letters_v2/letter-i-l-2.png"),
    ("ya", "l", "1", "letters_v2/letter-ya-l-1.png"),
    ("a",  "l", "2", "letters_v2/letter-a-l-2.png"),
]

SPREAD_SEQUENCE = [
    ("spreads/spread-a-1-meet-girl.pdf",   None, 0),
    ("spreads/spread-a-u-1-give-girl.pdf", 0,    0),
    ("spreads/spread-m-l-1-meet-girl.pdf", None, 1),
    ("spreads/spread-m-l-1-give-girl.pdf", 1,    1),
    ("spreads/spread-i-l-2-meet-girl.pdf", None, 2),
    ("spreads/spread-i-l-2-give-girl.pdf", 2,    2),
    ("spreads/spread-ya-l-1-meet-girl.pdf",None, 3),
    ("spreads/spread-ya-l-1-give-girl.pdf",3,    3),
    ("spreads/spread-a-l-2-meet-girl.pdf", None, 4),
    ("spreads/spread-a-l-2-give-girl.pdf", 4,    4),
]


def load_caption_data(xlsx_path):
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = rows[0]
    data = {}
    for row in rows[1:]:
        d = dict(zip(header, row))
        key = (str(d["key"]), str(d["case"]), d["gender"])
        data[key] = d
    return data


def normalize_spread(page):
    rect = page.rect
    w_mm = rect.width / MM_TO_PT
    if abs(w_mm - SPREAD_W_MM) > 0.5:
        excess_pt = rect.width - SPREAD_W_MM * MM_TO_PT
        trim = excess_pt / 2
        page.set_cropbox(fitz.Rect(rect.x0 + trim, rect.y0, rect.x1 - trim, rect.y1))


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


def solve_lowercase_height(letters, count_for_sizing):
    for candidate in [x / 10 for x in range(int(MAX_TOTAL_H_MM * 10), int(MIN_TOTAL_H_MM * 10) - 1, -1)]:
        gap = BASE_GAP_MM * (candidate / MAX_TOTAL_H_MM)
        total_w = sum((candidate * UPPERCASE_MULT if case == "u" else candidate) * aspect
                      for case, aspect in letters) + (count_for_sizing - 1) * gap
        if total_w <= ZONE_W_MM:
            return candidate, gap
    return MIN_TOTAL_H_MM, BASE_GAP_MM * (MIN_TOTAL_H_MM / MAX_TOTAL_H_MM)


def compute_fixed_layout(analyzed):
    n_total = len(analyzed)
    sizing_n = max(n_total, REFERENCE_N)
    letters_for_sizing = [(case, aspect) for (_, case, _, aspect) in analyzed]
    if n_total < REFERENCE_N:
        avg_aspect = sum(a for (_, a) in letters_for_sizing) / len(letters_for_sizing)
        letters_for_sizing += [("l", avg_aspect)] * (REFERENCE_N - n_total)
    H, gap_mm = solve_lowercase_height(letters_for_sizing, sizing_n)
    layout = []
    x_cursor = ZONE_X0_MM
    for (key, case, cropped, aspect) in analyzed:
        h_mm = H * UPPERCASE_MULT if case == "u" else H
        w_mm = h_mm * aspect
        layout.append((x_cursor, w_mm, h_mm))
        x_cursor += w_mm + gap_mm
    return layout


def draw_accumulation(page, given_letters_analyzed, full_layout, is_night=False):
    import os
    baseline_y_mm = ZONE_Y0_MM + BASELINE_FRACTION * ZONE_H_MM
    for (key, case, cropped, aspect), (x0_mm, w_mm, h_mm) in zip(given_letters_analyzed, full_layout):
        top_y_mm = baseline_y_mm - h_mm
        rect = fitz.Rect(x0_mm * MM_TO_PT, top_y_mm * MM_TO_PT,
                          (x0_mm + w_mm) * MM_TO_PT, baseline_y_mm * MM_TO_PT)

        use_cropped = cropped
        if is_night:
            # attempt to load a white-string variant of this same letter
            variant_guess = None
            for k2, c2, v2, p2 in NAME_SEQUENCE:
                if k2 == key and c2 == case:
                    variant_guess = v2
                    break
            night_path = f"{NIGHT_LETTERS_DIR}/letter-{key}-{case}-{variant_guess}.png"
            if os.path.exists(night_path):
                use_cropped, _ = analyze_letter(night_path)
            else:
                print(f"[warning] no white-string asset for {key}-{case} at {night_path}, using day version on night page")

        tmp_path = f"/tmp/_final_{key}_{case}_{'night' if is_night else 'day'}.png"
        use_cropped.save(tmp_path)
        page.insert_image(rect, filename=tmp_path)


def insert_caption(page, text, side, color=TEXT_COLOR_DAY):
    x0 = LEFT_TEXT_X0 if side == "left" else RIGHT_TEXT_X0
    x1 = LEFT_TEXT_X1 if side == "left" else RIGHT_TEXT_X1
    rect = fitz.Rect(x0 * MM_TO_PT, TEXT_TOP_Y0 * MM_TO_PT,
                      x1 * MM_TO_PT, (TEXT_TOP_Y0 + TEXT_BOX_H_MM) * MM_TO_PT)
    page.insert_textbox(rect, text, fontsize=FONT_SIZE, fontfile=FONT_PATH, fontname="playpen",
                         align=fitz.TEXT_ALIGN_CENTER, lineheight=LINEHEIGHT, color=color)


def build_full_test(output_path):
    caption_data = load_caption_data("data/caption_text_filled.xlsx")

    # pre-analyze all 5 letters once, compute the fixed layout once
    analyzed_all = []
    for key, case, variant, path in NAME_SEQUENCE:
        cropped, aspect = analyze_letter(path)
        analyzed_all.append((key, case, cropped, aspect))
    full_layout = compute_fixed_layout(analyzed_all)

    out_doc = fitz.open()
    given_count = 0
    first_give_done = False

    for spread_path, gives_idx, letter_idx in SPREAD_SEQUENCE:
        src = fitz.open(spread_path)
        src_page = src[0]
        normalize_spread(src_page)
        out_doc.insert_pdf(src, from_page=0, to_page=0)
        page = out_doc[-1]
        page.set_cropbox(src_page.cropbox)

        key, case, variant, _ = NAME_SEQUENCE[letter_idx]
        row = caption_data[(key, case, GENDER)]
        is_night = (key, case, variant) in NIGHT_SET
        text_color = TEXT_COLOR_NIGHT if is_night else TEXT_COLOR_DAY

        if gives_idx is None:
            # meet spread: two text blocks
            insert_caption(page, row["meet_text_left"].replace("\\n", "\n"), "left", text_color)
            insert_caption(page, row["meet_text_right"].replace("\\n", "\n"), "right", text_color)
        else:
            # give spread: accumulation garland (letters given BEFORE this one) + give text
            draw_accumulation(page, analyzed_all[:given_count], full_layout[:given_count], is_night)
            side = "left" if not first_give_done else "right"
            insert_caption(page, row["give_text"].replace("\\n", "\n"), side, text_color)
            first_give_done = True
            given_count += 1

    out_doc.save(output_path)
    print(f"Saved {output_path} ({len(out_doc)} pages)")


if __name__ == "__main__":
    import os
    os.chdir("/home/claude/amiyaa_test")
    build_full_test("/home/claude/amiyaa_test/amiyaa_FULL_test.pdf")
