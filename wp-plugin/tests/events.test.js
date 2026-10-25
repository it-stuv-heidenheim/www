const test = require("node:test");
const assert = require("node:assert");
const { berlinNow, upcoming } = require("../stuv-events/assets/events.js");

// The suite runs with TZ=America/Los_Angeles, so these prove the visitor's
// clock zone does not leak into the comparison.
test("berlinNow reads Berlin wall-clock time in winter", () => {
  assert.equal(berlinNow(new Date("2026-11-03T18:15:00Z")), "2026-11-03T19:15");
});

test("berlinNow reads Berlin wall-clock time in summer", () => {
  assert.equal(berlinNow(new Date("2026-07-14T21:59:00Z")), "2026-07-14T23:59");
});

test("berlinNow writes midnight as 00, never 24", () => {
  assert.equal(berlinNow(new Date("2026-11-02T23:00:00Z")), "2026-11-03T00:00");
});

const events = [
  { series: "sport", start: "2026-10-26T20:00", end: "2026-10-26T22:00" },
  { series: "party", start: "2026-10-28T19:30", end: "2026-10-28T23:00" },
  { series: "sport", start: "2026-11-02T20:00", end: "2026-11-02T22:00" },
  { series: "sitzung", start: "2026-11-03T19:15", end: "2026-11-03T21:00" },
  { series: "sport", start: "2026-11-09T20:00", end: "2026-11-09T22:00" },
];

test("upcoming shows each series once, at its next date", () => {
  assert.deepEqual(
    upcoming(events, "2026-10-26T12:00", 10).map((e) => e.start),
    ["2026-10-26T20:00", "2026-10-28T19:30", "2026-11-03T19:15"],
  );
});

test("upcoming keeps an event that is still running", () => {
  assert.equal(
    upcoming(events, "2026-10-26T21:00", 1)[0].start,
    "2026-10-26T20:00",
  );
});

test("upcoming drops what ended since the payload was cached", () => {
  // A day-old payload: Monday's training is over, the next one takes its place.
  assert.deepEqual(
    upcoming(events, "2026-10-27T09:00", 10).map((e) => e.start),
    ["2026-10-28T19:30", "2026-11-02T20:00", "2026-11-03T19:15"],
  );
});

test("upcoming respects the limit", () => {
  assert.equal(upcoming(events, "2026-10-26T12:00", 2).length, 2);
});

test("upcoming tolerates a missing or empty list", () => {
  assert.deepEqual(upcoming(undefined, "2026-10-26T12:00", 4), []);
  assert.deepEqual(upcoming([], "2026-10-26T12:00", 4), []);
});
