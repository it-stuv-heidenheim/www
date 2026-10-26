<?php
/**
 * Plugin Name: StuV Theme Toggle
 * Description: Schaltet den Dark Mode der Website um (Button in der Kopfzeile) und merkt sich die Wahl im Browser. Außerdem bietet es im Editor den Button-Stil „Auf Farbfläche“ an, liefert das Apple-Touch-Icon mit weißem Hintergrund aus und hält die Jahreszahl im Copyright der Fußzeile aktuell. ACHTUNG: Wird dieses Plugin deaktiviert, verschwindet der Umschalt-Button, die Seite zeigt immer das helle Design und das Icon auf dem iOS-Home-Bildschirm bekommt einen schwarzen Hintergrund. Quellcode: im Repository dieser Website (Verzeichnis wp-plugin/)
 * Version: 1.5.1
 * Requires PHP: 8.0
 * Author: StuV DHBW Heidenheim
 */

if (!defined('ABSPATH')) {
    exit;
}

define('STUV_THEME_VERSION', '1.5.1');

/**
 * Inline in <head> so .dark is set before first paint (no white flash). The click handler is
 * delegated from `document` because the header doesn't exist yet.
 */
function stuv_theme_script(): string {
    return <<<'JS'
(function () {
  var root = document.documentElement;
  var mq = window.matchMedia('(prefers-color-scheme: dark)');
  var MODES = ['light', 'dark', 'system'];
  var LABELS = { light: 'Thema: Hell', dark: 'Thema: Dunkel', system: 'Thema: System' };

  // localStorage throws in Safari's private mode.
  function stored() {
    try { return localStorage.getItem('stuv-theme'); } catch (e) { return null; }
  }

  function mode() {
    var m = stored();
    return MODES.indexOf(m) !== -1 ? m : 'system';
  }

  function resolve(m) {
    return m === 'system' ? (mq.matches ? 'dark' : 'light') : m;
  }

  function apply(m) {
    root.classList.toggle('dark', resolve(m) === 'dark');
    document.querySelectorAll('.stuv-theme-toggle').forEach(function (b) {
      b.setAttribute('aria-label', LABELS[m]);
    });
    // Only the menu's check mark tells System apart from a fixed choice.
    document.querySelectorAll('.stuv-theme-option').forEach(function (o) {
      o.setAttribute('aria-checked', String(o.dataset.themeSet === m));
    });
  }

  // Closing hides the focused option; return focus to the toggle.
  function closeMenus() {
    document.querySelectorAll('.stuv-theme-switch[open]').forEach(function (d) {
      if (d.contains(document.activeElement)) { d.querySelector('summary').focus(); }
      d.removeAttribute('open');
    });
  }

  apply(mode());

  // component.css hides the switch until this script runs.
  root.classList.add('stuv-theme-ready');

  mq.addEventListener('change', function () {
    if (mode() === 'system') { apply('system'); }
  });

  // Re-apply once the button exists, to label it.
  document.addEventListener('DOMContentLoaded', function () {
    apply(mode());
  });

  // Picks a mode and closes the menu on an outside click, which <details> doesn't do itself.
  document.addEventListener('click', function (e) {
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

/** A src-less handle only carries the inline script, printed in <head>. */
add_action('wp_enqueue_scripts', function (): void {
    wp_register_script('stuv-theme', false, [], STUV_THEME_VERSION, false);
    wp_enqueue_script('stuv-theme');
    wp_add_inline_script('stuv-theme', stuv_theme_script());
});

/** The overlay button style in the editor picker; its look lives in component.css. */
add_action('init', function (): void {
    register_block_style('core/button', [
        'name' => 'overlay',
        'label' => 'Auf Farbfläche',
    ]);
});

/**
 * iOS fills the transparent site icon with black, so point apple-touch-icon at the opaque
 * stuv-dhbw-apple-touch-icon.png, but only once it is uploaded.
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
 * Keeps the footer's © year current; the stored year is the fallback without the plugin. Only
 * inside .stuv-copyright (tools/test_content.py enforces that).
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
