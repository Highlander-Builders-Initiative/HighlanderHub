import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { copyFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

const advisory = 'GHSA-g3hv-75wg-m249';
const legacy = { version: '3.1.5', dev: true };
const modern = { version: '10.2.5', dev: true };

function runAudit(t, packages, nodes, id = advisory) {
  const root = mkdtempSync(join(tmpdir(), 'highlander-audit-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  mkdirSync(join(root, 'scripts'));
  copyFileSync(new URL('../scripts/audit-dependencies.mjs', import.meta.url),
    join(root, 'scripts/audit-dependencies.mjs'));
  writeFileSync(join(root, 'package-lock.json'), JSON.stringify({ packages }));
  const report = {
    vulnerabilities: {
      minimatch: {
        nodes,
        via: [{ severity: 'moderate', title: 'Test advisory', url: `https://github.com/advisories/${id}` }],
      },
    },
  };
  writeFileSync(join(root, 'npm'),
    `#!${process.execPath}\nconsole.log(${JSON.stringify(JSON.stringify(report))});\nprocess.exit(1);\n`,
    { mode: 0o755 });
  return spawnSync(process.execPath, [join(root, 'scripts/audit-dependencies.mjs')], {
    encoding: 'utf8',
    env: { ...process.env, PATH: `${root}:${process.env.PATH}` },
  });
}

test('audit accepts the advisory only for legacy minimatch dev dependencies', t => {
  const result = runAudit(t, {
    'node_modules/minimatch': legacy,
    'node_modules/parser/node_modules/minimatch': { version: '11.0.1', dev: true },
  }, ['node_modules/minimatch']);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Accepted GHSA-g3hv-75wg-m249/);
});

test('audit rejects an affected modern minimatch even alongside legacy copies', t => {
  const result = runAudit(t, {
    'node_modules/minimatch': legacy,
    'node_modules/parser/node_modules/minimatch': modern,
  }, ['node_modules/minimatch', 'node_modules/parser/node_modules/minimatch']);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /GHSA-g3hv-75wg-m249/);
  assert.doesNotMatch(result.stdout, /Accepted GHSA/);
});

test('audit rejects the advisory for a production dependency', t => {
  const result = runAudit(t, { 'node_modules/minimatch': { version: '3.1.5' } },
    ['node_modules/minimatch']);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /GHSA-g3hv-75wg-m249/);
});

test('audit rejects the advisory when a reported dependency is absent from the lockfile', t => {
  const result = runAudit(t, {}, ['node_modules/minimatch']);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /GHSA-g3hv-75wg-m249/);
});

test('audit does not accept other advisories on legacy minimatch', t => {
  const result = runAudit(t, { 'node_modules/minimatch': legacy },
    ['node_modules/minimatch'], 'GHSA-other-advisory');
  assert.equal(result.status, 1);
  assert.match(result.stderr, /GHSA-other-advisory/);
});
