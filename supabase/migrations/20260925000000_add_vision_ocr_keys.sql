-- Preserve existing monthly usage while adding two optional billing-account slots.
alter table public.vision_ocr_usage
    add column secondary_requests integer not null default 0
        check (secondary_requests between 0 and 1000),
    add column tertiary_requests integer not null default 0
        check (tertiary_requests between 0 and 1000);

-- Keep the zero-argument RPC available for existing two-key clients.
create function public.reserve_vision_ocr_request(
    p_secondary_enabled boolean,
    p_tertiary_enabled boolean
)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
    usage_month date := date_trunc('month', current_timestamp at time zone 'America/Los_Angeles')::date;
    current_usage public.vision_ocr_usage%rowtype;
    selected_slot text;
    used bigint;
begin
    insert into public.vision_ocr_usage (month) values (usage_month)
    on conflict (month) do nothing;

    -- Serialize all callers before selecting an allowance, including old clients.
    select * into current_usage from public.vision_ocr_usage
    where month = usage_month for update;

    if current_usage.primary_requests < 1000 then
        selected_slot := 'primary';
        used := current_usage.primary_requests + 1;
    elsif p_secondary_enabled and current_usage.secondary_requests < 1000 then
        selected_slot := 'secondary';
        used := current_usage.secondary_requests + 1;
    elsif p_tertiary_enabled and current_usage.tertiary_requests < 1000 then
        selected_slot := 'tertiary';
        used := current_usage.tertiary_requests + 1;
    else
        selected_slot := 'overflow';
        used := current_usage.overflow_requests + 1;
    end if;

    update public.vision_ocr_usage
    set primary_requests = primary_requests + (selected_slot = 'primary')::integer,
        secondary_requests = secondary_requests + (selected_slot = 'secondary')::integer,
        tertiary_requests = tertiary_requests + (selected_slot = 'tertiary')::integer,
        overflow_requests = overflow_requests + (selected_slot = 'overflow')::integer
    where month = usage_month;

    return jsonb_build_object('month', usage_month, 'slot', selected_slot, 'used', used);
end;
$$;

revoke all on function public.reserve_vision_ocr_request(boolean, boolean) from public, anon, authenticated;
grant execute on function public.reserve_vision_ocr_request(boolean, boolean) to service_role;
