-- FAQAT LOKAL TEST UCHUN: Supabase'dagi auth sxemasi va rollarining minimal o'xshashi
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticator') then create role authenticator login noinherit; end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then create role service_role nologin; end if;
end $$;
grant anon, authenticated, service_role to authenticator;
create schema if not exists auth;
create table if not exists auth.users (id uuid primary key default gen_random_uuid(), email text unique, encrypted_password text);
create or replace function auth.jwt() returns jsonb language sql stable as $$
  select coalesce(nullif(current_setting('request.jwt.claims', true), ''), '{}')::jsonb $$;
create or replace function auth.uid() returns uuid language sql stable as $$
  select nullif(auth.jwt() ->> 'sub', '')::uuid $$;
grant usage on schema auth to anon, authenticated;
grant execute on all functions in schema auth to anon, authenticated;
grant usage on schema public to anon, authenticated;
-- Supabase Auth sessiya jadvallarining soddalashtirilgan o'xshashi (sessiyalarni bekor qilishni sinash uchun)
create table if not exists auth.sessions (id uuid primary key default gen_random_uuid(), user_id uuid not null, created_at timestamptz default now());
create table if not exists auth.refresh_tokens (id bigserial primary key, token text, user_id varchar(255), revoked boolean default false,
  session_id uuid references auth.sessions (id) on delete cascade);
-- Supabase standart huquqlari taqlidi: public sxemasida yangi jadval/funksiya/sequence avtomatik anon, authenticated, service_role ga beriladi.
-- Migratsiyalarimiz buni bekor qilishi (revoke) kerak — production_verify va testlar shu sharoitda tekshiradi.
grant usage on schema public to anon, authenticated, service_role;
alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
alter default privileges in schema public grant all on functions to anon, authenticated, service_role;
alter default privileges in schema public grant all on sequences to anon, authenticated, service_role;
