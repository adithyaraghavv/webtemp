-- QR table ordering: schema, row-level security and the only functions customers can call.
-- One Supabase project per cafe. Money is stored in paise (integers). Customers never touch tables directly;
-- they call the functions below with a per-table secret, then a per-bill token.

create extension if not exists pgcrypto with schema extensions;

create table public.settings (
  id int primary key default 1 check (id = 1),
  cafe_name text not null,
  currency text not null default 'Rs ',
  upi_id text,
  upi_name text,
  google_place_id text
);

create table public.menu_items (
  id uuid primary key default gen_random_uuid(),
  category text not null,
  category_order int not null default 0,
  name text not null check (length(name) between 1 and 80),
  description text not null default '' check (length(description) <= 240),
  price_paise int not null check (price_paise >= 0 and price_paise <= 10000000),
  image_url text,
  available boolean not null default true,
  sort int not null default 0
);

create table public.cafe_tables (
  id uuid primary key default gen_random_uuid(),
  label text not null unique check (length(label) between 1 and 20),
  secret text not null default encode(extensions.gen_random_bytes(12), 'hex'),
  active boolean not null default true
);

create table public.bills (
  id uuid primary key default gen_random_uuid(),
  table_id uuid not null references public.cafe_tables(id),
  token text not null unique default encode(extensions.gen_random_bytes(16), 'hex'),
  status text not null default 'open' check (status in ('open','requested','paid')),
  total_paise int,
  rating int check (rating between 1 and 5),
  rating_comment text check (length(rating_comment) <= 500),
  created_at timestamptz not null default now(),
  requested_at timestamptz,
  paid_at timestamptz
);
-- one open or requested bill per table at a time
create unique index one_live_bill_per_table on public.bills(table_id) where status in ('open','requested');

create table public.orders (
  id uuid primary key default gen_random_uuid(),
  bill_id uuid not null references public.bills(id),
  status text not null default 'new' check (status in ('new','preparing','served','cancelled')),
  note text check (length(note) <= 300),
  created_at timestamptz not null default now()
);
create index on public.orders(bill_id);
create index on public.orders(status, created_at);

create table public.order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  menu_item_id uuid not null references public.menu_items(id),
  name text not null,
  price_paise int not null,
  qty int not null check (qty between 1 and 20)
);
create index on public.order_items(order_id);

create table public.staff (user_id uuid primary key);

alter table public.settings enable row level security;
alter table public.menu_items enable row level security;
alter table public.cafe_tables enable row level security;
alter table public.bills enable row level security;
alter table public.orders enable row level security;
alter table public.order_items enable row level security;
alter table public.staff enable row level security;

create function public.is_staff() returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.staff where user_id = (select auth.uid()))
$$;
revoke all on function public.is_staff() from public;
grant execute on function public.is_staff() to authenticated;

-- customers (anon): read the menu only
create policy menu_public_read on public.menu_items for select to anon, authenticated using (available);
-- staff: full control of the cafe's data
create policy menu_staff_all on public.menu_items for all to authenticated using (public.is_staff()) with check (public.is_staff());
create policy tables_staff_all on public.cafe_tables for all to authenticated using (public.is_staff()) with check (public.is_staff());
create policy settings_staff_all on public.settings for all to authenticated using (public.is_staff()) with check (public.is_staff());
create policy bills_staff_read on public.bills for select to authenticated using (public.is_staff());
create policy orders_staff_read on public.orders for select to authenticated using (public.is_staff());
create policy orders_staff_update on public.orders for update to authenticated using (public.is_staff()) with check (public.is_staff());
create policy items_staff_read on public.order_items for select to authenticated using (public.is_staff());
-- staff table: nobody reads it through the API (is_staff() is security definer)

revoke all on all tables in schema public from anon, authenticated;
grant select on public.menu_items to anon, authenticated;
grant select, insert, update, delete on public.menu_items, public.cafe_tables, public.settings to authenticated;
grant select on public.bills, public.order_items to authenticated;
grant select, update on public.orders to authenticated;

-- public facts a customer page may read (no UPI id; that is released only with a requested bill)
create function public.get_cafe() returns jsonb language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('cafe_name', cafe_name, 'currency', currency, 'google_place_id', google_place_id)
  from public.settings where id = 1
$$;
revoke execute on function public.get_cafe() from public;
grant execute on function public.get_cafe() to anon, authenticated;

-- place an order from a table. Prices always come from menu_items, never from the caller.
create function public.place_order(p_table text, p_secret text, p_items jsonb, p_note text default null)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  t public.cafe_tables; b public.bills; o public.orders; it jsonb; m public.menu_items;
  n_lines int; q int; recent int; total int := 0;
begin
  select * into t from public.cafe_tables where label = p_table and active;
  if not found or t.secret is distinct from p_secret then
    raise exception 'unknown table' using errcode = 'P0001';
  end if;
  if jsonb_typeof(p_items) is distinct from 'array' then raise exception 'items must be a list'; end if;
  n_lines := jsonb_array_length(p_items);
  if n_lines < 1 or n_lines > 30 then raise exception 'an order needs between 1 and 30 lines'; end if;

  select * into b from public.bills where table_id = t.id and status = 'open';
  if not found then
    -- a bill that was requested is still waiting for payment; new orders go on a fresh bill only after payment
    if exists (select 1 from public.bills where table_id = t.id and status = 'requested') then
      raise exception 'the bill for this table is being settled';
    end if;
    insert into public.bills(table_id) values (t.id) returning * into b;
  end if;

  select count(*) into recent from public.orders where bill_id = b.id and created_at > now() - interval '10 minutes';
  if recent >= 10 then raise exception 'too many orders, please ask the staff'; end if;

  insert into public.orders(bill_id, note) values (b.id, nullif(left(p_note, 300), '')) returning * into o;
  for it in select * from jsonb_array_elements(p_items) loop
    begin
      q := (it->>'qty')::int;
    exception when others then raise exception 'bad quantity'; end;
    if q is null or q < 1 or q > 20 then raise exception 'bad quantity'; end if;
    begin
      select * into m from public.menu_items where id = (it->>'id')::uuid and available;
    exception when others then raise exception 'bad item'; end;
    if not found then raise exception 'item not available'; end if;
    insert into public.order_items(order_id, menu_item_id, name, price_paise, qty) values (o.id, m.id, m.name, m.price_paise, q);
    total := total + m.price_paise * q;
  end loop;
  return jsonb_build_object('order_id', o.id, 'bill_token', b.token, 'order_total_paise', total);
end $$;

-- what a customer sees about their own bill, found only by the secret token
create function public.get_bill(p_token text) returns jsonb language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'status', b.status,
    'rated', b.rating is not null,
    'total_paise', coalesce(sum(oi.price_paise * oi.qty) filter (where o.status <> 'cancelled'), 0),
    'orders', coalesce(jsonb_agg(distinct jsonb_build_object('id', o.id, 'status', o.status, 'at', o.created_at)) filter (where o.id is not null), '[]'::jsonb),
    'lines', coalesce(jsonb_agg(jsonb_build_object('name', oi.name, 'qty', oi.qty, 'price_paise', oi.price_paise, 'order_status', o.status)) filter (where oi.id is not null), '[]'::jsonb)
  )
  from public.bills b
  left join public.orders o on o.bill_id = b.id
  left join public.order_items oi on oi.order_id = o.id
  where b.token = p_token
  group by b.id
$$;

grant execute on function public.place_order(text, text, jsonb, text) to anon, authenticated;
grant execute on function public.get_bill(text) to anon, authenticated;
revoke execute on function public.place_order(text, text, jsonb, text) from public;
revoke execute on function public.get_bill(text) from public;
