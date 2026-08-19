/**
 * StuV Mensa widget.
 *
 * Loaded as a classic script by wp_enqueue_script; also exports under
 * CommonJS so the pure helpers can be tested with `node --test`.
 *
 * Never parses an upstream timestamp — the REST route hands us plain
 * 'YYYY-MM-DD' dates and ready-made German labels.
 */
(function (root, factory) {
  var api = factory();
  root.StuvMensa = api;
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";

  var priceFormat = new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
  });

  function formatPrice(value) {
    return priceFormat.format(value);
  }

  /** Today's date in Berlin, as 'YYYY-MM-DD', whatever the visitor's clock says. */
  function todayInBerlin(date) {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone: "Europe/Berlin",
    }).format(date || new Date());
  }

  /**
   * Index of the day to show first: today if the Mensa is open today,
   * otherwise the next open day. -1 when there are no open days at all.
   */
  function pickInitialDay(days, todayIso) {
    if (!days || days.length === 0) {
      return -1;
    }
    var index = days.findIndex(function (day) {
      return day.date === todayIso;
    });
    return index === -1 ? 0 : index;
  }

  /**
   * Drop days that are already over.
   *
   * The payload is normalised against the date it was fetched on, and the REST
   * route serves the stale store indefinitely whenever api.dhbw.app is down —
   * there is no upper bound on its age. During a prolonged outage the widget
   * would therefore keep offering days that are now in the past, and select()
   * would label one of them "Nächster Speiseplan · Montag, 13. Juli" — a stale
   * menu presented as an upcoming one. Serving stale data is the right default;
   * mislabelling it is not. Filtering on read rather than only at fetch time
   * lets an expired payload fall through to the existing "Zurzeit ist kein
   * Speiseplan verfügbar." terminal state instead.
   *
   * ISO 'YYYY-MM-DD' strings compare correctly with >=, so no Date parsing —
   * the same reason the rest of this file never touches a timestamp.
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

      panel.appendChild(item);
    });
  }

  // Build the tab strip once. Switching days only moves aria-selected and the
  // roving tabindex (see selectTab); rebuilding every button on each click would
  // destroy the button the click landed on and force a focus-restore dance.
  function buildTabs(tabs, days, onSelect) {
    tabs.textContent = "";

    days.forEach(function (day, index) {
      var tab = el("button", "stuv-mensa-tab", day.weekday.slice(0, 2));
      tab.type = "button";
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-label", day.label);

      tab.addEventListener("click", function () {
        onSelect(index);
        tab.focus();
      });

      tab.addEventListener("keydown", function (event) {
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

      tabs.appendChild(tab);
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

    // Semester break, or a stale payload whose days have all expired. Terminal state.
    if (days.length === 0) {
      lead.textContent = "Zurzeit ist kein Speiseplan verfügbar.";
      tabs.hidden = true;
      panel.textContent = "";
      root.hidden = false;
      return;
    }

    function select(index) {
      var day = days[index];

      // A day that is not today must say so plainly — a highlighted tab alone
      // would be read as "today's food".
      lead.textContent =
        day.date === today ? day.label : "Nächster Speiseplan · " + day.label;

      selectTab(tabs, index);
      renderMeals(panel, day);
    }

    buildTabs(tabs, days, select);
    select(pickInitialDay(days, today));
    root.hidden = false; // revealed only once we have data
  }

  function init() {
    var root = document.querySelector("[data-stuv-mensa]");
    if (!root || typeof stuvMensaConfig === "undefined") {
      return;
    }

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

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", init);
    } else {
      init();
    }
  }

  return {
    formatPrice,
    pickInitialDay,
    dropPastDays,
    todayInBerlin,
    render,
    init,
  };
});
