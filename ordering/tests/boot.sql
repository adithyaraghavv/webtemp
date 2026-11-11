-- Run once against an EMPTY throwaway database before the migrations (never against Supabase):
-- creates the roles and the auth.uid() stub that Supabase normally provides.
do $$ begin
  if not exists (select 1 from pg_roles where rolname='anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname='authenticated') then create role authenticated nologin; end if;
end $$;
create schema if not exists auth; create schema if not exists extensions; create schema if not exists storage;
create extension if not exists pgcrypto with schema extensions;
create or replace function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub', true),'')::uuid $$;
grant usage on schema public, auth, extensions, storage to anon, authenticated;
grant execute on function auth.uid() to anon, authenticated;

-- minimal stand-in for Supabase Storage so 004_storage.sql can be applied locally
create schema if not exists storage;
create table if not exists storage.buckets (id text primary key, name text, public boolean, file_size_limit bigint, allowed_mime_types text[]);
create table if not exists storage.objects (id uuid primary key default gen_random_uuid(), bucket_id text, name text);
alter table storage.objects enable row level security;
