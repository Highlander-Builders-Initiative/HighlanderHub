import assert from "node:assert/strict";
import { test } from "node:test";
import { importTsModule } from "./helpers/import-ts-module.mjs";

const { isOnlineLocation } = await importTsModule("src/lib/events/location.ts");

test("online-only locations are recognized", () => {
  for (const location of [
    "Zoom",
    "ZOOM",
    "Virtual",
    "Online",
    "discord",
    "Google Meet",
    "Online via Zoom",
    "Zoom/Online",
    "Virtual (via Zoom Link)",
    "Online (Link in LinkTree)",
    "Zoom (link in bio)",
    "https://ucr.zoom.us/j/99083385403",
    "TBA or Zoom (Meeting ID: 945 1184 9309, Passcode: 071610)",
  ]) {
    assert.equal(isOnlineLocation(location), true, location);
  }
});

test("hybrid and in-person locations keep the pin", () => {
  for (const location of [
    "HUB 260",
    "SSC Group Meeting Room 1",
    "CE-CERT Room 105 & Zoom",
    "Genomics Auditorium (https://ucr.zoom.us/j/99083385403)",
    "Virtual Reality Lab, Bourns Hall",
    "",
    null,
    undefined,
  ]) {
    assert.equal(isOnlineLocation(location), false, String(location));
  }
});
