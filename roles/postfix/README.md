# marcstraube.server.postfix

Postfix as the MTA of the mail stack: virtual domains from PostfixAdmin,
delivery to Dovecot over LMTP, authenticated submission and a milter.

## Description

The role installs Postfix and owns its whole configuration (`main.cf` and
`master.cf`, one template each for all platforms). Mail domains, mailboxes
and aliases come from the PostfixAdmin schema in PostgreSQL or MariaDB
(`marcstraube.server.postfixadmin`); Postfix only reads them. Mail for these
domains goes to Dovecot over LMTP (`marcstraube.server.dovecot`), users send
through submission on port 587 (STARTTLS) and 465 (implicit TLS) after SASL
authentication through Dovecot, and every message passes a milter (rspamd,
`marcstraube.server.rspamd`). The database, Dovecot and rspamd may run on
other hosts.

The role also handles the local mail of the host (`sendmail`, aliases for
`root`), so it replaces `marcstraube.common.mta` there (see
[Migration from marcstraube.common.mta](#migration-from-marcstraubecommonmta)).
It prints the DNS records the MTA needs and checks whether they are set.

## Requirements

- ansible-core >= 2.19
- A PostgreSQL or MariaDB database with the PostfixAdmin schema and a user
  with `SELECT` on its tables (see [Database Privileges](#database-privileges))
- Dovecot with the LMTP and SASL listeners of the mail stack
  (`marcstraube.server.dovecot`, see [Dovecot](#dovecot))
- A certificate and key for the host name of the MTA (`marcstraube.common.pki`
  or `marcstraube.server.certbot`)
- On the controller: the Python library `dnspython` for the DNS check
  (`community.general.dig`)
- `mta_enabled: false` for the host when `marcstraube.common.mta` is in the
  play (unset counts as `true`)

### Required Collections

```yaml
collections:
  - community.general
```

## Supported Platforms

| Platform                  | Notes                                                |
| ------------------------- | ---------------------------------------------------- |
| Arch Linux                |                                                      |
| Debian Trixie             | Services run chrooted in the queue directory         |
| EL 9 (Rocky, Alma, RHEL)  | Postfix 3.5: compatibility level `2` (see below)     |
| EL 10 (Rocky, Alma, RHEL) | No `hash:` or `btree:` tables; the role uses `lmdb:` |

Other distributions in the same os_family (EndeavourOS, Manjaro, Ubuntu, Mint,
Fedora) should work but are not actively tested. Use distro-specific vars
overrides if needed.

## Role Variables

See [defaults/main.yml](defaults/main.yml) for all available variables.

### Role Control

| Variable                  | Default | Description                          |
| ------------------------- | ------- | ------------------------------------ |
| `postfix_enabled`         | `false` | Enable the postfix role              |
| `postfix_service_enabled` | `true`  | Enable and start the Postfix service |

### Package Updates

| Variable                   | Default     | Description                                                       |
| -------------------------- | ----------- | ----------------------------------------------------------------- |
| `postfix_packages_state`   | `'present'` | `present` installs missing packages only, `latest` updates them   |
| `postfix_packages_minimum` | `''`        | Lowest acceptable Postfix version, string or mapping per platform |

A regular run never updates Postfix. A targeted update, for example for a
security release, is requested on the command line:

```bash
ansible-playbook site.yml --tags postfix \
  -e postfix_packages_state=latest \
  -e postfix_packages_minimum=3.10.13
```

With `latest` the role refreshes the package metadata and updates every
installed Postfix package in one transaction, including the lookup modules
(`postfix-lmdb`, `postfix-pgsql`, `postfix-mysql`), which require the exact
version of `postfix`. The role reports the version change.

`postfix_packages_minimum` is checked twice. Before the update the role asks
the package manager which version the update would install and fails without
a change when it is older than the minimum, which shows that the repository
does not carry the fix yet. After the update it checks the installed version
again; this check is skipped under `--check`.

The minimum is an upstream version (`3.10.13`, any distribution release of
it) or the full distribution version (`3.10.13-0+deb13u1`,
`2:3.5.25-3.el9_8`). Debian and EL ship many fixes as backports that only
raise the release, so only the full version proves such a fix. Versions are
compared with the rules of the distribution (`dpkg --compare-versions`, rpm,
`vercmp`); a minimum without an epoch takes the epoch of the package (EL
packages carry epoch 2). For mixed hosts in one run, pass a mapping per
platform; the keys are `<os_family>-<major>` or `<os_family>`, and a host
without a matching key fails before any change:

```yaml
# postfix-minimum.yml, passed with -e @postfix-minimum.yml
postfix_packages_minimum:
  Debian: '3.10.13-0+deb13u1'
  RedHat-9: '2:3.5.25-3.el9_8'
  RedHat-10: '2:3.8.5-10.el10_2'
  Archlinux: '3.11.7'
```

The packages usually restart Postfix themselves. When they did not, for
example because of a `policy-rc.d`, the master process still executes the
replaced binary (`/var/spool/postfix/pid/master.pid`) and the role restarts
it after `postfix check` passed with the new binaries; when the check fails,
the old master keeps running and the run fails with the output.

On Arch Linux `postfix_packages_state` is ignored: updating single packages
is a partial upgrade there, Postfix updates with the full system upgrade. Run
the role with `latest` together with the system upgrade (`--tags
system-update,postfix`) to restart Postfix after it.

### Compatibility Level

| Variable                      | Default | Description                                          |
| ----------------------------- | ------- | ---------------------------------------------------- |
| `postfix_compatibility_level` | `''`    | `compatibility_level` of `main.cf`; empty: see below |

Postfix changes several defaults with its compatibility level. The role
writes a fixed level, so a package update never changes the behavior without
an inventory change. Empty selects the level of the release each platform
shipped when this role version was released:

| Platform      | Postfix | Default level |
| ------------- | ------- | ------------- |
| Arch Linux    | 3.11    | `3.11`        |
| Debian Trixie | 3.10    | `3.10`        |
| EL 10         | 3.8     | `3.8`         |
| EL 9          | 3.5     | `2`           |

Postfix before 3.6 knows the levels `0`, `1` and `2` only; from 3.6 on a
level is a release number. The role fails when the level is above the
installed release (Postfix itself accepts it silently): with Postfix
installed before any change, on a first install after the package install
and before `main.cf` is written. A level counts as fitting up to the full
installed version (`3.10.1` passes with Postfix 3.10.4). With
`postfix_packages_state: latest` the check before any change compares with
the release installed at that time, not with the one the update brings: a
level that only the new release knows fails before the update; raise it in
a run after the update.

### Identity

| Variable               | Default               | Description                                        |
| ---------------------- | --------------------- | -------------------------------------------------- |
| `postfix_myhostname`   | FQDN                  | Host name of the MTA (greeting, HELO, certificate) |
| `postfix_mydomain`     | domain of the host    | `mydomain`                                         |
| `postfix_myorigin`     | `postfix_myhostname`  | Domain of local mail without a domain              |
| `postfix_smtpd_banner` | `'$myhostname ESMTP'` | Greeting, without version or platform              |

`mydestination` holds the names of the host only (`$myhostname`,
`localhost.$mydomain`, `localhost`); every mail domain is virtual. The host
name must therefore not be a mail domain (`mail.example.com` for the domain
`example.com`).

### Network

| Variable                  | Default                        | Description                                |
| ------------------------- | ------------------------------ | ------------------------------------------ |
| `postfix_inet_interfaces` | `'all'`                        | Interfaces Postfix listens on              |
| `postfix_inet_protocols`  | `'all'`                        | `all`, `ipv4` or `ipv6`                    |
| `postfix_mynetworks`      | `['127.0.0.0/8', '[::1]/128']` | Trusted clients: may relay through port 25 |

A change of the interfaces or protocols restarts Postfix, everything else
reloads it.

### System Mail

| Variable          | Default | Description                                                  |
| ----------------- | ------- | ------------------------------------------------------------ |
| `postfix_aliases` | `{}`    | Local aliases (name: target or list), e.g. `root: 'admin@…'` |

The aliases go into a marked block of the alias file of the platform
(`/etc/aliases`, on Arch Linux `/etc/postfix/aliases`). A name in
`postfix_aliases` replaces the package entry of the same name (`postalias`
keeps the first entry of a name and skips a later one with a warning): the
role comments out that line with the prefix `# marcstraube.server.postfix:`
(names compare case-insensitively, continuation lines of the entry
included) and restores it when the name is removed from `postfix_aliases`.
Debian ships `postmaster` only; EL also `mailer-daemon`, `abuse`,
`webmaster` and other system names, Arch Linux `MAILER-DAEMON`, `abuse` and
others. The other package entries stay. Mail of cron and other local programs goes through `sendmail`
to `root@<host>`, which is delivered locally: forward `root` to a mailbox that
is read.

### Database

| Variable                 | Default          | Description                                             |
| ------------------------ | ---------------- | ------------------------------------------------------- |
| `postfix_db_type`        | `'postgresql'`   | `postgresql` or `mariadb`                               |
| `postfix_db_host`        | `'localhost'`    | Host, IP address or socket path (PostgreSQL: directory) |
| `postfix_db_port`        | `5432` / `3306`  | Port                                                    |
| `postfix_db_name`        | `'postfixadmin'` | Database of PostfixAdmin                                |
| `postfix_db_user`        | `'postfix'`      | Read-only user                                          |
| `postfix_db_password`    | `''`             | Password (**required**, store it in the vault)          |
| `postfix_db_tls`         | `false`          | Connect with TLS and verify the server certificate      |
| `postfix_db_tls_ca_file` | `''`             | CA file for the server certificate (required with TLS)  |
| `postfix_sql_queries`    | `{}`             | Queries replacing the defaults (see below)              |

Only connection settings: the database may run on another host and does not
have to be managed by Ansible. `localhost` with MariaDB connects through the
socket of the platform. With TLS the server certificate is verified against
the CA file and the host name (PostgreSQL `sslmode=verify-full`, MariaDB
`tls_verify_cert`); a connection without TLS is unencrypted and meant for a
private network or WireGuard. Without TLS the role warns when
`postfix_db_host` is neither a socket path nor `localhost`, `::1` or an
address in `127.0.0.0/8`.

Postfix reads every SQL table through `proxy:` (one connection pool in
`proxymap`, which also serves the chrooted services of Debian). The lookup
files below `/etc/postfix/sql` belong to `root:postfix` with mode `0640`.
PostgreSQL connects with a `postgresql://` URI; Postfix writes it into the
log when the connection fails, so the password is not part of it but of the
libpq password file `/var/lib/postfix/pgpass` (owner `postfix`, mode `0400`:
libpq reads it as the Postfix user and refuses it with any group or other
permission; below `/etc/postfix` `postfix check` of Debian expects root as
owner).
MariaDB has the password in the lookup files.

The default queries read the PostfixAdmin schema, only active rows of active
domains:

| Key (lookup file)                    | `main.cf`                 | Answers                                    |
| ------------------------------------ | ------------------------- | ------------------------------------------ |
| `virtual_mailbox_domains`            | `virtual_mailbox_domains` | Mail domains (no backup MX domains)        |
| `virtual_mailbox_maps`               | `virtual_mailbox_maps`    | Mailboxes                                  |
| `virtual_alias_maps`                 | `virtual_alias_maps` (1)  | Aliases, catch-all `@domain`               |
| `virtual_alias_domain_maps`          | `virtual_alias_maps` (2)  | Addresses of alias domains                 |
| `virtual_alias_domain_catchall_maps` | `virtual_alias_maps` (3)  | Catch-all of the target of an alias domain |
| `sender_login_maps`                  | `smtpd_sender_login_maps` | Owners of an address: mailbox, alias goto  |
| `sender_login_alias_domain_maps`     | `smtpd_sender_login_maps` | The same for an alias domain               |

`postfix_sql_queries` replaces single queries by key (Postfix expansions
`%s`, `%u`, `%d`); see [vars/main.yml](vars/main.yml) for the defaults.

### Delivery

| Variable               | Default                       | Description                                  |
| ---------------------- | ----------------------------- | -------------------------------------------- |
| `postfix_lmtp_address` | `'unix:private/dovecot-lmtp'` | Dovecot LMTP; `inet:<host>:24` for remote    |
| `postfix_sasl_path`    | `'private/auth'`              | Dovecot SASL; `inet:<host>:12345` for remote |

### Submission

| Variable                         | Default | Description                                          |
| -------------------------------- | ------- | ---------------------------------------------------- |
| `postfix_submission_enabled`     | `true`  | Port 587 with STARTTLS                               |
| `postfix_submissions_enabled`    | `true`  | Port 465 with implicit TLS                           |
| `postfix_submission_hide_client` | `false` | Remove the `Received` header with the client address |
| `postfix_sender_permissions`     | `{}`    | Further logins per sender address (shared mailboxes) |

Both ports require TLS and SASL authentication through Dovecot; `AUTH` is not
offered before TLS. `reject_sender_login_mismatch` lets a user send only from
addresses the user owns: the own mailbox, the aliases whose targets include
the user (an alias owner may send as the alias), the same addresses in alias
domains and the entries of `postfix_sender_permissions`. A catch-all alias
(`@example.com`) makes its targets owners of every address of the domain
without an owner of its own. Port 25 has no authentication, and
`postfix_mynetworks` never relays through submission.

A shared mailbox (`support@example.com`, see the dovecot role) owns its own
address. Read access to it never allows sending as it; the logins that may
send as the shared address are listed separately:

```yaml
postfix_sender_permissions:
  'support@example.com':
    - 'alice@example.com'
    - 'bob@example.com'
```

The role writes them into the `lmdb:` table `/etc/postfix/sender_permissions`
and joins it with the PostfixAdmin queries in a `unionmap:`, so the owners of
both count.

### Inbound

| Variable                         | Default | Description                                              |
| -------------------------------- | ------- | -------------------------------------------------------- |
| `postfix_postscreen_enabled`     | `false` | postscreen on port 25 (pregreet test, DNS blocklists)    |
| `postfix_postscreen_dnsbl_sites` | `[]`    | DNS blocklists of postscreen, e.g. `zen.spamhaus.org*2`  |
| `postfix_policy_services`        | `[]`    | Policy services per recipient, e.g. Dovecot quota-status |

Port 25 requires `HELO` with a valid, fully qualified name (except for
`postfix_mynetworks`), rejects senders and recipients without a fully
qualified domain or without DNS records, recipients the lookups do not know
and relaying (`reject_unauth_destination`), then asks the policy services.
`postfix_mynetworks` may relay through port 25, e.g. a Dovecot on another
host sending Sieve redirects and vacation replies; the milter applies to that
mail as to any other. DNS blocklists refuse queries from public resolvers;
use a local resolver such as `marcstraube.common.unbound`.

The Dovecot quota-status service rejects mail for a full mailbox at SMTP time
instead of bouncing it later:

```yaml
postfix_policy_services:
  - 'inet:127.0.0.1:12340'   # dovecot_quota_status_listen
```

### Milter

| Variable                        | Default                    | Description                         |
| ------------------------------- | -------------------------- | ----------------------------------- |
| `postfix_milters`               | `['inet:127.0.0.1:11332']` | Milters; `[]` disables them         |
| `postfix_milter_default_action` | `'tempfail'`               | Action when a milter is unreachable |

The default expects rspamd (`marcstraube.server.rspamd`) on the same host.
The milters apply to port 25, submission and the local `sendmail`. With
`tempfail` mail is deferred while a milter is unreachable instead of passing
unfiltered. The role probes every milter after the service task and prints a
warning when one does not answer; the run never fails on it, because rspamd
usually comes from a role that runs later.

### Outbound

| Variable                          | Default | Description                               |
| --------------------------------- | ------- | ----------------------------------------- |
| `postfix_relayhost`               | `''`    | Relay host, e.g. `[smtp.example.net]:587` |
| `postfix_relayhost_username`      | `''`    | Login at the relay host                   |
| `postfix_relayhost_password`      | `''`    | Password at the relay host (vault)        |
| `postfix_smtp_tls_security_level` | `'may'` | TLS of outbound connections               |

Empty `postfix_relayhost` delivers directly by MX. A relay host helps hosts
that cannot send on port 25. With a password the role writes the `lmdb:`
table `/etc/postfix/relay_password` (source and table `root`, mode `0600`;
the SMTP client opens it as root), sets `smtp_sasl_security_options` and
`smtp_sasl_tls_security_options` to `noanonymous` and raises the TLS level
from `none`, `may` or `dane` to `secure`: `may` would send the password
without TLS, `dane` falls back to `may` without TLSA records, and `encrypt`
encrypts without authenticating the relay host, so an active attacker in
the path could pose as it and capture the password. `secure` verifies the
certificate of the relay host against the system trust store
(`smtp_tls_CAfile`, the CA bundle of the platform) and its name
(`smtp_tls_secure_cert_match = nexthop, dot-nexthop`; with
`[smtp.example.net]:587` the name is `smtp.example.net`). Write the relay
host in brackets: without them Postfix looks up the MX records of the name,
and the certificate must then match that name itself (for `example.net`
also `*.example.net`), not the name of the MX host. Any other level
set in `postfix_smtp_tls_security_level` stays: `encrypt` is the opt-out for
a relay host with a self-signed or mismatching certificate, `verify`,
`dane-only` and `fingerprint` are stricter or different checks. Without a
password the table is removed.

`dane` needs a DNSSEC-validating resolver on the host, such as
`marcstraube.common.unbound`; the role then sets `smtp_dns_support_level =
dnssec`.

### TLS

| Variable                          | Default                              | Description                               |
| --------------------------------- | ------------------------------------ | ----------------------------------------- |
| `postfix_tls_cert_file`           | `''`                                 | Certificate with chain (**required**)     |
| `postfix_tls_key_file`            | `''`                                 | Private key (**required**)                |
| `postfix_tls_ca_file`             | `''`                                 | CA for client certificates; usually empty |
| `postfix_tls_protocols`           | `'!SSLv2, !SSLv3, !TLSv1, !TLSv1.1'` | Port 25 and opportunistic outbound TLS    |
| `postfix_tls_mandatory_protocols` | `'!SSLv2, !SSLv3, !TLSv1, !TLSv1.1'` | Submission and required outbound TLS      |

Port 25 offers STARTTLS (`smtpd_tls_security_level = may`), submission
requires TLS. The protocols use the exclusion syntax, which Postfix 3.5 on EL
9 understands as well; ranges such as `'>=TLSv1.2'` need Postfix 3.6, and the
role refuses them on EL 9 (Postfix 3.5 would accept them in `postfix check`
and run every TLS service without TLS). Postfix reads certificate and key as
root when a service starts, so root-only files work. Certificate, key, the
CA file (when set) and `postfix_db_tls_ca_file` (with `postfix_db_tls`) must
exist when the role runs: a missing file fails the run before any change
(`postfix check` does not open them; Postfix would only fail when a TLS
service starts). Check mode skips this check. The role reloads Postfix on the
`Reload cert services` handler topic of `marcstraube.common.pki`; for
renewals of the certbot timer set `certbot_postfix_enabled: true` in
`marcstraube.server.certbot`.

### Limits

| Variable                                     | Default    | Description                       |
| -------------------------------------------- | ---------- | --------------------------------- |
| `postfix_message_size_limit`                 | `52428800` | Largest message in bytes          |
| `postfix_smtpd_recipient_limit`              | `1000`     | Recipients per message            |
| `postfix_smtpd_client_connection_rate_limit` | `0`        | Connections per client and minute |
| `postfix_smtpd_client_message_rate_limit`    | `0`        | Messages per client and minute    |
| `postfix_smtpd_client_recipient_rate_limit`  | `0`        | Recipients per client and minute  |

`0` is no limit; `postfix_mynetworks` is excepted from the rate limits.

### Extra Configuration

| Variable                  | Default | Description                                  |
| ------------------------- | ------- | -------------------------------------------- |
| `postfix_extra_main_cf`   | `{}`    | Further `main.cf` parameters (name: value)   |
| `postfix_extra_master_cf` | `''`    | Further `master.cf` lines, appended verbatim |

A parameter of `postfix_extra_main_cf` replaces the one the role writes; a
list is joined with a comma and a space, `true`/`false` become `yes`/`no`.

The role renders `main.cf` and `master.cf` into
`/etc/postfix/ansible-staging` and checks them there before they replace the
active files: `postconf -n` and `postconf -M` (syntax, unknown parameters in
`main.cf` and in `-o` options of `master.cf`) and `postfix check` (values
Postfix cannot use, file permissions). Any error or warning fails the run;
the active files and the running service stay untouched. The one exception
is the warning of Debian's `postfix check` that a copy of a system file in
the chroot differs from the original (`/var/spool/postfix/etc/hosts and
/etc/hosts differ`): Postfix refreshes these copies when it starts, and
`postfix check` itself unless `SYNC_CHROOT` is empty in
`/etc/default/postfix`. The filter matches copies below the default
queue directory `/var/spool/postfix`; with `queue_directory` moved through
`postfix_extra_main_cf` the warning fails the run like any other. Every
change keeps the previous file next to it (`main.cf.<pid>.<date>@<time>~`,
likewise `master.cf`), so the first run over a hand-written `main.cf` does not
lose it; remove old copies by hand.

The reload or restart for a changed `main.cf` or `master.cf` runs as a
handler at the end of the play. When the run fails after the files were
activated and before the handlers ran, the running Postfix keeps the old
settings, and later runs report the files as unchanged and notify nothing:
restart it by hand (`systemctl restart postfix`).

### DNS

| Variable                    | Default            | Description                                     |
| --------------------------- | ------------------ | ----------------------------------------------- |
| `postfix_dns_check_enabled` | `true`             | Check the records (they are printed either way) |
| `postfix_dns_resolver`      | `''`               | IPv4 address of the resolver; empty: system's   |
| `postfix_dns_resolver_port` | `53`               | Port of the resolver                            |
| `postfix_dns_domains`       | `[]`               | Mail domains for the MX and SPF records         |
| `postfix_dns_addresses`     | `[]`               | Public addresses of the MTA; empty: default IPs |
| `postfix_dns_spf`           | `'v=spf1 mx -all'` | Expected SPF record; `''` skips it              |

See [DNS Records](#dns-records).

## Tags

| Tag                 | Description                                               |
| ------------------- | --------------------------------------------------------- |
| `postfix`           | All tasks of the role                                     |
| `postfix:install`   | Packages, targeted update                                 |
| `postfix:maps`      | Lookup files, sender permissions, relay password, aliases |
| `postfix:configure` | `main.cf` and `master.cf` (staged, checked, activated)    |
| `postfix:service`   | Service and milter check                                  |
| `postfix:dns`       | Print and check the DNS records                           |

## Example Playbook

```yaml
- name: Mail server
  hosts: mail_servers
  become: true
  roles:
    - role: marcstraube.server.postfix
      vars:
        postfix_enabled: true
        postfix_myhostname: 'mail.example.com'
        postfix_db_password: '{{ vault_postfix_db_password }}'
        postfix_tls_cert_file: '/etc/letsencrypt/live/mail.example.com/fullchain.pem'
        postfix_tls_key_file: '/etc/letsencrypt/live/mail.example.com/privkey.pem'
        postfix_policy_services:
          - 'inet:127.0.0.1:12340'
        postfix_sender_permissions:
          'support@example.com':
            - 'alice@example.com'
        postfix_aliases:
          root: 'admin@example.com'
        postfix_dns_domains:
          - 'example.com'
    # After Postfix: Dovecot creates its sockets in the queue directory
    - role: marcstraube.server.dovecot
```

On one host the run order is postfixadmin → postfix → dovecot → rspamd.
Postfix starts without the Dovecot sockets and defers delivery and
authentication until Dovecot has created them in the same run.

## Testing

```bash
cd roles/postfix

# Everything on one instance (one platform at a time)
MOLECULE_PLATFORM_NAME=postfix-postgresql-debian-trixie molecule test -s postgresql
MOLECULE_PLATFORM_NAME=postfix-mariadb-rocky-9 molecule test -s mariadb

# Postfix in one container, database, PostfixAdmin and Dovecot in another
molecule test -s split
```

Driver: `podman` | Scenarios: `postgresql`, `mariadb` (Arch Linux, Debian
Trixie, Rocky 9, Rocky 10), `split` (Debian Trixie, two containers)

Prepare sets up the database, PostfixAdmin and Dovecot of this collection
with test accounts (`molecule/shared/vars/accounts.yml`), a test CA and a
dnsmasq test resolver: the instance resolves through it, and it is published
to the controller on a port per platform (`15411`-`15414` for postgresql,
`15421`-`15424` for mariadb) for the DNS check. The controller needs
`dnspython`.

`postgresql` and `mariadb` run a check before converge and after
idempotence, the targeted package update with a rollback in side effect, and
verify the early failure with `mta_enabled` unset, with a compatibility
level above the release (before any change) and with a missing TLS key, the
lookups through proxymap, the permissions of the
lookup files, port 25 (mailbox, alias, alias domain, unknown recipient,
relaying from outside and from `mynetworks`), delivery into the Maildir over
LMTP, local mail to `root`, `postmaster` replacing the entry of the package alias
file (and the package entry restored in side effect), submission on 587 and 465 (`AUTH` before
STARTTLS refused, wrong password, sender of another user, alias, alias domain,
shared mailbox with and without `postfix_sender_permissions`, no relaying
from `mynetworks` without login), the removed or kept `Received` header, the
quota-status rejection, TLS 1.1 refused and TLS 1.2 accepted on 465 and 587
(the TLS library of EL refuses TLS 1.1 on the client side; there the
configuration is checked), a broken `postfix_extra_main_cf` rejected without
touching `main.cf` or the master process, mail deferred with a 4xx reply
while the milter is unreachable together with the warning, the relay host
settings and their removal, the submission login and the LMTP delivery in
the mail log, and the DNS report. `mariadb` also runs the lookups over TCP
with TLS (`db.example.com`, `tls_verify_cert`) against a MariaDB server with
the test certificate, for a user that may only connect with TLS.

`split` reads the lookups over TCP with TLS (`verify-full`), delivers over
the LMTP TCP listener, authenticates through the SASL TCP listener, and checks
a Sieve redirect and a vacation reply that the Dovecot container sends
through port 25, relaying from that container on port 25 but not on
submission, and relaying refused from another address. The Postfix
container has no `policy-rc.d` of the image, like a Debian host: verify
checks that the first install did not start Postfix with the packaged
configuration (one start, by the role) and that the role removed its
temporary `policy-rc.d`. Side effect runs the role with the `policy-rc.d` of
the dovecot role in place (kept) and with a chroot copy that differs from
the original while `SYNC_CHROOT` is off (`postfix check` warns, the role
passes), then leaves the role's own `policy-rc.d` behind, as an interrupted
first run does, runs the role with only `postfix:maps`, `postfix:configure`
and `postfix:service`, and runs it again in full, which removes the
leftover.

## Notes

### Migration from marcstraube.common.mta

`marcstraube.common.mta` makes a host a send-only null client; this role
makes it a full MTA. Both configure the same Postfix, so this role fails
early unless `mta_enabled` is `false` for the host (an unset `mta_enabled`
counts as `true`, the default of the mta role). The other role checks
`postfix_enabled` the same way.

1. Save the current settings: `postconf -n > postconf-before.txt`.
2. Move the variables:

   | `marcstraube.common.mta` | `marcstraube.server.postfix`                   |
   | ------------------------ | ---------------------------------------------- |
   | `mta_enabled`            | `false`; `postfix_enabled: true`               |
   | `mta_service_enabled`    | `postfix_service_enabled`                      |
   | `mta_myhostname`         | `postfix_myhostname`                           |
   | `mta_mydomain`           | `postfix_mydomain`                             |
   | `mta_myorigin`           | `postfix_myorigin` (default now `$myhostname`) |
   | `mta_relayhost`          | `postfix_relayhost` (+ username, password)     |
   | `mta_mynetworks`         | `postfix_mynetworks` (a list now)              |
   | `mta_inet_interfaces`    | `postfix_inet_interfaces` (default now `all`)  |
   | `mta_inet_protocols`     | `postfix_inet_protocols`                       |
   | `mta_extra_parameters`   | `postfix_extra_main_cf`                        |

3. Compare `postconf -n` after the first run with the saved file.

What changes: the listeners move from loopback only (`inet_interfaces =
loopback-only`) to all interfaces on 25, 465 and 587 (open them in the
firewall, see [Firewall](#firewall)), the role owns `main.cf` and `master.cf`
as a whole instead of single parameters, local tables use `lmdb:`, and
`myorigin` defaults to the host name, so `root@<host>` stays local instead of
going to a mail domain of the database. Set `postfix_aliases` for `root`.

### PostfixAdmin

The lookups need the PostfixAdmin schema and a read-only database user;
`postfixadmin_db_readers` of `marcstraube.server.postfixadmin` creates it for
a database on the PostfixAdmin host:

```yaml
postfixadmin_db_readers:
  - name: 'postfix'
    password: '{{ vault_postfix_db_password }}'
    host: '192.0.2.25'   # MariaDB: the address of the Postfix host
```

### Database Privileges

The user needs `SELECT` on `domain`, `mailbox`, `alias` and `alias_domain`.
With these privileges it can read the whole `mailbox` table, including the
password hashes of all mailboxes. Postfix itself only reads `username`,
`maildir`, `domain` and `active`; on PostgreSQL column privileges narrow it
down:

```sql
GRANT SELECT (username, maildir, domain, active) ON mailbox TO postfix;
GRANT SELECT ON domain, alias, alias_domain TO postfix;
```

### Dovecot

The interface is fixed in the mail stack contract (`docs/mail-stack-interfaces.md`
of the infrastructure repository):

| Interface | Dovecot on this host (default)                      | Dovecot on another host                          |
| --------- | --------------------------------------------------- | ------------------------------------------------ |
| LMTP      | `postfix_lmtp_address: 'unix:private/dovecot-lmtp'` | `postfix_lmtp_address: 'inet:<host>:24'`         |
| SASL      | `postfix_sasl_path: 'private/auth'`                 | `postfix_sasl_path: 'inet:<host>:12345'`         |
| quota     | `postfix_policy_services: ['inet:127.0.0.1:12340']` | `postfix_policy_services: ['inet:<host>:12340']` |
| Sieve     | local `sendmail`                                    | Dovecot host address in `postfix_mynetworks`     |

The unix sockets live in the Postfix queue directory and belong to the
dovecot role (`dovecot_postfix_local`). Postfix needs no virtual mail user
and does not know the mail path; everything after LMTP belongs to Dovecot.

### Remote Setups

Dovecot on another host (`dovecot_postfix_local: false` there):

```yaml
postfix_lmtp_address: 'inet:imap.example.com:24'
postfix_sasl_path: 'inet:imap.example.com:12345'
postfix_policy_services:
  - 'inet:imap.example.com:12340'
# Sieve redirects and vacation replies of Dovecot (dovecot_submission_host)
postfix_mynetworks:
  - '127.0.0.0/8'
  - '[::1]/128'
  - '192.0.2.30/32'
```

LMTP, the Dovecot authentication protocol and quota-status have no
encryption: only over a private network or WireGuard. Dovecot 2.4 has no SMTP
authentication for its outgoing Sieve mail, so Postfix trusts its address
instead; `mynetworks` relays on port 25 only.

Database on another host:

```yaml
postfix_db_host: 'db.example.com'
postfix_db_tls: true
postfix_db_tls_ca_file: '/etc/ssl/certs/internal-ca.pem'
```

### DNS Records

The role prints the records the MTA needs and checks each one from the
controller with `community.general.dig`, reported as `PRESENT`, `MISSING` or
`DIFFERENT` with the values found. A missing record never fails the run.

| Record                        | Expected                                                   |
| ----------------------------- | ---------------------------------------------------------- |
| `<domain>. IN MX`             | `postfix_myhostname` for every `postfix_dns_domains` entry |
| `<domain>. IN TXT`            | `postfix_dns_spf` (only `v=spf1` records count)            |
| `<myhostname>. IN A` / `AAAA` | Every address of `postfix_dns_addresses`                   |
| PTR of every address          | `postfix_myhostname` (forward-confirmed reverse DNS)       |

`postfix_dns_addresses` defaults to the default IPv4 and IPv6 address of the
host, which is wrong behind NAT: set the public addresses there. The PTR
record belongs to the owner of the address (provider, hoster). An empty
answer looks the same for a missing record and a resolver that does not
answer; when nothing at all is found the role warns about the resolver. When
the lookup itself fails (no `dnspython`, a resolver name that does not
resolve), the records are listed as unchecked with a warning and the run goes
on. DKIM and DMARC belong to the rspamd role.

### Firewall

The role does not manage firewall rules. Open SMTP (25), submission (587) and
submissions (465) through the `marcstraube.common.firewalld` inventory:

```yaml
firewalld_services:
  - 'smtp'
  - 'smtp-submission'
  - 'smtps'
```

The ports Postfix connects to (database, LMTP 24, SASL 12345, quota-status
12340, milter 11332) are opened on the hosts that offer them.

### SELinux

No port labels or booleans are needed. The Postfix domains of EL 9 and 10
(`postfix_smtpd_t`, `postfix_cleanup_t`, `postfix_smtp_t`, `postfix_master_t`,
which runs `proxymap`) may connect to every port type, including the
unlabeled ports of the milter (11332), quota-status (12340) and Dovecot SASL
(12345), and to the unix sockets of Dovecot, PostgreSQL and MariaDB (checked
with `sesearch` in the targeted policy). The listeners 25, 465 and 587 carry
`smtp_port_t`. Keep certificates where `postfix_smtpd_t` may read them
(`cert_t`, e.g. below `/etc/pki` or `/etc/letsencrypt`).

### Platform Differences

| Platform | Differences the role covers                                                              |
| -------- | ---------------------------------------------------------------------------------------- |
| Debian   | Services chrooted in `/var/spool/postfix` (as shipped); SQL through `proxymap`           |
| EL       | `sendmail` through the `mta` alternatives group; package epoch 2                         |
| EL 9     | Postfix 3.5: level `2`; no `submissions` in `/etc/services`, the role uses port numbers  |
| EL 10    | No `hash:` or `btree:`: `lmdb:` for every table and for the postscreen and verify caches |
| Arch     | Alias file `/etc/postfix/aliases`, programs in `/usr/bin`                                |

On Debian the package starts Postfix during its first install with the
packaged configuration (`Internet Site`, port 25 on every interface). The
role keeps it from starting with a temporary `/usr/sbin/policy-rc.d`,
removed right after the install, and starts it itself with its own
configuration. The file only ever blocks Postfix (`postfix`,
`postfix.service`), never other services; one left behind by an
interrupted first run (it carries the role's marker) is removed on the next
run that includes the install tasks (`postfix` or `postfix:install`, not
`postfix:configure` alone). An existing `policy-rc.d` of the host, or the
one of `marcstraube.server.dovecot` with its own marker, is left as it is.

### Logging

Postfix logs through syslog with the mail facility; the role sets no log
file (`maillog_file`). On every platform the lines are in the journal
(`journalctl SYSLOG_FACILITY=2`, or `journalctl -t postfix/smtpd` and the
other process names). EL installs rsyslog by default, which also writes them
to `/var/log/maillog`; Debian and Arch Linux install no syslog daemon by
default (with rsyslog, Debian writes `/var/log/mail.log`). A successful
submission login, a failed one and a delivery to Dovecot look like this:

<!-- markdownlint-disable MD013 -->
```text
postfix/submission/smtpd[19568]: F35512C30BAE: client=localhost[127.0.0.1], sasl_method=PLAIN, sasl_username=alice@example.com
postfix/submission/smtpd[19568]: warning: localhost[127.0.0.1]: SASL PLAIN authentication failed: (reason unavailable), sasl_username=alice@example.com
postfix/lmtp[17820]: AAC102C0F26C: to=<bob@example.com>, relay=mail.example.com[private/dovecot-lmtp], delay=0.16, delays=0.05/0/0.03/0.08, dsn=2.0.0, status=sent (250 2.0.0 <bob@example.com> GVmqKuiD+mqdRQAAHmWYQg Saved)
```
<!-- markdownlint-enable MD013 -->

Port 465 logs as `postfix/submissions/smtpd`, port 25 as `postfix/smtpd`.

### Removing State

The role removes what it can identify from the current variables: the relay
host password table without a password, the submission header checks
without `postfix_submission_hide_client`, the alias block without
`postfix_aliases` and the PostgreSQL password file with MariaDB. Turning the
role off leaves Postfix installed and configured.

## References

- [Postfix documentation](https://www.postfix.org/documentation.html)
- [Postfix SASL README](https://www.postfix.org/SASL_README.html)
- [Postfix compatibility level](https://www.postfix.org/COMPATIBILITY_README.html)
- [PostfixAdmin](https://github.com/postfixadmin/postfixadmin)
- [Dovecot LMTP](https://doc.dovecot.org/main/core/config/lmtp.html)

## License

MIT

## Author

Marc Straube
