<?php
/**
 * Tests for the copyright-year filter. Run: php wp-plugin/tests/test_theme.php
 * The WordPress functions are stubbed and the registered filter is captured.
 */
require __DIR__ . '/harness.php';

define('ABSPATH', __DIR__);
$filters = [];
function add_action(...$args): void {}
function add_filter(string $hook, callable $cb, int $priority = 10, int $args = 1): void {
    global $filters;
    $filters[$hook] = $cb;
}
function wp_date(string $format): string { return '2031'; }

require __DIR__ . '/../stuv-theme/stuv-theme.php';

// --- stuv_theme_copyright_year ---------------------------------------------
check('replaces the year after ©',
    stuv_theme_copyright_year('<p>© 2026 StuV</p>', '2031'), '<p>© 2031 StuV</p>');

check('leaves other numbers alone',
    stuv_theme_copyright_year('<p>© 2026 StuV, Raum 2024</p>', '2031'), '<p>© 2031 StuV, Raum 2024</p>');

check('no © means no change',
    stuv_theme_copyright_year('<p>Seit 2026</p>', '2031'), '<p>Seit 2026</p>');

// --- the render_block filter -----------------------------------------------
$render = $filters['render_block_core/paragraph'];

check('paragraph with stuv-copyright gets the current year',
    $render('<p class="stuv-copyright">© 2026 StuV</p>', ['attrs' => ['className' => 'stuv-copyright']]),
    '<p class="stuv-copyright">© 2031 StuV</p>');

check('other paragraphs are untouched',
    $render('<p>© 2026 StuV</p>', ['attrs' => ['className' => 'stuv-footer-note']]),
    '<p>© 2026 StuV</p>');

check('paragraph without className is untouched',
    $render('<p>© 2026 StuV</p>', ['attrs' => []]),
    '<p>© 2026 StuV</p>');
