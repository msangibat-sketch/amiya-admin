# Amiya Publishing — Admin System

This is the full order-management system: a Supabase database, a Python
book-generation service, and a React admin dashboard.

## What's real vs. what's left to wire up

**Real and tested:** every piece of book-generation logic (accumulation
garland, captions, dedication/photo, all fixed spreads) — this is the code
from our testing, copied directly into `service/assembly/`.

**Left to do (mechanical, not risky):**
1. Each file in `service/assembly/` has some hardcoded test paths
   (`/home/claude/amiyaa_test/...`) — these need to point at wherever the
   asset library actually lives on the server instead (see Step 2 below).
2. `service/assembly/stitch.py` has the orchestration commented out —
   uncomment once paths are fixed, and it calls everything in the right order.
3. File storage upload (`main.py`'s TODO) — decide where generated PDFs get
   stored (Supabase Storage is easiest since you already have a Supabase
   project) and add the upload call.

This is exactly the kind of step-by-step wiring work Claude Code is well
suited for — it can edit files directly in this project folder, run the
service locally to test, and deploy it, without losing context between
steps the way a chat conversation does.

## Deployment steps

### 1. Supabase (database + auth + storage)
1. Create a project at supabase.com (free tier is enough to start).
2. In the SQL editor, run `schema/schema.sql`.
3. Under Storage, create a bucket called `generated-books`.
4. Under Authentication, enable Email OTP (magic link) sign-in — this is
   what the dashboard's login screen uses. Add your own email as the first
   user (invite yourself, or just sign in once and you're in).
5. Copy your Project URL and anon key (Settings → API) — you'll need these
   for both the service and the dashboard.

### 2. Asset library
Upload your full spread/letter/font library to the server. Simplest path:
put everything in `service/assets/` following the same structure we used
in testing (`spreads/`, `letters/`, `letters_night/`, `fonts/`), matching
the naming convention we locked in. Since this is several GB, don't commit
it to git — instead, either bake it into the Docker image at build time,
or upload it once to Supabase Storage / S3 and have `sync_assets()` in
`main.py` pull it down on first startup.

### 3. Generation service (Render or Railway)
1. Push this `service/` folder to a GitHub repo.
2. On Render (or Railway): New → Web Service → connect the repo, point it
   at the Dockerfile.
3. Set environment variables: `ASSET_ROOT=/app/assets`,
   `OUTPUT_ROOT=/app/output`, plus your Supabase URL/key if `main.py`
   uploads directly to Supabase Storage.
4. Deploy. Test with: `curl https://your-service.onrender.com/health`

### 4. Dashboard (Netlify — same workflow you already use)
1. `cd dashboard && npm install`
2. Create `.env`:
   ```
   VITE_SUPABASE_URL=https://your-project.supabase.co
   VITE_SUPABASE_ANON_KEY=your-anon-key
   VITE_GENERATION_SERVICE_URL=https://your-service.onrender.com
   ```
3. `npm run build`, then drag the `dist/` folder into Netlify like you
   already do for the e-commerce site.

### 5. Connect order intake
Once this is live, wire your checkout flow to write directly into the
`orders` table via the Supabase JS client (same pattern as `supabaseClient.js`
here) instead of only sending the EmailJS notification — this is the
"orders land automatically" piece from our earlier conversation.

## Local testing before deploying anything
```
cd service
pip install -r requirements.txt
python main.py
# in another terminal:
curl -X POST http://localhost:8000/generate -H "Content-Type: application/json" -d '{...}'
```
