-- Counts for the weekly numbers in the dashboard (Stats page).
-- Run once in Supabase → SQL Editor. Safe to re-run.
--
-- One row per step a visitor reaches. No names, photos, phone numbers or
-- other personal details are stored -- only what happened and when.
--   form_started        passed the name step on the website
--   preview_built       the book service built a preview
--   preview_unsupported name had a letter with no art yet (detail = the letters)
--   preview_limited     visitor hit the hourly preview limit
--   preview_failed      preview couldn't be built (detail = reason)
--   package_reached     reached the package step after the preview
-- Orders started / paid and the Premium share come from the orders table.

create table if not exists funnel_events (
    id bigserial primary key,
    created_at timestamptz not null default now(),
    event text not null,
    detail text
);

create index if not exists funnel_events_created_at_idx on funnel_events(created_at desc);

-- Written by the book service and the website's Netlify function with the
-- service key (which bypasses this); the dashboard only reads.
alter table funnel_events enable row level security;
drop policy if exists "Authenticated users can read" on funnel_events;
create policy "Authenticated users can read"
    on funnel_events for select
    using (auth.role() = 'authenticated');
