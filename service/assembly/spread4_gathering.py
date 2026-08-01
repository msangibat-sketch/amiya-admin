import fitz
from .config import FONT_PLAYPEN

MM_TO_PT = 72 / 25.4
BLEED_MM = 3.0
PAGE_TRIM_MM = 210.0
MARGIN_MM = 20.0

FONT_PATH = FONT_PLAYPEN
FONT_SIZE = 18
LINEHEIGHT = 30 / 18
TEXT_BOX_H_MM = 30
BOTTOM_BUFFER_MM = 12  # distance from the true trim edge (spills past the 20mm margin line, but less than before)

LEFT_X0 = BLEED_MM + MARGIN_MM
LEFT_X1 = BLEED_MM + PAGE_TRIM_MM - MARGIN_MM
RIGHT_X0 = BLEED_MM + PAGE_TRIM_MM + MARGIN_MM
RIGHT_X1 = BLEED_MM + PAGE_TRIM_MM + PAGE_TRIM_MM - MARGIN_MM
BOTTOM_Y1 = BLEED_MM + PAGE_TRIM_MM - BOTTOM_BUFFER_MM  # spills past the 20mm margin line
BOTTOM_Y0 = BOTTOM_Y1 - TEXT_BOX_H_MM

LEFT_TEXT = "Амьтад нэг нэгээрээ аяархан\nгишгэлсээр охины дэргэд хүрч ирэв."
RIGHT_TEXT = "Тэд бяцхан найздаа зориулан өөрсдийн\nбэлдсэн онцгой бэлгүүдээ авчирсан байна."


def insert_bottom_caption(page, text, side):
    x0 = LEFT_X0 if side == "left" else RIGHT_X0
    x1 = LEFT_X1 if side == "left" else RIGHT_X1
    rect = fitz.Rect(x0 * MM_TO_PT, BOTTOM_Y0 * MM_TO_PT, x1 * MM_TO_PT, BOTTOM_Y1 * MM_TO_PT)
    page.insert_textbox(rect, text, fontsize=FONT_SIZE, fontfile=FONT_PATH, fontname="playpen",
                         align=fitz.TEXT_ALIGN_CENTER, lineheight=LINEHEIGHT,
                         color=(0.15, 0.1, 0.05))


def build_spread4(spread_path, out_path):
    doc = fitz.open(spread_path)
    page = doc[0]
    insert_bottom_caption(page, LEFT_TEXT, "left")
    insert_bottom_caption(page, RIGHT_TEXT, "right")
    doc.save(out_path)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    build_spread4("/mnt/user-data/uploads/Spread_4_-_Gathering.pdf",
                  "/home/claude/amiyaa_test/spread4_test.pdf")
