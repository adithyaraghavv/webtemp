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
  google_place_id text,
  timezone text not null default 'Asia/Kolkata'
);

create table public.menu_categories (
  id uuid primary key default gen_random_uuid(),
  name text not null unique check (length(name) between 1 and 40),
  sort int not null default 0
);

-- options: [{"name":"Size","required":true,"choices":[{"label":"Regular","delta_paise":0},{"label":"Large","delta_paise":2000}]}]
create table public.menu_items (
  id uuid primary key default gen_random_uuid(),
  category_id uuid not null references public.menu_categories(id) on delete restrict,
  name text not null check (length(name) between 1 and 80),
  description text not null default '' check (length(description) <= 240),
  price_paise int not null check (price_paise >= 0 and price_paise <= 10000000),
  image_url text check (image_url is null or length(image_url) <= 500),
  options jsonb not null default '[]'::jsonb,
  available boolean not null default true,
  sort int not null default 0
);

create function public.menu_items_check() returns trigger language plpgsql set search_path = '' as $$
declare g jsonb; c jsonb; names text[] := '{}'; labels text[];
begin
  if jsonb_typeof(new.options) is distinct from 'array' or jsonb_array_length(new.options) > 6 then
    raise exception 'options must be a list of at most 6 groups';
  end if;
  for g in select value from jsonb_array_elements(new.options) loop
    if jsonb_typeof(g) is distinct from 'object' or coalesce(length(g->>'name'), 0) not between 1 and 30 then
      raise exception 'bad option group name';
    end if;
    if (g->>'name') = any(names) then raise exception 'duplicate option group'; end if;
    names := names || (g->>'name');
    if jsonb_typeof(g->'choices') is distinct from 'array' or jsonb_array_length(g->'choices') not between 1 and 10 then
      raise exception 'each option group needs 1 to 10 choices';
    end if;
    labels := '{}';
    for c in select value from jsonb_array_elements(g->'choices') loop
      if jsonb_typeof(c) is distinct from 'object' or coalesce(length(c->>'label'), 0) not between 1 and 30 then
        raise exception 'bad choice label';
      end if;
      if (c->>'label') = any(labels) then raise exception 'duplicate choice'; end if;
      labels := labels || (c->>'label');
      if c ? 'delta_paise' and (jsonb_typeof(c->'delta_paise') is distinct from 'number'
         or (c->>'delta_paise')::numeric <> trunc((c->>'delta_paise')::numeric) or abs((c->>'delta_paise')::numeric) > 100000) then
        raise exception 'bad price change';
      end if;
    end loop;
  end loop;
  return new;
end $$;
create trigger menu_items_check before insert or update on public.menu_items for each row execute function public.menu_items_check();

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
  status text not null default 'new' check (status in ('new','preparing','ready','completed','cancelled')),
  note text check (length(note) <= 300),
  customer_name text check (length(customer_name) <= 40),
  customer_phone text check (customer_phone ~ '^[0-9+ -]{8,15}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- the only allowed moves: new > preparing > ready > completed, and cancel while not finished
create function public.orders_status_guard() returns trigger language plpgsql set search_path = '' as $$
begin
  if new.status = old.status then return new; end if;
  if not ((old.status = 'new' and new.status in ('preparing', 'cancelled'))
       or (old.status = 'preparing' and new.status in ('ready', 'cancelled'))
       or (old.status = 'ready' and new.status in ('completed', 'cancelled'))) then
    raise exception 'invalid status change from % to %', old.status, new.status;
  end if;
  new.updated_at := now();
  return new;
end $$;
create trigger orders_status_guard before update on public.orders for each row execute function public.orders_status_guard();
create index on public.orders(bill_id);
create index on public.orders(status, created_at);

create table public.order_items (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references public.orders(id) on delete cascade,
  menu_item_id uuid references public.menu_items(id) on delete set null,
  name text not null,
  price_paise int not null,           -- unit price including chosen options, fixed at order time
  qty int not null check (qty between 1 and 20),
  options jsonb not null default '[]'::jsonb,   -- [{"group":"Size","choice":"Large","delta_paise":2000}]
  note text check (length(note) <= 120)
);
create index on public.order_items(order_id);

create table public.staff (user_id uuid primary key);

alter table public.settings enable row level security;
alter table public.menu_categories enable row level security;
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
-- customers see every item, including sold-out ones (the page marks them); place_order refuses unavailable items
create policy menu_public_read on public.menu_items for select to anon, authenticated using (true);
create policy categories_public_read on public.menu_categories for select to anon, authenticated using (true);
create policy categories_staff_all on public.menu_categories for all to authenticated using (public.is_staff()) with check (public.is_staff());
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
grant select on public.menu_items, public.menu_categories to anon, authenticated;
grant select, insert, update, delete on public.menu_items, public.menu_categories, public.cafe_tables, public.settings to authenticated;
grant select on public.bills, public.order_items to authenticated;
grant select, update on public.orders to authenticated;

-- public facts a customer page may read (no UPI id; that is released only with a requested bill)
create function public.get_cafe() returns jsonb language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('cafe_name', cafe_name, 'currency', currency, 'google_place_id', google_place_id)
  from public.settings where id = 1
$$;
revoke execute on function public.get_cafe() from public;
grant execute on function public.get_cafe() to anon, authenticated;

-- place an order from a table. Prices and option prices always come from menu_items, never from the caller.
-- p_items: [{"id": "<menu item id>", "qty": 2, "options": {"Size": "Large"}, "note": "less sugar"}]
create function public.place_order(p_table text, p_secret text, p_items jsonb, p_note text default null,
                                   p_name text default null, p_phone text default null)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  t public.cafe_tables; b public.bills; o public.orders; it jsonb; m public.menu_items; grp jsonb; ch jsonb; req jsonb;
  n_lines int; q int; recent int; unit int; delta int; total int := 0; snap jsonb; k text; val text; nm text; ph text; ln text;
begin
  select * into t from public.cafe_tables where label = p_table and active;
  if not found or t.secret is distinct from p_secret then
    raise exception 'unknown table' using errcode = 'P0001';
  end if;
  if jsonb_typeof(p_items) is distinct from 'array' then raise exception 'items must be a list'; end if;
  n_lines := jsonb_array_length(p_items);
  if n_lines < 1 or n_lines > 30 then raise exception 'an order needs between 1 and 30 lines'; end if;
  nm := nullif(left(trim(coalesce(p_name, '')), 40), '');
  ph := nullif(trim(coalesce(p_phone, '')), '');
  if ph is not null and ph !~ '^[0-9+ -]{8,15}$' then raise exception 'bad phone'; end if;

  select * into b from public.bills where table_id = t.id and status = 'open';
  if not found then
    if exists (select 1 from public.bills where table_id = t.id and status = 'requested') then
      raise exception 'the bill for this table is being settled';
    end if;
    insert into public.bills(table_id) values (t.id) returning * into b;
  end if;

  select count(*) into recent from public.orders where bill_id = b.id and created_at > now() - interval '10 minutes';
  if recent >= 10 then raise exception 'too many orders, please ask the staff'; end if;

  insert into public.orders(bill_id, note, customer_name, customer_phone)
    values (b.id, nullif(left(p_note, 300), ''), nm, ph) returning * into o;

  for it in select value from jsonb_array_elements(p_items) loop
    begin q := (it->>'qty')::int; exception when others then raise exception 'bad quantity'; end;
    if q is null or q < 1 or q > 20 then raise exception 'bad quantity'; end if;
    begin
      select * into m from public.menu_items where id = (it->>'id')::uuid and available;
    exception when others then raise exception 'bad item'; end;
    if not found then raise exception 'item not available'; end if;

    req := coalesce(it->'options', '{}'::jsonb);
    if jsonb_typeof(req) is distinct from 'object' then raise exception 'bad options'; end if;
    for k in select jsonb_object_keys(req) loop
      if not exists (select 1 from jsonb_array_elements(m.options) g where g->>'name' = k) then
        raise exception 'bad option';
      end if;
    end loop;
    unit := m.price_paise; snap := '[]'::jsonb;
    for grp in select value from jsonb_array_elements(m.options) loop
      val := req->>(grp->>'name');
      if val is null then
        if coalesce((grp->>'required')::boolean, false) then raise exception 'missing option'; end if;
        continue;
      end if;
      ch := null;
      select value into ch from jsonb_array_elements(grp->'choices') where value->>'label' = val limit 1;
      if ch is null then raise exception 'bad option'; end if;
      delta := coalesce((ch->>'delta_paise')::int, 0);
      unit := unit + delta;
      snap := snap || jsonb_build_array(jsonb_build_object('group', grp->>'name', 'choice', val, 'delta_paise', delta));
    end loop;
    if unit < 0 then raise exception 'bad option'; end if;
    ln := nullif(left(trim(coalesce(it->>'note', '')), 120), '');
    insert into public.order_items(order_id, menu_item_id, name, price_paise, qty, options, note)
      values (o.id, m.id, m.name, unit, q, snap, ln);
    total := total + unit * q;
  end loop;
  return jsonb_build_object('order_id', o.id, 'bill_token', b.token, 'order_total_paise', total);
end $$;

-- what a customer sees about their own bill, found only by the secret token
create function public.get_bill(p_token text) returns jsonb language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'status', b.status,
    'rated', b.rating is not null,
    'total_paise', coalesce(sum(oi.price_paise * oi.qty) filter (where o.status <> 'cancelled'), 0),
    'lines', coalesce(jsonb_agg(jsonb_build_object('name', oi.name, 'qty', oi.qty, 'price_paise', oi.price_paise,
              'options', oi.options, 'note', oi.note, 'order_status', o.status) order by o.created_at, oi.id) filter (where oi.id is not null), '[]'::jsonb)
  )
  from public.bills b
  left join public.orders o on o.bill_id = b.id
  left join public.order_items oi on oi.order_id = o.id
  where b.token = p_token
  group by b.id
$$;

grant execute on function public.place_order(text, text, jsonb, text, text, text) to anon, authenticated;
grant execute on function public.get_bill(text) to anon, authenticated;
revoke execute on function public.place_order(text, text, jsonb, text, text, text) from public;
revoke execute on function public.get_bill(text) from public;
