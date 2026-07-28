import fitz

MM_TO_PT = 72 / 25.4
BLEED_MM = 3.0
PAGE_TRIM_MM = 210.0
MARGIN_MM = 20.0

FONT_PATH = "/home/claude/fonts/nexa/NexaScript-Regular.ttf"
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


def build_hello_test(spread_path, name, out_path):
    text = f"Сайн уу, {name}!"
    doc = fitz.open(spread_path)
    page = doc[0]

    max_width_pt = BOX_WIDTH_MM * MM_TO_PT
    fs = fit_font_size(text, max_width_pt, FONT_PATH)
    font = fitz.Font(fontfile=FONT_PATH)
    text_w_pt = font.text_length(text, fontsize=fs)

    x_start = ((BOX_X0 + BOX_X1) / 2) * MM_TO_PT - text_w_pt / 2
    baseline_y_pt = BOX_Y0 * MM_TO_PT + fs

    page.insert_text(
        fitz.Point(x_start, baseline_y_pt),
        text, fontsize=fs, fontfile=FONT_PATH, fontname="nexa",
        color=(203/255, 233/255, 250/255)  # sampled directly from the frame's own pixels
    )

    doc.save(out_path)
    print(f"font_size={fs}pt text_width={text_w_pt/MM_TO_PT:.1f}mm (box={BOX_WIDTH_MM}mm)")


if __name__ == "__main__":
    build_hello_test("/mnt/user-data/uploads/Spread_1_-_Inside_cover.pdf", "Амияа",
                      "/home/claude/amiyaa_test/hello_test_v2.pdf")
