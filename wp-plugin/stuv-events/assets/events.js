/**
 * StuV event list.
 *
 * Loaded as a classic script by wp_enqueue_script; also exports under
 * CommonJS so the pure helpers can be tested with `node --test`.
 *
 * Never parses a timestamp: the REST route hands us Berlin wall-clock strings
 * ('2026-10-28T19:30') and ready-made German labels, and those strings
 * compare correctly as text.
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

  /**
   * The next `limit` events that have not ended, each series once.
   *
   * The payload may be hours old (the plugin serves its cache while Google is
   * unreachable), so what has ended since is dropped here, not only at fetch
   * time. A weekly series then shows its next date instead of every Monday.
   */
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
    if (text !== undefined) node.textContent = text; // never innerHTML: calendar text
    return node;
  }

  function renderEvent(event) {
    var item = el("li", "stuv-event");

    var badge = el("div", "stuv-event-date");
    badge.setAttribute("aria-hidden", "true");
    badge.appendChild(el("span", "stuv-event-month", event.month));
    badge.appendChild(el("span", "stuv-event-day", event.day));
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
    // Enqueued in the footer only on a page with a list, after its config.
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
        // Quiet failure: the fallback text in the markup stays, and it points
        // to the calendar.
      });
  }

  if (typeof document !== "undefined") init();

  return {
    berlinNow,
    upcoming,
  };
});
