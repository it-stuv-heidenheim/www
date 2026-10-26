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
 * Whether the post contains an embed. Embeds in template parts, widgets or reusable blocks
 * would never load; if one appears, drop this check.
 */
function stuv_dsgvo_has_embed(): bool {
    $post = get_post();

    return $post instanceof WP_Post
        && str_contains($post->post_content, 'data-stuv-src');
}

/**
 * Click-to-load. Embeds carry `data-stuv-src` and no `src`, so nothing reaches Google before a
 * click; without this script the visible `.stuv-dsgvo-fallback` link remains. Consent is kept
 * in localStorage, so a loaded embed always shows a revoke link (DSGVO: withdrawing as easy as
 * giving).
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

  // localStorage throws on access in Safari private mode; then the script asks every time.
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

      // The clicked button is gone; keep focus off <body>.
      fresh.querySelector('.stuv-dsgvo-load-btn').focus();
    });
    return p;
  }

  function buildPlaceholder(iframe) {
    var title = iframe.getAttribute('title') || 'Eingebetteter Inhalt';

    var placeholder = document.createElement('div');
    placeholder.className = 'stuv-dsgvo-placeholder';
    // Without role="group" assistive tech ignores aria-label.
    placeholder.setAttribute('role', 'group');
    placeholder.setAttribute('aria-label', title);
    placeholder.innerHTML =
      ICON +
      '<p class="stuv-dsgvo-notice"></p>' +
      '<p class="stuv-dsgvo-note">Aus Datenschutzgründen wird der Kalender nicht automatisch geladen. Beim Laden werden Daten wie deine IP-Adresse an Server von Google in den USA übertragen. Mehr dazu in der <a href="' +
      GOOGLE_PRIVACY +
      '" target="_blank" rel="noopener noreferrer">Datenschutzerklärung von Google</a>.</p>' +
      '<button type="button" class="stuv-button-outline stuv-dsgvo-load-btn">Kalender laden</button>';

    // textContent: `title` comes from page markup anyone with edit rights can change.
    placeholder.querySelector('.stuv-dsgvo-notice').textContent = title;

    placeholder.querySelector('.stuv-dsgvo-load-btn').addEventListener('click', function () {
      rememberConsent(true);
      loadEmbed(iframe);
      placeholder.remove();
      iframe.focus();
    });
    return placeholder;
  }

  function loadEmbed(iframe) {
    iframe.src = iframe.getAttribute('data-stuv-src');
    iframe.classList.add('stuv-dsgvo-loaded');
    iframe.parentNode.insertBefore(buildRevoke(iframe), iframe.nextSibling);
  }

  /** Revoke: `src = ''` would keep Google's document alive, so swap in a clone taken after removing it. */
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

      // Hide the no-JS fallback only once this script has run.
      var wrapper = iframe.closest('.stuv-dsgvo-embed');
      if (wrapper) wrapper.classList.add('stuv-dsgvo-ready');
    }
  }

  document.addEventListener('DOMContentLoaded', setupEmbeds);
})();
JS);
});
