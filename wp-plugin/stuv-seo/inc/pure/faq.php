<?php
/**
 * Pure helper: extract question/answer pairs from Gutenberg blocks.
 *
 * NO WordPress dependencies may be added to this file — it is unit-tested with
 * the plain `php` CLI (wp-plugin/tests/test_seo_faq.php). Input is the nested
 * array `parse_blocks()` produces, output is plain data; nothing here touches
 * WordPress.
 *
 * EXPECTION MANAGEMENT: Google only shows FAQ rich results for government and
 * health sites since August 2023. The markup stays useful anyway — it is valid
 * structured data that other consumers (assistants, aggregators) read — and it
 * costs nothing because it is derived from content that already exists. Nobody
 * should later search for the FAQ list in Google results and be surprised.
 */

/**
 * Walk innerBlocks recursively and collect `core/details` blocks as
 * question/answer pairs.
 *
 * A pair is only emitted when both halves survive extraction: a <details>
 * without a <summary> or without an answer body is skipped, never half-emitted.
 *
 * @param array<int, array<string, mixed>> $blocks parse_blocks() output.
 * @return array<int, array{question: string, answer: string}>
 */
function stuv_seo_faq_pairs(array $blocks): array {
    $pairs = [];

    foreach ($blocks as $block) {
        if (!is_array($block)) {
            continue;
        }

        if (($block['blockName'] ?? '') === 'core/details') {
            $pair = stuv_seo_faq_pair_from_html(stuv_seo_faq_block_html($block));
            if (null !== $pair) {
                $pairs[] = $pair;
            }

            // Its inner blocks ARE the answer — walking them again would emit a
            // nested <details> twice: once inside the answer text, once as an
            // entry of its own.
            continue;
        }

        if (!empty($block['innerBlocks']) && is_array($block['innerBlocks'])) {
            $pairs = array_merge($pairs, stuv_seo_faq_pairs($block['innerBlocks']));
        }
    }

    return $pairs;
}

/**
 * Reassemble one block's HTML, inner blocks included.
 *
 * `innerHTML` alone is NOT the block's markup: parse_blocks() splits a block
 * into the string chunks in `innerContent` with a `null` placeholder wherever
 * an inner block belongs, and `innerHTML` is only the concatenated strings. For
 * `core/details` that is exactly the half without the answer — the answer
 * paragraphs are separate `core/paragraph` inner blocks, so reading `innerHTML`
 * yields `<details><summary>…</summary></details>` and every pair is dropped as
 * answerless. Walking `innerContent` puts the pieces back in document order.
 *
 * Inner-block HTML is padded with newlines: strip_tags() glues text across tag
 * boundaries ("Eins.Zwei."), and whitespace is what stuv_seo_normalize_text()
 * collapses back into a single separator.
 */
function stuv_seo_faq_block_html(array $block): string {
    $inner_blocks = array_values(array_filter((array) ($block['innerBlocks'] ?? []), 'is_array'));
    $inner_content = $block['innerContent'] ?? null;

    // Hand-built or flat blocks without placeholders: keep the string part and
    // append whatever inner blocks there are, rather than losing them.
    if (!is_array($inner_content) || [] === $inner_content) {
        return (string) ($block['innerHTML'] ?? '')
            . implode('', array_map('stuv_seo_faq_block_html', $inner_blocks));
    }

    $html = '';
    $next = 0;
    foreach ($inner_content as $chunk) {
        if (is_string($chunk)) {
            $html .= $chunk;
        } elseif (isset($inner_blocks[$next])) {
            $html .= "\n" . stuv_seo_faq_block_html($inner_blocks[$next]) . "\n";
            $next++;
        }
    }

    return $html;
}

/**
 * Split the reassembled HTML of one `core/details` block into a pair.
 *
 * The question is the <summary> content, the answer is everything after it.
 * Extraction uses preg_match + strip_tags (both PHP built-ins) — deliberately
 * NOT wp_strip_all_tags or WP_HTML_Tag_Processor, which would make this file
 * dependent on WordPress. The trailing `</details>` needs no special case: it
 * is markup and strip_tags() drops it.
 */
function stuv_seo_faq_pair_from_html(string $html): ?array {
    if (!preg_match('/<summary[^>]*>(.*?)<\/summary>(.*)/is', $html, $m)) {
        return null;
    }

    $question = stuv_seo_normalize_text($m[1]);
    $answer   = stuv_seo_normalize_text($m[2]);

    if ('' === $question || '' === $answer) {
        return null;
    }

    return ['question' => $question, 'answer' => $answer];
}
