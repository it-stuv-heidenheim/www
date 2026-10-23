/**
 * StuV Mensa widget.
 *
 * Loaded as a classic script by wp_enqueue_script; also exports under
 * CommonJS so the pure helpers can be tested with `node --test`.
 *
 * Never parses an upstream timestamp: the REST route hands us plain
 * 'YYYY-MM-DD' dates and ready-made German labels.
 */
(function (factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
})(function () {
  "use strict";

  // format is a bound getter, so these work unattached.
  var formatPrice = new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
  }).format;

  /** Today's date in Berlin, as 'YYYY-MM-DD', whatever the visitor's clock says. */
  var todayInBerlin = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Berlin",
  }).format;

  /**
   * Drop days that are already over.
   *
   * The payload is normalised against the date it was fetched on, and the REST
   * route serves the stale store indefinitely whenever api.dhbw.app is down,
   * with no upper bound on its age. During a prolonged outage the widget
   * would therefore keep offering days that are now in the past, and select()
   * would label one of them "Nächster Speiseplan · Montag, 13. Juli", presenting a
   * stale menu as an upcoming one. Serving stale data is the right default;
   * mislabelling it is not. Filtering on read rather than only at fetch time
   * lets an expired payload fall through to the existing "Zurzeit ist kein
   * Speiseplan verfügbar." terminal state instead.
   *
   * ISO 'YYYY-MM-DD' strings compare correctly with >=, so no Date parsing,
   * for the same reason the rest of this file never touches a timestamp.
   */
  function dropPastDays(days, todayIso) {
    if (!days) {
      return [];
    }
    return days.filter(function (day) {
      return day && day.date >= todayIso;
    });
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text; // never innerHTML: upstream text
    return node;
  }

  function renderMeals(panel, day) {
    panel.textContent = "";
    var frame = document.createDocumentFragment();

    day.meals.forEach(function (meal) {
      var item = el("div", "stuv-mensa-meal");

      if (meal.image) {
        var img = el("img", "stuv-mensa-meal-image");
        img.src = meal.image;
        img.alt = "";
        img.loading = "lazy";
        img.width = 96;
        img.height = 96;
        item.appendChild(img);
      }

      var body = el("div", "stuv-mensa-meal-body");
      body.appendChild(el("p", "stuv-mensa-meal-name", meal.name));
      body.appendChild(
        el("p", "stuv-mensa-meal-price", formatPrice(meal.price)),
      );
      item.appendChild(body);

      frame.appendChild(item);
    });

    panel.appendChild(frame);
  }

  // Build the tab strip once. Switching days only moves aria-selected and the
  // roving tabindex (see selectTab); rebuilding every button on each click would
  // destroy the button the click landed on and force a focus-restore dance.
  function buildTabs(tabs, days, onSelect) {
    days.forEach(function (day) {
      var tab = el("button", "stuv-mensa-tab", day.weekday.slice(0, 2));
      tab.type = "button";
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-label", day.label);
      tabs.appendChild(tab);
    });

    // A tab holds only text, so the event target is the tab or the strip (-1).
    function indexOf(target) {
      return Array.prototype.indexOf.call(tabs.children, target);
    }

    tabs.addEventListener("click", function (event) {
      var index = indexOf(event.target);
      if (index < 0) return;
      onSelect(index);
      tabs.children[index].focus();
    });

    tabs.addEventListener("keydown", function (event) {
      var index = indexOf(event.target);
      if (index < 0) return;
      var next =
        event.key === "ArrowRight"
          ? index + 1
          : event.key === "ArrowLeft"
            ? index - 1
            : null;
      if (next === null || next < 0 || next >= days.length) {
        return;
      }
      event.preventDefault();
      onSelect(next);
      tabs.children[next].focus();
    });
  }

  function selectTab(tabs, activeIndex) {
    Array.prototype.forEach.call(tabs.children, function (tab, index) {
      var isActive = index === activeIndex;
      tab.setAttribute("aria-selected", String(isActive));
      tab.tabIndex = isActive ? 0 : -1; // roving tabindex
    });
  }

  function render(root, data) {
    var lead = root.querySelector("[data-stuv-mensa-lead]");
    var tabs = root.querySelector("[data-stuv-mensa-tabs]");
    var panel = root.querySelector("[data-stuv-mensa-panel]");
    var hours = root.querySelector("[data-stuv-mensa-hours]");

    var today = todayInBerlin();
    var days = dropPastDays(data.days, today);

    hours.textContent = data.openingHours
      ? "Öffnungszeiten: " + data.openingHours
      : "";
    root.hidden = false; // revealed only once we have data

    // Semester break, or a stale payload whose days have all expired. Terminal state.
    if (days.length === 0) {
      lead.textContent = "Zurzeit ist kein Speiseplan verfügbar.";
      tabs.hidden = true;
      return;
    }

    function select(index) {
      var day = days[index];

      // A day that is not today must say so plainly: a highlighted tab alone
      // would be read as "today's food".
      lead.textContent =
        day.date === today ? day.label : "Nächster Speiseplan · " + day.label;

      selectTab(tabs, index);
      renderMeals(panel, day);
    }

    // Days come sorted and from today on (dropPastDays), so the first one is
    // today if the Mensa is open today, otherwise the next open day.
    buildTabs(tabs, days, select);
    select(0);
  }

  function init() {
    // Enqueued in the footer only on a page with the widget, after its config.
    var root = document.querySelector("[data-stuv-mensa]");
    fetch(stuvMensaConfig.endpoint, { headers: { Accept: "application/json" } })
      .then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
      })
      .then(function (data) {
        render(root, data);
      })
      .catch(function () {
        // Quiet failure: leave the widget hidden. The section still shows its
        // cards and the outbound Speiseplan button, which is the fallback.
        root.remove();
      });
  }

  if (typeof document !== "undefined") init();

  return {
    formatPrice,
    dropPastDays,
    todayInBerlin,
  };
});
