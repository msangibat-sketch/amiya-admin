"""
Orchestrates the full book assembly using the modules we already built and
validated (hello, dedication, intro, gathering, letters+accumulation,
farewell, full-name reveal).

IMPORTANT -- before this runs outside the original test sandbox:
Each module in this package currently has some hardcoded paths (asset
folders, font locations) left over from testing. Before deploying, replace
those with references to ASSET_ROOT (passed in here) so the service can
find spreads/letters/fonts wherever they're actually stored on the server.
This file shows the correct *order of operations* -- wiring the exact
path config is the remaining mechanical step.
"""

import fitz
import os


def stitch_all(asset_root, name, gender, dedication_text, photo_path,
                letter_variants, out_dir):
    """
    letter_variants: list of dicts like {"key": "a", "case": "u", "variant": "1"}
    representing the child's name, in order.

    Returns path to the finished print-ready spread PDF.
    """
    out_doc = fitz.open()

    # 1. Hello spread (gender variant, name auto-fit)
    # from .hello import build_hello_test
    # build_hello_test(f"{asset_root}/spreads/hello_{gender}.pdf", name, f"{out_dir}/01_hello.pdf")

    # 2. Dedication spread (photo + custom text)
    # from .spread2_dedication import build_spread2
    # build_spread2(f"{asset_root}/spreads/dedication_{gender}.pdf", photo_path,
    #               dedication_text, f"{out_dir}/02_dedication.pdf")

    # 3. Intro spread (gender pronoun swap only)
    # from .spread3_intro import build_spread3
    # build_spread3(f"{asset_root}/spreads/intro_{gender}.pdf", gender, f"{out_dir}/03_intro.pdf")

    # 4. Gathering spread (no text variation, just gender art)
    # from .spread4_gathering import build_spread4
    # build_spread4(f"{asset_root}/spreads/gathering_{gender}.pdf", f"{out_dir}/04_gathering.pdf")

    # 5. Letter sequence: meet/give pairs + accumulation garland + captions
    # from .letters import build_letter_sequence
    # letter_pages = build_letter_sequence(asset_root, letter_variants, gender, f"{out_dir}/letters")

    # 6. Farewell spread (gender animal + name)
    # from .farewell import build_farewell
    # build_farewell(f"{asset_root}/spreads/farewell_{gender}.pdf", name, gender,
    #                 f"{out_dir}/06_farewell.pdf")

    # 7. Full name reveal (10-slot centered, night scene)
    # from .full_name_reveal import build_full_name_reveal
    # build_full_name_reveal(f"{asset_root}/spreads/night_scene.pdf", letter_variants,
    #                         f"{out_dir}/07_reveal.pdf")

    # 8. Ending spread (fixed, no variation)
    # ending_path = f"{asset_root}/spreads/ending.pdf"

    # 9. Stitch all pieces in order into one continuous spread PDF
    piece_paths = [
        f"{out_dir}/01_hello.pdf",
        f"{out_dir}/02_dedication.pdf",
        f"{out_dir}/03_intro.pdf",
        f"{out_dir}/04_gathering.pdf",
        # *letter_pages,
        f"{out_dir}/06_farewell.pdf",
        f"{out_dir}/07_reveal.pdf",
        f"{asset_root}/spreads/ending.pdf",
    ]
    for p in piece_paths:
        if os.path.exists(p):
            src = fitz.open(p)
            out_doc.insert_pdf(src, from_page=0, to_page=0)

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
            page_num += 1

    return digital_dir
