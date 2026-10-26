/**
 * StuV event list. Classic script, exports under CommonJS for `node --test`. Never parses a
 * timestamp: Berlin wall-clock strings ('2026-10-28T19:30') compare correctly as text.
 */
(function (factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
})(function () {
  "use strict";

  var berlinParts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Berlin",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });

  /** The current Berlin wall-clock time as 'YYYY-MM-DDTHH:MM', whatever the visitor's clock zone. */
  function berlinNow(date) {
    var p = {};
    berlinParts.formatToParts(date || new Date()).forEach(function (part) {
      p[part.type] = part.value;
    });
    return p.year + "-" + p.month + "-" + p.day + "T" + p.hour + ":" + p.minute;
  }

  /** The next `limit` events not yet ended, each series once (the payload may be hours old). */
  function upcoming(events, now, limit) {
    var seen = {};
    return (events || [])
      .filter(function (event) {
        if (!event || event.end <= now || seen[event.series]) return false;
        seen[event.series] = true;
        return true;
      })
      .slice(0, limit);
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function renderEvent(event) {
    var item = el("li", "stuv-event");

    var badge = el("div", "stuv-event-date");
    badge.setAttribute("aria-hidden", "true");
    badge.appendChild(el("span", "stuv-event-day", event.day));
    badge.appendChild(el("span", "stuv-event-month", event.month));
    item.appendChild(badge);

    var body = el("div", "stuv-event-body");
    body.appendChild(el("p", "stuv-event-title", event.title));
    var meta = el("p", "stuv-event-meta");
    meta.appendChild(el("span", "stuv-sr-only", event.day_month + ", "));
    var when = el("time", null, event.weekday + ", " + event.time);
    when.setAttribute("datetime", event.start);
    meta.appendChild(when);
    if (event.place) {
      meta.appendChild(document.createTextNode(" · " + event.place));
    }
    body.appendChild(meta);
    item.appendChild(body);
    return item;
  }

  function render(root, events) {
    var limit = parseInt(root.getAttribute("data-stuv-events-limit"), 10) || 4;
    var list = upcoming(events, berlinNow(), limit);
    root.textContent = "";
    if (!list.length) {
      root.appendChild(
        el(
          "p",
          "stuv-events-empty",
          "Gerade stehen keine Termine im Kalender.",
        ),
      );
      return;
    }
    var ol = el("ol", "stuv-events-list");
    list.forEach(function (event) {
      ol.appendChild(renderEvent(event));
    });
    root.appendChild(ol);
  }

  function init() {
    var roots = document.querySelectorAll("[data-stuv-events]");
    fetch(stuvEventsConfig.endpoint, {
      headers: { Accept: "application/json" },
    })
      .then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
      })
      .then(function (data) {
        Array.prototype.forEach.call(roots, function (root) {
          render(root, data && data.events);
        });
      })
      .catch(function () {
        // The markup's fallback text stays and points to the calendar.
      });
  }

  if (typeof document !== "undefined") init();

  return {
    berlinNow,
    upcoming,
  };
});
