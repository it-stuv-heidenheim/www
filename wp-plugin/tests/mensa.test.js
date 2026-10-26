const test = require("node:test");
const assert = require("node:assert");
const {
  formatPrice,
  dropPastDays,
  todayInBerlin,
} = require("../stuv-mensa/assets/mensa.js");

// Intl puts a non-breaking space before the currency symbol, depending on ICU.
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
  // Upstream down for a week: every stored day has passed, so no "Nächster Speiseplan".
  const days = [{ date: "2026-07-13" }, { date: "2026-07-14" }];
  assert.deepEqual(dropPastDays(days, "2026-07-20"), []);
});

test("dropPastDays tolerates a missing or malformed day list", () => {
  assert.deepEqual(dropPastDays(undefined, "2026-07-20"), []);
  assert.deepEqual(dropPastDays([], "2026-07-20"), []);
  assert.deepEqual(dropPastDays([{}, null], "2026-07-20"), []);
});

test("todayInBerlin is timezone-independent", () => {
  // 00:30 Berlin on the 14th as UTC; a visitor in Los Angeles still gets the 14th.
  const at = new Date("2026-07-13T22:30:00.000Z");
  assert.equal(todayInBerlin(at), "2026-07-14");
});
