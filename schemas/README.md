# Shared Supabase row contracts

Pipeline (Python) and the Next.js app (TypeScript) both read/write the same Postgres tables. These JSON Schemas are the **cross-language contract** for upsert rows — not a replacement for migrations.

| Artifact | Role |
| --- | --- |
| `supabase/migrations/*.sql` | Database source of truth (columns, enums, constraints, RLS) |
| `schemas/*.upsert.schema.json` | Pipeline ↔ app row shape (snake_case fields each side must produce/consume) |
| `src/lib/supabase-rows.ts` | Generated TypeScript types (`npm run generate:rows`) |
| `tests/schema-contracts.test.mjs` | TS enums + `EventRow` stay aligned with schemas |
| `pipeline/tests/test_schema_contract.py` | Python mappers emit exactly the schema property set |

## Regenerate TypeScript after schema edits

```bash
npm run generate:rows
```

## Optional: Supabase CLI types

For full `Database` typings (including `submissions`, joins, RPCs), you can still run:

```bash
supabase gen types typescript --local > src/lib/database.types.ts
```

That complements — but does not replace — the upsert schemas above. Pipeline code does not import `database.types.ts`; it validates against JSON Schema in unit tests instead.
