"""
Cover generation for Amiya Publishing hardcover books.

Layout is safe-zone-first: the 207x218mm safe zone, 20mm wrap margin, and
13mm groove are the fixed constants. Panel width (240mm, symmetric front
and back) is derived from those. Only the spine width varies, based on
total page count -- which itself is derived purely from the child's real
letter count (dashes excluded), via the same formula as the URL Generator
/ Page Calculator tool. This means a cover can be generated independently
of the interior book PDF -- it never needs to inspect print_ready.pdf.

Canvas width is NOT fixed -- it grows/shrinks with spine width:
    total_width = 240 + spine_width + 240

The source template PDFs (covers/boy_cover.pdf, covers/girl_cover.pdf)
are built for a 15mm spine (30-36pg bracket). Panel art is sliced out and
copied pixel-for-pixel (just resampled to the true 240mm panel width);
only the spine strip between them is stretched/compressed to the actual
target width. The title and logo are NOT baked into the source templates
-- both are rendered/placed programmatically, centered on each panel's
own safe-zone center, so they stay correctly positioned regardless of
spine width.
"""
import os
import fitz
from PIL import Image, ImageDraw, ImageFont

MM_TO_PT = 72 / 25.4
DPI = 300

# --- safe-zone-first constants ---
SAFE_W_MM = 207.0
SAFE_H_MM = 218.0
MARGIN_MM = 20.0
GROOVE_MM = 13.0
PANEL_W_MM = SAFE_W_MM + MARGIN_MM + GROOVE_MM  # 240.0, symmetric both sides
TOTAL_H_MM = SAFE_H_MM + 2 * MARGIN_MM  # 258.0, fixed regardless of page count

# Where the spine sits in the SOURCE template files specifically (used only
# for slicing the source image -- downstream layout uses PANEL_W_MM instead)
SOURCE_SPINE_START_MM = 242.0
SOURCE_SPINE_END_MM = 257.0

# --- title text style ---
FONT_SIZE_PT = 55
TRACKING_1000EM = -7  # Photoshop tracking units: -7/1000 em
STROKE_PX_AT_300DPI = 3
TITLE_TOP_MM = 32.44
LEADING_PT = FONT_SIZE_PT * 1.2  # Photoshop "Auto" leading ~= 120% of size
STROKE_COLOR = {"boy": (249, 170, 140), "girl": (246, 171, 197)}  # f9aa8c / f6abc5

# --- logo ---
LOGO_W_MM = 23.2
LOGO_H_MM = 15.66
LOGO_TOP_MM = 212.55

# --- page count -> spine width ---
# 14 fixed pages (hello, dedication, intro, gathering, farewell, night
# scene, full-name-reveal, etc) + 4 pages per letter (meet + give spread,
# 2 single pages each) + 2. Matches the URL Generator / Page Calculator
# tool exactly; verified against a real order (8 letters -> 48 pages).
def calc_total_pages(n_letters):
    return 14 + n_letters * 4 + 2


SPINE_TABLE_MM = {
    12: 8, 14: 8,
    16: 9, 18: 9,
    20: 12, 22: 12, 24: 12, 26: 12, 28: 12,
    30: 15, 32: 15, 34: 15, 36: 15,
    38: 16.5,
    40: 17,
    42: 17.5, 44: 17.5,
    46: 18,
    48: 18.5, 50: 18.5,
    52: 19, 54: 19,
    56: 20,
    58: 20.5,
    60: 21, 62: 21,
    64: 21.5,
}


def get_spine_width_mm(n_letters):
    pages = calc_total_pages(n_letters)
    if pages in SPINE_TABLE_MM:
        return SPINE_TABLE_MM[pages], pages
    known_pages = sorted(SPINE_TABLE_MM)
    for p in known_pages:
        if p >= pages:
            print(f"[warning] {pages} pages has no exact table entry, using {p}-page bracket instead")
            return SPINE_TABLE_MM[p], pages
    raise ValueError(f"{pages} pages exceeds the spine table's range (max {known_pages[-1]}) -- "
                      f"need the printer's spine width for this bracket")


def draw_title(page, line1, line2, gender, font_path, cx_mm, top_mm):
    """
    Draws the title as real vector text directly on the page -- not a
    rasterized PNG. A rasterized title, even supersampled, is still a
    fixed-resolution grid of pixels: zoom in far enough (as happens
    naturally in Acrobat, or on a large print) and the curve edges show
    a visible staircase. Vector text has no such limit -- it stays
    perfectly smooth at any zoom level or print size, because it's math,
    not pixels.

    fitz.Page.insert_text's render_mode=2 draws fill+stroke together
    natively (a real PDF text rendering mode). border_width is a
    fraction of fontsize, not an absolute unit -- calibrated here so the
    stroke's physical width matches the original 3px-at-300dpi spec
    (0.72pt) regardless of what fontsize is actually used.
    """
    font = fitz.Font(fontfile=font_path)
    fontsize = FONT_SIZE_PT
    tracking = TRACKING_1000EM / 1000 * fontsize
    stroke_color = tuple(c / 255 for c in STROKE_COLOR[gender])
    border_width = (STROKE_PX_AT_300DPI / 300 * 72) / fontsize  # -> physical 0.72pt stroke

    def line_width(line):
        w = sum(font.text_length(ch, fontsize=fontsize) + tracking for ch in line)
        return w - tracking

    def draw_line(line, y_mm):
        w_pt = line_width(line)
        x_pt = cx_mm * MM_TO_PT - w_pt / 2
        y_pt = y_mm * MM_TO_PT
        for ch in line:
            page.insert_text((x_pt, y_pt), ch, fontsize=fontsize, fontfile=font_path,
                              fontname="lazydog", fill=(1, 1, 1), color=stroke_color,
                              border_width=border_width, render_mode=2)
            x_pt += font.text_length(ch, fontsize=fontsize) + tracking

    # insert_text's y is the text BASELINE, not the top -- offset down by
    # the font's ascender so top_mm means the same "top of the glyphs"
    # as the rest of this file's mm-from-top convention.
    ascender_mm = font.ascender * fontsize / MM_TO_PT
    leading_mm = LEADING_PT / MM_TO_PT
    draw_line(line1, top_mm + ascender_mm)
    draw_line(line2, top_mm + ascender_mm + leading_mm)


def build_resized_cover_background(blank_cover_path, spine_width_mm, out_path):
    doc = fitz.open(blank_cover_path)
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(DPI / 72, DPI / 72))
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()

    mm_to_px = DPI / 25.4
    spine_x0_px = round(SOURCE_SPINE_START_MM * mm_to_px)
    spine_x1_px = round(SOURCE_SPINE_END_MM * mm_to_px)
    panel_w_px = round(PANEL_W_MM * mm_to_px)

    back_panel = img.crop((0, 0, spine_x0_px, img.height)).resize((panel_w_px, img.height), Image.LANCZOS)
    spine_strip = img.crop((spine_x0_px, 0, spine_x1_px, img.height))
    front_panel = img.crop((spine_x1_px, 0, img.width, img.height)).resize((panel_w_px, img.height), Image.LANCZOS)

    target_spine_px = round(spine_width_mm * mm_to_px)
    spine_resized = spine_strip.resize((target_spine_px, img.height), Image.LANCZOS)

    total_w_px = panel_w_px * 2 + target_spine_px
    canvas = Image.new("RGB", (total_w_px, img.height))
    canvas.paste(back_panel, (0, 0))
    canvas.paste(spine_resized, (panel_w_px, 0))
    canvas.paste(front_panel, (panel_w_px + target_spine_px, 0))
    canvas.save(out_path)
    return canvas.size


def build_cover(child_name, gender, asset_root, out_path):
    n_letters = len(child_name.replace("-", ""))
    spine_width_mm, total_pages = get_spine_width_mm(n_letters)

    blank_cover_path = os.path.join(asset_root, "covers", f"{gender}_cover.pdf")
    font_path = os.path.join(asset_root, "fonts", "Lazydog-Regular.ttf")
    logo_path = os.path.join(asset_root, "covers", "logo.png")

    resized_bg_png = "/tmp/_cover_bg_resized.png"
    total_w_px, total_h_px = build_resized_cover_background(blank_cover_path, spine_width_mm, resized_bg_png)
    total_w_mm = total_w_px / DPI * 25.4
    total_h_mm = total_h_px / DPI * 25.4

    front_panel_x0_mm = PANEL_W_MM + spine_width_mm
    front_safe_cx_mm = front_panel_x0_mm + GROOVE_MM + SAFE_W_MM / 2
    back_safe_cx_mm = MARGIN_MM + SAFE_W_MM / 2

    doc = fitz.open()
    page = doc.new_page(width=total_w_mm * MM_TO_PT, height=total_h_mm * MM_TO_PT)
    page.insert_image(page.rect, filename=resized_bg_png)

    draw_title(page, "МИНИЙ НЭР", child_name.upper(), gender, font_path,
               cx_mm=front_safe_cx_mm, top_mm=TITLE_TOP_MM)

    for cx_mm in (back_safe_cx_mm, front_safe_cx_mm):
        lx0_mm = cx_mm - LOGO_W_MM / 2
        ly0_mm = LOGO_TOP_MM
        lrect = fitz.Rect(lx0_mm * MM_TO_PT, ly0_mm * MM_TO_PT,
                           (lx0_mm + LOGO_W_MM) * MM_TO_PT, (ly0_mm + LOGO_H_MM) * MM_TO_PT)
        page.insert_image(lrect, filename=logo_path)

    doc.save(out_path)
    doc.close()
    print(f"Saved {out_path}  {n_letters} letters -> {total_pages} pages -> spine={spine_width_mm}mm  "
          f"total={total_w_mm:.2f}x{total_h_mm:.2f}mm")
    return out_path
