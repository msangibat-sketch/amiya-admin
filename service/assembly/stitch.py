"""
Orchestrates the full book assembly: hello -> dedication -> intro ->
gathering -> letter sequence (with accumulation) -> farewell ->
full-name reveal -> ending.
"""

import fitz
import os

from .hello import build_hello_test
from .spread2_dedication import build_spread2
from .spread3_intro import build_spread3
from .spread4_gathering import build_spread4
from .letters import build_letter_sequence
from .farewell import build_farewell
from .full_name_reveal import build_full_name_reveal


def stitch_all(asset_root, name, gender, dedication_text, photo_path,
                letter_variants, out_dir):
    """
    letter_variants: list of dicts like {"key": "a", "case": "u", "variant": "1"}
    representing the child's name, in order.

    Returns path to the finished print-ready spread PDF.
    """
    os.makedirs(out_dir, exist_ok=True)
    spreads_dir = os.path.join(asset_root, "spreads")

    piece_paths = []

    # 1. Hello spread
    print(f"[{name}] building hello spread...")
    hello_out = os.path.join(out_dir, "01_hello.pdf")
    build_hello_test(os.path.join(spreads_dir, f"hello_{gender}.pdf"), name, hello_out)
    piece_paths.append(hello_out)
    print(f"[{name}] hello done -> {hello_out} (exists: {os.path.exists(hello_out)})")

    # 2. Dedication spread (photo + custom text)
    print(f"[{name}] building dedication spread...")
    dedication_out = os.path.join(out_dir, "02_dedication.pdf")
    build_spread2(os.path.join(spreads_dir, "dedication.pdf"),
                  photo_path, dedication_text, dedication_out)
    piece_paths.append(dedication_out)
    print(f"[{name}] dedication done -> {dedication_out} (exists: {os.path.exists(dedication_out)})")

    # 3. Intro spread (gender pronoun swap only)
    print(f"[{name}] building intro spread...")
    intro_out = os.path.join(out_dir, "03_intro.pdf")
    build_spread3(os.path.join(spreads_dir, f"intro_{gender}.pdf"), gender, intro_out)
    piece_paths.append(intro_out)
    print(f"[{name}] intro done -> {intro_out} (exists: {os.path.exists(intro_out)})")

    # 4. Gathering spread (art varies by gender, text is fixed)
    print(f"[{name}] building gathering spread...")
    gathering_out = os.path.join(out_dir, "04_gathering.pdf")
    build_spread4(os.path.join(spreads_dir, f"gathering_{gender}.pdf"), gathering_out)
    piece_paths.append(gathering_out)
    print(f"[{name}] gathering done -> {gathering_out} (exists: {os.path.exists(gathering_out)})")

    # 5. Letter sequence: meet/give pairs + accumulation garland + captions
    print(f"[{name}] building letter sequence ({len(letter_variants)} letters)...")
    letter_dir = os.path.join(out_dir, "letters")
    letter_pages = build_letter_sequence(asset_root, letter_variants, gender, letter_dir)
    piece_paths.extend(letter_pages)
    print(f"[{name}] letter sequence done -> {len(letter_pages)} pages")

    # 6. Farewell spread (gender animal + name)
    print(f"[{name}] building farewell spread...")
    farewell_out = os.path.join(out_dir, "06_farewell.pdf")
    build_farewell(os.path.join(spreads_dir, f"farewell_{gender}.pdf"), name, gender, farewell_out)
    piece_paths.append(farewell_out)
    print(f"[{name}] farewell done -> {farewell_out} (exists: {os.path.exists(farewell_out)})")

    # 7. Full name reveal (10-slot centered, night scene)
    print(f"[{name}] building full name reveal...")
    reveal_out = os.path.join(out_dir, "07_reveal.pdf")
    reveal_sequence = [
        (lv['key'], lv['case'], lv['variant'],
         os.path.join(asset_root, "letters_night", f"{lv['key']}-{lv['case']}-{lv['variant']}.png"))
        for lv in letter_variants
    ]
    build_full_name_reveal(os.path.join(spreads_dir, f"night_scene_{gender}.pdf"), reveal_sequence, reveal_out)
    piece_paths.append(reveal_out)
    print(f"[{name}] reveal done -> {reveal_out} (exists: {os.path.exists(reveal_out)})")

    # 8. Ending spread (fixed, no variation)
    piece_paths.append(os.path.join(spreads_dir, "ending.pdf"))

    print(f"[{name}] TOTAL PIECES: {len(piece_paths)}")
    for p in piece_paths:
        print(f"  - {p} (exists: {os.path.exists(p)})")

    # 9. Stitch all pieces in order into one continuous spread PDF
    out_doc = fitz.open()
    for p in piece_paths:
        if os.path.exists(p):
            src = fitz.open(p)
            out_doc.insert_pdf(src, from_page=0, to_page=0)
            src.close()
        else:
            raise FileNotFoundError(f"Expected assembled piece missing: {p}")

    print(f"[{name}] final page count before save: {len(out_doc)}")
    print_pdf_path = os.path.join(out_dir, "print_ready.pdf")
    out_doc.save(print_pdf_path)
    return print_pdf_path


def split_for_digital(print_pdf_path, out_dir, dpi=150):
    """Split each spread down the center into single pages for Heyzine."""
    doc = fitz.open(print_pdf_path)
    digital_dir = os.path.join(out_dir, "digital_pages")
    os.makedirs(digital_dir, exist_ok=True)

    page_num = 1
    for page in doc:
        rect = page.rect
        mid_x = rect.width / 2
        for side_rect in [fitz.Rect(rect.x0, rect.y0, mid_x, rect.y1),
                           fitz.Rect(mid_x, rect.y0, rect.x1, rect.y1)]:
            pix = page.get_pixmap(clip=side_rect, matrix=fitz.Matrix(dpi / 72, dpi / 72))
            pix.save(os.path.join(digital_dir, f"page_{page_num:02d}.jpg"))
            pix = None  # release pixmap memory promptly
            page_num += 1
    doc.close()

    return digital_dir
