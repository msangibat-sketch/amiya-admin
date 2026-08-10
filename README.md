# Amiya Publishing — Admin System

This is the full order-management and book-generation system: a Supabase
database, a Python book-generation service (Render), and a React admin
dashboard (Netlify). This README explains how the pieces fit together, so
you can find your way back into any part of it later.

## The big picture

```
   Netlify                    Render                      Supabase
  (dashboard)  <---REST--->  (generation      <--REST-->  (database +
                              service)                     storage)
       |                          |
       |                          | reads assets baked into
       |                          | the Docker image at build
       |                          v
       |                    GitHub Release
       |                    (asset zip: spreads,
       |                     letters, fonts, covers,
       |                     caption spreadsheet)
       v
  Supabase Auth
  (email magic-link login)
```

Four separate places you deploy to, four separate places something can go
stale if you only update one of them:

1. **GitHub repo** (`msangibat-sketch/amiya-admin`) — all the code
2. **GitHub Release** (a separate thing from the repo — a big zip of art
   assets, downloaded fresh every time Render builds)
3. **Render** — runs the Python generation service, rebuilds from GitHub +
   the Release zip whenever you trigger a deploy
4. **Netlify** — runs the React dashboard, rebuilds from GitHub whenever
   you push

**The single most common failure in this whole project has been forgetting
one of these four when you meant to update all of them together.** If
something that should be fixed still isn't working, the first question is
always: did the code change on GitHub, AND did Render/Netlify actually
redeploy afterward?

## Repo structure

```
amiya-admin/
├── README.md                  (this file)
├── schema/
│   ├── schema.sql              original orders table
│   └── migration_*.sql         changes since then, run in order
├── dashboard/                  React admin app (Netlify)
│   ├── package.json
│   └── src/
│       ├── App.jsx              basically the whole dashboard, one file
│       ├── main.jsx
│       └── supabaseClient.js
└── service/                    Python generation API (Render)
    ├── Dockerfile               builds the container, downloads assets
    ├── requirements.txt
    ├── main.py                  FastAPI app, all HTTP endpoints
    └── assembly/                the actual book/cover-building logic
        ├── stitch.py             orchestrates the whole book
        ├── letters.py            letter accumulation garland + captions
        ├── cover.py               hardcover wraparound cover
        ├── hello.py, spread2_dedication.py, spread3_intro.py,
        │   spread4_gathering.py, farewell.py, full_name_reveal.py
        │                         one file per fixed spread
        ├── photo_utils.py
        └── config.py
```

## The asset library — separate from code, easy to forget

Spreads, letter PNGs, fonts, cover templates, and the caption spreadsheet
are **not** in the git repo — they're too big (hundreds of MB to low GB).
Instead:

1. You keep a master copy of everything in Google Drive.
2. When something changes, you zip the whole `amiya-assets/` folder and
   upload it as a new file under the GitHub **Release** (Releases tab on
   the repo, not a normal commit).
3. `service/Dockerfile` has a `wget` line pointing at that exact zip
   filename. **This filename has a timestamp in it and must be updated
   every time you upload a new zip** — the Dockerfile doesn't
   automatically pick up "the latest" release, it downloads one exact
   file.
4. Every Render deploy re-downloads and unzips this file into
   `/app/assets` inside the container.

Expected folder structure inside the zip:
```
amiya-assets/
├── caption_text.xlsx
├── spreads/         hello_{gender}.pdf, gathering_{gender}.pdf,
│                    spread-{key}-{variant}-meet-{gender}.pdf,
│                    spread-{key}-{case}-{variant}-give-{gender}.pdf, etc.
├── letters/         {key}-{case}-{variant}.png  (day versions)
├── letters_night/   same filenames, white-string night versions
├── fonts/           PlaypenSans-Regular.ttf, Nunito-Custom450.ttf,
│                    NexaScript-Regular.ttf, Lazydog-Regular.ttf
└── covers/          boy_cover.pdf, girl_cover.pdf (NO logo/title baked
                     in — those get placed by code), logo.png
```

**Filenames must match exactly** — case-sensitive, no `_asset` suffixes
or other leftovers from however you downloaded a file. `main.py` prints
an OK/MISSING check for every expected asset file every time the service
starts up — check Render's logs right after a deploy to catch a missing
or misnamed file immediately, rather than waiting for a real order to
crash on it.

## How book generation actually works

1. Dashboard sends `POST /generate` to Render with the order's name,
   gender, tier, dedication text, photo URL, and the letter variants the
   admin picked.
2. `stitch.py` builds each spread in order: hello → dedication → intro →
   gathering → letter sequence (meet/give pairs with the accumulating
   garland) → farewell → full-name reveal → ending, using the matching
   file in `assembly/`.
3. Everything gets combined into one `print_ready.pdf` (full spreads,
   300dpi, print quality).
4. That same PDF gets split down the center into single pages and
   recombined into one `digital_pages.pdf` at a lower resolution
   (150dpi/JPEG q85) — this is the version for Heyzine's on-screen reader,
   deliberately smaller than print quality since it's never printed.
5. Both PDFs get uploaded to Supabase Storage, and their public URLs get
   saved back onto the order.

Letter accumulation sizing is **computed fresh per page** (not once for
the whole book) — each give-spread packs however many letters have been
given so far into a fixed-width zone, so early pages show bigger letters
that shrink toward the book's final size as more letters join. Dash
characters (for hyphenated names) don't count toward this sizing at all —
they're inserted afterward at a small fixed size so they never shrink the
real letters.

## How cover generation works

Separate endpoint (`POST /generate-cover`), and deliberately **independent**
of `/generate` — it never inspects `print_ready.pdf`. Page count (and
therefore spine width) comes purely from the child's letter count, using
the same formula as the standalone Page Calculator tool:
`total_pages = 14 + 4×(real letters, dashes excluded) + 2`, then looked up
against the printer's spine-width table (`SPINE_TABLE_MM` in `cover.py`).

The layout is safe-zone-first: a 207×218mm safe zone + 20mm wrap margin +
13mm groove defines a fixed 240mm panel width, symmetric front and back.
Only the spine width changes per order — the two panels get sliced out of
the source template pixel-for-pixel and never resized in a way that moves
their own artwork or logo position; only the spine strip between them
stretches or compresses to fit. Title and logo are rendered programmatically
(not baked into the source PDF) and centered on each panel's own safe-zone
center, so they stay correctly positioned no matter what page count the
order needs.

If you ever need to support books longer than 64 pages (13+ letter names),
`SPINE_TABLE_MM` in `cover.py` needs real numbers from the printer for
that range — right now it raises a clear error rather than guessing.

## Environment variables

**Render (service):**
- `ASSET_ROOT` — `/app/assets` (set in the Dockerfile already)
- `OUTPUT_ROOT` — `/app/output` (set in the Dockerfile already)
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` — needed for uploading generated
  PDFs to Storage

**Netlify (dashboard)**, as a `.env` or Netlify's own env var settings:
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_GENERATION_SERVICE_URL` — your Render service's base URL

## Supabase setup

- `orders` table (see `schema/schema.sql` + the `migration_*.sql` files,
  run in numeric order) holds every order: name, gender, tier, dedication
  text, shipping info, `letter_variants` (JSONB), `status` (a Postgres
  enum — see below), `selling_price`/`cost` (profit tracking),
  `print_pdf_url`, `digital_pages_url`, `cover_pdf_url`.
- `status` is a real Postgres enum type (`order_status`), not free text —
  adding a new status value needs `alter type order_status add value ...`
  run on its own (can't be inside a multi-statement transaction).
  Current values the dashboard offers: New, Generated, Sent to print,
  Shipped, Delivered (plus an internal `generating` transient state set
  automatically during generation).
- Storage bucket `generated-books`, public, holds every generated PDF.
- Auth: email magic-link (OTP) sign-in for the dashboard.

## Dashboard endpoints it calls

- `GET /health` — plain uptime check
- `GET /animal-names` — `{key}-{variant} → animal name` lookup, built
  from `caption_text.xlsx` at request time, used to show which animal a
  letter variant corresponds to when picking letters for an order
- `POST /generate` — full interior book
- `POST /generate-cover` — cover, independently of the above

## Deploying a change — checklist

**Code change in `service/`:** upload the changed file(s) to GitHub at
their exact path → Render should auto-deploy on push (or trigger Manual
Deploy) → check the startup asset-verification block in the logs to
confirm nothing broke.

**Code change in `dashboard/`:** upload to GitHub → Netlify auto-deploys
on push. If you changed `package.json` (new dependency), Netlify needs to
run `npm install` again, not just rebuild — check the build log.

**Asset change** (new/fixed artwork, font, or the caption spreadsheet):
update your local `amiya-assets/` folder → re-zip → upload as a new file
in the GitHub Release → **update the filename in `service/Dockerfile`**
to match → push the Dockerfile change → redeploy Render.

**Database change:** run the SQL directly in Supabase's SQL editor. Doesn't
need a redeploy anywhere, but code that depends on a new column (like a
dashboard field or a status value) obviously does.

## Things that have gone wrong before (so you recognize them faster)

- **Partial deploys**: uploading a file that *calls* a new function
  without also uploading the file that *defines* it (or vice versa) —
  always causes an immediate crash on first use. When in doubt after a
  multi-file change, re-check each file's content directly on GitHub.
- **Variant numbers stored inconsistently** in the caption spreadsheet
  (Excel sometimes saves `2` as `2.0`) — handled by normalizing to a
  clean integer everywhere it's read, but worth knowing about if a lookup
  ever seems to fail for a row you can see is right there.
- **Stray blank rows** in the caption spreadsheet (Excel can mark a row
  as "used" even with nothing typed in it, invisible to the eye) — the
  loader skips these automatically now, but if you ever see an
  `IndexError` or `TypeError` reading the spreadsheet, this is the first
  thing to suspect.
- **Captions that silently vanish**: if a caption line is wider than its
  text box, PyMuPDF renders *nothing at all* rather than clipping it.
  `insert_caption()` now auto-shrinks the font for any caption that's
  borderline too long, but a caption that's drastically too long (like a
  missing line break merging two sentences into one) still needs a
  spreadsheet fix, not a code fix.
- **Print buffering hiding logs**: without `PYTHONUNBUFFERED=1` in the
  Dockerfile, `print()` output can be delayed or dropped from Render's
  log view, making it look like the startup checks didn't run at all when
  they actually did.
- **Asset filenames need to be exact**: no `_asset` suffixes, no case
  differences, no stray spaces — the code does exact-match path lookups,
  not fuzzy search.
