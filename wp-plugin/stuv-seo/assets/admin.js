/**
 * Character counter and media picker for the StuV SEO admin fields.
 *
 * Deliberately dependency-free DOM code (no build, no framework): it talks to
 * wp.media, which wp_enqueue_media() makes available on the pages where this
 * script is enqueued, and to the markup produced by inc/admin.php. Reviewed by
 * hand like the stuv-theme and stuv-dsgvo scripts (docs/testing.md) — there is
 * no test runner for it.
 */
(function () {
  // Set by inc/admin.php right before this file, so the counter, the hint under
  // the field and the start checklist all mark the same number. The literal is
  // only the fallback for a lost inline script.
  var DESCRIPTION_LIMIT = window.stuvSeoDescriptionLimit || 155;

  // --- character counter ---------------------------------------------------
  function updateCounter(textarea) {
    var field = textarea.closest(".stuv-seo-counter-field");
    var out = field && field.querySelector(".stuv-seo-counter");
    if (!out) return;
    var len = textarea.value.length;
    out.textContent = len + " Zeichen";
    out.style.color = len > DESCRIPTION_LIMIT ? "#b32d2e" : "";
  }

  document
    .querySelectorAll(".stuv-seo-description")
    .forEach(function (textarea) {
      updateCounter(textarea);
      textarea.addEventListener("input", function () {
        updateCounter(textarea);
      });
    });

  // --- media picker --------------------------------------------------------
  // A field is .stuv-seo-media-field around a hidden input (attachment id), a
  // preview <img>, and "Bild wählen"/"Entfernen" buttons.
  function setMedia(field, attachment) {
    field.querySelector(".stuv-seo-media-value").value = attachment.id;
    var url =
      (attachment.sizes &&
        attachment.sizes.medium &&
        attachment.sizes.medium.url) ||
      attachment.url;
    var preview = field.querySelector(".stuv-seo-media-preview");
    preview.src = url;
    preview.removeAttribute("hidden");
    field.querySelector(".stuv-seo-media-remove").removeAttribute("hidden");
  }

  function clearMedia(field) {
    field.querySelector(".stuv-seo-media-value").value = "";
    field.querySelector(".stuv-seo-media-preview").setAttribute("hidden", "");
    field.querySelector(".stuv-seo-media-remove").setAttribute("hidden", "");
  }

  document.querySelectorAll(".stuv-seo-media-field").forEach(function (field) {
    field.addEventListener("click", function (e) {
      if (e.target.closest(".stuv-seo-media-open")) {
        if (typeof wp === "undefined" || !wp.media) return;
        var frame = wp.media({
          title: "Vorschaubild wählen",
          library: { type: "image" },
          multiple: false,
          button: { text: "Auswählen" },
        });
        frame.on("select", function () {
          var attachment = frame.state().get("selection").first().toJSON();
          setMedia(field, attachment);
        });
        frame.open();
        return;
      }
      if (e.target.closest(".stuv-seo-media-remove")) {
        clearMedia(field);
      }
    });
  });
})();
