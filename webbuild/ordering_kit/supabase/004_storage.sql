-- Menu photos live in a public Storage bucket; only staff can add, replace or remove them.
-- Run this on Supabase (the storage schema comes with it).
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
  values ('menu', 'menu', true, 2097152, array['image/jpeg', 'image/png', 'image/webp'])
  on conflict (id) do nothing;

create policy menu_images_staff_insert on storage.objects for insert to authenticated
  with check (bucket_id = 'menu' and public.is_staff());
create policy menu_images_staff_update on storage.objects for update to authenticated
  using (bucket_id = 'menu' and public.is_staff()) with check (bucket_id = 'menu' and public.is_staff());
create policy menu_images_staff_delete on storage.objects for delete to authenticated
  using (bucket_id = 'menu' and public.is_staff());
