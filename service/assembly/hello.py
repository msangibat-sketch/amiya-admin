import fitz
from .config import FONT_NEXA

MM_TO_PT = 72 / 25.4
BLEED_MM = 3.0
PAGE_TRIM_MM = 210.0
MARGIN_MM = 20.0

FONT_PATH = FONT_NEXA
BOX_WIDTH_MM = 125.0
MAX_FONT_SIZE = 60
MIN_FONT_SIZE = 10

# Hello spread text sits on the RIGHT page (per reference image),
# box horizontally centered on that page, top edge at the 20mm margin line.
RIGHT_PAGE_X0 = BLEED_MM + PAGE_TRIM_MM
RIGHT_PAGE_CENTER_X = RIGHT_PAGE_X0 + PAGE_TRIM_MM / 2
BOX_X0 = RIGHT_PAGE_CENTER_X - BOX_WIDTH_MM / 2
BOX_X1 = RIGHT_PAGE_CENTER_X + BOX_WIDTH_MM / 2
BOX_Y0 = BLEED_MM + MARGIN_MM


def fit_font_size(text, max_width_pt, fontfile):
    font = fitz.Font(fontfile=fontfile)
    for fs in [x / 2 for x in range(MAX_FONT_SIZE * 2, MIN_FONT_SIZE * 2 - 1, -1)]:
        w = font.text_length(text, fontsize=fs)
        if w <= max_width_pt:
            return fs
    return MIN_FONT_SIZE


HELLO_TEXT_COLOR = (0.5529, 0.7843, 0.9333)  # #8dc8ee, exact Canva match

# New Year edition title, calibrated (Oct 2026) from the final approved
# hello_girl New Year reference PDF: same NexaScript font and right-page
# centering as standard, but a fixed size/baseline and the exact CMYK green
# used in that file.
NEWYEAR_LAYOUT = {
    "max_font_size": 47.93,     # size used for "Сайн уу, Амияа!" in the reference
    "max_width_mm": 150.0,      # longer names shrink to stay well inside the garland (~179mm inner)
    "baseline_mm": 44.96,       # from the top edge of the bleed
    "color": (0.70, 0.46, 0.97, 0.45),  # CMYK C70 M46 Y97 K45
}


def build_hello_test(spread_path, name, out_path, layout=None):
    """layout=None: the classic hello page, exactly as before.
    layout=NEWYEAR_LAYOUT: the New Year edition."""
    text = f"Сайн уу, {name}!"
    doc = fitz.open(spread_path)
    page = doc[0]

    font = fitz.Font(fontfile=FONT_PATH)
    if layout:
        max_width_pt = layout["max_width_mm"] * MM_TO_PT
        fs = layout["max_font_size"]
        while fs > MIN_FONT_SIZE and font.text_length(text, fontsize=fs) > max_width_pt:
            fs -= 0.5
        baseline_y_pt = layout["baseline_mm"] * MM_TO_PT
        text_color = layout["color"]
    else:
        max_width_pt = BOX_WIDTH_MM * MM_TO_PT
        fs = fit_font_size(text, max_width_pt, FONT_PATH)
        baseline_y_pt = BOX_Y0 * MM_TO_PT + fs
        text_color = HELLO_TEXT_COLOR
    text_w_pt = font.text_length(text, fontsize=fs)
    x_start = ((BOX_X0 + BOX_X1) / 2) * MM_TO_PT - text_w_pt / 2

    page.insert_text(
        fitz.Point(x_start, baseline_y_pt),
        text, fontsize=fs, fontfile=FONT_PATH, fontname="nexa",
        color=text_color
    )

    doc.save(out_path)
    doc.close()
    print(f"font_size={fs}pt text_width={text_w_pt/MM_TO_PT:.1f}mm (box={BOX_WIDTH_MM}mm) color={text_color}")


if __name__ == "__main__":
    build_hello_test("/mnt/user-data/uploads/Spread_1_-_Inside_cover.pdf", "Амияа",
                      "/home/claude/amiyaa_test/hello_test_v2.pdf")
