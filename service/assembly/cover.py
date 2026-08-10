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


def render_title_png(line1, line2, gender, font_path, out_path):
    font_size_px = round(FONT_SIZE_PT / 72 * DPI)
    font = ImageFont.truetype(font_path, font_size_px)
    leading_px = round(LEADING_PT / 72 * DPI)
    stroke_px = STROKE_PX_AT_300DPI
    tracking_px = TRACKING_1000EM / 1000 * font_size_px

    def line_width(line):
        w = 0
        for ch in line:
            bbox = font.getbbox(ch)
            w += (bbox[2] - bbox[0]) if bbox else font.getlength(ch)
            w += tracking_px
        return w - tracking_px

    def draw_tracked_line(draw, line, cx, y):
        w = line_width(line)
        x = cx - w / 2
        for ch in line:
            draw.text((x, y), ch, font=font, fill=(255, 255, 255, 255),
                       stroke_width=stroke_px, stroke_fill=STROKE_COLOR[gender] + (255,))
            bbox = font.getbbox(ch)
            adv = (bbox[2] - bbox[0]) if bbox else font.getlength(ch)
            x += adv + tracking_px

    w1, w2 = line_width(line1), line_width(line2)
    canvas_w = int(max(w1, w2) + stroke_px * 4 + 40)
    canvas_h = int(leading_px * 2 + stroke_px * 4 + 40)
    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = canvas_w / 2
    draw_tracked_line(draw, line1, cx, 20)
    draw_tracked_line(draw, line2, cx, 20 + leading_px)

    bbox = img.getbbox()
    img = img.crop(bbox)
    img.save(out_path)
    return img.size


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

    title_png_path = "/tmp/_cover_title.png"
    png_w_px, png_h_px = render_title_png("МИНИЙ НЭР", child_name.upper(), gender, font_path, title_png_path)
    png_w_mm = png_w_px / DPI * 25.4
    png_h_mm = png_h_px / DPI * 25.4

    doc = fitz.open()
    page = doc.new_page(width=total_w_mm * MM_TO_PT, height=total_h_mm * MM_TO_PT)
    page.insert_image(page.rect, filename=resized_bg_png)

    x0_mm = front_safe_cx_mm - png_w_mm / 2
    y0_mm = TITLE_TOP_MM
    rect = fitz.Rect(x0_mm * MM_TO_PT, y0_mm * MM_TO_PT,
                      (x0_mm + png_w_mm) * MM_TO_PT, (y0_mm + png_h_mm) * MM_TO_PT)
    page.insert_image(rect, filename=title_png_path)

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
