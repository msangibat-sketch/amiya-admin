-- Lets the admin dashboard (signed-in staff) see and manage discount
-- codes and gift cards, the same way it already manages orders.
-- Run once in Supabase → SQL Editor. Safe to re-run.
--
-- The promo_codes table itself is created by the website repo's
-- supabase/promo-codes.sql (run that first, if it isn't already).

drop policy if exists "Authenticated users can do everything" on promo_codes;
create policy "Authenticated users can do everything"
    on promo_codes for all
    using (auth.role() = 'authenticated')
    with check (auth.role() = 'authenticated');
