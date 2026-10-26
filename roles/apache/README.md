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

### MPM Tuning

| Variable                               | Default | Description                    |
| -------------------------------------- | ------- | ------------------------------ |
| `apache_mpm_start_servers`             | `3`     | StartServers (event/worker)    |
| `apache_mpm_min_spare_threads`         | `25`    | MinSpareThreads                |
| `apache_mpm_max_spare_threads`         | `75`    | MaxSpareThreads                |
| `apache_mpm_threads_per_child`         | `25`    | ThreadsPerChild                |
| `apache_mpm_max_request_workers`       | `400`   | MaxRequestWorkers              |
| `apache_mpm_max_connections_per_child` | `1000`  | MaxConnectionsPerChild         |
| `apache_mpm_server_limit`              | `''`    | ServerLimit; empty: no setting |

Without `ServerLimit`, Apache sizes its scoreboard to
`MaxRequestWorkers / ThreadsPerChild` server processes, with no free slot.
A process that is shutting down keeps its slot until its last connection ends:
after a graceful reload, when idle threads exceed `MaxSpareThreads`, and when it
reaches `MaxConnectionsPerChild`. Apache then cannot start new processes and
logs `AH03490: scoreboard is full, not at MaxRequestWorkers`. Set
`apache_mpm_server_limit` above that ratio, for example to twice its value, to
leave room for these processes.

The role checks that `apache_mpm_server_limit` × `apache_mpm_threads_per_child`
reaches `apache_mpm_max_request_workers`. Apache reads `ServerLimit` only at
startup, so the role restarts Apache instead of reloading it when the value
changes. A restart interrupts the service. On EL and Debian the unit stops
Apache gracefully: it closes its listening sockets at once and starts again only
after the open connections have finished. On Arch Linux the unit stops Apache
immediately, aborting requests in progress.

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

SELinux also restricts the ports httpd may bind to those labeled `http_port_t`
(80, 81, 443, 488, 8008, 8009, 8443 and 9000). Every other port in
`apache_listen_ports`, and in `apache_listen_ssl_ports` while SSL is enabled,
gets that label from the role; without it Apache cannot bind the port and shuts
down on the next reload. Labels the role added stay in place when a port is
removed from the lists.

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
| `apache_remoteip_header`                    | `remoteip`                       |
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
- `vhost` writes one `<FilesMatch>` block into every vhost of
  `apache_vhosts_ssl` and `apache_vhosts`. HTTP vhosts with
  `redirect_to_https` are skipped, since they answer every request with a
  redirect.

Both HTTP and SSL vhosts accept `php_fpm_socket` and `php_fpm_timeout`.
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

### Address Binding

By default every vhost answers on all addresses (`<VirtualHost *:PORT>`). Set
`listen_address` on an entry of `apache_vhosts`, `apache_vhosts_ssl` or
`apache_reverse_proxies` to bind it to one address, for example a backend
behind a reverse proxy that should only answer on its internal interface.
IPv6 addresses go in brackets (`'[2001:db8::10]'`).

`listen_address` only changes the `<VirtualHost>` line. Apache accepts
connections on that address only if a matching `Listen` entry exists:
`apache_listen_ports` and `apache_listen_ssl_ports` are rendered verbatim, so
list the entries as `'ADDRESS:PORT'`. Two `Listen` entries for the same
address and port make Apache refuse to start.

```yaml
apache_listen_ports:
  - '192.0.2.10:8081'
apache_vhosts:
  - server_name: 'app.example.com'
    document_root: '/var/www/app.example.com'
    listen_address: '192.0.2.10'
    listen_port: 8081
```

Binding to an address limits the interfaces Apache listens on; it does not
restrict which clients may connect. Restrict the source addresses with the
firewall, for example through the `marcstraube.common.firewalld` role.

### Client Address Behind a Reverse Proxy

| Variable                          | Default | Description                                  |
| --------------------------------- | ------- | -------------------------------------------- |
| `apache_remoteip_header`          | `''`    | Header with the client address; empty = off  |
| `apache_remoteip_trusted_proxies` | `[]`    | Proxies whose header is trusted              |

Behind a reverse proxy or load balancer, Apache sees the proxy as the client:
access logs, `REMOTE_ADDR` in applications and `Require ip` all get the proxy
address. With `apache_remoteip_header` set, the role loads `mod_remoteip` and
renders `RemoteIPHeader` and `RemoteIPTrustedProxy` into the main
configuration, so the client address from the header replaces the proxy
address for every vhost. Only requests from the addresses or CIDR ranges in
`apache_remoteip_trusted_proxies` are trusted; the role refuses an empty list,
since any client could otherwise set an arbitrary address through the header.

```yaml
apache_remoteip_header: 'X-Forwarded-For'
apache_remoteip_trusted_proxies:
  - '192.0.2.1'
```

### Service Limits

| Variable              | Default | Description                                                   |
| --------------------- | ------- | ------------------------------------------------------------- |
| `apache_limit_nofile` | `''`    | `LimitNOFILE` of the service; empty keeps the systemd default |

Apache needs one file descriptor per log directive in a virtual host and one
per distinct error log file ([File Descriptor Limits](https://httpd.apache.org/docs/2.4/vhosts/fd-limits.html)).
With the systemd default soft limit of 1024 a host with many virtual hosts that
log separately runs out: the configuration test passes, but the restart fails
with `AH00019: Unable to open logs` and the service stops. Setting
`apache_limit_nofile` (e.g. `65536`) deploys a systemd drop-in with
`LimitNOFILE` and restarts Apache, since a reload keeps the running main
process and its limit. Debian starts Apache through `apachectl`, which applies
its own `ulimit -n` from `APACHE_ULIMIT_MAX_FILES` (8192 when unset); the role
sets that line in `/etc/apache2/envvars` to the same value. Emptying the
variable removes the drop-in and restores the commented distro line.

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
