# marcstraube.server.certbot

Install and configure Certbot for Let's Encrypt TLS certificates.

## Description

Installs Certbot, obtains and renews Let's Encrypt (ACME) certificates, and wires
up automatic renewal via a systemd timer (or cron). Supports the webroot,
standalone, nginx, apache and DNS-01 authenticators, ECDSA or RSA keys, deploy
hooks for reloading services on renewal, a handler topic that reloads consuming
roles when a certificate is issued inside a play, combined PEM / PKCS12 output
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

| Platform                 | Notes                       |
| ------------------------ | --------------------------- |
| Arch Linux               |                             |
| Debian Trixie            |                             |
| EL 9 (Rocky, Alma, RHEL) | Requires EPEL for `certbot` |

Other distributions in the same os_family (EndeavourOS, Manjaro, Ubuntu, Mint,
Fedora, EL 10) should work but are not actively tested. Use distro-specific vars
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

| Variable                      | Default | Description                                   |
| ----------------------------- | ------- | --------------------------------------------- |
| `certbot_postfix_enabled`     | `false` | Reload Postfix after issuance and renewal     |
| `certbot_dovecot_enabled`     | `false` | Reload Dovecot after issuance and renewal     |
| `certbot_nginx_enabled`       | `false` | Reload nginx after issuance and renewal       |
| `certbot_apache_enabled`      | `false` | Reload Apache after issuance and renewal      |
| `certbot_reload_services`     | `[]`    | Extra systemd services to reload likewise     |
| `certbot_create_combined_pem` | `false` | Emit `cert+key` PEM (HAProxy) on renewal      |

These toggles build the deploy hook `renewal-hooks/deploy/reload-services.sh`,
which the certbot timer runs after every renewal — outside of any Ansible run.
Set them for every service that reads a certificate from this host, including
services managed by a role of this collection: the handler topic below only
covers certificates issued inside a play.

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

This role subscribes itself with `reload-services.sh`, so the services from the
Service Integration toggles also pick up a certificate issued inside a play. A
host without any consumer and without toggles does not fail: Ansible aborts a
run when a notification reaches no handler, and this listener is always defined.

Two consequences follow from the mechanics:

- certbot runs the deploy hook directory on `certonly` itself since 5.3.0, so on
  hosts with a newer certbot a service may be reloaded twice when a certificate
  is reissued. A reload is idempotent; the duplicate is accepted.
- The notification keys on `Successfully received certificate` in certbot's
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
configuration, the webroot layout, and the renewal timer.

## Notes

- **Opt-in default:** `certbot_enabled` defaults to `false`. Set it to `true` in
  inventory (or the playbook toggle) to run the role.
- **EPEL on EL:** the RedHat `certbot` package requires EPEL. This role installs
  packages but never enables repositories — provision EPEL via
  `marcstraube.common.package_management` (`dnf_epel_enabled`) first.
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
