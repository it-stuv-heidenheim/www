# WordPress Authentication Reference

## Application Password

Modern WordPress (5.6+) uses Application Passwords for REST API access.

1. Log in to `https://<site>/wp-admin`.
2. Go to `Users → Profile` (or `Benutzer → Profil`).
3. Scroll to **Application Passwords**.
4. Enter a name (e.g. `claude-api`) and click **Add New**.
5. Copy the generated password (format: `xxxx xxxx xxxx xxxx`).

## Environment Variables

Export for the session:

```bash
export WP_USER="your_wp_username"
export WP_APP_PASS="xxxx xxxx xxxx xxxx"
export WP_SITE="https://example.com"
```

## Verify Access

```bash
curl -s -u "$WP_USER:$WP_APP_PASS" "$WP_SITE/wp-json/wp/v2/users/me" | python3 -m json.tool
```

## SSO / Google Login

If the site uses Google Apps Login or another OAuth plugin, normal passwords are blocked. Application Passwords still work.
