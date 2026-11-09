-- Demo data for the Brew House test cafe. Fake UPI id; never use real payment details in a demo.
insert into public.settings(id, cafe_name, currency, upi_id, upi_name, google_place_id)
  values (1, 'Brew House', 'Rs ', 'test.cafe@upi', 'Brew House (test)', null)
  on conflict (id) do nothing;
insert into public.menu_items(category, category_order, name, description, price_paise, image_url, sort) values
  ('Coffee', 1, 'Filter coffee', 'Dark roast, hot milk, served in a davara', 9000, null, 1),
  ('Coffee', 1, 'Cold brew', 'Steeped for twelve hours, over ice', 14000, null, 2),
  ('Chai', 2, 'Masala chai', 'Ginger, cardamom and a little cinnamon', 6000, null, 1),
  ('Bakes', 3, 'Banana bread', 'Baked every morning, sold until it runs out', 12000, null, 1);
insert into public.cafe_tables(label, secret) values ('T1', 'demo-secret-t1'), ('T2', 'demo-secret-t2'), ('T3', 'demo-secret-t3');
insert into public.staff(user_id) values ('11111111-1111-1111-1111-111111111111') on conflict do nothing;
