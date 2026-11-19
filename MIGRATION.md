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
