-- Bill, optional rating, manual payment confirmation, and the staff dashboard view.

-- staff may only change an order's status, nothing else
revoke update on public.orders from authenticated;
grant update (status) on public.orders to authenticated;

create view public.staff_orders with (security_invoker = true) as
  select o.id, o.status, o.note, o.customer_name, o.customer_phone, o.created_at, o.updated_at,
         t.label as table_label, b.status as bill_status, b.id as bill_id,
         coalesce(jsonb_agg(jsonb_build_object('name', oi.name, 'qty', oi.qty, 'options', oi.options, 'note', oi.note)
                  order by oi.id) filter (where oi.id is not null), '[]'::jsonb) as items
  from public.orders o
  join public.bills b on b.id = o.bill_id
  join public.cafe_tables t on t.id = b.table_id
  left join public.order_items oi on oi.order_id = o.id
  group by o.id, t.label, b.status, b.id;
grant select on public.staff_orders to authenticated;

create view public.staff_bills with (security_invoker = true) as
  select b.id, b.status, b.created_at, b.requested_at, b.paid_at, b.rating, b.rating_comment, t.label as table_label,
         coalesce(b.total_paise, sum(oi.price_paise * oi.qty) filter (where o.status <> 'cancelled'), 0) as total_paise
  from public.bills b
  join public.cafe_tables t on t.id = b.table_id
  left join public.orders o on o.bill_id = b.id
  left join public.order_items oi on oi.order_id = o.id
  group by b.id, t.label;
grant select on public.staff_bills to authenticated;

-- the customer asks for the bill; the total is computed here from stored prices
create function public.request_bill(p_token text) returns jsonb language plpgsql security definer set search_path = '' as $$
declare b public.bills; total int; s public.settings;
begin
  select * into b from public.bills where token = p_token for update;
  if not found then raise exception 'unknown bill'; end if;
  if b.status = 'paid' then return jsonb_build_object('status', 'paid'); end if;
  select coalesce(sum(oi.price_paise * oi.qty), 0) into total
    from public.orders o join public.order_items oi on oi.order_id = o.id
    where o.bill_id = b.id and o.status <> 'cancelled';
  if total <= 0 then raise exception 'nothing to pay for yet'; end if;
  if b.status = 'open' then
    update public.bills set status = 'requested', total_paise = total, requested_at = now() where id = b.id returning * into b;
  end if;
  select * into s from public.settings where id = 1;
  return jsonb_build_object('status', b.status, 'total_paise', b.total_paise, 'bill_ref', left(b.id::text, 8),
    'cafe_name', s.cafe_name, 'currency', s.currency, 'upi_id', s.upi_id, 'upi_name', s.upi_name,
    'google_place_id', s.google_place_id, 'rated', b.rating is not null);
end $$;

-- optional, once, only after the bill was requested. Skipping simply never calls this.
create function public.submit_rating(p_token text, p_stars int, p_comment text default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare b public.bills;
begin
  if p_stars is null or p_stars < 1 or p_stars > 5 then raise exception 'stars must be 1 to 5'; end if;
  select * into b from public.bills where token = p_token for update;
  if not found then raise exception 'unknown bill'; end if;
  if b.status = 'open' then raise exception 'ask for the bill first'; end if;
  if b.rating is not null then raise exception 'already rated'; end if;
  update public.bills set rating = p_stars, rating_comment = nullif(left(p_comment, 500), '') where id = b.id;
  return jsonb_build_object('ok', true);
end $$;

-- staff only: the money was received (checked by a person; nothing here confirms it automatically)
create function public.mark_paid(p_bill uuid) returns jsonb language plpgsql security definer set search_path = '' as $$
declare b public.bills; total int;
begin
  if not public.is_staff() then raise exception 'not allowed' using errcode = '42501'; end if;
  select * into b from public.bills where id = p_bill for update;
  if not found then raise exception 'unknown bill'; end if;
  if b.status = 'paid' then return jsonb_build_object('status', 'paid'); end if;
  select coalesce(sum(oi.price_paise * oi.qty), 0) into total
    from public.orders o join public.order_items oi on oi.order_id = o.id
    where o.bill_id = b.id and o.status <> 'cancelled';
  update public.bills set status = 'paid', paid_at = now(), total_paise = coalesce(b.total_paise, total) where id = b.id;
  return jsonb_build_object('status', 'paid');
end $$;

revoke execute on function public.request_bill(text), public.submit_rating(text, int, text), public.mark_paid(uuid) from public;
grant execute on function public.request_bill(text), public.submit_rating(text, int, text) to anon, authenticated;
grant execute on function public.mark_paid(uuid) to authenticated;
