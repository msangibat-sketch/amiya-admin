import fitz
from .config import FONT_PLAYPEN

MM_TO_PT = 72 / 25.4
BLEED_MM = 3.0
PAGE_TRIM_MM = 210.0
MARGIN_MM = 20.0

FONT_PATH = FONT_PLAYPEN
FONT_SIZE = 18
LINEHEIGHT = 30 / 18

LEFT_MARGIN_X0 = BLEED_MM + MARGIN_MM
LEFT_MARGIN_X1 = BLEED_MM + PAGE_TRIM_MM - MARGIN_MM
LEFT_MARGIN_Y0 = BLEED_MM + MARGIN_MM
LEFT_MARGIN_Y1 = BLEED_MM + PAGE_TRIM_MM - MARGIN_MM

# right page: this spread also shows an animal on the right, text on the left
# (matches the intro spread pattern -- confirm if farewell text is also left-page only)

FAREWELL_TEXT_TEMPLATE = (
    "Хөгжилтэй өдөр өнгөрч, \n"
    "\tхөвсгөр цас шиг намуухан үдэш болжээ.\n"
    "Одоо зөвхөн {animal} үлдэж, \n"
    "\t{gender} чихэнд аяархан шивнэв:\n"
    "\u201cЭрхэм {name} минь энэ дэлхийд тавтай морил,\n"
    "\tэнд ирсэнд чинь бид бүгд үнэхээр их баяртай байна. \n"
    "Чиний нэр гайхалтай бөгөөд яг л чамд \n"
    "\tтөгс тохирсон үзэсгэлэнтэй. \n"
    "Өнөөдөр амьтад чиний ямар онцгойг ярьж өглөө,\n"
    "\tМаргааш чи бүр ч илүү гайхалтай болно\u201d."
)

ANIMAL_BY_GENDER = {"girl": "Цагаан баавгай", "boy": "Арслан"}
GENDER_WORD = {"girl": "охины", "boy": "хүүгийн"}


def build_farewell(spread_path, name, gender, out_path):
    animal = ANIMAL_BY_GENDER[gender]
    gender_word = GENDER_WORD[gender]
    text = FAREWELL_TEXT_TEMPLATE.format(animal=animal, gender=gender_word, name=name)
    lines = text.split("\n")

    doc = fitz.open(spread_path)
    page = doc[0]

    font = fitz.Font(fontfile=FONT_PATH)
    indent_pt = FONT_SIZE * 1.8
    leading_pt = FONT_SIZE * LINEHEIGHT

    line_widths = []
    for line in lines:
        is_indented = line.startswith("\t")
        clean_line = line.lstrip("\t")
        w = font.text_length(clean_line, fontsize=FONT_SIZE) + (indent_pt if is_indented else 0)
        line_widths.append(w)
    block_w_pt = max(line_widths)
    block_h_pt = leading_pt * len(lines)

    margin_w_pt = (LEFT_MARGIN_X1 - LEFT_MARGIN_X0) * MM_TO_PT
    margin_h_pt = (LEFT_MARGIN_Y1 - LEFT_MARGIN_Y0) * MM_TO_PT

    block_x0 = LEFT_MARGIN_X0 * MM_TO_PT + max(0, (margin_w_pt - block_w_pt) / 2)
    block_y0 = LEFT_MARGIN_Y0 * MM_TO_PT + max(0, (margin_h_pt - block_h_pt) / 2)

    y_cursor = block_y0 + FONT_SIZE
    for line in lines:
        is_indented = line.startswith("\t")
        clean_line = line.lstrip("\t")
        x = block_x0 + (indent_pt if is_indented else 0)
        page.insert_text(fitz.Point(x, y_cursor), clean_line, fontsize=FONT_SIZE,
                          fontfile=FONT_PATH, fontname="playpen", color=(0.15, 0.1, 0.05))
        y_cursor += leading_pt

    doc.save(out_path)
    doc.close()
    print(f"Saved {out_path}")


if __name__ == "__main__":
    build_farewell("/mnt/user-data/uploads/Spread_-_Farewell_girl.pdf", "Амияа", "girl",
                    "/home/claude/amiyaa_test/farewell_test.pdf")
