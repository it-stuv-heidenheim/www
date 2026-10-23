const test = require("node:test");
const assert = require("node:assert");
const {
  formatPrice,
  dropPastDays,
  todayInBerlin,
} = require("../stuv-mensa/assets/mensa.js");

// Intl inserts a non-breaking space before the currency symbol; normalize it
// so the assertion does not depend on the platform's ICU build.
const norm = (s) => s.replace(/ /g, " ");

test("formatPrice renders German currency", () => {
  assert.equal(norm(formatPrice(4.55)), "4,55 €");
  assert.equal(norm(formatPrice(4)), "4,00 €");
});

test("dropPastDays keeps today and everything after it", () => {
  const days = [
    { date: "2026-07-13" },
    { date: "2026-07-14" },
    { date: "2026-07-15" },
  ];
  assert.deepEqual(dropPastDays(days, "2026-07-14"), [
    { date: "2026-07-14" },
    { date: "2026-07-15" },
  ]);
});

test("dropPastDays empties a fully expired stale payload", () => {
  // api.dhbw.app down for a week: every day in the store is now in the past,
  // so the widget must fall through to its "kein Speiseplan" state rather than
  // label a past Monday "Nächster Speiseplan".
  const days = [{ date: "2026-07-13" }, { date: "2026-07-14" }];
  assert.deepEqual(dropPastDays(days, "2026-07-20"), []);
});

test("dropPastDays tolerates a missing or malformed day list", () => {
  assert.deepEqual(dropPastDays(undefined, "2026-07-20"), []);
  assert.deepEqual(dropPastDays([], "2026-07-20"), []);
  assert.deepEqual(dropPastDays([{}, null], "2026-07-20"), []);
});

test("todayInBerlin is timezone-independent", () => {
  // 00:30 Berlin time on the 14th, expressed as UTC. A visitor in Los Angeles
  // must still be told it is the 14th in Berlin.
  const at = new Date("2026-07-13T22:30:00.000Z");
  assert.equal(todayInBerlin(at), "2026-07-14");
});
