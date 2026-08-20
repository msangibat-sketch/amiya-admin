"""
Amiya Publishing book generation service.

Wraps the assembly logic we built and validated in testing (accumulation
garland, captions, dedication/photo spread, fixed pages) behind a simple
HTTP API so the admin dashboard (or a one-button page) can trigger it.

Deploy this to Render/Railway as a standalone web service. It expects the
asset library (spreads/, letters/, fonts/) to be present on disk -- either
baked into the deploy image, or synced from cloud storage on startup
(see sync_assets() below, which you'll wire up to Google Drive/S3/etc).
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import uuid

app = FastAPI(title="Amiya Book Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your Netlify URL once things are stable
    allow_methods=["*"],
    allow_headers=["*"],
)

ASSET_ROOT = os.environ.get("ASSET_ROOT", "/app/assets")
OUTPUT_ROOT = os.environ.get("OUTPUT_ROOT", "/app/output")
HEYZINE_CLIENT_ID = os.environ.get("HEYZINE_CLIENT_ID")
HEYZINE_API_KEY = os.environ.get("HEYZINE_API_KEY")
# A flipbook ID that's already styled the way every book should look (no
# logo, transparent background, controls hidden) -- Heyzine's "template"
# param copies that styling to every new upload automatically, so this
# only ever needs to be set up once, by hand, in Heyzine's own editor.
HEYZINE_TEMPLATE_ID = os.environ.get("HEYZINE_TEMPLATE_ID")


class LetterVariant(BaseModel):
    key: str
    case: Optional[str] = None    # "u" or "l" -- None for a dash
    variant: Optional[str] = None  # None for a dash


class GenerateRequest(BaseModel):
    order_number: str
    child_name: str
    gender: str          # "boy" or "girl"
    tier: str             # "essential" | "signature" | "magical"
    dedication_text: str
    photo_url: str
    letter_variants: List[LetterVariant]


class GenerateResponse(BaseModel):
    order_number: str
    print_pdf_url: str
    digital_pages_url: str
    heyzine_book_id: Optional[str] = None
    status: str


class GenerateCoverRequest(BaseModel):
    order_number: str
    child_name: str
    gender: str  # "boy" or "girl"


class GenerateCoverResponse(BaseModel):
    order_number: str
    cover_pdf_url: str
    total_pages: int
    spine_width_mm: float


class UploadPhotoRequest(BaseModel):
    order_number: str
    image_base64: str
    content_type: str = "image/jpeg"


class UploadPhotoResponse(BaseModel):
    photo_url: str


def download_photo(photo_url: str, dest_path: str):
    import requests
    r = requests.get(photo_url, timeout=30)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(r.content)


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
STORAGE_BUCKET = "generated-books"


def slugify_key_component(value: str) -> str:
    """
    Supabase Storage object keys must be ASCII-safe. order_number is normally
    a short alphanumeric code, but if Cyrillic text (or anything else non-ASCII)
    ends up in there by mistake -- e.g. the child's name typed into the wrong
    field -- the upload fails with a hard-to-diagnose InvalidKey error instead
    of a clear validation message. Strip/replace anything outside
    [A-Za-z0-9_-] rather than trusting the caller's data is already safe.
    """
    import re
    import unicodedata
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", ascii_value).strip("-")
    return slug or "order"


def upload_to_storage(local_path: str, storage_path: str, bucket: str = None) -> str:
    """
    Uploads a file to Supabase Storage via its REST API directly (no SDK
    dependency needed) and returns the public URL. Requires SUPABASE_URL
    and SUPABASE_SERVICE_KEY env vars to be set, and the target bucket to
    already exist and be public in the Supabase project. Defaults to
    STORAGE_BUCKET ('generated-books') if no bucket is given, so every
    existing call site is unaffected.
    """
    import requests
    import mimetypes

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY env vars are not set")

    bucket = bucket or STORAGE_BUCKET
    content_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    upload_url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{storage_path}"

    with open(local_path, "rb") as f:
        resp = requests.post(
            upload_url,
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": content_type,
                "x-upsert": "true",  # overwrite if this path already exists
            },
            data=f.read(),
            timeout=120,
        )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Upload failed ({resp.status_code}): {resp.text}")

    return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{storage_path}"


def upload_to_heyzine(pdf_public_url: str) -> str | None:
    """
    Sends the already-uploaded digital_pages.pdf (needs to be a public
    URL -- Heyzine fetches it server-side) to Heyzine's Sync REST API,
    which converts it into a flipbook and returns its details in one
    call. template=HEYZINE_TEMPLATE_ID copies the logo/background/control
    styling from an existing, already-styled flipbook, so nothing needs
    manual re-styling per book.

    Returns the SHORT flipbook id (e.g. "8790ac10b5") -- matching what
    the digital reader's own "book" URL parameter expects, extracted
    from the response's flipbook url, not the long filename-style "id"
    field the API also returns.

    Returns None on any failure rather than raising -- a Heyzine hiccup
    should never fail the whole book generation; the dashboard's Digital
    Book URL panel still lets the book ID be pasted in by hand as a
    fallback if this comes back empty.
    """
    import requests
    import re

    if not HEYZINE_CLIENT_ID:
        print("[warning] HEYZINE_CLIENT_ID not set -- skipping automatic flipbook creation")
        return None

    payload = {
        "pdf": pdf_public_url,
        "client_id": HEYZINE_CLIENT_ID,
        # Set explicitly, redundant with whatever the template also
        # covers -- these control which buttons show on the reader, and
        # shouldn't depend solely on template inheritance working
        # perfectly. All false = fullscreen/share/prev-next buttons and
        # the title/subtitle overlay all hidden.
        "full_screen": False,
        "share": False,
        "prev_next": False,
        "show_info": False,
        "download": False,
        # Matches the template's own Page Effect setting (Image 2:
        # "Book") -- explicit and redundant with template, but harmless.
        "page_effect": "book",
    }
    if HEYZINE_TEMPLATE_ID:
        payload["template"] = HEYZINE_TEMPLATE_ID
    else:
        print("[warning] HEYZINE_TEMPLATE_ID not set -- new flipbooks will use Heyzine's default "
              "styling (visible controls, logo, background) instead of the configured template")

    print(f"[heyzine] sending payload: {payload}")

    try:
        resp = requests.post("https://heyzine.com/api1/rest", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        print(f"[heyzine] response: {data}")

        # Second attempt at applying the template: creation-time template
        # inheritance appears not to reliably cover controls/background
        # (confirmed by directly inspecting a created flipbook's own
        # settings) even though the docs say it should. Try the
        # dedicated design-update endpoint too, best-effort -- if this
        # also doesn't work, it's a genuine Heyzine-side limitation worth
        # reporting to their support with this exact reproducible case.
        if HEYZINE_TEMPLATE_ID and HEYZINE_API_KEY and data.get("id"):
            try:
                design_resp = requests.patch(
                    "https://heyzine.com/api1/flipbook-design",
                    headers={"Authorization": f"Bearer {HEYZINE_API_KEY}"},
                    json={"id": data["id"], "template": HEYZINE_TEMPLATE_ID},
                    timeout=30,
                )
                print(f"[heyzine] flipbook-design follow-up status={design_resp.status_code} "
                      f"body={design_resp.text}")
            except Exception as e:
                print(f"[warning] flipbook-design follow-up call failed: {e}")

        match = re.search(r"/flip-book/([a-zA-Z0-9]+)\.html", data.get("url", ""))
        if not match:
            print(f"[warning] Heyzine response didn't contain a parseable flipbook url: {data}")
            return None
        return match.group(1)
    except Exception as e:
        print(f"[warning] Heyzine upload failed, book ID will need to be set manually: {e}")
        return None


@app.on_event("startup")
def startup():
    os.makedirs(OUTPUT_ROOT, exist_ok=True)

    print("=" * 50)
    print("ASSET VERIFICATION AT STARTUP")
    print("=" * 50)
    print(f"ASSET_ROOT = {ASSET_ROOT}")

    expected = {
        "spreads": os.path.join(ASSET_ROOT, "spreads"),
        "letters": os.path.join(ASSET_ROOT, "letters"),
        "letters_night": os.path.join(ASSET_ROOT, "letters_night"),
        "fonts": os.path.join(ASSET_ROOT, "fonts"),
    }
    for label, path in expected.items():
        if os.path.isdir(path):
            count = len(os.listdir(path))
            print(f"  [OK] {label}/ -- {count} files")
        else:
            print(f"  [MISSING] {label}/ -- folder not found at {path}")

    caption_path = os.path.join(ASSET_ROOT, "caption_text.xlsx")
    print(f"  [{'OK' if os.path.exists(caption_path) else 'MISSING'}] caption_text.xlsx")

    fonts_needed = ["PlaypenSans-Regular.ttf", "NexaScript-Regular.ttf", "Nunito-Custom450.ttf"]
    for f in fonts_needed:
        p = os.path.join(ASSET_ROOT, "fonts", f)
        print(f"  [{'OK' if os.path.exists(p) else 'MISSING'}] fonts/{f}")

    for gender in ["girl", "boy"]:
        for name in ["hello", "intro", "gathering", "farewell"]:
            p = os.path.join(ASSET_ROOT, "spreads", f"{name}_{gender}.pdf")
            print(f"  [{'OK' if os.path.exists(p) else 'MISSING'}] spreads/{name}_{gender}.pdf")
        p = os.path.join(ASSET_ROOT, "spreads", f"night_scene_{gender}.pdf")
        print(f"  [{'OK' if os.path.exists(p) else 'MISSING'}] spreads/night_scene_{gender}.pdf")
        p = os.path.join(ASSET_ROOT, "covers", f"{gender}_cover.pdf")
        print(f"  [{'OK' if os.path.exists(p) else 'MISSING'}] covers/{gender}_cover.pdf")

    for f in ["Lazydog-Regular.ttf"]:
        p = os.path.join(ASSET_ROOT, "fonts", f)
        print(f"  [{'OK' if os.path.exists(p) else 'MISSING'}] fonts/{f}")
    p = os.path.join(ASSET_ROOT, "covers", "logo.png")
    print(f"  [{'OK' if os.path.exists(p) else 'MISSING'}] covers/logo.png")
    for fixed in ["dedication.pdf", "ending.pdf"]:
        p = os.path.join(ASSET_ROOT, "spreads", fixed)
        print(f"  [{'OK' if os.path.exists(p) else 'MISSING'}] spreads/{fixed}")

    print("=" * 50)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/animal-names")
def animal_names():
    """
    Returns a {"<key>-<variant>": "<animal name>"} lookup built from the
    caption spreadsheet, so the dashboard can show which animal a variant
    number corresponds to instead of just a bare number. Animal identity is
    consistent across gender and night/day (verified against the actual
    data), so key+variant alone is enough -- no need to disambiguate further.
    """
    import openpyxl

    caption_path = os.path.join(ASSET_ROOT, "caption_text.xlsx")
    if not os.path.exists(caption_path):
        raise HTTPException(500, f"caption_text.xlsx not found at {caption_path}")

    wb = openpyxl.load_workbook(caption_path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = rows[0]

    lookup = {}
    for row in rows[1:]:
        # openpyxl's read_only mode doesn't pad short rows with None the way
        # normal mode does -- a row missing a value in a trailing column
        # (e.g. animal_name blank) comes back shorter than the header, so
        # positional indexing can throw IndexError. zip(header, row) safely
        # stops at the shorter of the two, and dict.get() below returns None
        # for anything that fell off the end instead of crashing.
        d = dict(zip(header, row))
        key = d.get("key")
        variant = d.get("variant")
        animal_name = d.get("animal_name")
        if key is None or variant is None or animal_name is None:
            continue
        # Excel cells can store the variant number as either an int or a
        # float depending on how it was entered/edited (e.g. 2 vs 2.0) --
        # normalize so the lookup key is always a clean integer string,
        # since the dashboard always sends a plain integer like "2", never "2.0".
        try:
            variant = int(float(variant))
        except (TypeError, ValueError):
            continue
        lookup_key = f"{key}-{variant}"
        # first one wins; the few rows that differ only by trailing
        # whitespace all refer to the same animal
        lookup.setdefault(lookup_key, str(animal_name).strip())

    return lookup


@app.post("/generate", response_model=GenerateResponse)
def generate_book(req: GenerateRequest):
    """
    Full pipeline:
    1. Download the child's photo.
    2. Assemble the fixed spreads (hello, dedication, intro, gathering,
       farewell, full-name reveal, ending) with real text/photo.
    3. Assemble the letter sequence (meet/give pairs + accumulation garland).
    4. Stitch everything into one print-ready spread PDF.
    5. Split into single-page PDFs for the digital reader.
    6. Upload outputs, return their URLs.
    """
    if req.gender not in ("boy", "girl"):
        raise HTTPException(400, "gender must be 'boy' or 'girl'")

    job_id = str(uuid.uuid4())[:8]
    job_dir = os.path.join(OUTPUT_ROOT, f"{req.order_number}_{job_id}")
    os.makedirs(job_dir, exist_ok=True)

    photo_path = os.path.join(job_dir, "photo.jpg")
    download_photo(req.photo_url, photo_path)

    if not req.letter_variants:
        raise HTTPException(400, "letter_variants is empty -- cannot generate a book without knowing which letter art to use for each letter of the name")

    from assembly.stitch import stitch_all, split_for_digital
    from assembly.cover import build_digital_cover_page
    from assembly.letters import SPREAD_W_MM, SPREAD_H_MM

    print_pdf_path, digital_skip_pages = stitch_all(
        asset_root=ASSET_ROOT,
        name=req.child_name,
        gender=req.gender,
        dedication_text=req.dedication_text,
        photo_path=photo_path,
        letter_variants=[lv.dict() for lv in req.letter_variants],
        out_dir=job_dir,
    )

    digital_cover_path = os.path.join(job_dir, "digital_cover.pdf")
    build_digital_cover_page(
        req.child_name, req.gender, ASSET_ROOT,
        target_w_mm=SPREAD_W_MM / 2, target_h_mm=SPREAD_H_MM,
        out_path=digital_cover_path,
    )

    digital_pdf_path = split_for_digital(
        print_pdf_path, job_dir,
        skip_pages=digital_skip_pages,
        cover_page_path=digital_cover_path,
    )

    print_pdf_url = upload_to_storage(
        print_pdf_path, f"{slugify_key_component(req.order_number)}/{job_id}/print_ready.pdf"
    )
    digital_pages_url = upload_to_storage(
        digital_pdf_path, f"{slugify_key_component(req.order_number)}/{job_id}/digital_pages.pdf"
    )

    heyzine_book_id = upload_to_heyzine(digital_pages_url)

    return GenerateResponse(
        order_number=req.order_number,
        print_pdf_url=print_pdf_url,
        digital_pages_url=digital_pages_url,
        heyzine_book_id=heyzine_book_id,
        status="ready",
    )


@app.post("/generate-cover", response_model=GenerateCoverResponse)
def generate_cover(req: GenerateCoverRequest):
    """
    Generates the hardcover wraparound cover for an order. Fully
    independent of /generate -- spine width comes from the child's real
    letter count via the same page-count formula the URL Generator /
    Page Calculator tool uses, not from inspecting print_ready.pdf. So a
    cover can be generated before, after, or without ever running the
    interior book generation for this order.
    """
    if req.gender not in ("boy", "girl"):
        raise HTTPException(400, "gender must be 'boy' or 'girl'")

    job_id = str(uuid.uuid4())[:8]
    job_dir = os.path.join(OUTPUT_ROOT, f"{req.order_number}_{job_id}_cover")
    os.makedirs(job_dir, exist_ok=True)

    from assembly.cover import build_cover, calc_total_pages, get_spine_width_mm

    cover_pdf_path = os.path.join(job_dir, "cover.pdf")
    try:
        build_cover(req.child_name, req.gender, ASSET_ROOT, cover_pdf_path)
    except FileNotFoundError as e:
        raise HTTPException(500, f"Missing cover asset: {e}")
    except ValueError as e:
        raise HTTPException(400, str(e))

    n_letters = len(req.child_name.replace("-", ""))
    spine_width_mm, total_pages = get_spine_width_mm(n_letters)

    cover_pdf_url = upload_to_storage(
        cover_pdf_path, f"{slugify_key_component(req.order_number)}/{job_id}/cover.pdf"
    )

    return GenerateCoverResponse(
        order_number=req.order_number,
        cover_pdf_url=cover_pdf_url,
        total_pages=total_pages,
        spine_width_mm=spine_width_mm,
    )


@app.post("/upload-photo", response_model=UploadPhotoResponse)
def upload_photo_endpoint(req: UploadPhotoRequest):
    """
    Lets the admin dashboard attach or replace a photo on an existing
    order -- e.g. when the original checkout upload failed (large photo,
    413 from Netlify) and the customer had to resend it another way.
    Reuses upload_to_storage against the same 'customer-photos' bucket
    the checkout site's own upload-photo Netlify Function writes to, so
    both paths produce identically-shaped, correctly public URLs.
    """
    import base64

    job_dir = os.path.join(OUTPUT_ROOT, f"{req.order_number}_photo_{str(uuid.uuid4())[:8]}")
    os.makedirs(job_dir, exist_ok=True)

    ext = "png" if "png" in req.content_type else "jpg"
    local_path = os.path.join(job_dir, f"photo.{ext}")
    try:
        image_bytes = base64.b64decode(req.image_base64)
    except Exception:
        raise HTTPException(400, "image_base64 could not be decoded")
    with open(local_path, "wb") as f:
        f.write(image_bytes)

    storage_path = f"{slugify_key_component(req.order_number)}-{str(uuid.uuid4())[:8]}.{ext}"
    photo_url = upload_to_storage(local_path, storage_path, bucket="customer-photos")

    return UploadPhotoResponse(photo_url=photo_url)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
