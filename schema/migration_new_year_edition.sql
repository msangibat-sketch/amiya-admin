-- New Year special edition: which edition each order is, and (New Year
-- only) which cover color the customer chose. Price is the same for both.
-- Run once in Supabase → SQL Editor. Safe to re-run.
--
-- Every existing order becomes 'classic' automatically.

alter table orders add column if not exists edition text not null default 'classic';
alter table orders add column if not exists cover_color text;

-- Only allow known values (a typo from the website is caught here instead
-- of producing a wrong book). Deliberately does NOT require a color for
-- New Year orders, so a paid order is never rejected at checkout -- the
-- dashboard flags a New Year order that is missing its color instead.
alter table orders drop constraint if exists orders_edition_check;
alter table orders add constraint orders_edition_check
    check (edition in ('classic', 'new_year'));

alter table orders drop constraint if exists orders_cover_color_check;
alter table orders add constraint orders_cover_color_check
    check (cover_color is null or cover_color in ('blue', 'green', 'red'));

create index if not exists orders_edition_idx on orders(edition);
