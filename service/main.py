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


class LetterVariant(BaseModel):
    key: str
    case: str          # "u" or "l"
    variant: str


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
    status: str


def download_photo(photo_url: str, dest_path: str):
    import requests
    r = requests.get(photo_url, timeout=30)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(r.content)


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
STORAGE_BUCKET = "generated-books"


def upload_to_storage(local_path: str, storage_path: str) -> str:
    """
    Uploads a file to Supabase Storage via its REST API directly (no SDK
    dependency needed) and returns the public URL. Requires SUPABASE_URL
    and SUPABASE_SERVICE_KEY env vars to be set, and a public bucket named
    'generated-books' to already exist in the Supabase project.
    """
    import requests
    import mimetypes

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY env vars are not set")

    content_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    upload_url = f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{storage_path}"

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

    return f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{storage_path}"


def zip_directory(dir_path: str, zip_path: str):
    import shutil
    shutil.make_archive(zip_path.replace(".zip", ""), "zip", dir_path)


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
    for fixed in ["dedication.pdf", "ending.pdf"]:
        p = os.path.join(ASSET_ROOT, "spreads", fixed)
        print(f"  [{'OK' if os.path.exists(p) else 'MISSING'}] spreads/{fixed}")

    print("=" * 50)


@app.get("/health")
def health():
    return {"status": "ok"}


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

    print_pdf_path = stitch_all(
        asset_root=ASSET_ROOT,
        name=req.child_name,
        gender=req.gender,
        dedication_text=req.dedication_text,
        photo_path=photo_path,
        letter_variants=[lv.dict() for lv in req.letter_variants],
        out_dir=job_dir,
    )
    digital_dir = split_for_digital(print_pdf_path, job_dir)

    # zip the digital pages into one file, then upload both to storage
    digital_zip_path = os.path.join(job_dir, "digital_pages.zip")
    zip_directory(digital_dir, digital_zip_path)

    print_pdf_url = upload_to_storage(
        print_pdf_path, f"{req.order_number}/{job_id}/print_ready.pdf"
    )
    digital_pages_url = upload_to_storage(
        digital_zip_path, f"{req.order_number}/{job_id}/digital_pages.zip"
    )

    return GenerateResponse(
        order_number=req.order_number,
        print_pdf_url=print_pdf_url,
        digital_pages_url=digital_pages_url,
        status="ready",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
