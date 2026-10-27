"""
Letter sequence assembly: meet/give spreads with accumulation garland and
caption text, generalized to work for any name (not just the test case).
"""

import fitz
import openpyxl
from .config import FONT_PLAYPEN
from .letter_art import load_letter_art, draw_hanging_letter, draw_centered_piece

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

BASELINE_Y_MM = 90.0  # letter bottoms sit exactly here, measured from the true top edge of the page -- confirmed by visual comparison against real spread art, not the 3/8 line
DASH_BASELINE_REFERENCE_MM = 89.0  # frozen reference so the dash's position doesn't move when BASELINE_Y_MM changes (lowered 6mm from 83.0 per visual check)
# All sizes below are relative to the LOWERCASE GLYPH height (the illustrated
# letter only, thread excluded) -- see letter_art.py for why.
UPPERCASE_MULT = 1.8   # capital glyph height = this x lowercase glyph height
GAP_MULT = 0.085       # space between letters = this x lowercase glyph height
DASH_SIZE_MULT = 0.6   # dash height = this x lowercase glyph height
DASH_MAX_WIDTH_MULT = 0.8  # dash max width = this x lowercase glyph height
LETTER_TOP_MIN_MM = BLEED_MM + MARGIN_MM  # no glyph may rise above the top margin
THREAD_TOP_Y_MM = -1.0  # threads are drawn up to here: just past the top (bleed) edge
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


def normalize_variant(variant):
    """
    Variant can arrive as an int, a float (2.0), or a string ("2" or "2.0")
    depending on whether it came from an Excel cell or the order's JSON
    payload. Always normalize to a clean integer string so lookups match
    regardless of source -- see the /animal-names endpoint for the same fix
    applied to that lookup.
    """
    return str(int(float(variant)))


def load_caption_data(xlsx_path):
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = rows[0]
    data = {}
    for row in rows[1:]:
        d = dict(zip(header, row))
        if d.get("key") is None or d.get("variant") is None or d.get("gender") is None:
            # blank/incomplete row (e.g. a stray trailing row in the sheet) --
            # nothing usable here, skip rather than crash
            continue
        key = (str(d["key"]), normalize_variant(d["variant"]), d["gender"])
        data[key] = d
    return data


def normalize_spread(page):
    rect = page.rect
    w_mm = rect.width / MM_TO_PT
    if abs(w_mm - SPREAD_W_MM) > 0.5:
        excess_pt = rect.width - SPREAD_W_MM * MM_TO_PT
        trim = excess_pt / 2
        page.set_cropbox(fitz.Rect(rect.x0 + trim, rect.y0, rect.x1 - trim, rect.y1))


def size_mult_for(case, kind):
    if kind == "dash":
        return DASH_SIZE_MULT
    return UPPERCASE_MULT if case == "u" else 1.0


def compute_fixed_layout(analyzed):
    """
    analyzed: list of (key, case, art, variant, kind) where art is a LetterArt.
    Returns (layout, g): layout is one (x0_mm, w_mm, h_mm) per item -- h_mm
    being the GLYPH height -- and g is the lowercase glyph height in mm.

    The garland is solved in one step: every letter's width is
    g x size_mult x glyph_aspect, plus a gap proportional to g, so the
    largest g that fits ZONE_W_MM is a straight division.
    """
    if not analyzed:
        return [], 0.0

    # Dashes are deliberately excluded from the sizing pass: they render
    # tiny and capped (see below), so letting them occupy a real slot + gap
    # here would shrink every other letter just to make room for something
    # that barely takes any visible space.
    letters_only = [a for a in analyzed if a[4] != "dash"]
    n_letters = len(letters_only)
    sizing_n = max(n_letters, REFERENCE_N)

    units = [size_mult_for(case, kind) * art.aspect for (_, case, art, _, kind) in letters_only]
    if n_letters < REFERENCE_N:
        # short garlands are sized as if REFERENCE_N letters were there, so the
        # first pages don't start out huge and then visibly shrink
        avg_aspect = sum(art.aspect for (_, _, art, _, _) in letters_only) / n_letters
        units += [avg_aspect] * (REFERENCE_N - n_letters)
    total_units = sum(units) + (sizing_n - 1) * GAP_MULT

    g = ZONE_W_MM / total_units
    # never let the tallest glyph rise above the top margin
    tallest_mult = max(size_mult_for(case, kind) for (_, case, _, _, kind) in letters_only)
    g = min(g, (BASELINE_Y_MM - LETTER_TOP_MIN_MM) / tallest_mult)
    gap_mm = GAP_MULT * g

    layout = []
    x_cursor = ZONE_X0_MM
    for (key, case, art, variant, kind) in analyzed:
        if kind == "dash":
            h_mm = g * DASH_SIZE_MULT
            w_mm = h_mm * art.aspect
            max_w_mm = g * DASH_MAX_WIDTH_MULT
            if w_mm > max_w_mm:
                h_mm *= max_w_mm / w_mm
                w_mm = max_w_mm
        else:
            h_mm = g * size_mult_for(case, kind)
            w_mm = h_mm * art.aspect
        layout.append((x_cursor, w_mm, h_mm))
        x_cursor += w_mm + gap_mm
    return layout, g


def draw_accumulation(page, given_items, full_layout, g, is_night, night_letters_dir):
    import os
    # dash centers on the FROZEN reference, not the current letter baseline,
    # so adjusting BASELINE_Y_MM moves the letters without dragging the dash along
    dash_center_y_mm = DASH_BASELINE_REFERENCE_MM - g / 2

    for (key, case, art, variant, kind), (x0_mm, w_mm, h_mm) in zip(given_items, full_layout):
        use_art = art
        if is_night:
            if kind == "dash":
                night_path = os.path.join(night_letters_dir, DASH_FILENAME)
            else:
                night_path = os.path.join(night_letters_dir, f"{key}-{case}-{variant}.png")
            if os.path.exists(night_path):
                use_art = load_letter_art(night_path)
            else:
                print(f"[warning] no white-string asset for {key}-{case}-{variant} "
                      f"(kind={kind}) at {night_path}, using day version on night page")

        if kind == "dash":
            # vertically centered in the gap, not baseline-anchored, no string
            w = h_mm * use_art.aspect
            draw_centered_piece(page, use_art, x0_mm, w, h_mm, dash_center_y_mm, MM_TO_PT)
        else:
            # Sized by GLYPH height, so the day and night files of the same
            # letter come out identical even though their threads are trimmed
            # differently; the thread is lengthened to reach the top edge.
            draw_hanging_letter(page, use_art, x0_mm, h_mm, BASELINE_Y_MM,
                                THREAD_TOP_Y_MM, MM_TO_PT)


def insert_caption(page, text, side, color=TEXT_COLOR_DAY):
    x0 = LEFT_TEXT_X0 if side == "left" else RIGHT_TEXT_X0
    x1 = LEFT_TEXT_X1 if side == "left" else RIGHT_TEXT_X1
    box_w_mm = x1 - x0
    rect = fitz.Rect(x0 * MM_TO_PT, TEXT_TOP_Y0 * MM_TO_PT,
                      x1 * MM_TO_PT, (TEXT_TOP_Y0 + TEXT_BOX_H_MM) * MM_TO_PT)

    # If any line is wider than the box, PyMuPDF word-wraps it onto an
    # extra visual line -- which can then overflow the box's height
    # entirely. When that happens insert_textbox silently renders
    # NOTHING at all (not even a clipped partial render), so a caption
    # just a fraction of a mm too wide can vanish completely. Shrink the
    # font in small steps until every line actually fits, rather than
    # risk that -- this only ever affects the rare caption that's
    # borderline too long; everything else renders at FONT_SIZE unchanged.
    font = fitz.Font(fontfile=FONT_PATH)
    fontsize = FONT_SIZE
    while fontsize > 14:
        widest_line_mm = max(font.text_length(line, fontsize=fontsize) / MM_TO_PT
                              for line in text.split("\n"))
        if widest_line_mm <= box_w_mm:
            break
        fontsize -= 0.5
    else:
        print(f"[warning] caption still doesn't fit at {fontsize}pt, rendering anyway: {text!r}")

    lineheight = (FONT_SIZE * LINEHEIGHT) / fontsize  # keep the same absolute leading in mm
    page.insert_textbox(rect, text, fontsize=fontsize, fontfile=FONT_PATH, fontname="playpen",
                         align=fitz.TEXT_ALIGN_CENTER, lineheight=lineheight, color=color)


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


def build_letter_sequence(asset_root, letter_variants, gender, out_dir, caption_xlsx_path=None, max_letters=None):
    """
    letter_variants: list of dicts [{"key":"a","case":"u","variant":"1"}, ...]
    representing the child's name in order. A dash is represented as
    {"key": "-", "case": None, "variant": None}.

    Returns list of paths to individual per-letter spread PDFs (meet+give
    pairs, in order) ready to be stitched into the full book by stitch.py.
    Dash entries contribute no page of their own -- they just become part
    of the accumulation garland from that point onward.

    max_letters: stop after this many letters (the website preview builds
    only the first two). The pages it does build are identical to the full
    book's, since each give spread's garland only uses letters given so far.
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
        analyzed_all.append((key, case, load_letter_art(path), variant, kind))

    os.makedirs(out_dir, exist_ok=True)
    output_paths = []
    given_count = 0
    first_give_done = False
    page_idx = 0

    for key, case, variant, _, kind in name_sequence:
        if max_letters is not None and page_idx >= max_letters:
            break
        if kind == "dash":
            # no page of its own -- just becomes part of the accumulation
            # for whatever letter comes next
            given_count += 1
            continue

        row = caption_data.get((key, normalize_variant(variant), gender))
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
        given_so_far = analyzed_all[:given_count]
        if given_so_far:
            page_layout, page_g = compute_fixed_layout(given_so_far)
            draw_accumulation(give_page, given_so_far, page_layout,
                               page_g, is_night, night_letters_dir)
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
