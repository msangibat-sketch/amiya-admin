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
BASELINE_Y_MM = 90.0  # letter bottoms sit exactly here, measured from the true top edge of the page
DASH_BASELINE_REFERENCE_MM = 83.0  # frozen reference so the dash's position doesn't move when BASELINE_Y_MM changes
UPPERCASE_MULT = 1.8
DASH_SIZE_MULT = 0.6   # dash's height relative to the VISIBLE letter glyph (not the full string+letter image)
DASH_MAX_WIDTH_MULT = 0.8  # dash's max width relative to the visible letter glyph height
TYPICAL_LETTER_VISUAL_RATIO = 0.17  # visible glyph is roughly this fraction of the full H (rest is string)
DASH_FILENAME = "hyphen-1-u.png"  # single shared file, no gender/variant needed
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
# Night/day is now read directly from the caption spreadsheet's `night_day`
# column (per key+variant, gender-independent) -- no separate list to maintain.

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
        key = (str(d["key"]), str(d["variant"]), d["gender"])
        data[key] = d
    return data


def normalize_spread(page):
    rect = page.rect
    w_mm = rect.width / MM_TO_PT
    if abs(w_mm - SPREAD_W_MM) > 0.5:
        excess_pt = rect.width - SPREAD_W_MM * MM_TO_PT
        trim = excess_pt / 2
        page.set_cropbox(fitz.Rect(rect.x0 + trim, rect.y0, rect.x1 - trim, rect.y1))


def measure_letter_only_ratio(cropped):
    """What fraction of this cropped (string+letter) image is actually the
    visible letter glyph, measured directly from the image rather than
    assumed -- more accurate than a fixed average constant, especially at
    larger render sizes where small ratio errors become visible mm-shifts."""
    arr = np.array(cropped)
    alpha = arr[:, :, 3]
    widths = (alpha > 10).sum(axis=1)
    max_w = widths.max()
    letter_rows = np.where(widths > max_w * 0.15)[0]
    letter_top_row = int(letter_rows.min())
    total_h = cropped.height
    return (total_h - letter_top_row) / total_h


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


def solve_lowercase_height(items, count_for_sizing):
    """items: list of (size_mult, aspect) tuples."""
    for candidate in [x / 10 for x in range(int(MAX_TOTAL_H_MM * 10), int(MIN_TOTAL_H_MM * 10) - 1, -1)]:
        gap = BASE_GAP_MM * (candidate / MAX_TOTAL_H_MM)
        total_w = sum(candidate * size_mult * aspect for size_mult, aspect in items) + (count_for_sizing - 1) * gap
        if total_w <= ZONE_W_MM:
            return candidate, gap
    return MIN_TOTAL_H_MM, BASE_GAP_MM * (MIN_TOTAL_H_MM / MAX_TOTAL_H_MM)


def size_mult_for(case, kind, actual_letter_ratio=TYPICAL_LETTER_VISUAL_RATIO):
    if kind == "dash":
        return actual_letter_ratio * DASH_SIZE_MULT
    return UPPERCASE_MULT if case == "u" else 1.0


def compute_fixed_layout(analyzed):
    """analyzed: list of (key, case, cropped, aspect, variant, kind)."""
    n_total = len(analyzed)
    sizing_n = max(n_total, REFERENCE_N)

    letter_ratios = [measure_letter_only_ratio(cropped) for (_, _, cropped, _, _, kind) in analyzed if kind != "dash"]
    actual_letter_ratio = sum(letter_ratios) / len(letter_ratios) if letter_ratios else TYPICAL_LETTER_VISUAL_RATIO

    items_for_sizing = [(size_mult_for(case, kind, actual_letter_ratio), aspect) for (_, case, _, aspect, _, kind) in analyzed]
    if n_total < REFERENCE_N:
        avg_aspect = sum(a for (_, a) in items_for_sizing) / len(items_for_sizing)
        items_for_sizing += [(1.0, avg_aspect)] * (REFERENCE_N - n_total)
    H, gap_mm = solve_lowercase_height(items_for_sizing, sizing_n)
    layout = []
    x_cursor = ZONE_X0_MM
    letter_visual_h_mm = H * actual_letter_ratio
    for (key, case, cropped, aspect, variant, kind) in analyzed:
        if kind == "dash":
            h_mm = letter_visual_h_mm * DASH_SIZE_MULT
            w_mm = h_mm * aspect
            max_w_mm = letter_visual_h_mm * DASH_MAX_WIDTH_MULT
            if w_mm > max_w_mm:
                scale = max_w_mm / w_mm
                h_mm *= scale
                w_mm = max_w_mm
        else:
            h_mm = H * size_mult_for(case, kind, actual_letter_ratio)
            w_mm = h_mm * aspect
        layout.append((x_cursor, w_mm, h_mm))
        x_cursor += w_mm + gap_mm
    return layout, H, actual_letter_ratio


def draw_accumulation(page, given_items, full_layout, reference_H, actual_letter_ratio, is_night, night_letters_dir):
    import os
    baseline_y_mm = BASELINE_Y_MM
    letter_visual_h_mm = reference_H * actual_letter_ratio
    # dash centers on the FROZEN reference, not the current letter baseline,
    # so adjusting BASELINE_Y_MM moves the letters without dragging the dash along
    dash_center_y_mm = DASH_BASELINE_REFERENCE_MM - letter_visual_h_mm / 2

    for (key, case, cropped, aspect, variant, kind), (x0_mm, w_mm, h_mm) in zip(given_items, full_layout):
        if kind == "dash":
            # vertically centered in the gap, not baseline-anchored, no string
            top_y_mm = dash_center_y_mm - h_mm / 2
            bottom_y_mm = dash_center_y_mm + h_mm / 2
        else:
            top_y_mm = baseline_y_mm - h_mm
            bottom_y_mm = baseline_y_mm

        rect = fitz.Rect(x0_mm * MM_TO_PT, top_y_mm * MM_TO_PT,
                          (x0_mm + w_mm) * MM_TO_PT, bottom_y_mm * MM_TO_PT)

        use_cropped = cropped
        if is_night:
            if kind == "dash":
                night_path = os.path.join(night_letters_dir, DASH_FILENAME)
            else:
                night_path = os.path.join(night_letters_dir, f"{key}-{case}-{variant}.png")
            if os.path.exists(night_path):
                use_cropped, _ = analyze_letter(night_path)
            else:
                print(f"[warning] no white-string asset for {key}-{case}-{variant} "
                      f"(kind={kind}) at {night_path}, using day version on night page")

        tmp_path = f"/tmp/_final_{key}_{case}_{variant}_{kind}_{'night' if is_night else 'day'}.png"
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

    For give spreads, if the requested case's artwork doesn't exist, falls
    back to the other case -- many letters look identical upper/lower, so
    only one file needs to be uploaded unless they genuinely differ.
    """
    import os
    if kind == "meet":
        name = f"spread-{key}-{variant}-meet-{gender}.pdf"
        p = os.path.join(spreads_dir, name)
        if os.path.exists(p):
            return p
        raise FileNotFoundError(
            f"No spread file found for key={key} variant={variant} "
            f"kind=meet gender={gender}. Expected: {name}"
        )

    name = f"spread-{key}-{case}-{variant}-give-{gender}.pdf"
    p = os.path.join(spreads_dir, name)
    if os.path.exists(p):
        return p

    fallback_case = "l" if case == "u" else "u"
    fallback_name = f"spread-{key}-{fallback_case}-{variant}-give-{gender}.pdf"
    fallback_p = os.path.join(spreads_dir, fallback_name)
    if os.path.exists(fallback_p):
        print(f"[fallback] {name} not found -- using {fallback_name} instead "
              f"(same variant, other case's art reused)")
        return fallback_p

    raise FileNotFoundError(
        f"No spread file found for key={key} case={case} variant={variant} "
        f"kind=give gender={gender}. Tried: {name}, {fallback_name}"
    )


def build_letter_sequence(asset_root, letter_variants, gender, out_dir, caption_xlsx_path=None):
    """
    letter_variants: list of dicts [{"key":"a","case":"u","variant":"1"}, ...]
    representing the child's name in order. A dash is represented as
    {"key": "-", "case": None, "variant": None}.

    Returns list of paths to individual per-letter spread PDFs (meet+give
    pairs, in order) ready to be stitched into the full book by stitch.py.
    Dash entries contribute no page of their own -- they just become part
    of the accumulation garland from that point onward.
    """
    import os
    spreads_dir = os.path.join(asset_root, "spreads")
    letters_dir = os.path.join(asset_root, "letters")
    night_letters_dir = os.path.join(asset_root, "letters_night")
    caption_xlsx_path = caption_xlsx_path or os.path.join(asset_root, "caption_text.xlsx")

    caption_data = load_caption_data(caption_xlsx_path)

    name_sequence = []
    for lv in letter_variants:
        if lv['key'] == '-':
            dash_png = os.path.join(letters_dir, DASH_FILENAME)
            name_sequence.append(('-', None, None, dash_png, 'dash'))
        else:
            letter_png = os.path.join(letters_dir, f"{lv['key']}-{lv['case']}-{lv['variant']}.png")
            name_sequence.append((lv['key'], lv['case'], lv['variant'], letter_png, 'letter'))

    analyzed_all = []
    for key, case, variant, path, kind in name_sequence:
        cropped, aspect = analyze_letter(path)
        analyzed_all.append((key, case, cropped, aspect, variant, kind))
    full_layout, reference_H, actual_letter_ratio = compute_fixed_layout(analyzed_all)

    os.makedirs(out_dir, exist_ok=True)
    output_paths = []
    given_count = 0
    first_give_done = False
    page_idx = 0

    for key, case, variant, _, kind in name_sequence:
        if kind == "dash":
            # no page of its own -- just becomes part of the accumulation
            # for whatever letter comes next
            given_count += 1
            continue

        row = caption_data.get((key, variant, gender))
        if row is None:
            raise KeyError(f"No caption text found for key={key} variant={variant} gender={gender}")
        is_night = str(row.get("night_day", "day")).strip().lower() == "night"
        text_color = TEXT_COLOR_NIGHT if is_night else TEXT_COLOR_DAY

        # --- meet spread ---
        meet_src_path = resolve_spread_path(spreads_dir, key, case, variant, "meet", gender)
        meet_doc = fitz.open(meet_src_path)
        meet_page = meet_doc[0]
        normalize_spread(meet_page)
        insert_caption(meet_page, row["meet_text_left"].replace("\\n", "\n"), "left", text_color)
        insert_caption(meet_page, row["meet_text_right"].replace("\\n", "\n"), "right", text_color)
        meet_out = os.path.join(out_dir, f"letter_{page_idx:02d}_meet.pdf")
        meet_doc.save(meet_out)
        meet_doc.close()
        output_paths.append(meet_out)

        # --- give spread ---
        give_src_path = resolve_spread_path(spreads_dir, key, case, variant, "give", gender)
        give_doc = fitz.open(give_src_path)
        give_page = give_doc[0]
        normalize_spread(give_page)
        draw_accumulation(give_page, analyzed_all[:given_count], full_layout[:given_count],
                           reference_H, actual_letter_ratio, is_night, night_letters_dir)
        side = "left" if not first_give_done else "right"
        insert_caption(give_page, row["give_text"].replace("\\n", "\n"), side, text_color)
        first_give_done = True
        given_count += 1
        give_out = os.path.join(out_dir, f"letter_{page_idx:02d}_give.pdf")
        give_doc.save(give_out)
        give_doc.close()
        output_paths.append(give_out)
        page_idx += 1

    return output_paths
