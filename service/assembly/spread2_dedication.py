import fitz
from .photo_utils import contain_fit_with_feather, PHOTO_BOX_W_MM, PHOTO_BOX_H_MM, FEATHER_MM
from .config import FONT_NUNITO

MM_TO_PT = 72 / 25.4
BLEED_MM = 3.0
PAGE_TRIM_MM = 210.0
MARGIN_MM = 20.0

DEDICATION_FONT = FONT_NUNITO
DEDICATION_FONT_SIZE = 14
DEDICATION_LEADING_PT = 24
DEDICATION_LINEHEIGHT = DEDICATION_LEADING_PT / DEDICATION_FONT_SIZE

LEFT_MARGIN_X0 = BLEED_MM + MARGIN_MM
LEFT_MARGIN_X1 = BLEED_MM + PAGE_TRIM_MM - MARGIN_MM
LEFT_MARGIN_Y0 = BLEED_MM + MARGIN_MM
LEFT_MARGIN_Y1 = BLEED_MM + PAGE_TRIM_MM - MARGIN_MM

RIGHT_MARGIN_X0 = BLEED_MM + PAGE_TRIM_MM + MARGIN_MM
RIGHT_MARGIN_X1 = BLEED_MM + PAGE_TRIM_MM + PAGE_TRIM_MM - MARGIN_MM
RIGHT_MARGIN_Y0 = BLEED_MM + MARGIN_MM
RIGHT_MARGIN_Y1 = BLEED_MM + PAGE_TRIM_MM - MARGIN_MM


def build_spread2(spread_path, photo_path, dedication_text, out_path):
    doc = fitz.open(spread_path)
    page = doc[0]

    # photo, contain-fit + feathered, centered in left page margin box
    canvas = contain_fit_with_feather(photo_path, PHOTO_BOX_W_MM, PHOTO_BOX_H_MM, FEATHER_MM)
    tmp_path = "/tmp/_spread2_photo.png"
    canvas.save(tmp_path)
    avail_w = LEFT_MARGIN_X1 - LEFT_MARGIN_X0
    avail_h = LEFT_MARGIN_Y1 - LEFT_MARGIN_Y0
    box_x0 = LEFT_MARGIN_X0 + (avail_w - PHOTO_BOX_W_MM) / 2
    box_y0 = LEFT_MARGIN_Y0 + (avail_h - PHOTO_BOX_H_MM) / 2
    rect = fitz.Rect(box_x0 * MM_TO_PT, box_y0 * MM_TO_PT,
                      (box_x0 + PHOTO_BOX_W_MM) * MM_TO_PT, (box_y0 + PHOTO_BOX_H_MM) * MM_TO_PT)
    page.insert_image(rect, filename=tmp_path)

    # dedication text: measure actual used height first (dry run on a scratch
    # page), then center that block both horizontally and vertically within
    # the right page's full margin box
    full_w = RIGHT_MARGIN_X1 - RIGHT_MARGIN_X0
    full_h = RIGHT_MARGIN_Y1 - RIGHT_MARGIN_Y0

    scratch = fitz.open()
    scratch_page = scratch.new_page(width=PAGE_TRIM_MM * MM_TO_PT, height=1000 * MM_TO_PT)
    tall_rect = fitz.Rect(0, 0, full_w * MM_TO_PT, 1000 * MM_TO_PT)
    remaining = scratch_page.insert_textbox(tall_rect, dedication_text, fontsize=DEDICATION_FONT_SIZE,
                                             fontfile=DEDICATION_FONT, fontname="nunito",
                                             align=fitz.TEXT_ALIGN_CENTER, lineheight=DEDICATION_LINEHEIGHT,
                                             color=(0, 0, 0))
    used_h_mm = (1000 * MM_TO_PT - remaining) / MM_TO_PT
    scratch.close()

    box_y0 = RIGHT_MARGIN_Y0 + max(0, (full_h - used_h_mm) / 2)
    text_rect = fitz.Rect(RIGHT_MARGIN_X0 * MM_TO_PT, box_y0 * MM_TO_PT,
                           RIGHT_MARGIN_X1 * MM_TO_PT, (box_y0 + used_h_mm + 5) * MM_TO_PT)
    page.insert_textbox(text_rect, dedication_text, fontsize=DEDICATION_FONT_SIZE,
                         fontfile=DEDICATION_FONT, fontname="nunito",
                         align=fitz.TEXT_ALIGN_CENTER, lineheight=DEDICATION_LINEHEIGHT,
                         color=(0.15, 0.1, 0.05))

    doc.save(out_path)
    doc.close()
    print(f"Saved {out_path}")


if __name__ == "__main__":
    dedication_text = (
        "Хайрт Аялгуун чамдаа,\n\n"
        "Чи бол аав ээжийнхээ амьдралд эгшиг нэмж ирсэн Аялгуун, эмээ өвөөгийнхөө "
        "амьдралд наран гийгүүлж ирсэн амин зээ, ах эгчийнхээ амьдралд аз жаргал "
        "болж ирсэн бяцхан гүнж. Чи бол энэ номны бас өөрийнхөө амьдралын гол дүр нь "
        "юм шүү. Үргэлж өөрийнхөөрөө байж аз жаргал хайрыг түгээж, хүн бүрд хайрлуулж "
        "хүндлүүлсэн бахархалт хүн болоорой. Бид нар чамдаа хязгааргүй их ХАЙРТАЙ шүү. "
        "Хэзээд арыг чинь дааж, унахад чинь түшиж, зөв явахад чинь бахархаж үргэлж "
        "чиний хажууд чинь байгаа шүү. Чангаас чанга тэврэлтийг тэвэр дүүрэн хайртай "
        "цуг илгээж байна."
    )
    build_spread2(
        "/mnt/user-data/uploads/Spread_2_-_Photo_and_Dedication.pdf",
        "/home/claude/amiyaa_test/real_photo.jpg",
        dedication_text,
        "/home/claude/amiyaa_test/spread2_test.pdf"
    )
