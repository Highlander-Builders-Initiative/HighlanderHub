-- Apply before the app deploy: sign-in fails closed if this RPC is unavailable.
create table public.admin_login_attempts (
  key text primary key check (key ~ '^[a-f0-9]{64}$'),
  attempts integer not null check (attempts between 1 and 6),
  reset_at timestamptz not null
);
create index admin_login_attempts_reset_idx on public.admin_login_attempts (reset_at);
alter table public.admin_login_attempts enable row level security;
revoke all on public.admin_login_attempts from public, anon, authenticated;
grant select, insert, update, delete on public.admin_login_attempts to service_role;

create function public.check_admin_login_rate_limit(p_key text)
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare
  attempt public.admin_login_attempts;
  checked_at timestamptz := clock_timestamp();
begin
  if p_key is null or p_key !~ '^[a-f0-9]{64}$' then
    raise exception 'Invalid rate limit key';
  end if;
  delete from public.admin_login_attempts where reset_at <= checked_at;
  insert into public.admin_login_attempts as current (key, attempts, reset_at)
    values (p_key, 1, checked_at + interval '10 minutes')
    on conflict (key) do update set
      attempts = least(current.attempts + 1, 6)
    returning * into attempt;
  return jsonb_build_object(
    'ok', attempt.attempts <= 5,
    'retry_after_seconds', case when attempt.attempts <= 5 then 0
      else greatest(1, ceil(extract(epoch from attempt.reset_at - checked_at))::integer) end
  );
end;
$$;
revoke all on function public.check_admin_login_rate_limit(text) from public, anon, authenticated;
grant execute on function public.check_admin_login_rate_limit(text) to service_role;
