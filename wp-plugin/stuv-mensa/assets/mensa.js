/**
 * StuV Mensa widget. Classic script, exports under CommonJS for `node --test`. Never parses
 * an upstream timestamp: the route sends 'YYYY-MM-DD' dates and German labels.
 */
(function (factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
})(function () {
  "use strict";

  var formatPrice = new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
  }).format;

  /** Today's date in Berlin, as 'YYYY-MM-DD', whatever the visitor's clock says. */
  var todayInBerlin = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Berlin",
  }).format;

  /**
   * Drop past days: the stale store is served during an outage, and a past day would be
   * labelled as the next menu. 'YYYY-MM-DD' strings compare correctly.
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
    if (text !== undefined) node.textContent = text;
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

  // Built once: rebuilding on click would destroy the focused button.
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
      tab.tabIndex = isActive ? 0 : -1;
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
    root.hidden = false;

    // Semester break, or every cached day has passed.
    if (days.length === 0) {
      lead.textContent = "Zurzeit ist kein Speiseplan verfügbar.";
      tabs.hidden = true;
      return;
    }

    function select(index) {
      var day = days[index];

      // Otherwise a highlighted tab reads as "today's food".
      lead.textContent =
        day.date === today ? day.label : "Nächster Speiseplan · " + day.label;

      selectTab(tabs, index);
      renderMeals(panel, day);
    }

    // Days are sorted from today, so the first is today or the next open day.
    buildTabs(tabs, days, select);
    select(0);
  }

  function init() {
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
        // Stay hidden; the section's cards and Speiseplan button are the fallback.
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
