import { spawnSync } from 'node:child_process';

// npm audit cannot ignore an advisory. Each entry here is one with no patched
// release that the depending packages accept, and that has been judged not to
// apply; remove it once they move to a fixed version.
const ACCEPTED = {
  // picomatch <=4.0.7 (every release): ReDoS from single-branch repeated
  // extglobs. No patched release exists. Reached only through dev tooling
  // (tailwindcss via anymatch, micromatch, and readdirp; eslint via
  // tinyglobby), which expands this repository's own globs, never user input.
  'GHSA-fc5q-39xc-vjpf': 'picomatch has no patched release; dev tooling only',
};
const BLOCKING = new Set(['moderate', 'high', 'critical']);

const audit = spawnSync('npm', ['audit', '--json'], { encoding: 'utf8' });
const report = JSON.parse(audit.stdout || '{}');
if (!report.vulnerabilities) {
  console.error(audit.stderr || audit.stdout);
  process.exit(1);
}
// Packages listed only through a vulnerable dependency name no advisory of
// their own; each chain ends at an advisory object somewhere in the report.
const advisories = new Map();
for (const [name, entry] of Object.entries(report.vulnerabilities)) {
  for (const via of entry.via) {
    if (typeof via === 'object' && BLOCKING.has(via.severity)) {
      advisories.set(via.url.split('/').pop(), `${name}: ${via.title} (${via.url})`);
    }
  }
}
const blocking = [...advisories].filter(([id]) => !(id in ACCEPTED));
for (const [id, reason] of Object.entries(ACCEPTED)) {
  console.log(advisories.has(id)
    ? `Accepted ${id}: ${reason}`
    : `Accepted ${id} no longer appears; remove it from scripts/audit-dependencies.mjs`);
}
if (blocking.length) {
  for (const [, description] of blocking) console.error(description);
  process.exit(1);
}
console.log('No unaccepted moderate or higher advisories.');
