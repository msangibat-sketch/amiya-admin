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
    allow_origins=["*"],
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


def sync_assets():
    """
    Placeholder: sync the spread/letter/font library from wherever it's
    canonically stored (Google Drive, S3, etc) onto local disk, if not
    already present. Assets change rarely, so this can just check a
    version marker and skip if already up to date.
    """
    pass


def download_photo(photo_url: str, dest_path: str):
    import requests
    r = requests.get(photo_url, timeout=30)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(r.content)


@app.on_event("startup")
def startup():
    sync_assets()
    os.makedirs(OUTPUT_ROOT, exist_ok=True)


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

    # TODO: upload print_pdf_path and digital_dir to real storage (S3,
    # Supabase storage, etc) and return their public URLs. For now,
    # returning local paths so this is testable end-to-end first.
    return GenerateResponse(
        order_number=req.order_number,
        print_pdf_url=print_pdf_path,
        digital_pages_url=digital_dir,
        status="ready",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
