<?php
/**
 * Zero-dependency test harness shared by the test_*.php scripts.
 *
 * Each test file requires this, then its unit under test, then calls check().
 * summarize() prints the tally and exits with the right status; it is
 * registered as a shutdown function so a test file just ends with its last
 * check() instead of repeating the same two lines.
 */

$failed = 0;

function check(string $name, $actual, $expected): void {
    global $failed;
    if ($actual === $expected) {
        echo "  ok    $name\n";
        return;
    }
    $failed++;
    echo "FAIL    $name\n";
    echo "        expected: " . var_export($expected, true) . "\n";
    echo "        actual:   " . var_export($actual, true) . "\n";
}

register_shutdown_function(function (): void {
    global $failed;
    // A fatal error also ends in shutdown; without this it would read as a pass.
    $error = error_get_last();
    if ($error && in_array($error['type'], [E_ERROR, E_PARSE, E_CORE_ERROR, E_COMPILE_ERROR], true)) {
        $failed++;
    }
    echo $failed ? "\n$failed failed\n" : "\nall passed\n";
    exit($failed ? 1 : 0);
});
