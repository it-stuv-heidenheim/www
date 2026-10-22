<?php
/**
 * Plugin Name: StuV Theme Toggle
 * Description: Schaltet den Dark Mode der Website um (Button in der Kopfzeile) und merkt sich die Wahl im Browser. Außerdem liefert es das Apple-Touch-Icon mit weißem Hintergrund aus und hält die Jahreszahl im Copyright der Fußzeile aktuell. ACHTUNG: Wird dieses Plugin deaktiviert, verschwindet der Umschalt-Button, die Seite zeigt immer das helle Design und das Icon auf dem iOS-Home-Bildschirm bekommt einen schwarzen Hintergrund. Quellcode: im Repository dieser Website (Verzeichnis wp-plugin/)
 * Version: 1.4.0
 * Requires PHP: 8.0
 * Author: StuV DHBW Heidenheim
 */

if (!defined('ABSPATH')) {
    exit;
}

define('STUV_THEME_VERSION', '1.4.0');

/**
 * The theme script, inline in <head>.
 *
 * Inline and head-level on purpose: the .dark class must be on <html> before the
 * browser paints the first pixel, otherwise every visitor with a dark preference
 * gets a white flash. An external file would still block the parser, but costs a
 * round trip for ~700 bytes; a footer script would be far too late.
 *
 * The click handler is delegated from `document` because this runs before the
 * header markup exists. That avoids a DOMContentLoaded dance, and the button keeps working
 * wherever it is moved to.
 */
function stuv_theme_script(): string {
    return <<<'JS'
(function () {
  var root = document.documentElement;
  var mq = window.matchMedia('(prefers-color-scheme: dark)');
  var MODES = ['light', 'dark', 'system'];
  var LABELS = {
    light: 'Thema: Hell',
    dark: 'Thema: Dunkel',
    system: 'Thema: System',
  };

  // localStorage throws in Safari's private mode rather than returning null.
  function stored() {
    try { return localStorage.getItem('stuv-theme'); } catch (e) { return null; }
  }

  // Resolve the stored string to one of the three real modes; anything absent
  // or unrecognised means "follow the OS", so it maps to 'system'.
  function mode() {
    var m = stored();
    return MODES.indexOf(m) !== -1 ? m : 'system';
  }

  // 'system' looks at the OS right now; 'light'/'dark' resolve to themselves.
  function resolve(m) {
    return m === 'system' ? (mq.matches ? 'dark' : 'light') : m;
  }

  function apply(m) {
    root.classList.toggle('dark', resolve(m) === 'dark');
    var buttons = document.querySelectorAll('.stuv-theme-toggle');
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].setAttribute('aria-label', LABELS[m]);
    }
    // The check mark in the menu is what tells System apart from a fixed
    // choice; the trigger icon only ever shows the resolved theme.
    var options = document.querySelectorAll('.stuv-theme-option');
    for (var j = 0; j < options.length; j++) {
      options[j].setAttribute(
        'aria-checked',
        options[j].dataset.themeSet === m ? 'true' : 'false'
      );
    }
  }

  function closeMenus() {
    var open = document.querySelectorAll('.stuv-theme-switch[open]');
    for (var i = 0; i < open.length; i++) {
      open[i].removeAttribute('open');
    }
  }

  apply(mode());

  // Reveals .stuv-theme-switch, which component.css hides by default: no plugin
  // (or no JS) means no click handler, so the control must not be there at all.
  root.classList.add('stuv-theme-ready');

  // The OS listener only moves the page while the visitor is in System mode.
  mq.addEventListener('change', function () {
    if (mode() === 'system') { apply('system'); }
  });

  // The head script ran before the button existed, so apply() couldn't label it
  // yet; re-apply once the DOM is ready to name the current mode on the button.
  document.addEventListener('DOMContentLoaded', function () {
    apply(mode());
  });

  // One listener covers both jobs: picking a mode from the menu, and the
  // outside-click dismissal that <details> does not do on its own.
  document.addEventListener('click', function (e) {
    if (!e.target.closest) { return; }
    var option = e.target.closest('.stuv-theme-option');
    if (option) {
      var next = option.dataset.themeSet;
      if (MODES.indexOf(next) === -1) { return; }
      apply(next);
      try { localStorage.setItem('stuv-theme', next); } catch (e2) {}
      closeMenus();
      return;
    }
    if (!e.target.closest('.stuv-theme-switch')) { closeMenus(); }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closeMenus(); }
  });
})();
JS;
}

/**
 * A src-less handle exists only to carry the inline script; WordPress prints it
 * in <head> because nothing marks it as a footer script.
 */
add_action('wp_enqueue_scripts', function (): void {
    wp_register_script('stuv-theme', false, [], STUV_THEME_VERSION, false);
    wp_enqueue_script('stuv-theme');
    wp_add_inline_script('stuv-theme', stuv_theme_script());
});

/**
 * The site icon is one image for every size, so WordPress also serves the
 * transparent favicon as the apple-touch-icon, and iOS fills transparency with
 * black. Point that tag at an opaque copy instead (data/media/
 * stuv-dhbw-apple-touch-icon.png). Only once it is uploaded: a missing file
 * keeps core's tag rather than linking a 404.
 */
add_filter('site_icon_meta_tags', function (array $tags): array {
    $uploads = wp_get_upload_dir();
    $file = '/stuv-dhbw-apple-touch-icon.png';
    if (!file_exists($uploads['basedir'] . $file)) {
        return $tags;
    }
    foreach ($tags as $i => $tag) {
        if (str_contains($tag, 'rel="apple-touch-icon"')) {
            $tags[$i] = sprintf('<link rel="apple-touch-icon" href="%s" />', esc_url($uploads['baseurl'] . $file));
        }
    }
    return $tags;
});

/**
 * Keeps the footer's copyright year current.
 *
 * The template part stores a real year, so the footer still reads correctly
 * with the plugin off; it only goes stale. On render the first four-digit
 * number after the © is replaced, and only inside a paragraph carrying the
 * stuv-copyright class (tools/test_content.py fails on a © year outside one).
 */
function stuv_theme_copyright_year(string $html, string $year): string {
    return preg_replace('/©\s*\K\d{4}/u', $year, $html, 1) ?? $html;
}

add_filter('render_block_core/paragraph', function (string $content, array $block): string {
    $classes = explode(' ', $block['attrs']['className'] ?? '');
    if (!in_array('stuv-copyright', $classes, true)) {
        return $content;
    }
    return stuv_theme_copyright_year($content, wp_date('Y'));
}, 10, 2);
