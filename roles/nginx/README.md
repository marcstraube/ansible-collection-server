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

### Sites

| Variable      | Default | Description              |
| ------------- | ------- | ------------------------ |
| `nginx_sites` | `[]`    | Site (virtual host) list |

Site types: `static`, `proxy`, `php`, `custom`. See defaults/main.yml for
full site definition schema with SSL, basic auth, rate limiting, and locations.

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
