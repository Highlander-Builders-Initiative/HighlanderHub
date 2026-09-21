-- Shared by Actions and local ingestion. Stable slots represent billing accounts,
-- so replacing a secret or losing pipeline/data never resets the monthly count.
create table public.vision_ocr_usage (
    month date primary key,
    primary_requests integer not null default 0 check (primary_requests between 0 and 1000),
    overflow_requests bigint not null default 0 check (overflow_requests >= 0)
);

alter table public.vision_ocr_usage enable row level security;
revoke all on public.vision_ocr_usage from public, anon, authenticated;
grant select, insert, update on public.vision_ocr_usage to service_role;

-- One atomic upsert serializes concurrent reservations. Attempt 1000 uses the
-- primary key; 1001 and later use overflow, with paid usage allowed there.
-- Reserve before HTTP and keep the reservation on any failure/uncertain result.
create function public.reserve_vision_ocr_request()
returns jsonb
language sql
security invoker
set search_path = ''
as $$
    insert into public.vision_ocr_usage as usage (month, primary_requests, overflow_requests)
    values (date_trunc('month', current_timestamp at time zone 'America/Los_Angeles')::date, 1, 0)
    on conflict (month) do update
    set primary_requests = least(usage.primary_requests + 1, 1000),
        overflow_requests = usage.overflow_requests + case when usage.primary_requests >= 1000 then 1 else 0 end
    returning jsonb_build_object(
        'month', month,
        'slot', case when overflow_requests = 0 then 'primary' else 'overflow' end,
        'used', case when overflow_requests = 0 then primary_requests else overflow_requests end
    );
$$;

revoke all on function public.reserve_vision_ocr_request() from public, anon, authenticated;
grant execute on function public.reserve_vision_ocr_request() to service_role;
