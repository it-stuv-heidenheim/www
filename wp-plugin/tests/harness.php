<?php
/** Zero-dependency harness: require it, then the unit, then call check(); the tally prints at shutdown. */

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
