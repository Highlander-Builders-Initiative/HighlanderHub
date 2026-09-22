import assert from 'node:assert/strict';
import { test } from 'node:test';
import { importTsModule } from './helpers/import-ts-module.mjs';
const { eventRowToCampusEvent } = await importTsModule('src/lib/events/map-event-row.ts');
const { buildEventSearchText } = await importTsModule('src/components/events/events-filters.ts');
const { getClubs } = await importTsModule('src/lib/clubs.ts');

test('merged hosts display, search, and populate the club picker without exposing private accounts', () => {
  const event = eventRowToCampusEvent({
    id: 'ig_a_p1', title: 'Celebration', description: '', starts_at: '2026-10-03T01:00:00Z',
    host: 'Club Alpha', host_handle: 'alpha', location: 'HUB', category: 'club', tags: [],
    hosts: [{ host: 'Alpha duplicate', host_handle: '@ALPHA' },
      { host: 'Club Beta', host_handle: 'beta' },
      { host: 'Hidden', host_handle: 'highlander_opps' }],
  });
  assert.equal(event.host, 'Club Alpha & Club Beta');
  assert.equal(event.hosts.length, 2);
  assert.ok(buildEventSearchText(event).includes('beta'));
  assert.ok(!buildEventSearchText(event).includes('highlander_opps'));
  const clubs = getClubs([event]);
  assert.equal(clubs.find(c => c.handle === 'alpha').label, 'Club Alpha');
  assert.equal(clubs.find(c => c.handle === 'beta').label, 'Club Beta');
});
