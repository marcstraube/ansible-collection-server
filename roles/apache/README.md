# marcstraube.server.apache

Install and configure Apache HTTP Server.

## Description

Installs and configures Apache 2.4+ as a web server or reverse proxy.
Supports MPM selection, HTTP/2, SSL/TLS with modern ciphers, virtual hosts,
reverse proxy, PHP-FPM integration, and security hardening.

## Requirements

- ansible-core >= 2.19
- `ansible.posix` collection (for firewalld integration)
- `community.general` collection

## Supported Platforms

| Platform                  | Notes              |
| ------------------------- | ------------------ |
| Arch Linux                | Package: `apache`  |
| Debian Trixie             | Package: `apache2` |
| EL 9 (Rocky, Alma, RHEL)  | Package: `httpd`   |
| EL 10 (Rocky, Alma, RHEL) | Package: `httpd`   |

Other distributions in the same os_family (EndeavourOS, Manjaro, Ubuntu, Mint,
Fedora) should work but are not actively tested. Use distro-specific vars
overrides if needed.

## Role Variables

See [defaults/main.yml](defaults/main.yml) for all available variables.

### Role Control

| Variable                 | Default | Description                         |
| ------------------------ | ------- | ----------------------------------- |
| `apache_enabled`         | `false` | Enable the apache role              |
| `apache_service_enabled` | `true`  | Enable and start the Apache service |

### Essential Variables

| Variable                  | Default                   | Description                       |
| ------------------------- | ------------------------- | --------------------------------- |
| `apache_mpm_module`       | `'event'`                 | MPM module (prefork/worker/event) |
| `apache_server_name`      | `'{{ ansible_fqdn }}'`    | Server hostname                   |
| `apache_server_admin`     | `'webmaster@example.com'` | Server admin email                |
| `apache_listen_ports`     | `[80]`                    | HTTP listen ports                 |
| `apache_listen_ssl_ports` | `[443]`                   | HTTPS listen ports                |
| `apache_ssl_enabled`      | `false`                   | Enable SSL/TLS                    |
| `apache_http2_enabled`    | `false`                   | Enable HTTP/2                     |

### Security

| Variable                          | Default  | Description                      |
| --------------------------------- | -------- | -------------------------------- |
| `apache_server_tokens`            | `'Prod'` | ServerTokens directive           |
| `apache_server_signature`         | `'Off'`  | ServerSignature directive        |
| `apache_trace_enable`             | `'Off'`  | TraceEnable directive            |
| `apache_security_headers_enabled` | `true`   | Enable security response headers |
| `apache_hsts_enabled`             | `true`   | Enable HSTS header               |
| `apache_selinux_connect_db`       | `null`   | Let PHP-FPM reach a database     |
| `apache_selinux_network_connect`  | `null`   | Let httpd call out to a service  |
| `apache_selinux_sendmail`         | `null`   | Let httpd submit mail via an MTA |

On SELinux systems, httpd and its PHP-FPM workers cannot open outbound network
connections or submit mail unless the matching boolean is set. In every case the
failure surfaces as a bare permission error, with nothing in the Apache or PHP
logs pointing at SELinux.

Set `apache_selinux_connect_db` when an application served by this role connects
to a database on another host, `apache_selinux_network_connect` when it calls out
to a remote service such as an API endpoint, and `apache_selinux_sendmail` when
it sends mail through PHP's `mail()` or a sendmail binary. Reverse proxy vhosts
are handled automatically: `httpd_can_network_connect` is also enabled whenever
`apache_reverse_proxies` is set; setting `apache_selinux_network_connect` to
`false` alongside reverse proxies fails the run.

Each variable takes three values: `true` switches the boolean on, `false`
switches it off, and `null` (the default) leaves it as it is on the host. The
booleans apply to the whole `httpd_t` domain, which nginx and PHP-FPM share, so
the role switches one off only when the variable is explicitly `false`.
Returning a variable to `null` therefore does not revert a boolean the role set
earlier; set it to `false` for that.

### Sensitive Paths

| Variable                      | Default   | Description                          |
| ----------------------------- | --------- | ------------------------------------ |
| `apache_deny_htaccess`        | `true`    | Deny `.ht*` files                    |
| `apache_deny_sensitive_files` | `true`    | Deny `apache_deny_patterns`          |
| `apache_deny_patterns`        | see below | Paths denied in every document root  |

```yaml
apache_deny_patterns:
  - '\.git'
  - '\.svn'
  - '\.hg'
  - '\.env'
  - '\.env\.[^/]+'
  - '\.DS_Store'
  - 'Thumbs\.db'
  - '[^/]+~'
  - '[^/]+\.(bak|orig|swp|swo)'
  - '[^/]+\.sql(\.(gz|bz2|xz|zst))?'
```

The patterns are rendered server-wide as one `<DirectoryMatch>`, anchored as
`/(...)(/|$)`. Each pattern must therefore match a whole path component:
`\.git` blocks `.git` and everything below it, but not `.github`. Apache
applies the section to file paths as well, so files such as `.env` are covered
too.

### Modules

| Variable                  | Default | Description                                    |
| ------------------------- | ------- | ---------------------------------------------- |
| `apache_modules_enabled`  | `[]`    | Additional modules to load                     |
| `apache_modules_disabled` | `[]`    | Modules to keep out, even if a feature uses it |
| `apache_optional_modules` | `[]`    | Same as `apache_modules_enabled`               |
| `apache_status_enabled`   | `false` | Serve `/server-status` to localhost            |

The role loads only the modules its configuration needs. A fixed base set
(`authz_core`, `authz_host`, `dir`, `log_config`, `mime`, `reqtimeout`,
`unixd`) is always loaded. Every enabled feature adds its own modules:

| Feature                                     | Modules                          |
| ------------------------------------------- | -------------------------------- |
| `apache_ssl_enabled`                        | `ssl`, `socache_shmcb`           |
| `apache_security_headers_enabled`           | `headers`                        |
| `apache_compression_enabled`                | `deflate`, `filter`, `setenvif`  |
| `apache_caching_enabled`                    | `expires`                        |
| `apache_acme_challenge_enabled`             | `alias`                          |
| `apache_http2_enabled`                      | `http2`                          |
| `apache_status_enabled`                     | `status`                         |
| `apache_php_fpm_enabled`                    | `proxy`, `proxy_fcgi`            |
| `apache_reverse_proxies`                    | `proxy`, `proxy_http`, `rewrite` |
| a vhost with `redirect_to_https`            | `rewrite`                        |

Modules an application needs beyond that go into `apache_modules_enabled`,
for example `rewrite` for `.htaccess` rules, `auth_basic`, `authn_file` and
`authz_user` for Basic Auth, `access_compat` for Apache 2.2 syntax
(`Order`/`Allow`/`Deny`) or `autoindex` for directory listings. Names are
written without the `mod_` prefix. Modules a listed one depends on are added
automatically.

On EL and Arch Linux the role writes one `LoadModule` line per module into
`httpd.conf`; the package's `conf.modules.d` is not included. Because the
package's `conf.d/autoindex.conf` uses directives of `mod_autoindex`, the role
replaces it with an empty file while `autoindex` is not loaded.

On Debian the role enables the modules with `a2enmod`. Modules the `apache2`
package enables by default but nothing needs are disabled with `a2dismod`.
Modules enabled by other packages, such as `php` or `security2`, are left
alone unless they appear in `apache_modules_disabled`.

### PHP-FPM

| Variable                 | Default   | Description                          |
| ------------------------ | --------- | ------------------------------------ |
| `apache_php_fpm_enabled` | `false`   | Enable PHP-FPM integration           |
| `apache_php_fpm_socket`  | see below | FPM socket the handler proxies to    |
| `apache_php_fpm_timeout` | `60`      | ProxyTimeout for the FPM backend     |
| `apache_php_fpm_scope`   | `'global'`| Where the handler is configured      |

The default socket is `unix:/run/php-fpm/php-fpm.sock|fcgi://localhost`. A Unix
socket needs that placeholder URL after the pipe, because the path alone is not a
complete proxy URL; the role appends it when it is missing. A TCP backend is
written as `fcgi://host:port` and is passed through untouched — appending the
suffix there would make Apache read the whole string as a hostname.

`apache_php_fpm_scope` selects where the handler lands:

- `global` writes a single block into the server configuration. Every vhost
  inherits it, including vhosts written by something other than this role.
- `vhost` writes one `<FilesMatch>` block into every SSL vhost.

In `global` mode a vhost overrides the handler with its own `php_fpm_socket`,
because a vhost-local `<FilesMatch>` takes precedence over the server-context one
— so hosts running several PHP versions stay expressible. The same applies to
`php_fpm_timeout`, and the two override independently: a vhost may set a shorter
timeout and keep using the global handler.

`ProxyTimeout` belongs at server level in `global` mode, since Apache rejects it
in `<Directory>` context.

### Firewall

| Variable                   | Default    | Description           |
| -------------------------- | ---------- | --------------------- |
| `apache_firewalld_enabled` | `true`     | Enable firewalld rule |
| `apache_firewalld_zone`    | `'public'` | Firewalld zone        |

### ACME / Let's Encrypt

| Variable                        | Default                  | Description                                 |
| ------------------------------- | ------------------------ | ------------------------------------------- |
| `apache_acme_challenge_enabled` | tracks `certbot_enabled` | Serve ACME challenge, exclude from redirect |
| `apache_acme_webroot`           | `'/var/www/letsencrypt'` | Webroot for `/.well-known/acme-challenge/`  |

When enabled, every HTTP and reverse-proxy vhost gets an
`Alias /.well-known/acme-challenge/` into `apache_acme_webroot`, a `RewriteCond`
that excludes that path from any `redirect_to_https`, and — for proxy vhosts — a
`ProxyPass /.well-known/acme-challenge/ !` so the challenge is served locally
rather than forwarded. The webroot directory is created automatically. The
default tracks `certbot_enabled`, so certbot's webroot authenticator works
turnkey on hosts where this role and `marcstraube.server.certbot` run together.

The reload handler of this role subscribes to the `Reload cert services` handler
topic of `marcstraube.server.certbot` and `marcstraube.common.pki`, so a
certificate issued or renewed inside the same play takes effect without a
second include of this role. Renewal through the certbot timer runs outside of
Ansible — set `certbot_apache_enabled` for that path.

### Default Vhost

Apache answers requests whose Host header matches no vhost (direct IP access,
unknown domains) from the first loaded vhost — with this role that means the
alphabetically first config file. Set `default_vhost: true` on at most one
entry per list (`apache_vhosts`, `apache_vhosts_ssl`, `apache_reverse_proxies`)
to deploy that config as `00-<name>.conf`, making it the explicit catch-all.
On the SSL side the default vhost also serves clients with unknown SNI. When
`apache_vhosts_exclusive` is enabled, the previously unprefixed config of a
newly flagged vhost is pruned automatically.

### Exclusive Vhost Pruning

| Variable                  | Default | Description                                       |
| ------------------------- | ------- | ------------------------------------------------- |
| `apache_vhosts_exclusive` | `false` | Remove orphaned role-managed vhost configs        |
| `apache_vhosts_keep`      | `[]`    | Config file names to keep even when unmanaged     |

With `apache_vhosts_exclusive: true` the role removes vhost configs it deployed
earlier that are no longer listed in `apache_vhosts`, `apache_vhosts_ssl` or
`apache_reverse_proxies` — for example after a vhost was renamed or dropped
from inventory. On Debian the site is disabled via `a2dissite` before the file
is removed. Only files whose content starts with the `ansible_managed` header
are removed; distro-provided or hand-written configs never match and are left
untouched. If the `ansible_managed` text changes between runs, configs deployed
with the old text are no longer recognized and survive (fail-safe — remove them
by hand or re-deploy first). List file names in `apache_vhosts_keep` to exempt
unmanaged files explicitly.

## Tags

| Tag                | Scope                     |
| ------------------ | ------------------------- |
| `apache`           | All role tasks            |
| `apache:install`   | Package installation      |
| `apache:configure` | Configuration deployment  |
| `apache:vhosts`    | Virtual host management   |
| `apache:service`   | Service management        |
| `apache:firewall`  | Firewalld rule management |

## Example Playbook

```yaml
- name: Include apache role
  ansible.builtin.include_role:
    name: marcstraube.server.apache
  tags:
    - apache
  when: apache_enabled | default(false) | bool
```

### HTTPS with Reverse Proxy

```yaml
- name: Include apache role
  ansible.builtin.include_role:
    name: marcstraube.server.apache
  vars:
    apache_ssl_enabled: true
    apache_hsts_enabled: true
    apache_http2_enabled: true
    apache_reverse_proxies:
      - server_name: 'app.example.com'
        proxy_pass: 'http://localhost:3000'
        proxy_preserve_host: true
  tags:
    - apache
  when: apache_enabled | default(false) | bool
```

### HTTP vhost with Let's Encrypt (webroot HTTP-01)

The HTTP vhost redirects to HTTPS but still serves the ACME challenge, so
certbot's webroot authenticator can issue the certificate. Enabling
`certbot_enabled` on the host turns `apache_acme_challenge_enabled` on
automatically.

```yaml
- name: Include apache role
  ansible.builtin.include_role:
    name: marcstraube.server.apache
  vars:
    apache_acme_challenge_enabled: true
    apache_acme_webroot: '/var/www/letsencrypt'
    apache_vhosts:
      - server_name: 'www.example.com'
        listen_port: 80
        redirect_to_https: true
  tags:
    - apache
  when: apache_enabled | default(false) | bool
```

## Testing

```bash
cd roles/apache
molecule test
```

Driver: `podman` | Platforms: Arch Linux, Debian Trixie, Rocky 9, Rocky 10

## References

- [Apache HTTP Server Documentation](https://httpd.apache.org/docs/2.4/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [CIS Apache HTTP Server Benchmark](https://www.cisecurity.org/benchmark/apache_http_server)
- [Apache MPM Documentation](https://httpd.apache.org/docs/2.4/mpm.html)

## License

MIT

## Author

Marc Straube
