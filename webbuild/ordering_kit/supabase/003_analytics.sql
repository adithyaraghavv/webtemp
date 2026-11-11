-- Numbers for the owner dashboard. Staff only. "Revenue" = value of orders that were not cancelled (what was sold);
-- "paid" = bills staff marked as paid in the range. Days, weeks and months follow settings.timezone.
create function public.analytics(p_from timestamptz, p_to timestamptz, p_bucket text default 'day') returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare tz text; res jsonb;
begin
  if not public.is_staff() then raise exception 'not allowed' using errcode = '42501'; end if;
  if p_bucket not in ('day', 'week', 'month') then raise exception 'bucket must be day, week or month'; end if;
  if p_from is null or p_to is null or p_to <= p_from or p_to - p_from > interval '800 days' then raise exception 'bad range'; end if;
  select timezone into tz from public.settings where id = 1;
  tz := coalesce(tz, 'Asia/Kolkata');

  with lines as (
    select o.id as order_id, o.created_at, oi.name, oi.qty, oi.price_paise * oi.qty as amount
    from public.orders o join public.order_items oi on oi.order_id = o.id
    where o.status <> 'cancelled' and o.created_at >= p_from and o.created_at < p_to
  ), ord as (
    select order_id, min(created_at) as created_at, sum(amount) as amount from lines group by order_id
  ), series as (
    select g as b from generate_series(date_trunc(p_bucket, p_from at time zone tz),
                                       date_trunc(p_bucket, (p_to - interval '1 microsecond') at time zone tz),
                                       ('1 ' || p_bucket)::interval) g
  )
  select jsonb_build_object(
    'overview', jsonb_build_object(
      'orders', (select count(*) from ord),
      'revenue_paise', coalesce((select sum(amount) from ord), 0),
      'avg_order_paise', coalesce((select round(avg(amount)) from ord), 0),
      'paid_paise', coalesce((select sum(total_paise) from public.bills where status = 'paid' and paid_at >= p_from and paid_at < p_to), 0)),
    'series', (select coalesce(jsonb_agg(jsonb_build_object('bucket', to_char(s.b, 'YYYY-MM-DD'), 'orders', coalesce(x.n, 0),
                                         'revenue_paise', coalesce(x.r, 0)) order by s.b), '[]'::jsonb)
               from series s left join (select date_trunc(p_bucket, created_at at time zone tz) as b, count(*) as n, sum(amount) as r
                                        from ord group by 1) x on x.b = s.b),
    'top', (select coalesce(jsonb_agg(jsonb_build_object('name', t.name, 'qty', t.q, 'revenue_paise', t.r) order by t.q desc, t.name), '[]'::jsonb)
            from (select l.name, sum(l.qty) as q, sum(l.amount) as r from lines l group by l.name order by sum(l.qty) desc, l.name limit 5) t),
    'least', (select coalesce(jsonb_agg(jsonb_build_object('name', t.name, 'qty', t.q, 'revenue_paise', t.r) order by t.q, t.name), '[]'::jsonb)
              from (select mi.name, coalesce(sum(l.qty), 0) as q, coalesce(sum(l.amount), 0) as r
                    from public.menu_items mi left join lines l on l.name = mi.name
                    where mi.available group by mi.id, mi.name order by coalesce(sum(l.qty), 0), mi.name limit 5) t),
    'hours', (select jsonb_agg(jsonb_build_object('hour', h, 'orders', coalesce(c.n, 0)) order by h)
              from generate_series(0, 23) h
              left join (select extract(hour from created_at at time zone tz)::int as hr, count(*) as n from ord group by 1) c on c.hr = h)
  ) into res;
  return res;
end $$;
revoke execute on function public.analytics(timestamptz, timestamptz, text) from public;
grant execute on function public.analytics(timestamptz, timestamptz, text) to authenticated;
