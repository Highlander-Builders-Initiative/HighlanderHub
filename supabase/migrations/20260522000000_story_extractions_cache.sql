-- Durable cache for Instagram story OCR + Gemini extraction results.
--
-- The pipeline still checks pipeline/data/extracted first for fast local runs,
-- but this table prevents stateless CI workers from repeating paid Vision and
-- Gemini calls for story IDs that were already classified.

create table story_extractions (
  story_id      text primary key,
  handle        text not null,
  status        text not null check (
    status in ('ok', 'not_event', 'no_text', 'image_expired', 'error')
  ),
  ocr_text      text,
  result        jsonb,
  extracted_at  timestamptz not null default now(),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index story_extractions_handle_idx on story_extractions (handle);
create index story_extractions_status_idx on story_extractions (status);
create index story_extractions_extracted_at_idx on story_extractions (extracted_at desc);

create trigger story_extractions_set_updated_at
before update on story_extractions
for each row execute function set_updated_at();

alter table story_extractions enable row level security;
