<?php
/**
 * Plugin Name: StuV Theme Toggle
 * Description: Schaltet den Dark Mode der Website um (Button in der Kopfzeile) und merkt sich die Wahl im Browser. ACHTUNG: Wird dieses Plugin deaktiviert, verschwindet der Umschalt-Button und die Seite zeigt immer das helle Design. Quellcode: im Repository dieser Website (Verzeichnis wp-plugin/)
 * Version: 1.2.0
 * Requires PHP: 8.0
 * Author: StuV DHBW Heidenheim
 */

if (!defined('ABSPATH')) {
    exit;
}

define('STUV_THEME_VERSION', '1.2.0');

/**
 * The theme script, inline in <head>.
 *
 * Inline and head-level on purpose: the .dark class must be on <html> before the
 * browser paints the first pixel, otherwise every visitor with a dark preference
 * gets a white flash. An external file would still block the parser, but costs a
 * round trip for ~700 bytes; a footer script would be far too late.
 *
 * The click handler is delegated from `document` because this runs before the
 * header markup exists — no DOMContentLoaded dance, and the button keeps working
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
    root.dataset.themeMode = m;
    root.classList.toggle('dark', resolve(m) === 'dark');
    var buttons = document.querySelectorAll('.stuv-theme-toggle');
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].setAttribute('aria-label', LABELS[m]);
    }
    // The check mark in the menu is what tells System apart from a fixed
    // choice — the trigger icon only ever shows the resolved theme.
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
