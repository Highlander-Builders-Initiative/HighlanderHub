-- Guardrails for user-facing event links and event time ordering.
-- NOT VALID keeps existing rows from blocking the migration while still
-- enforcing the constraints for new inserts and future updates.

alter table events
  add constraint events_ends_at_after_starts_at
    check (ends_at is null or ends_at >= starts_at) not valid,
  add constraint events_source_url_http
    check (source_url is null or source_url ~* '^https?://[^[:space:]]+$') not valid,
  add constraint events_image_url_http
    check (image_url is null or image_url ~* '^https?://[^[:space:]]+$') not valid,
  add constraint events_rsvp_url_http
    check (rsvp_url is null or rsvp_url ~* '^https?://[^[:space:]]+$') not valid;

alter table submissions
  add constraint submissions_ends_at_after_starts_at
    check (ends_at is null or ends_at >= starts_at) not valid,
  add constraint submissions_source_url_http
    check (source_url is null or source_url ~* '^https?://[^[:space:]]+$') not valid,
  add constraint submissions_image_url_http
    check (image_url is null or image_url ~* '^https?://[^[:space:]]+$') not valid,
  add constraint submissions_rsvp_url_http
    check (rsvp_url is null or rsvp_url ~* '^https?://[^[:space:]]+$') not valid;
