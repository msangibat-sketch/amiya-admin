"""
Letter sequence assembly: meet/give spreads with accumulation garland and
caption text, generalized to work for any name (not just the test case).
"""

import fitz
from PIL import Image
import numpy as np
import openpyxl
from .config import FONT_PLAYPEN

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
FONT_PATH = FONT_PLAYPEN
FONT_SIZE = 18
LINEHEIGHT = 30 / 18
LEFT_TEXT_X0 = BLEED_MM + MARGIN_MM
LEFT_TEXT_X1 = BLEED_MM + PAGE_TRIM_MM - MARGIN_MM
RIGHT_TEXT_X0 = BLEED_MM + PAGE_TRIM_MM + MARGIN_MM
RIGHT_TEXT_X1 = BLEED_MM + PAGE_TRIM_MM + PAGE_TRIM_MM - MARGIN_MM
TEXT_TOP_Y0 = BLEED_MM + MARGIN_MM
TEXT_BOX_H_MM = 40

# Night-scene letters: (key, case, variant) -> True. Text goes white, and
# accumulation letters swap to their white-string variant on these pages.
# Both meet and give spreads for a night-scene animal are night.
# NOTE: extend this set as more night-scene animals are added to the alphabet.
NIGHT_SET = {("a", "l", "2")}  # giraffe

TEXT_COLOR_DAY = (0.15, 0.1, 0.05)
TEXT_COLOR_NIGHT = (1, 1, 1)


def load_caption_data(xlsx_path):
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = rows[0]
    data = {}
    for row in rows[1:]:
        d = dict(zip(header, row))
        key = (str(d["key"]), d["gender"])
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


def draw_accumulation(page, given_letters_analyzed, full_layout, is_night, night_letters_dir):
    import os
    baseline_y_mm = ZONE_Y0_MM + BASELINE_FRACTION * ZONE_H_MM
    for (key, case, cropped, aspect), (x0_mm, w_mm, h_mm) in zip(given_letters_analyzed, full_layout):
        top_y_mm = baseline_y_mm - h_mm
        rect = fitz.Rect(x0_mm * MM_TO_PT, top_y_mm * MM_TO_PT,
                          (x0_mm + w_mm) * MM_TO_PT, baseline_y_mm * MM_TO_PT)

        use_cropped = cropped
        if is_night:
            # try every variant number for this key/case since we don't
            # carry the original variant here -- glob for a match instead
            import glob
            matches = glob.glob(os.path.join(night_letters_dir, f"{key}-{case}-*.png"))
            if matches:
                use_cropped, _ = analyze_letter(matches[0])
            else:
                print(f"[warning] no white-string asset for {key}-{case} in {night_letters_dir}, using day version on night page")

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


def resolve_spread_path(spreads_dir, key, case, variant, kind, gender):
    """
    Meet spreads don't show the letter itself, so their filename doesn't
    include case: spread-{key}-{variant}-meet-{gender}.pdf
    Give spreads do show the letter, so case is included:
    spread-{key}-{case}-{variant}-give-{gender}.pdf
    """
    import os
    if kind == "meet":
        name = f"spread-{key}-{variant}-meet-{gender}.pdf"
    else:
        name = f"spread-{key}-{case}-{variant}-give-{gender}.pdf"
    p = os.path.join(spreads_dir, name)
    if os.path.exists(p):
        return p
    raise FileNotFoundError(
        f"No spread file found for key={key} case={case} variant={variant} "
        f"kind={kind} gender={gender}. Expected: {name}"
    )


def build_letter_sequence(asset_root, letter_variants, gender, out_dir, caption_xlsx_path=None):
    """
    letter_variants: list of dicts [{"key":"a","case":"u","variant":"1"}, ...]
    representing the child's name in order.

    Returns list of paths to individual per-letter spread PDFs (meet+give
    pairs, in order) ready to be stitched into the full book by stitch.py.
    """
    import os
    spreads_dir = os.path.join(asset_root, "spreads")
    letters_dir = os.path.join(asset_root, "letters")
    night_letters_dir = os.path.join(asset_root, "letters_night")
    caption_xlsx_path = caption_xlsx_path or os.path.join(asset_root, "caption_text.xlsx")

    caption_data = load_caption_data(caption_xlsx_path)

    name_sequence = []
    for lv in letter_variants:
        letter_png = os.path.join(letters_dir, f"{lv['key']}-{lv['case']}-{lv['variant']}.png")
        name_sequence.append((lv['key'], lv['case'], lv['variant'], letter_png))

    analyzed_all = []
    for key, case, variant, path in name_sequence:
        cropped, aspect = analyze_letter(path)
        analyzed_all.append((key, case, cropped, aspect))
    full_layout = compute_fixed_layout(analyzed_all)

    os.makedirs(out_dir, exist_ok=True)
    output_paths = []
    given_count = 0
    first_give_done = False

    for idx, (key, case, variant, _) in enumerate(name_sequence):
        row = caption_data.get((key, gender))
        if row is None:
            raise KeyError(f"No caption text found for key={key} case={case} gender={gender}")
        is_night = (key, case, variant) in NIGHT_SET
        text_color = TEXT_COLOR_NIGHT if is_night else TEXT_COLOR_DAY

        # --- meet spread ---
        meet_src_path = resolve_spread_path(spreads_dir, key, case, variant, "meet", gender)
        meet_doc = fitz.open(meet_src_path)
        meet_page = meet_doc[0]
        normalize_spread(meet_page)
        insert_caption(meet_page, row["meet_text_left"].replace("\\n", "\n"), "left", text_color)
        insert_caption(meet_page, row["meet_text_right"].replace("\\n", "\n"), "right", text_color)
        meet_out = os.path.join(out_dir, f"letter_{idx:02d}_meet.pdf")
        meet_doc.save(meet_out)
        meet_doc.close()
        output_paths.append(meet_out)

        # --- give spread ---
        give_src_path = resolve_spread_path(spreads_dir, key, case, variant, "give", gender)
        give_doc = fitz.open(give_src_path)
        give_page = give_doc[0]
        normalize_spread(give_page)
        draw_accumulation(give_page, analyzed_all[:given_count], full_layout[:given_count],
                           is_night, night_letters_dir)
        side = "left" if not first_give_done else "right"
        insert_caption(give_page, row["give_text"].replace("\\n", "\n"), side, text_color)
        first_give_done = True
        given_count += 1
        give_out = os.path.join(out_dir, f"letter_{idx:02d}_give.pdf")
        give_doc.save(give_out)
        give_doc.close()
        output_paths.append(give_out)

    return output_paths
