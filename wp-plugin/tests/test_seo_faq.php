<?php
/**
 * Zero-dependency test harness for the pure FAQ layer.
 * Run: php wp-plugin/tests/test_seo_faq.php
 *
 * The block fixture lives in this file on purpose: the files under fixtures/
 * are byte-exact captures of a foreign API and must never be rewritten; a
 * hand-written block array is something else and belongs to the test.
 *
 * The fixture builders below mirror parse_blocks() semantics exactly: string
 * chunks in `innerContent` with a `null` placeholder per inner block, and
 * `innerHTML` as nothing but the concatenated strings. An earlier version of
 * this file inlined the answer <p> into `innerHTML` and left `innerBlocks`
 * empty — a shape the parser never produces for `data/pages/kummer-karsten/`,
 * which is why it passed while the plugin emitted no FAQPage node at all.
 */
require __DIR__ . '/../stuv-seo/inc/pure/tags.php'; // stuv_seo_normalize_text()
require __DIR__ . '/../stuv-seo/inc/pure/faq.php';

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

/**
 * One block as parse_blocks() returns it. $inner_content holds strings and a
 * null per inner block; innerHTML is derived from it, never passed separately.
 */
function block(string $name, array $inner_content, array $inner_blocks = []): array {
    return [
        'blockName'    => $name,
        'attrs'        => [],
        'innerHTML'    => implode('', array_filter($inner_content, 'is_string')),
        'innerBlocks'  => $inner_blocks,
        'innerContent' => $inner_content,
    ];
}

function paragraph(string $html): array {
    return block('core/paragraph', ["\n" . $html . "\n"]);
}

/**
 * A `core/details` block with its answer in inner paragraph blocks — the shape
 * the FAQ page actually produces.
 */
function details_block(string $summary_html, array $answer_html): array {
    $inner_blocks  = array_map('paragraph', $answer_html);
    $inner_content = ['<details class="wp-block-details stuv-accordion"><summary>' . $summary_html . '</summary>'];
    foreach ($inner_blocks as $_) {
        $inner_content[] = null;
    }
    $inner_content[] = '</details>';

    return block('core/details', $inner_content, $inner_blocks);
}

/**
 * A `core/details` block whose answer sits in the raw markup, without inner
 * blocks — hand-written HTML rather than editor output. Still supported.
 */
function flat_details_block(string $inner_html): array {
    return block('core/details', [$inner_html]);
}

// --- a simple pair ---------------------------------------------------------
$simple = details_block(
    'Wie anonym bin ich?',
    ['<p>Vollständig — nur der Vorsitz liest die Nachricht.</p>']
);
$pairs = stuv_seo_faq_pairs([$simple]);
check('simple: one pair', count($pairs), 1);
check('simple: question from summary', $pairs[0]['question'] ?? null, 'Wie anonym bin ich?');
check('simple: answer from the inner paragraph block',
    $pairs[0]['answer'] ?? null, 'Vollständig — nur der Vorsitz liest die Nachricht.');

// --- several answer paragraphs ---------------------------------------------
// strip_tags() would glue "Eins.Zwei." into one token; the block boundary has
// to survive as a separator.
$multi = stuv_seo_faq_pairs([
    details_block('Zwei Absätze?', ['<p>Eins.</p>', '<p>Zwei.</p>']),
]);
check('multi: paragraphs joined with a space', $multi[0]['answer'] ?? null, 'Eins. Zwei.');

// --- the flat, block-less shape still works --------------------------------
$flat = stuv_seo_faq_pairs([
    flat_details_block('<details><summary>Flach?</summary><p>Auch das geht.</p></details>'),
]);
check('flat: pair from innerHTML alone', $flat[0] ?? null,
    ['question' => 'Flach?', 'answer' => 'Auch das geht.']);

// --- recursion through innerBlocks ----------------------------------------
$nested = [
    block(
        'core/group',
        ['<div class="wp-block-group">', null, null, '</div>'],
        [
            details_block('Frage eins', ['<p>Antwort eins.</p>']),
            block(
                'core/group',
                ['<div class="wp-block-group">', null, '</div>'],
                [details_block('Frage zwei', ['<p>Antwort zwei.</p>'])]
            ),
        ]
    ),
    details_block('Frage drei', ['<p>Antwort drei.</p>']),
];
$nested_pairs = stuv_seo_faq_pairs($nested);
check('nested: all three found', array_column($nested_pairs, 'question'),
    ['Frage eins', 'Frage zwei', 'Frage drei']);
check('nested: order preserved (inner first)', array_column($nested_pairs, 'answer'),
    ['Antwort eins.', 'Antwort zwei.', 'Antwort drei.']);

// --- skipped blocks --------------------------------------------------------
$without_summary = stuv_seo_faq_pairs([
    flat_details_block('<details><p>Kein summary hier.</p></details>'),
]);
check('no summary: skipped, not half-emitted', $without_summary, []);

$empty_answer = stuv_seo_faq_pairs([
    details_block('Leere Frage?', []),
]);
check('empty answer: skipped', $empty_answer, []);

$non_details = stuv_seo_faq_pairs([paragraph('<p>Nur Text.</p>')]);
check('non-details block: ignored', $non_details, []);

// --- question with markup inside summary -----------------------------------
$markup = stuv_seo_faq_pairs([
    details_block('<strong>Anzeige</strong> melden?',
        ['<p>Schreib an <a href="/">das Formular</a>.</p>']),
]);
check('markup: question tags stripped', $markup[0]['question'] ?? null, 'Anzeige melden?');
check('markup: link tags stripped from answer', $markup[0]['answer'] ?? null, 'Schreib an das Formular.');

// --- a nested <details> is not counted twice -------------------------------
$inner_details = details_block('Unterfrage?', ['<p>Unterantwort.</p>']);
$outer = block(
    'core/details',
    ['<details><summary>Oberfrage?</summary>', null, '</details>'],
    [$inner_details]
);
$outer_pairs = stuv_seo_faq_pairs([$outer]);
check('nested details: one entry, not two', count($outer_pairs), 1);
check('nested details: inner text stays part of the answer',
    $outer_pairs[0]['answer'] ?? null, 'Unterfrage? Unterantwort.');

echo $failed ? "\n$failed failed\n" : "\nall passed\n";
exit($failed ? 1 : 0);
