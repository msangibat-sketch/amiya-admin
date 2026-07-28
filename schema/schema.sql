-- Amiya Publishing order management schema
-- Run this in the Supabase SQL editor (or via `supabase db push`)

create type order_tier as enum ('essential', 'signature', 'magical');
create type order_status as enum ('new', 'generating', 'ready', 'packed', 'shipped', 'delivered');
create type child_gender as enum ('boy', 'girl');

create table orders (
    id uuid primary key default gen_random_uuid(),
    order_number text unique not null,           -- human-friendly, e.g. "ORD-0001"
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    -- book content
    child_name text not null,
    gender child_gender not null,
    tier order_tier not null,
    dedication_text text,
    photo_url text,                                -- ImgBB (or Drive) link to the uploaded photo

    -- per-letter variant assignments, e.g.
    -- [{"key":"a","case":"u","variant":"1"}, {"key":"m","case":"l","variant":"1"}, ...]
    letter_variants jsonb not null default '[]'::jsonb,

    -- shipping
    recipient_name text,
    phone text,
    province text,
    city text,
    street_address text,
    delivery_notes text,

    -- fulfillment
    status order_status not null default 'new',
    print_pdf_url text,                            -- where the generated print PDF lives once ready
    digital_pages_url text,                         -- folder/zip of page images for Heyzine

    notes text                                       -- free-form internal notes
);

create index orders_status_idx on orders(status);
create index orders_created_at_idx on orders(created_at desc);

-- keep updated_at fresh automatically
create or replace function set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger orders_updated_at
    before update on orders
    for each row execute function set_updated_at();

-- Row-level security: only authenticated staff can read/write.
-- (Adjust once you add multiple staff accounts with roles.)
alter table orders enable row level security;

create policy "Authenticated users can do everything"
    on orders for all
    using (auth.role() = 'authenticated')
    with check (auth.role() = 'authenticated');
