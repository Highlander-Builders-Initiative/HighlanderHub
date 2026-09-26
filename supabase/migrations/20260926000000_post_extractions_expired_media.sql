-- A post whose saved image URL expired before it was read is set aside until
-- that URL is refreshed, instead of failing every run as a retryable error.
alter table public.post_extractions
    drop constraint post_extractions_status_check,
    add constraint post_extractions_status_check check (
        status in ('ok', 'no_text', 'unsupported_media', 'no_media', 'expired_media', 'error')
    );
