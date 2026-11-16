# Migration Guide

Upgrade guide for users of `marcstraube.server`. Each release with
breaking changes adds a section here with before/after inventory
snippets. For the full list of changes per release, see
[CHANGELOG.md](CHANGELOG.md).

Following the [Keep a Changelog](https://keepachangelog.com/) convention,
the file always carries a persistent `## Unreleased` section at the top.
Breaking-change PRs append their entries under that section; the release
workflow dates it to `## v<X.Y.Z> - YYYY-MM-DD` at release time and
inserts a fresh empty `## Unreleased` above it. A release without
entries under `## Unreleased` gets no section of its own. Do not delete the
heading or rename it to a concrete version — the workflow handles that.

## Unreleased

### `nginx` — HTTP/2 moves from the `listen` parameter to `http2 on;`

On nginx 1.25.1 and later the role no longer renders the deprecated `http2`
parameter of `listen`. Every HTTPS server block of a site with HTTP/2 on, and
the 443 block of the default site, gets its own `http2 on;` instead; plain
HTTP ports never get HTTP/2. HTTP/2 stays on by default
(`nginx_http2_enabled: true`) and a site can switch it off with
`http2: false`. Older nginx (EL 9's default 1.20) keeps the `listen`
parameter.

The `listen` parameter used to switch HTTP/2 on for every server block on
the same address and port. That no longer happens, which affects server
blocks the role does not manage on a port it shares with role sites:

- A block without any HTTP/2 setting of its own no longer gets HTTP/2 from
  the role's sites.
- A block that still uses `listen … http2` switches HTTP/2 on for the whole
  address and port, so role sites there with `http2: false` lose their
  setting, and `nginx -t` may warn about redefined protocol options.

#### Required action

None for hosts where the role writes every server block. Otherwise find the
server blocks the role does not manage that listen with `ssl`:

```bash
grep -rnE 'listen[^;]*\bssl\b' /etc/nginx/conf.d /etc/nginx/sites-enabled
```

In each block that should keep HTTP/2, drop `http2` from the `listen` lines
and add the directive:

```nginx
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    # ...
}
```

### `apache` — Debian unloads `mod_http2` when nothing enables HTTP/2

On Debian the role now disables `mod_http2` with `a2dismod` while neither
`apache_http2_enabled` nor an entry of `apache_vhosts_ssl` with `http2: true`
enables HTTP/2, also when it was enabled by hand with `a2enmod`. It also
replaces the package's `mods-available/http2.conf` with a neutral file: its
`Protocols h2 h2c http/1.1` added up with the role's own `Protocols` line,
which turned HTTP/2 over TLS on for vhosts meant to stay on HTTP/1.1 and
offered HTTP/2 over plain HTTP (`h2c`). `h2c` is no longer offered.

The replaced file is a dpkg conffile. When Debian changes it, an interactive
`apt upgrade` asks which version to keep; keep the local one. Ansible's
`apt` module keeps it without asking.

#### Required action

None for hosts that configure HTTP/2 through the role. To keep `mod_http2`
loaded without HTTP/2 from the role, for example for a configuration of your
own, list it in `apache_modules_enabled`; the role then neither disables nor
unloads it:

```yaml
apache_modules_enabled:
  - 'http2'
```

The server-wide `Protocols` line the role then writes follows
`apache_http2_enabled`, so set `Protocols` in your own vhosts.
