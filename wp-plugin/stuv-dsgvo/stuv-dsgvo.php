<?php
/**
 * Plugin Name: StuV DSGVO Embeds
 * Description: Lädt die eingebetteten Google Kalender erst auf Klick statt automatisch und zeigt vorher einen Datenschutz-Hinweis. Die Zustimmung wird auf Wunsch im Browser des Geräts gemerkt und lässt sich unter dem Kalender jederzeit widerrufen. ACHTUNG: Wird dieses Plugin deaktiviert, verschwindet der Kalender und an seiner Stelle steht ein Link zu Google. Die Embeds tragen keine eigene src, also lädt nie etwas ungefragt von Google. Quellcode: im Repository dieser Website (Verzeichnis wp-plugin/)
 * Version: 1.1.2
 * Requires PHP: 8.0
 * Author: StuV DHBW Heidenheim
 */

if (!defined('ABSPATH')) {
    exit;
}

define('STUV_DSGVO_VERSION', '1.1.2');

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

/**
 * The click-to-load script.
 *
 * The embeds in the page content carry `data-stuv-src` and no `src` at all, so
 * nothing reaches Google until a visitor asks for it. That also decides the
 * failure mode: with this plugin off (or JavaScript off) the iframe stays empty
 * forever, so the markup ships a visible `.stuv-dsgvo-fallback` link that this
 * script hides again once it has taken over. It fails closed both ways:
 * no silent empty box, and no request to Google that nobody asked for.
 *
 * The consent is remembered per device in localStorage, so moving between the
 * homepage and the Events page does not ask again. That is only defensible with
 * a way back out, so a loaded embed always carries a visible revoke link: the
 * DSGVO wants withdrawing to be as easy as giving. Revoking replaces the iframe
 * with a fresh, src-less clone rather than clearing `src`, because clearing it
 * leaves the already-loaded Google document running in the frame.
 */
add_action('wp_enqueue_scripts', function (): void {
    if (!stuv_dsgvo_has_embed()) {
        return;
    }

    wp_register_script('stuv-dsgvo', false, [], STUV_DSGVO_VERSION, false);
    wp_enqueue_script('stuv-dsgvo');
    wp_add_inline_script('stuv-dsgvo', <<<'JS'
(function () {
  var GOOGLE_PRIVACY = 'https://policies.google.com/privacy?hl=de';
  var STORAGE_KEY = 'stuv-dsgvo-calendar';
  var ICON =
    '<svg class="stuv-dsgvo-icon" width="32" height="32" viewBox="0 0 256 256" fill="currentColor" aria-hidden="true"><path d="M208,32H184V24a8,8,0,0,0-16,0v8H88V24a8,8,0,0,0-16,0v8H48A16,16,0,0,0,32,48V208a16,16,0,0,0,16,16H208a16,16,0,0,0,16-16V48A16,16,0,0,0,208,32ZM72,48v8a8,8,0,0,0,16,0V48h80v8a8,8,0,0,0,16,0V48h24V80H48V48ZM208,208H48V96H208V208Z"/></svg>';

  // Safari in private mode and "block all cookies" settings make localStorage
  // throw on access, not just on write. A device that cannot remember the
  // consent simply falls back to asking every time, never to an exception that
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

  function buildRevoke(iframe) {
    var p = document.createElement('p');
    p.className = 'stuv-dsgvo-revoke';
    p.innerHTML =
      'Der Kalender wird auf diesem Gerät automatisch geladen. ' +
      '<button type="button" class="stuv-dsgvo-revoke-btn">Nicht mehr automatisch laden</button>';
    p.querySelector('button').addEventListener('click', function () {
      rememberConsent(false);
      p.remove();

      var reset = unloadEmbed(iframe);
      var fresh = buildPlaceholder(reset);
      reset.parentNode.insertBefore(fresh, reset);

      // The button that was clicked is gone. Without this, focus falls back to
      // <body> and a keyboard visitor is thrown to the top of the page.
      fresh.querySelector('.stuv-dsgvo-load-btn').focus();
    });
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
      '<p class="stuv-dsgvo-note">Aus Datenschutzgründen wird der Kalender nicht automatisch geladen. Beim Laden werden Daten wie deine IP-Adresse an Server von Google in den USA übertragen. Mehr dazu in der <a href="' +
      GOOGLE_PRIVACY +
      '" target="_blank" rel="noopener noreferrer">Datenschutzerklärung von Google</a>.</p>' +
      '<button type="button" class="stuv-button-outline stuv-dsgvo-load-btn">Kalender laden</button>';

    // textContent, not innerHTML: `title` comes out of block markup, which is
    // editable in wp-admin by anyone who can edit pages.
    placeholder.querySelector('.stuv-dsgvo-notice').textContent = title;

    placeholder.querySelector('.stuv-dsgvo-load-btn').addEventListener('click', function () {
      rememberConsent(true);
      loadEmbed(iframe);
      placeholder.remove();
      iframe.focus(); // the button had focus, see above
    });
    return placeholder;
  }

  function loadEmbed(iframe) {
    iframe.src = iframe.getAttribute('data-stuv-src');
    iframe.classList.add('stuv-dsgvo-loaded');
    iframe.parentNode.insertBefore(buildRevoke(iframe), iframe.nextSibling);
  }

  /**
   * Undo a load. `src = ''` would leave Google's document alive in the frame,
   * so the iframe is swapped for a clone taken *after* the attribute is gone.
   */
  function unloadEmbed(iframe) {
    iframe.removeAttribute('src');
    iframe.classList.remove('stuv-dsgvo-loaded');
    var fresh = iframe.cloneNode(false);
    iframe.parentNode.replaceChild(fresh, iframe);
    return fresh;
  }

  function setupEmbeds() {
    var iframes = document.querySelectorAll('iframe[data-stuv-src]');
    for (var i = 0; i < iframes.length; i++) {
      var iframe = iframes[i];
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

  // Printed in <head>, so the document is still loading.
  document.addEventListener('DOMContentLoaded', setupEmbeds);
})();
JS);
});
