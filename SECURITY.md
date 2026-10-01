# Security

Only the current default branch receives security fixes. Keep Next.js and the
pipeline dependencies updated, and run the dependency audits in App CI before
deploying changes.

Report vulnerabilities through [GitHub private vulnerability reporting](https://github.com/Highlander-Builders-Initiative/HighlanderHub/security/advisories/new).
Do not post credentials, private pipeline data, or exploitable details in public
issues. Regular event corrections and nonsecurity bugs can use public issues.

The public app reads published events. Administrative writes require server-side
authentication and a service-role client. Apply all Supabase migrations before
deploying the app; the admin login limiter fails closed if its migration is absent.
Keep service-role keys, provider credentials, and the admin password in environment
or Actions secrets. Never put them in client environment variables or Git.

Pipeline recovery state and diagnostics use authenticated encryption before
being uploaded to Actions caches or artifacts. Keep `PIPELINE_CACHE_KEY` as an
Actions secret and retain a private recovery copy. Changing that key without
reencrypting saved state prevents recovery of pending paid runs.
