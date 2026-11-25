# marcstraube.server.certbot

Install and configure Certbot for Let's Encrypt TLS certificates.

## Description

Installs Certbot, obtains and renews Let's Encrypt (ACME) certificates, and wires
up automatic renewal via a systemd timer (or cron). Supports the webroot,
standalone, nginx, apache and DNS-01 authenticators, ECDSA or RSA keys, a
checked reload of the certificate services once per renewal run, a handler
topic that reloads consuming roles when a certificate is issued inside a play,
combined PEM / PKCS12 output
for HAProxy and Java consumers, and a helper for generating a single
mail-service certificate.

The role is **opt-in**: it does nothing until `certbot_enabled` is set to `true`.

## Requirements

- ansible-core >= 2.19
- On RedHat/EL: the `certbot` package lives in **EPEL**. This role does not manage
  repositories — enable EPEL beforehand (the `marcstraube.common.package_management`
  role does this via `dnf_epel_enabled`). Arch and Debian ship Certbot in their
  official repositories.

## Supported Platforms

| Platform                  | Notes                                      |
| ------------------------- | ------------------------------------------ |
| Arch Linux                |                                            |
| Debian Trixie             |                                            |
| EL 9 (Rocky, Alma, RHEL)  | Requires EPEL for `certbot`                |
| EL 10 (Rocky, Alma, RHEL) | Currently unsupported, see [Notes](#notes) |

Other distributions in the same os_family (EndeavourOS, Manjaro, Ubuntu, Mint,
Fedora) should work but are not actively tested. Use distro-specific vars
overrides if needed.

## Role Variables

See [defaults/main.yml](defaults/main.yml) for all available variables.

### Role Control

| Variable             | Default | Description                          |
| -------------------- | ------- | ------------------------------------ |
| `certbot_enabled`    | `false` | Enable the certbot role (opt-in)     |
| `certbot_auto_renew` | `true`  | Enable automatic certificate renewal |

### Account

| Variable                                  | Default | Description                                 |
| ----------------------------------------- | ------- | ------------------------------------------- |
| `certbot_email`                           | `''`    | Contact email for ACME registration/notices |
| `certbot_agree_tos`                       | `true`  | Agree to the Let's Encrypt Terms of Service |
| `certbot_register_unsafely_without_email` | `false` | Register without an email (not recommended) |
| `certbot_staging`                         | `false` | Use the ACME staging server (higher limits) |

### Certificate Defaults

| Variable                  | Default       | Description                              |
| ------------------------- | ------------- | ---------------------------------------- |
| `certbot_key_type`        | `'ecdsa'`     | Key type: `ecdsa` or `rsa`               |
| `certbot_elliptic_curve`  | `'secp384r1'` | Curve for ECDSA keys                     |
| `certbot_rsa_key_size`    | `4096`        | Key size for RSA keys                    |
| `certbot_preferred_chain` | `''`          | Preferred CA chain (e.g. `ISRG Root X1`) |

### Authenticator

| Variable                 | Default                  | Description                        |
| ------------------------ | ------------------------ | ---------------------------------- |
| `certbot_authenticator`  | `'webroot'`              | Default authenticator (see below)  |
| `certbot_webroot_path`   | `'/var/www/letsencrypt'` | Webroot for HTTP-01 challenges     |
| `certbot_create_webroot` | `true`                   | Create the webroot + challenge dir |

Available authenticators: `webroot`, `standalone`, `nginx`, `apache`, `dns-*`.

### Certificates

| Variable               | Default | Description                                   |
| ---------------------- | ------- | --------------------------------------------- |
| `certbot_certificates` | `[]`    | List of certificates to obtain (schema below) |

Each entry is a dict:

```yaml
certbot_certificates:
  - name: 'www.example.com' # cert lineage name (optional; defaults to domains[0])
    domains:
      - 'www.example.com'
      - 'example.com'
    authenticator: 'webroot' # optional; defaults to certbot_authenticator
    webroot: '/var/www/letsencrypt' # optional; defaults to certbot_webroot_path
    key_type: 'ecdsa' # optional per-cert overrides
    staging: false
    force_renewal: false
    deploy_hook: 'systemctl reload apache2'
```

### Renewal

| Variable                      | Default | Description                          |
| ----------------------------- | ------- | ------------------------------------ |
| `certbot_use_systemd_timer`   | `true`  | Use the systemd timer (else cron)    |
| `certbot_renew_before_expiry` | `30`    | Days before expiry to renew          |
| `certbot_pre_hook`            | `''`    | Global pre-renewal hook              |
| `certbot_post_hook`           | `''`    | Global post-renewal hook             |
| `certbot_deploy_hook`         | `''`    | Global deploy hook (runs on renewal) |

### DNS Plugins

| Variable          | Default | Description                                              |
| ----------------- | ------- | -------------------------------------------------------- |
| `certbot_plugins` | `[]`    | Authenticator plugins to install (e.g. `dns-cloudflare`) |

Cloudflare, Route53 and DigitalOcean credential files are rendered from vault
variables — see the DNS section of [defaults/main.yml](defaults/main.yml).

### Service Integration

| Variable                             | Default | Description                                  |
| ------------------------------------ | ------- | -------------------------------------------- |
| `certbot_postfix_enabled`            | `false` | Reload Postfix after issuance and renewal    |
| `certbot_dovecot_enabled`            | `false` | Reload Dovecot after issuance and renewal    |
| `certbot_nginx_enabled`              | `false` | Reload nginx after issuance and renewal      |
| `certbot_apache_enabled`             | `false` | Reload Apache after issuance and renewal     |
| `certbot_reload_services`            | `[]`    | Extra systemd services to reload likewise    |
| `certbot_reload_retry_timer_enabled` | `true`  | Retry a failed reload hourly (timer or cron) |
| `certbot_create_combined_pem`        | `false` | Emit `cert+key` PEM (HAProxy) on renewal     |

These toggles select the services reloaded after a renewal run of the certbot
timer, outside of any Ansible run. Set them for every service that reads a
certificate from this host, including services managed by a role of this
collection: the handler topic below only covers certificates issued inside a
play.

#### Reload After Renewal

The role writes the script `/usr/local/sbin/certbot-reload-services` and passes
it as `--post-hook` to the renew command of the renewal unit. certbot runs a
post hook from the command line once per `renew` run, after all certificates,
and only when it attempted a renewal: a run that renews many certificates
reloads each service once, and `certonly` never runs it.

| Platform                                  | Renewal unit            | Post hook                                      |
| ----------------------------------------- | ----------------------- | ---------------------------------------------- |
| EL                                        | `certbot-renew.service` | `POST_HOOK` in `/etc/sysconfig/certbot`        |
| Debian                                    | `certbot.service`       | Drop-in `post-hook.conf`                       |
| Arch Linux                                | `certbot-renew.service` | Drop-in `post-hook.conf`                       |
| cron (`certbot_use_systemd_timer: false`) | —                       | Cron job `certbot renew --quiet --post-hook=…` |

On EL the role changes only the `POST_HOOK` line of the packaged file. The
unit expands `$POST_HOOK` unquoted and splits it at whitespace, so the value is
the single word `--post-hook=/usr/local/sbin/certbot-reload-services`. The role
owns the line only while it is empty or holds that value: with reload services
it fails before any change when any `POST_HOOK` line holds another value (move
that command to `certbot_post_hook` or remove it), and without reload services
it resets only its own value to `POST_HOOK=""`.

On Debian and Arch Linux the drop-in clears `ExecStart` and sets the packaged
renew command, taken from `__certbot_renew_command` in `vars/Debian.yml` and
`vars/Archlinux.yml`, plus the post hook. When a package update changes the
packaged command, the role warns and the variable has to follow; Molecule
verify compares both as well. The role fails when the effective unit does not
run exactly one renew command with the post hook, i.e. another drop-in adds or
replaces `ExecStart`, and warns when the unit is masked or missing.

For each service the script runs the configuration check of the service where
the role knows one (`apachectl configtest` for `apache2` and `httpd`,
`nginx -t`, `postfix check`, `doveconf -n`), then `systemctl reload`. It never
restarts: after a failed check or reload the service keeps running on its old
configuration. A service that is not active is skipped with a warning, it
reads the new certificate when it starts. A unit that is not loaded (does not
exist, or has an error in its unit file), or one without reload support, fails
like a failed reload; only at an issuance in a play (see
[Certificate Change Notifications](#certificate-change-notifications)) a unit
that does not exist is skipped with a warning. The script sets its own
`PATH`, so it also works from cron. It tries every service, exits non-zero
when a check or a reload failed, and logs each result to the journal under the
tag `certbot-reload-services`; skips and failures at priority `warning` or
higher:

```bash
journalctl -t certbot-reload-services -p warning
```

Watch that tag rather than the renewal unit: certbot logs a failing post hook
only as a warning, which `-q` (Debian, Arch Linux) keeps out of the journal,
and still exits with 0.

#### Retry of a Failed Reload

A failed check or reload leaves the marker
`/var/lib/certbot-reload-services/pending` (directory mode `0700`, root only).
The role-managed `certbot-reload-retry.timer` starts
`certbot-reload-retry.service` hourly, which runs only while the marker exists
(`ConditionPathExists=`) and calls the script with `--retry`. The retry follows
the same rules — configuration check, then reload, never a restart — and logs
every attempt. A run in which every service reloaded removes the marker, so
the retry heals itself once the configuration is fixed. With
`certbot_use_systemd_timer: false` a cron job of root runs
`/usr/local/sbin/certbot-reload-services --retry` hourly instead. Set
`certbot_reload_retry_timer_enabled: false` to stop the timer (or drop the cron
job); the marker is still written. The retry service discards its own output,
as the script logs every message under the `certbot-reload-services` tag.
Runs of the script are serialized by a lock in
`/var/lib/certbot-reload-services`, so a renewal, a handler and a retry never
reload at the same time and a concurrent run cannot clear a fresh marker.

To retry by hand after fixing a configuration:

```bash
systemctl start certbot-reload-retry.service
/usr/local/sbin/certbot-reload-services --retry  # cron mode, or without the timer
ls /var/lib/certbot-reload-services/pending    # gone after a successful retry
```

Running `/usr/local/sbin/certbot-reload-services` without `--retry` reloads
all services whether or not a retry is pending.

Consequences of the mechanism:

- **Manual renewal:** a manual `certbot renew` passes no post hook and reloads
  nothing. Renew through the unit instead, which also reloads:
  `systemctl start certbot-renew.service` (Debian: `certbot.service`). certbot
  saves the post hook of a renewal in the renewal configuration of each
  certificate it renewed (`/etc/letsencrypt/renewal/<name>.conf`), so a manual
  `certbot renew` does run the script for certificates the unit has renewed
  before; do not rely on it.
- **Certificates issued outside the role:** a certificate issued with
  `certbot certonly` by hand or by other tooling reloads nothing at issuance.
  Reload the services yourself, for example by running the script.
- **Per-certificate post hooks:** a post hook on the command line replaces the
  post hook certbot saved for a certificate, and certbot then saves it in its
  place. The role fails when an entry of `certbot_certificates` sets `post_hook`
  while services are reloaded; move the command to `certbot_post_hook`
  (`renewal-hooks/post/`), which certbot runs in addition, before the script.
  Certificates issued outside the role with `--post-hook` lose that hook the
  same way; the role reads `/etc/letsencrypt/renewal/*.conf` (without changing
  them) and warns about every saved post hook other than its script.
- **Stopped services stay stopped:** the reload never starts a service. A
  service a `pre_hook` stops for the standalone authenticator has to be
  started by `certbot_post_hook`.
- **Turning the reload off:** without reload services the role removes the
  script, the retry marker directory, the retry timer and service and the retry
  cron job, resets its own `POST_HOOK` value, removes the drop-in and drops the hook
  from the cron job. Renewal configurations in which certbot saved the hook keep it, and
  certbot logs a warning about the missing script on their next renewal;
  remove the line `post_hook = /usr/local/sbin/certbot-reload-services` from
  `/etc/letsencrypt/renewal/*.conf` to silence it.

## Tags

| Tag                    | Scope                                       |
| ---------------------- | ------------------------------------------- |
| `certbot`              | All role tasks                              |
| `certbot:install`      | Package installation                        |
| `certbot:configure`    | Directories and DNS plugin credentials      |
| `certbot:certificates` | Certificate issuance                        |
| `certbot:renewal`      | Renewal hooks, timer, and monitoring script |

## Certificate Change Notifications

Both tasks that obtain a certificate notify the handler topic
`Reload cert services` when certbot actually issued one. The topic is the
contract consumers rely on; the role names no service for it and the inventory
configures nothing.

A role that reads certificate material subscribes by adding `listen` to its own
reload or restart handler, keeping its own service conditionals:

```yaml
- name: Reload my service
  ansible.builtin.systemd_service:
    name: '{{ __myrole_service_name }}'
    state: reloaded
  listen: Reload cert services
  when: myrole_service_enabled | bool
```

Only roles that actually run in the play react. Within this collection `apache`,
`nginx` and `postgresql` subscribe; `marcstraube.common.pki` notifies the same
topic, so a consumer covers both certificate sources with one `listen`.

This role subscribes itself with the handler `Run certbot service reload
script`, which runs `/usr/local/sbin/certbot-reload-services --issuance`, so the
services from the Service Integration toggles also pick up a certificate issued
inside a play. A service that is not installed yet (no unit) is skipped and
named in the play output and, with priority `warning`, in the journal, because a
later play may install it: it reads the certificate at its first start, so the
toggles can be set before the first run on a new host. A misspelled name is
skipped the same way and fails only at the next renewal. A failed configuration
check or reload fails the handler and the play, and leaves the retry marker. The
renewal tasks write the script; a run limited to `--tags certbot:certificates`
on a host that does not have it yet skips the reload instead of failing. A host
without any consumer and without toggles does not fail: Ansible aborts a
run when a notification reaches no handler, and this listener is always defined.

The notification keys on `Successfully received certificate` in certbot's
output. With `certbot_quiet: true` that line is suppressed and nothing in the
play reacts to an issuance — renewal through the timer is unaffected.

## Example Playbook

```yaml
- name: Include certbot role
  ansible.builtin.include_role:
    name: marcstraube.server.certbot
  tags:
    - certbot
  when: certbot_enabled | default(false) | bool
```

### Webroot certificates (HTTP-01)

```yaml
- name: Include certbot role
  ansible.builtin.include_role:
    name: marcstraube.server.certbot
  vars:
    certbot_enabled: true
    certbot_email: 'admin@example.com'
    certbot_authenticator: 'webroot'
    certbot_webroot_path: '/var/www/letsencrypt'
    certbot_certificates:
      - name: 'www.example.com'
        domains:
          - 'www.example.com'
        deploy_hook: 'systemctl reload apache2'
  tags:
    - certbot
  when: certbot_enabled | default(false) | bool
```

## Testing

```bash
cd roles/certbot
molecule test
```

Driver: `podman` | Platforms: Arch Linux, Debian Trixie, Rocky 9

The molecule scenario uses the ACME staging server and requests no real
certificates (`certbot_certificates: []`) — it validates installation,
configuration, the webroot layout, and the renewal timer. For the reload after
renewal it checks the script, the post hook on the renew command (as systemd
passes it to certbot in a run of the renewal unit, which renews nothing and
does not run the hook), a run of the script with cron's `PATH` that reloads
nginx and a test unit without a restart and skips a stopped unit, a failed
`nginx -t` that fails the script while nginx keeps running and leaves the retry
marker, and the retry unit that reloads and clears the marker and does nothing
without it. `side_effect` covers the refused per-certificate post hook and
foreign `POST_HOOK` (EL), the read-only check of saved post hooks, the cron
jobs, a configured unit that does not exist, and the removal without reload
services, which keeps a foreign `POST_HOOK`.

## Notes

- **Opt-in default:** `certbot_enabled` defaults to `false`. Set it to `true` in
  inventory (or the playbook toggle) to run the role.
- **EPEL on EL:** the RedHat `certbot` package requires EPEL. This role installs
  packages but never enables repositories — provision EPEL via
  `marcstraube.common.package_management` (`dnf_epel_enabled`) first.
- **EL 10 currently unsupported:** the EPEL certbot packages cannot be
  installed there. `python3-acme` needs `python3-pyOpenSSL >= 25`, and the only
  build EPEL offers requires a newer `python3-cryptography` than the
  distribution ships. The role fails on EL 10 before it installs anything
  ([#145](https://github.com/marcstraube/ansible-collection-server/issues/145));
  the support returns once EPEL ships installable packages.
- **Webroot vs. apache authenticator:** the webroot authenticator serves the ACME
  challenge from `certbot_webroot_path` without restarting the web server, which
  is preferable when the running vhost already exposes `/.well-known/acme-challenge/`.

## References

- [Certbot Documentation](https://eff-certbot.readthedocs.io/en/stable/)
- [Certbot User Guide](https://eff-certbot.readthedocs.io/en/stable/using.html)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [ACME Challenge Types](https://letsencrypt.org/docs/challenge-types/)

## License

MIT

## Author

Marc Straube
