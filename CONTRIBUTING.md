# Contributing

Fork the repository and open a pull request. Explain the problem, the resulting
behavior, and how you verified it. Keep changes focused and discuss substantial
ingestion, publication, database, or deployment changes with the maintainers first.

For local web development, install Node.js 24, run `npm ci`, copy `.env.example`
to `.env.local`, and configure your own Supabase project. Apply the migrations to
that project and run `npm run dev`. Public browse fixtures are available through
`HIGHLANDERHUB_E2E_FIXTURES=1`; never point fixture tests at production credentials.

Run `npm run lint`, `npm test`, `npm run build`, and `npm run e2e` for relevant web
changes. For pipeline changes, use Python 3.12 and install
`pipeline/requirements.txt` plus `pipeline/requirements-legacy.txt`; then run
`PYTHON_DOTENV_DISABLED=1 python -m unittest discover -s pipeline/tests -p 'test_*.py'`.
See [pipeline/README.md](pipeline/README.md) for setup and operating contracts.

Do not commit environment files, cookies, sessions, runtime state, raw archives,
internal reports, or generated build output. Use synthetic or intentionally public
source fixtures for tests. Do not run paid collection, publish data, or apply
migrations against production while testing a contribution.

App CI runs without production secrets. Preserve that boundary: untrusted PR code
must never run with production credentials. Review security fixes through the
private reporting process in [SECURITY.md](SECURITY.md).
