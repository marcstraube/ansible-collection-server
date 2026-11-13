# marcstraube.server.nginx

Install and configure Nginx web server and reverse proxy.

## Description

Installs and configures Nginx from the distribution packages as a web server,
reverse proxy, or load balancer. Features include SSL/TLS with modern ciphers,
HTTP/2, gzip compression, rate limiting, WebSocket proxying, stream (TCP/UDP)
proxying, and security headers.

## Requirements

- ansible-core >= 2.19
- `community.general` collection

## Supported Platforms

| Platform                  | Notes |
| ------------------------- | ----- |
| Arch Linux                |       |
| Debian Trixie             |       |
| EL 9 (Rocky, Alma, RHEL)  |       |
| EL 10 (Rocky, Alma, RHEL) |       |

Other distributions in the same os_family (EndeavourOS, Manjaro, Ubuntu, Mint,
Fedora) should work but are not actively tested. Use distro-specific vars
overrides if needed.

## Role Variables

See [defaults/main.yml](defaults/main.yml) for all available variables.

### Role Control

| Variable                | Default | Description                        |
| ----------------------- | ------- | ---------------------------------- |
| `nginx_enabled`         | `false` | Enable the nginx role              |
| `nginx_service_enabled` | `true`  | Enable and start the Nginx service |

### Installation

| Variable         | Default | Description                           |
| ---------------- | ------- | ------------------------------------- |
| `nginx_mainline` | `false` | Use mainline instead of stable (Arch) |
| `nginx_modules`  | `[]`    | Additional modules to install         |

### Package Updates

| Variable                 | Default     | Description                                                     |
| ------------------------ | ----------- | --------------------------------------------------------------- |
| `nginx_packages_state`   | `'present'` | `present` installs missing packages only, `latest` updates them |
| `nginx_packages_minimum` | `''`        | Lowest acceptable nginx version, string or mapping per platform |

A regular run never updates nginx. A targeted update, for example for a
security release, is requested on the command line:

```bash
ansible-playbook site.yml --tags nginx \
  -e nginx_packages_state=latest \
  -e nginx_packages_minimum=1.28.1
```

With `latest` the role refreshes the package metadata and updates every
installed nginx package in one transaction, including the parts pulled in as
dependencies and the dynamic modules (on Debian `nginx*` and
`libnginx-mod-*`, on EL `nginx*`). The role reports the version change.

`nginx_packages_minimum` is checked twice. Before the update the role asks
the package manager which version the update would install and fails without
a change when it is older than the minimum, which shows that the repository
does not carry the fix yet. After the update it checks the installed version
again; this check is skipped under `--check`.

The minimum is an upstream version (`1.28.1`, any distribution release of it)
or the full distribution version (`1.26.3-3+deb13u10`,
`2:1.20.1-28.el9_8.6`). Debian and EL ship many fixes as backports that only
raise the release, so only the full version proves such a fix. Versions are
compared with the rules of the distribution (`dpkg --compare-versions`, rpm,
`vercmp`); a minimum without an epoch takes the epoch of the package. For
mixed hosts in one run, pass a mapping per platform; the keys are
`<os_family>-<major>` or `<os_family>`, and a host without a matching key
fails before any change:

```yaml
# nginx-minimum.yml, passed with -e @nginx-minimum.yml
nginx_packages_minimum:
  Debian: '1.26.3-3+deb13u10'
  RedHat-9: '2:1.20.1-28.el9_8.6'
  RedHat-10: '2:1.26.3-6.el10_2.7'
  Archlinux: '1.28.1'
```

The packages usually restart nginx themselves. When they did not, for example
because of a `policy-rc.d`, the running master still executes the replaced
binary; the role then tests the configuration with `nginx -t` and restarts
nginx. When the test fails, the run fails without a restart and the running
master keeps serving; the next run with `latest` restarts it.

On Arch Linux `nginx_packages_state` is ignored: updating single packages is
a partial upgrade there, nginx updates with the full system upgrade. Run the
role with `latest` together with the system upgrade (`--tags
system-update,nginx`) to restart nginx after it.

### HTTP Core

| Variable                     | Default  | Description                         |
| ---------------------------- | -------- | ----------------------------------- |
| `nginx_worker_processes`     | `'auto'` | Worker processes (auto = CPU cores) |
| `nginx_worker_connections`   | `1024`   | Max connections per worker          |
| `nginx_keepalive_timeout`    | `65`     | Keep-alive timeout (seconds)        |
| `nginx_server_tokens`        | `false`  | Hide Nginx version in headers       |
| `nginx_client_max_body_size` | `'64m'`  | Client body size limit              |

### SSL/TLS

| Variable                          | Default                  | Description                |
| --------------------------------- | ------------------------ | -------------------------- |
| `nginx_ssl_protocols`             | `['TLSv1.2', 'TLSv1.3']` | Allowed protocols          |
| `nginx_ssl_prefer_server_ciphers` | `false`                  | Prefer server cipher order |
| `nginx_ssl_stapling`              | `true`                   | Enable OCSP stapling       |
| `nginx_ssl_dhparam`               | `''`                     | DH parameters file path    |

The reload handler of this role subscribes to the `Reload cert services` handler
topic of `marcstraube.server.certbot` and `marcstraube.common.pki`, so a
certificate issued or renewed inside the same play takes effect in that run.
Renewal through the certbot timer runs outside of Ansible — set
`certbot_nginx_enabled` for that path.

### Security Headers

| Variable                         | Default    | Description                    |
| -------------------------------- | ---------- | ------------------------------ |
| `nginx_security_headers_enabled` | `true`     | Enable global security headers |
| `nginx_hsts_enabled`             | `true`     | Enable HSTS                    |
| `nginx_hsts_max_age`             | `31536000` | HSTS max-age (seconds)         |

### Sensitive Paths

| Variable              | Default      | Description                |
| --------------------- | ------------ | -------------------------- |
| `nginx_deny_patterns` | see below    | Paths denied on every site |

```yaml
nginx_deny_patterns:
  - '\.git'
  - '\.svn'
  - '\.hg'
  - '\.env'
  - '\.env\.[^/]+'
  - '\.ht[^/]*'
  - '\.DS_Store'
  - 'Thumbs\.db'
  - '[^/]+~'
  - '[^/]+\.(bak|orig|swp|swo)'
  - '[^/]+\.sql(\.(gz|bz2|xz|zst))?'
```

Each pattern must match a whole path component: the list is anchored as
`/(...)(/|$)`, so `\.git` blocks `.git` and everything below it, but not
`.github`.

The patterns are rendered as one regex `location` per site, above the site-type
branch, so `static`, `php`, `proxy` and `custom` sites are covered alike. A site
overrides the list with its own `deny_patterns` key; an empty list drops the
block for that site.

Keep the patterns explicit. A generic `/\.` would also match
`/.well-known/acme-challenge/`, and an nginx regex location takes precedence over
a plain prefix location, so certificate renewal would break.

### SELinux

| Variable                         | Default | Description                      |
| -------------------------------- | ------- | -------------------------------- |
| `nginx_selinux_connect_db`       | `null`  | Let PHP-FPM reach a database     |
| `nginx_selinux_network_connect`  | `null`  | Let nginx call out to a service  |
| `nginx_selinux_sendmail`         | `null`  | Let nginx submit mail via an MTA |

On SELinux systems, nginx and the PHP-FPM workers behind it run in the
`httpd_t` domain and cannot open outbound network connections or submit mail
unless the matching boolean is set. In every case the failure surfaces as a
bare permission error, or a 502 from nginx, with nothing in the nginx or PHP
logs pointing at SELinux.

Set `nginx_selinux_connect_db` when an application served by this role
connects to a database on another host, `nginx_selinux_network_connect` when
it calls out to a remote service such as an API endpoint, and
`nginx_selinux_sendmail` when it sends mail through PHP's `mail()` or a
sendmail binary. Proxies are handled automatically: `httpd_can_network_connect`
is also enabled whenever a site of type `proxy`, an enabled site with
`authentik.enabled` or, with `nginx_stream_enabled`, a stream server exists;
setting `nginx_selinux_network_connect` to `false` alongside any of them fails
the run. An entry in `nginx_upstreams` alone does not count, because only a
site or location that proxies to it opens the connection: a `locations` or
`extra_config` entry that proxies from a site of another type needs
`nginx_selinux_network_connect: true`.

Each variable takes three values: `true` switches the boolean on, `false`
switches it off, and `null` (the default) leaves it as it is on the host. The
booleans apply to the whole `httpd_t` domain, which Apache and PHP-FPM share,
so the role switches one off only when the variable is explicitly `false`.
Returning a variable to `null` therefore does not revert a boolean the role set
earlier; set it to `false` for that.

A PHP application that talks to a remote database, calls an external API and
sends mail through the local MTA:

```yaml
nginx_selinux_connect_db: true
nginx_selinux_network_connect: true
nginx_selinux_sendmail: true
nginx_sites:
  - name: 'php-app'
    server_names:
      - 'php.example.com'
    root: '/var/www/php-app'
    index: 'index.php index.html'
    type: 'php'
    php:
      socket: 'unix:/run/php-fpm/www.sock'
```

### Sites

| Variable      | Default | Description              |
| ------------- | ------- | ------------------------ |
| `nginx_sites` | `[]`    | Site (virtual host) list |

Site types: `static`, `proxy`, `php`, `custom`. See defaults/main.yml for
full site definition schema with SSL, basic auth, rate limiting, and locations.

A site without SSL listens on `listen` (default `80`), a site with SSL on
`listen_ssl` (default `443`) and, with `http_redirect`, also on `listen` for
the redirect. The HTTP redirect (`http_redirect`) and the www redirect
(`www_redirect`) keep the port of the site: with `listen_ssl: 8444` the
HTTP redirect points to `https://<host>:8444/`, with `443` the URL carries
no port.

On SELinux systems nginx may only bind TCP ports labeled `http_port_t` (80,
81, 443, 488, 8008, 8009, 8443 and 9000) and no UDP port. Every other
`listen` and `listen_ssl` port of an enabled site and, with
`nginx_stream_enabled`, every `listen` port of a stream server (TCP, or UDP
with `udp: true`) gets that label from the role;
without it nginx cannot bind the port. A port of another type, such as 3306
(`mysqld_port_t`), is relabeled `http_port_t`. Labels the role added stay in
place when a port is removed from the configuration. Outbound connections
are covered under [SELinux](#selinux).

The default site listens on 80 and on `443 ssl http2`, the same options as
the SSL sites, so the sites can share port 443 with it.

### Upstreams

| Variable          | Default | Description                  |
| ----------------- | ------- | ---------------------------- |
| `nginx_upstreams` | `[]`    | Upstream backend definitions |

Strategies: `round_robin` (default), `least_conn`, `ip_hash`, `hash`.

## Tags

| Tag               | Scope                     |
| ----------------- | ------------------------- |
| `nginx`           | All role tasks            |
| `nginx:install`   | Package installation      |
| `nginx:configure` | Configuration deployment  |
| `nginx:service`   | Service management        |
| `nginx:firewall`  | Firewalld rule management |

## Example Playbook

```yaml
- name: Include nginx role
  ansible.builtin.include_role:
    name: marcstraube.server.nginx
  tags:
    - nginx
  when: nginx_enabled | default(false) | bool
```

### Reverse Proxy with SSL

```yaml
- name: Include nginx role
  ansible.builtin.include_role:
    name: marcstraube.server.nginx
  vars:
    nginx_sites:
      - name: 'app.example.com'
        server_names:
          - 'app.example.com'
        type: 'proxy'
        proxy_pass: 'http://127.0.0.1:3000'
        websocket: true
        ssl:
          enabled: true
          certificate: '/etc/letsencrypt/live/app.example.com/fullchain.pem'
          certificate_key: '/etc/letsencrypt/live/app.example.com/privkey.pem'
        http_redirect: true
  tags:
    - nginx
  when: nginx_enabled | default(false) | bool
```

## Testing

```bash
cd roles/nginx
molecule test
```

Driver: `podman` | Platforms: Arch Linux, Debian Trixie, Rocky 9, Rocky 10

## References

- [Nginx Documentation](https://nginx.org/en/docs/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
- [Nginx Admin Guide](https://docs.nginx.com/nginx/admin-guide/)
- [Nginx Security Controls](https://docs.nginx.com/nginx/admin-guide/security-controls/)

## License

MIT

## Author

Marc Straube
