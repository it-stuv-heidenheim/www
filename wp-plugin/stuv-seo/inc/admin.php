<?php
/**
 * Admin surface: the SEO metabox on every page, the settings page under
 * Einstellungen → StuV SEO, and the assets/enqueueing for both.
 *
 * Both are plain PHP against the fifteen-year-stable metabox and Settings
 * API — deliberately no editor sidebar panel, which would need either an npm
 * build (the repo's first) or hand-written React globals that move between
 * WordPress versions. The price is accepted: the metabox sits BELOW the page
 * content in the block editor, not in the sidebar.
 *
 * Storage still goes through register_post_meta (inc/meta.php) — that is where
 * the sanitizer and the auth_callback live; the metabox is only the input.
 *
 * The page also carries a read-only start checklist: title length (diagnosis,
 * not control — the plugin does not touch titles, see the plan E3),
 * description length with a warning above STUV_SEO_DESCRIPTION_LIMIT, whether
 * a preview image resolves, and the noindex flag. That table is the
 * replacement for a SEO dashboard and the one place a new board sees what is
 * still missing.
 */

if (!defined('ABSPATH')) {
    exit;
}

/* ------------------------------------------------------------------ *
 * Metabox
 * ------------------------------------------------------------------ */

function stuv_seo_add_meta_box(): void {
    add_meta_box('stuv-seo', 'SEO', 'stuv_seo_meta_box_render', 'page', 'normal', 'default');
}
add_action('add_meta_boxes', 'stuv_seo_add_meta_box');

function stuv_seo_meta_box_render(WP_Post $post): void {
    wp_nonce_field('stuv_seo_save', 'stuv_seo_nonce');

    $description = stuv_seo_get_description($post->ID);
    $image_id    = stuv_seo_get_og_image_id($post->ID);
    $noindex     = stuv_seo_get_noindex($post->ID);
    ?>
    <p>
        <label for="stuv-seo-description"><strong>Beschreibung</strong></label><br>
        <span class="stuv-seo-counter-field">
            <textarea name="_stuv_seo_description" id="stuv-seo-description" class="stuv-seo-description"
                rows="3" style="width:100%"><?php echo esc_textarea($description); ?></textarea>
            <?php /* No aria-live: the counter changes on every keystroke, and a
                     live region would read each one out over the typing. */ ?>
            <span class="stuv-seo-counter"></span>
        </span>
        <span class="description">Erscheint als Beschreibung in Such- und Teilen-Vorschauen (max.
            <?php echo (int) STUV_SEO_DESCRIPTION_LIMIT; ?> Zeichen).</span>
    </p>
    <p>
        <strong>Vorschaubild</strong><br>
        <?php echo stuv_seo_media_field('_stuv_seo_og_image', $image_id); // phpcs:ignore WordPress.Security.EscapeOutput ?>
        <span class="description">Falls leer, gilt das Standardbild aus Einstellungen → StuV SEO.</span>
    </p>
    <p>
        <label>
            <input type="checkbox" name="_stuv_seo_noindex" value="1" <?php checked($noindex); ?>>
            <strong>Von Suchmaschinen ausschließen</strong>
        </label><br>
        <span class="description">Setzt die Seite auf <code>noindex, follow</code> — sie fällt dadurch auch aus der Sitemap.</span>
    </p>
    <?php
}

/**
 * The media picker markup shared by the metabox and the settings page.
 *
 * The hidden input carries the attachment id; assets/admin.js wires the two
 * buttons against wp.media and refreshes the preview.
 */
function stuv_seo_media_field(string $name, int $image_id): string {
    $url = $image_id > 0 ? (string) wp_get_attachment_image_url($image_id, 'medium') : '';

    ob_start();
    ?>
    <span class="stuv-seo-media-field">
        <input type="hidden" class="stuv-seo-media-value" name="<?php echo esc_attr($name); ?>"
            value="<?php echo esc_attr($image_id); ?>">
        <img class="stuv-seo-media-preview" src="<?php echo esc_url($url); ?>" alt=""
            style="max-width:300px;height:auto;display:block;margin:8px 0" <?php echo $url ? '' : 'hidden'; ?>>
        <button type="button" class="button stuv-seo-media-open">Bild wählen</button>
        <button type="button" class="button-link stuv-seo-media-remove" <?php echo $url ? '' : 'hidden'; ?>>Entfernen</button>
    </span>
    <?php
    return (string) ob_get_clean();
}

function stuv_seo_save_meta(int $post_id): void {
    if (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE) {
        return;
    }
    if (!isset($_POST['stuv_seo_nonce']) || !wp_verify_nonce(sanitize_key($_POST['stuv_seo_nonce']), 'stuv_seo_save')) {
        return;
    }
    if (!current_user_can('edit_page', $post_id)) {
        return;
    }

    $description = isset($_POST['_stuv_seo_description'])
        ? sanitize_text_field(wp_unslash($_POST['_stuv_seo_description']))
        : '';
    update_post_meta($post_id, '_stuv_seo_description', $description);

    $image_id = isset($_POST['_stuv_seo_og_image']) ? absint($_POST['_stuv_seo_og_image']) : 0;
    update_post_meta($post_id, '_stuv_seo_og_image', $image_id);

    $noindex = !empty($_POST['_stuv_seo_noindex']);
    update_post_meta($post_id, '_stuv_seo_noindex', $noindex);
}
add_action('save_post_page', 'stuv_seo_save_meta', 10, 1);

/* ------------------------------------------------------------------ *
 * Settings page
 * ------------------------------------------------------------------ */

function stuv_seo_register_settings(): void {
    register_setting('stuv_seo', 'stuv_seo_settings', [
        'type'              => 'array',
        'sanitize_callback' => 'stuv_seo_sanitize_settings',
    ]);
}
add_action('admin_init', 'stuv_seo_register_settings');

function stuv_seo_sanitize_settings($value): array {
    $value = is_array($value) ? $value : [];

    return [
        'og_image'            => isset($value['og_image']) ? absint($value['og_image']) : 0,
        'google_verification' => isset($value['google_verification'])
            ? sanitize_text_field((string) $value['google_verification'])
            : '',
    ];
}

function stuv_seo_add_settings_page(): void {
    add_options_page('StuV SEO', 'StuV SEO', 'manage_options', 'stuv-seo', 'stuv_seo_settings_page_render');
}
add_action('admin_menu', 'stuv_seo_add_settings_page');

function stuv_seo_settings_page_render(): void {
    $settings = stuv_seo_get_settings();
    ?>
    <div class="wrap">
        <h1>StuV SEO</h1>

        <form method="post" action="options.php">
            <?php settings_fields('stuv_seo'); ?>

            <h2>Allgemein</h2>
            <table class="form-table" role="presentation">
                <tr>
                    <th scope="row"><label>Standard-Vorschaubild</label></th>
                    <td>
                        <?php echo stuv_seo_media_field('stuv_seo_settings[og_image]', (int) ($settings['og_image'] ?? 0)); // phpcs:ignore WordPress.Security.EscapeOutput ?>
                        <p class="description">Wird als Teilen-Vorschau genutzt, wenn eine Seite kein eigenes Bild hat.</p>
                    </td>
                </tr>
                <tr>
                    <th scope="row"><label for="stuv-seo-google-verification">Google Search Console Token</label></th>
                    <td>
                        <input type="text" id="stuv-seo-google-verification"
                            name="stuv_seo_settings[google_verification]" class="regular-text"
                            value="<?php echo esc_attr($settings['google_verification'] ?? ''); ?>">
                        <p class="description">Der Wert aus dem Verifikations-Tag der Search Console (ohne das Tag selbst).</p>
                    </td>
                </tr>
            </table>

            <?php submit_button(); ?>
        </form>

        <?php stuv_seo_start_checklist(); ?>
    </div>
    <?php
}

/**
 * The read-only start checklist over all pages.
 */
function stuv_seo_start_checklist(): void {
    $query = new WP_Query([
        'post_type'      => 'page',
        'post_status'    => 'publish',
        'posts_per_page' => -1,
        'orderby'        => 'menu_order',
        'order'          => 'ASC',
        'no_found_rows'  => true,
    ]);

    if (!$query->have_posts()) {
        return;
    }

    $settings = stuv_seo_get_settings();

    echo '<h2>Startcheckliste</h2>';
    echo '<p>Zahlen sind Diagnose, nicht Steuerung — Titel und Beschreibungen werden auf der jeweiligen Seite gepflegt.</p>';
    echo '<table class="widefat striped">';
    echo '<thead><tr>'
        . '<th>Seite</th>'
        . '<th>Titel (Zeichen)</th>'
        . '<th>Beschreibung</th>'
        . '<th>Vorschaubild</th>'
        . '<th>noindex</th>'
        . '</tr></thead>';
    echo '<tbody>';

    while ($query->have_posts()) {
        $query->the_post();

        $post_id   = (int) get_the_ID();
        $title_len = mb_strlen((string) get_the_title());
        $desc_len  = mb_strlen(stuv_seo_get_description($post_id));
        $has_image = stuv_seo_get_og_image_id($post_id) > 0 || (int) ($settings['og_image'] ?? 0) > 0;

        printf(
            '<tr><td>%s</td>'
            . '<td%s>%d</td>'
            . '<td%s>%d</td>'
            . '<td>%s</td>'
            . '<td>%s</td></tr>',
            esc_html((string) get_the_title()),
            $title_len > 60 ? ' style="color:#b32d2e"' : '',
            $title_len,
            $desc_len > STUV_SEO_DESCRIPTION_LIMIT ? ' style="color:#b32d2e"' : '',
            $desc_len,
            $has_image ? 'ja' : '—',
            stuv_seo_get_noindex($post_id) ? 'ja' : '—'
        );
    }

    echo '</tbody></table>';

    wp_reset_postdata();
}

/* ------------------------------------------------------------------ *
 * Assets
 * ------------------------------------------------------------------ */

function stuv_seo_admin_enqueue(string $hook): void {
    $screen       = get_current_screen();
    $is_editor    = in_array($hook, ['post.php', 'post-new.php'], true)
        && $screen && 'page' === $screen->post_type;
    $is_settings  = 'settings_page_stuv-seo' === $hook;

    if (!$is_editor && !$is_settings) {
        return;
    }

    wp_enqueue_media();
    wp_enqueue_script(
        'stuv-seo-admin',
        plugins_url('assets/admin.js', STUV_SEO_FILE), // not __FILE__ — see the constant
        [],
        STUV_SEO_VERSION,
        true
    );
    // The counter's limit comes from PHP so that the metabox hint, the
    // checklist and the counter cannot drift apart.
    wp_add_inline_script(
        'stuv-seo-admin',
        'window.stuvSeoDescriptionLimit = ' . (int) STUV_SEO_DESCRIPTION_LIMIT . ';',
        'before'
    );
}
add_action('admin_enqueue_scripts', 'stuv_seo_admin_enqueue');
