-- Demo data for the Brew House test cafe. Fake UPI id; never use real payment details in a demo.
insert into public.settings(id, cafe_name, currency, upi_id, upi_name, google_place_id)
  values (1, 'Brew House', 'Rs ', 'test.cafe@upi', 'Brew House (test)', null) on conflict (id) do nothing;

insert into public.menu_categories(id, name, sort) values
  ('c0000000-0000-0000-0000-000000000001', 'Coffee', 1),
  ('c0000000-0000-0000-0000-000000000002', 'Chai', 2),
  ('c0000000-0000-0000-0000-000000000003', 'Bakes', 3);

insert into public.menu_items(category_id, name, description, price_paise, image_url, options, sort) values
  ('c0000000-0000-0000-0000-000000000001', 'Filter coffee', 'Dark roast, hot milk, served in a davara', 9000, 'img/filter-coffee.jpg',
   '[{"name":"Size","choices":[{"label":"Regular","delta_paise":0},{"label":"Large","delta_paise":2000}]},{"name":"Sugar","choices":[{"label":"Normal"},{"label":"Less sugar"},{"label":"No sugar"}]}]', 1),
  ('c0000000-0000-0000-0000-000000000001', 'Cold brew', 'Steeped for twelve hours, over ice', 14000, 'img/cold-brew.jpg',
   '[{"name":"Size","choices":[{"label":"Regular","delta_paise":0},{"label":"Large","delta_paise":3000}]}]', 2),
  ('c0000000-0000-0000-0000-000000000002', 'Masala chai', 'Ginger, cardamom and a little cinnamon', 6000, 'img/masala-chai.jpg',
   '[{"name":"Sugar","choices":[{"label":"Normal"},{"label":"Less sugar"},{"label":"No sugar"}]}]', 1),
  ('c0000000-0000-0000-0000-000000000003', 'Banana bread', 'Baked every morning, sold until it runs out', 12000, 'img/banana-bread.jpg', '[]', 1);

insert into public.cafe_tables(label, secret) values ('T1', 'demo-secret-t1'), ('T2', 'demo-secret-t2'), ('T3', 'demo-secret-t3');
insert into public.staff(user_id) values ('11111111-1111-1111-1111-111111111111') on conflict do nothing;
