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

### `nginx` — the role serves the ACME challenge on hosts with certbot

With `certbot_enabled: true` the role now serves
`/.well-known/acme-challenge/` from `certbot_webroot_path`
(`/var/www/letsencrypt` when it is not set) in the default site, the HTTP
redirect servers and the sites. A site or `nginx_global_locations` that defines
this location keeps its own. The path is exempt from basic authentication and
IP lists. A renewal may fail where something else answered the challenge:

- a certificate with a `webroot` of its own in `certbot_certificates`, or
  `certbot_mail_webroot`, for example the document root of the site
- a proxy site whose backend answers the challenge
- a wider location that serves the challenge, such as `/.well-known/` or
  `~ /\.well-known`
- a location in a file that `extra_config` includes: nginx refuses the
  duplicate of the same prefix

On every host the role also checks the certificate and key files configured in
the inventory, not those the deployed configuration names. A site that does not
serve HTTPS yet waits for them: a deployed HTTP site is kept on HTTP, of any
other site only the HTTP redirect is deployed. A site whose deployed
configuration has an HTTPS server fails the run before any site is changed. The
default site falls back to its self-signed certificate while the files of
`nginx_default_site_ssl_certificate` are missing.

#### Required action

On every host, make sure the certificate and key files of the sites in
`nginx_sites` exist. Where nginx does not start because an enabled site names a
certificate that was never issued, remove the link of the site in
`/etc/nginx/sites-enabled` and run the role again.

On hosts with `certbot_enabled`, unless every certificate uses
`certbot_webroot_path` or a DNS authenticator, find the locations and the
webroots in use before the upgrade:

```bash
grep -rnE 'acme-challenge|well-known' /etc/nginx
grep -rnE 'webroot|authenticator' /etc/letsencrypt/renewal
```

Point the certificates to one webroot (`nginx_acme_webroot` overrides the
default), define the location in the site, or keep the previous behavior:

```yaml
nginx_acme_challenge_enabled: false
```

Check the result with `certbot renew --dry-run`.

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

### `certbot` — a non-default `certbot_config_dir` now reaches certbot

Only hosts with a `certbot_config_dir` other than `/etc/letsencrypt` are
affected. Up to v1.1.4 the role wrote `cli.ini` and the renewal hooks to that
directory, but certbot never read it: it kept its account, certificates and
renewal configurations in `/etc/letsencrypt`, and the services use
`/etc/letsencrypt/live/<name>/`. The role now passes
`--config=<certbot_config_dir>/cli.ini` to every certbot command and to the
renew command of the renewal unit (drop-in on Debian and Arch Linux,
`CERTBOT_ARGS` in `/etc/sysconfig/certbot` on EL) and of the cron job.

With it certbot switches to `certbot_config_dir`. Without preparation:

- The role would find no certificate there and request every certificate of
  `certbot_certificates` and the mail certificate again, with a new ACME
  account, into `<certbot_config_dir>/live/<name>/`.
- The certificates in `/etc/letsencrypt` would no longer be renewed and
  expire; services that still read `/etc/letsencrypt/live/<name>/` serve them
  until then.

To prevent this, the role fails before any change while
`/etc/letsencrypt/renewal` holds renewal configurations and
`certbot_config_dir` is another directory. The check runs with every tag.

#### Required action

Before the upgrade, choose one:

- Move the existing state into `certbot_config_dir`: move `accounts/`,
  `archive/`, `live/` and `renewal/` from `/etc/letsencrypt` there, and replace
  `/etc/letsencrypt/` with `<certbot_config_dir>/` in the paths of every
  `renewal/<name>.conf` (`archive_dir`, `cert`, `privkey`, `chain`,
  `fullchain`, and any other option that names the directory). The links in
  `live/` are relative and keep working. Check the result with
  `certbot --config=<certbot_config_dir>/cli.ini certificates`, then point the
  services at `<certbot_config_dir>/live/<name>/`.
- Or let the role request the certificates again in `certbot_config_dir`,
  point the services at the new `live/` paths, and remove the certificates in
  `/etc/letsencrypt` with `certbot delete --cert-name <name>` once nothing reads
  them.
- Or set `certbot_config_dir: '/etc/letsencrypt'`, the directory certbot used
  so far.
- Or, when another tool manages the certificates in `/etc/letsencrypt`, set
  `certbot_default_dir_leftovers_ok: true`.

Remove a `/etc/letsencrypt/cli.ini` after the move: certbot still reads it,
and its settings apply wherever the `cli.ini` of the role does not set them.
`certbot_config_dir` must now be an absolute path of letters, digits and
`. _ / @ + -`, and on EL the role fails while a `CERTBOT_ARGS` line it did not
write holds a value; move such options to `certbot_custom_config`.

## v1.1.4 - 2026-11-19

### `certbot` — services reload once per renewal run, without a restart

The services of `certbot_postfix_enabled`, `certbot_dovecot_enabled`,
`certbot_nginx_enabled`, `certbot_apache_enabled` and `certbot_reload_services`
are no longer reloaded from the deploy hook
`/etc/letsencrypt/renewal-hooks/deploy/reload-services.sh`, which ran once per
renewed certificate and ended in `systemctl reload || systemctl restart || true`.
The role removes that file and writes `/usr/local/sbin/certbot-reload-services`,
which the renewal unit passes to `certbot renew` as `--post-hook`: it runs once
per renewal run, checks the configuration of each service the role knows, and
only reloads. A failed check or reload leaves the service running on its old
configuration, makes the script exit non-zero and leaves a retry marker;
nothing restarts.

The post hook sits on the renew command: the `POST_HOOK` line of
`/etc/sysconfig/certbot` on EL, a drop-in `post-hook.conf` for
`certbot.service` (Debian) or `certbot-renew.service` (Arch Linux), or the cron
job with `certbot_use_systemd_timer: false`.

A failed reload is retried: the new `certbot-reload-retry.timer` (or an hourly
cron job of root with `certbot_use_systemd_timer: false`) runs the script with
`--retry` while `/var/lib/certbot-reload-services/pending` exists, and a run
without failures removes the marker.
Switching from cron to the systemd timer now removes the `certbot renewal`
cron job and the retry cron job wherever cron is installed.

Behaviour that changes with it:

- The `Reload cert services` handler of the role now fails the play when a
  configuration check or a reload fails; the old script ended in `|| true`.
- The reload no longer starts a stopped service (the old `reload || restart`
  did). A stopped service is skipped with a warning; a configured unit that
  does not exist is an error.
- On EL the role owns `POST_HOOK` in `/etc/sysconfig/certbot` while services
  are reloaded and fails before any change when the line holds another value.

#### Required action

- `/etc/sysconfig/certbot` (EL): if `POST_HOOK` holds a command of your own,
  move it to `certbot_post_hook` and set `POST_HOOK=""`, or the role fails.
- Setups that rely on the reload starting a service, for example a `pre_hook`
  that stops the web server for the standalone authenticator, start it from
  `certbot_post_hook` instead.
- Move a `post_hook` of an entry in `certbot_certificates` to
  `certbot_post_hook`; the role fails while both are set, because the post
  hook of the renewal run replaces the hook saved for the certificate.
  Certificates issued outside the role with `--post-hook` lose that hook on
  their next renewal the same way; the role warns about them.
- Watch `journalctl -t certbot-reload-services -p warning` for skipped and
  failed reloads; certbot only logs a failing post hook as a warning and the
  renewal unit succeeds. Retry by hand with
  `systemctl start certbot-reload-retry.service`, or in cron mode
  (`certbot_use_systemd_timer: false`) with
  `/usr/local/sbin/certbot-reload-services --retry`. The hourly retry can be
  switched off with `certbot_reload_retry_timer_enabled: false`.
- Renew by hand with `systemctl start certbot-renew.service` (Debian:
  `certbot.service`) instead of `certbot renew`, which reloads nothing.
- Reload the services yourself after issuing a certificate with
  `certbot certonly` outside the role.
- A service that was only restarted by the old fallback (no reload support in
  its unit) now fails the script; add reload support or reload it from a hook
  of your own.
