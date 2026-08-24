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


def normalize_name_case(name):
    """
    Forces proper capitalization regardless of how the name was typed or
    stored upstream -- customer-typed casing at checkout varies a lot
    (e.g. all-caps), and nothing upstream currently normalizes it. First
    letter of the name, and of each hyphen-separated segment, gets
    capitalized; everything else lowercased. Matches the exact
    segmentation rule the dashboard's own parseNameTokens already uses
    for per-letter case, so verbatim name text (hello/farewell spreads)
    stays visually consistent with the letter garland, which was never
    affected by this in the first place since it derives case from
    position, not from the raw name string.
    """
    result = []
    capitalize_next = True
    for ch in name:
        if ch == "-":
            result.append(ch)
            capitalize_next = True
        elif capitalize_next:
            result.append(ch.upper())
            capitalize_next = False
        else:
            result.append(ch.lower())
    return "".join(result)


def stitch_all(asset_root, name, gender, dedication_text, photo_path,
                letter_variants, out_dir):
    """
    letter_variants: list of dicts like {"key": "a", "case": "u", "variant": "1"}
    representing the child's name, in order.

    Returns path to the finished print-ready spread PDF.
    """
    name = normalize_name_case(name)
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
    build_spread4(os.path.join(spreads_dir, f"gathering_{gender}.pdf"), gathering_out, gender)
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
    farewell_idx = len(piece_paths)  # position this piece will occupy in the final PDF
    farewell_out = os.path.join(out_dir, "06_farewell.pdf")
    build_farewell(os.path.join(spreads_dir, f"farewell_{gender}.pdf"), name, gender, farewell_out)
    piece_paths.append(farewell_out)
    print(f"[{name}] farewell done -> {farewell_out} (exists: {os.path.exists(farewell_out)})")

    # 7. Full name reveal (10-slot centered, night scene)
    print(f"[{name}] building full name reveal...")
    reveal_idx = len(piece_paths)
    reveal_out = os.path.join(out_dir, "07_reveal.pdf")
    night_letters_dir = os.path.join(asset_root, "letters_night")
    reveal_sequence = [
        "-" if lv['key'] == '-' else
        (lv['key'], lv['case'], lv['variant'],
         os.path.join(night_letters_dir, f"{lv['key']}-{lv['case']}-{lv['variant']}.png"))
        for lv in letter_variants
    ]
    build_full_name_reveal(os.path.join(spreads_dir, f"night_scene_{gender}.pdf"), reveal_sequence, reveal_out,
                            night_letters_dir=night_letters_dir)
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

    # farewell and the night full-name-reveal are excluded from the
    # DIGITAL reader specifically -- Heyzine's own reader already has its
    # own immersive treatment of those two moments, so including the
    # static print versions too would be redundant. Print PDF is
    # unaffected; this only feeds into split_for_digital.
    digital_skip_pages = {farewell_idx, reveal_idx}
    return print_pdf_path, digital_skip_pages


def split_for_digital(print_pdf_path, out_dir, skip_pages=None, cover_page_path=None, dpi=150, jpeg_quality=85):
    """
    Splits each spread down the center into single pages for Heyzine,
    combined into ONE multi-page PDF. This is the digital reader copy,
    viewed on-screen (desktop, embedded in Heyzine's flip-book player) --
    not the print file, so it doesn't need 300dpi. 150dpi + JPEG q85 is a
    balance point: sharp enough for on-screen reading at typical zoom
    levels, while keeping file size well down from print quality. (An
    earlier version deliberately degraded this further, to 100dpi/q70,
    to discourage screenshotting -- reversed, since it hurt the reading
    experience more than it was worth.)

    skip_pages: 0-indexed print-PDF page numbers to leave out entirely
    (e.g. farewell/reveal, which the digital reader already handles with
    its own immersive treatment).

    cover_page_path: an already-built single-page PDF (matching this
    function's own target page dimensions) to insert as page 1, ahead of
    everything else -- see cover.build_digital_cover_page.
    """
    import io
    from PIL import Image

    skip_pages = skip_pages or set()
    doc = fitz.open(print_pdf_path)
    digital_doc = fitz.open()

    if cover_page_path:
        cover_src = fitz.open(cover_page_path)
        digital_doc.insert_pdf(cover_src, from_page=0, to_page=0)
        cover_src.close()

    for page_idx, page in enumerate(doc):
        if page_idx in skip_pages:
            continue
        rect = page.rect
        mid_x = rect.width / 2
        for side_rect in [fitz.Rect(rect.x0, rect.y0, mid_x, rect.y1),
                           fitz.Rect(mid_x, rect.y0, rect.x1, rect.y1)]:
            pix = page.get_pixmap(clip=side_rect, matrix=fitz.Matrix(dpi / 72, dpi / 72))
            pil_img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=jpeg_quality)
            jpeg_bytes = buf.getvalue()
            pix = None  # release pixmap memory promptly

            new_page = digital_doc.new_page(width=side_rect.width, height=side_rect.height)
            new_page.insert_image(new_page.rect, stream=jpeg_bytes)

    digital_pdf_path = os.path.join(out_dir, "digital_pages.pdf")
    digital_doc.save(digital_pdf_path, garbage=4, deflate=True)
    digital_doc.close()
    doc.close()
    return digital_pdf_path
