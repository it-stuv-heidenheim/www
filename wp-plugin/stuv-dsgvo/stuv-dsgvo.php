<?php
/**
 * Plugin Name: StuV DSGVO Embeds
 * Description: Lädt die eingebetteten Google Kalender erst auf Klick statt automatisch und zeigt vorher einen Datenschutz-Hinweis. Die Zustimmung wird auf Wunsch im Browser des Geräts gemerkt und lässt sich unter dem Kalender jederzeit widerrufen. ACHTUNG: Wird dieses Plugin deaktiviert, verschwindet der Kalender und an seiner Stelle steht ein Link zu Google — die Embeds tragen keine eigene src, es wird also nie ungefragt bei Google geladen. Quellcode: im Repository dieser Website (Verzeichnis wp-plugin/)
 * Version: 1.1.0
 * Requires PHP: 8.0
 * Author: StuV DHBW Heidenheim
 */

if (!defined('ABSPATH')) {
    exit;
}

define('STUV_DSGVO_VERSION', '1.1.0');

/**
 * The click-to-load script.
 *
 * The embeds in the page content carry `data-stuv-src` and no `src` at all, so
 * nothing reaches Google until a visitor asks for it. That also decides the
 * failure mode: with this plugin off (or JavaScript off) the iframe stays empty
 * forever, so the markup ships a visible `.stuv-dsgvo-fallback` link that this
 * script hides again once it has taken over. Fail-closed in both directions —
 * never a silent empty box, never an unasked-for request to Google.
 *
 * Delegated from `document` rather than bound per button, so a placeholder that
 * is built after this runs still works.
 *
 * The consent is remembered per device in localStorage, so moving between the
 * homepage and the Events page does not ask again. That is only defensible with
 * a way back out, so a loaded embed always carries a visible revoke link — the
 * DSGVO wants withdrawing to be as easy as giving. Revoking replaces the iframe
 * with a fresh, src-less clone rather than clearing `src`, because clearing it
 * leaves the already-loaded Google document running in the frame.
 */
function stuv_dsgvo_script(): string {
    return <<<'JS'
(function () {
  var GOOGLE_PRIVACY = 'https://policies.google.com/privacy?hl=de';
  var STORAGE_KEY = 'stuv-dsgvo-calendar';
  var ICON =
    '<svg class="stuv-dsgvo-icon" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/></svg>';

  // Which iframe a placeholder belongs to. The old version walked
  // nextElementSibling, which turns the button into a silent no-op the moment
  // anything wraps either element.
  var iframeFor = new WeakMap();

  // Safari in private mode and "block all cookies" settings make localStorage
  // throw on access, not just on write. A device that cannot remember the
  // consent simply falls back to asking every time — never to an exception that
  // takes the whole click handler down with it.
  function consentGiven() {
    try {
      return window.localStorage.getItem(STORAGE_KEY) === '1';
    } catch (e) {
      return false;
    }
  }

  function rememberConsent(on) {
    try {
      if (on) window.localStorage.setItem(STORAGE_KEY, '1');
      else window.localStorage.removeItem(STORAGE_KEY);
    } catch (e) {}
  }

  function buildRevoke() {
    var p = document.createElement('p');
    p.className = 'stuv-dsgvo-revoke';
    p.innerHTML =
      'Der Kalender wird auf diesem Gerät automatisch geladen. ' +
      '<button type="button" class="stuv-dsgvo-revoke-btn">Nicht mehr automatisch laden</button>';
    return p;
  }

  function buildPlaceholder(iframe) {
    var title = iframe.getAttribute('title') || 'Eingebetteter Inhalt';

    var placeholder = document.createElement('div');
    placeholder.className = 'stuv-dsgvo-placeholder';
    // role="group" is what makes the label count: a bare <div> has no role, so
    // assistive tech drops aria-label on the floor.
    placeholder.setAttribute('role', 'group');
    placeholder.setAttribute('aria-label', title);
    placeholder.innerHTML =
      ICON +
      '<p class="stuv-dsgvo-notice"></p>' +
      '<p class="stuv-dsgvo-note">Aus Datenschutzgründen wird der Kalender nicht automatisch geladen. Beim Laden werden Daten wie deine IP-Adresse an Server von Google in den USA übertragen — siehe die <a href="' +
      GOOGLE_PRIVACY +
      '" target="_blank" rel="noopener noreferrer">Datenschutzerklärung von Google</a>.</p>' +
      '<button type="button" class="stuv-button-outline stuv-dsgvo-load-btn">Kalender laden</button>';

    // textContent, not innerHTML: `title` comes out of block markup, which is
    // editable in wp-admin by anyone who can edit pages.
    placeholder.querySelector('.stuv-dsgvo-notice').textContent = title;

    iframeFor.set(placeholder, iframe);
    return placeholder;
  }

  function loadEmbed(iframe) {
    iframe.src = iframe.getAttribute('data-stuv-src');
    iframe.classList.add('stuv-dsgvo-loaded');
    iframe.parentNode.insertBefore(buildRevoke(), iframe.nextSibling);
  }

  /**
   * Undo a load. `src = ''` would leave Google's document alive in the frame,
   * so the iframe is swapped for a clone taken *after* the attribute is gone.
   */
  function unloadEmbed(iframe) {
    iframe.removeAttribute('src');
    iframe.classList.remove('stuv-dsgvo-loaded');
    delete iframe.dataset.stuvPlaceholder;

    var fresh = iframe.cloneNode(false);
    iframe.parentNode.replaceChild(fresh, iframe);
    return fresh;
  }

  function setupEmbeds() {
    var iframes = document.querySelectorAll('iframe[data-stuv-src]');
    for (var i = 0; i < iframes.length; i++) {
      var iframe = iframes[i];
      if (iframe.dataset.stuvPlaceholder) continue;
      iframe.dataset.stuvPlaceholder = '1';

      if (consentGiven()) {
        loadEmbed(iframe);
      } else {
        iframe.parentNode.insertBefore(buildPlaceholder(iframe), iframe);
      }

      // Hides the no-JS fallback link. Set here and not in the markup so that
      // it only disappears once this script has actually run.
      var wrapper = iframe.closest('.stuv-dsgvo-embed');
      if (wrapper) wrapper.classList.add('stuv-dsgvo-ready');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupEmbeds);
  } else {
    setupEmbeds();
  }

  document.addEventListener('click', function (e) {
    if (!e.target.closest) return;

    var loadBtn = e.target.closest('.stuv-dsgvo-load-btn');
    if (loadBtn) {
      var placeholder = loadBtn.closest('.stuv-dsgvo-placeholder');
      var iframe = placeholder && iframeFor.get(placeholder);
      if (!iframe) return;

      rememberConsent(true);
      loadEmbed(iframe);
      placeholder.remove();

      // The element that had focus is gone. Without this, focus falls back to
      // <body> and a keyboard visitor is thrown to the top of the page.
      iframe.focus();
      return;
    }

    var revokeBtn = e.target.closest('.stuv-dsgvo-revoke-btn');
    if (revokeBtn) {
      var note = revokeBtn.closest('.stuv-dsgvo-revoke');
      var loaded = note && note.previousElementSibling;
      if (!loaded || loaded.tagName !== 'IFRAME') return;

      rememberConsent(false);
      note.remove();

      var reset = unloadEmbed(loaded);
      var fresh = buildPlaceholder(reset);
      reset.parentNode.insertBefore(fresh, reset);
      reset.dataset.stuvPlaceholder = '1';

      // Same focus reasoning as above — the button that was clicked is gone.
      var loadAgain = fresh.querySelector('.stuv-dsgvo-load-btn');
      if (loadAgain) loadAgain.focus();
    }
  });
})();
JS;
}

/**
 * Whether the current request renders an embed at all.
 *
 * Both calendars live in page content, so a substring check on the post is
 * enough and keeps ~1.5 KB of inline script off the other eight pages. The
 * trade-off: an embed placed in a template part, a widget or a reusable block
 * would not be found here and would never load. If one ever is, drop this
 * check rather than trying to teach it about every content source.
 */
function stuv_dsgvo_has_embed(): bool {
    $post = get_post();

    return $post instanceof WP_Post
        && str_contains($post->post_content, 'data-stuv-src');
}

add_action('wp_enqueue_scripts', function (): void {
    if (!stuv_dsgvo_has_embed()) {
        return;
    }

    wp_register_script('stuv-dsgvo', false, [], STUV_DSGVO_VERSION, false);
    wp_enqueue_script('stuv-dsgvo');
    wp_add_inline_script('stuv-dsgvo', stuv_dsgvo_script());
});
