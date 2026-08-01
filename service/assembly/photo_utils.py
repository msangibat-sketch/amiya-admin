"""
Dedication spread photo handling:
- Contain-fit (whole photo visible, no crop/zoom) into a 120x130mm box.
- 8mm feather applied to the photo's own edges (wherever it actually lands).
"""

import fitz
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

MM_TO_PT = 72 / 25.4
BLEED_MM = 3.0
PAGE_TRIM_MM = 210.0
MARGIN_MM = 20.0

PHOTO_BOX_W_MM = 140.0
PHOTO_BOX_H_MM = 140.0
FEATHER_MM = 8.0

# left page, box position: let's center it within the left page's margin area for now
LEFT_PAGE_X0 = BLEED_MM
LEFT_PAGE_MARGIN_X0 = BLEED_MM + MARGIN_MM
LEFT_PAGE_MARGIN_X1 = BLEED_MM + PAGE_TRIM_MM - MARGIN_MM
LEFT_PAGE_MARGIN_Y0 = BLEED_MM + MARGIN_MM
LEFT_PAGE_MARGIN_Y1 = BLEED_MM + PAGE_TRIM_MM - MARGIN_MM


def contain_fit_with_feather(photo_path, box_w_mm, box_h_mm, feather_mm, dpi=300):
    """Returns a PIL RGBA image sized exactly box_w_mm x box_h_mm (at given dpi),
    with the source photo contain-fit centered inside, and its own edges
    feathered by feather_mm."""
    px_per_mm = dpi / 25.4
    box_w_px = int(box_w_mm * px_per_mm)
    box_h_px = int(box_h_mm * px_per_mm)
    feather_px = int(feather_mm * px_per_mm)

    src = Image.open(photo_path).convert('RGB')
    src_w, src_h = src.size
    scale = min(box_w_px / src_w, box_h_px / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    resized = src.resize((new_w, new_h), Image.LANCZOS)

    # build alpha mask for the resized photo: opaque center, feathered edges
    mask = Image.new('L', (new_w, new_h), 255)
    mdraw = ImageDraw.Draw(mask)
    # draw a black border rectangle inset, then blur, to create edge feather
    mask2 = Image.new('L', (new_w, new_h), 0)
    md2 = ImageDraw.Draw(mask2)
    md2.rectangle([feather_px, feather_px, new_w - feather_px, new_h - feather_px], fill=255)
    mask2 = mask2.filter(ImageFilter.GaussianBlur(feather_px / 2))

    rgba = resized.convert('RGBA')
    rgba.putalpha(mask2)

    # composite onto a transparent canvas of the full box size, centered.
    # IMPORTANT: paste WITHOUT a separate mask arg -- passing the RGBA image
    # itself as the mask causes Pillow to alpha-blend the color channels
    # against the (black) canvas background, darkening edges toward black
    # wherever alpha is low. A plain paste copies RGBA values directly,
    # preserving the true photo color under the fading alpha.
    canvas = Image.new('RGBA', (box_w_px, box_h_px), (0, 0, 0, 0))
    offset_x = (box_w_px - new_w) // 2
    offset_y = (box_h_px - new_h) // 2
    canvas.paste(rgba, (offset_x, offset_y))
    return canvas


def build_dedication_photo_test(spread_path, photo_path, out_path):
    doc = fitz.open(spread_path)
    page = doc[0]

    canvas = contain_fit_with_feather(photo_path, PHOTO_BOX_W_MM, PHOTO_BOX_H_MM, FEATHER_MM)
    tmp_path = "/tmp/_dedication_photo.png"
    canvas.save(tmp_path)

    # center the box within the left page's margin area
    avail_w = LEFT_PAGE_MARGIN_X1 - LEFT_PAGE_MARGIN_X0
    avail_h = LEFT_PAGE_MARGIN_Y1 - LEFT_PAGE_MARGIN_Y0
    box_x0 = LEFT_PAGE_MARGIN_X0 + (avail_w - PHOTO_BOX_W_MM) / 2
    box_y0 = LEFT_PAGE_MARGIN_Y0 + (avail_h - PHOTO_BOX_H_MM) / 2

    rect = fitz.Rect(box_x0 * MM_TO_PT, box_y0 * MM_TO_PT,
                      (box_x0 + PHOTO_BOX_W_MM) * MM_TO_PT, (box_y0 + PHOTO_BOX_H_MM) * MM_TO_PT)
    page.insert_image(rect, filename=tmp_path)
    doc.save(out_path)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    build_dedication_photo_test(
        "/mnt/user-data/uploads/Spread_2.pdf",
        "/home/claude/amiyaa_test/placeholder_photo.jpg",
        "/home/claude/amiyaa_test/dedication_photo_test.pdf"
    )
