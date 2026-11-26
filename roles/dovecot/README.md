# marcstraube.server.dovecot

Install and configure Dovecot 2.4 as IMAP server, LMTP delivery agent, SASL
service for Postfix and ManageSieve server.

## Description

[Dovecot](https://www.dovecot.org/) stores the mail of the mailboxes that
PostfixAdmin manages and serves it over IMAP (and POP3). Postfix delivers to
it over LMTP and authenticates SMTP clients through its auth service. The
role installs Dovecot 2.4, creates the virtual mail user, writes one
`dovecot.conf` for all platforms and reads the users from the PostfixAdmin
schema in PostgreSQL or MariaDB. It adds per-mailbox quota with an optional
quota-status service for Postfix, global Sieve scripts (spam into Junk),
spam training through rspamd and shared mailboxes with locked rights.
Postfix, the database, rspamd and the webmail clients may run on other
hosts.

## Requirements

- ansible-core >= 2.19
- The PostfixAdmin schema (`marcstraube.server.postfixadmin`) in PostgreSQL
  or MariaDB and a database user with `SELECT` on the tables `mailbox` and
  `domain` (see [Database](#database))
- A TLS certificate and key, e.g. from `marcstraube.common.pki` or
  `marcstraube.server.certbot`
- Postfix on the same host for the local unix listeners (default), installed
  before the role runs (see [Postfix](#postfix))
- EL: EPEL (`marcstraube.common.package_management`); the Dovecot CE
  packages depend on `libunwind` from EPEL

### Required Collections

```yaml
collections:
  - community.general  # SELinux port labels (EL)
```

## Supported Platforms

| Platform                  | Notes                                                     |
| ------------------------- | --------------------------------------------------------- |
| Arch Linux                | Dovecot 2.4 from the official repository                  |
| Debian Trixie             | Dovecot 2.4.1 from Debian                                 |
| EL 9 (Rocky, Alma, RHEL)  | Dovecot CE 2.4 repository of upstream, set up by the role |
| EL 10 (Rocky, Alma, RHEL) | Dovecot CE 2.4 repository of upstream, set up by the role |

Other distributions in the same os_family (EndeavourOS, Manjaro, Ubuntu, Mint,
Fedora) should work but are not actively tested. Use distro-specific vars
overrides if needed.

Only Dovecot 2.4 is supported; the role asserts the installed release. EL
AppStream ships Dovecot 2.3: on a host with the AppStream package installed
the role fails before any change (before it adds the CE repository) and does
not upgrade it; remove the 2.3 packages and their configuration first.

On EL every host gets the 2.4.x release that the `ce-2.4-latest` repository
serves at the time of its install, so hosts set up at different times run
different releases. To keep a fleet on one release, hold it with `dnf
versionlock` (the install and the version queries of the role honor it), or
move all hosts together with a targeted update and
`dovecot_packages_minimum` (see [Package Updates](#package-updates)).

## Role Variables

See [defaults/main.yml](defaults/main.yml) for all available variables.

### Role Control

| Variable                  | Default | Description                          |
| ------------------------- | ------- | ------------------------------------ |
| `dovecot_enabled`         | `false` | Enable the dovecot role              |
| `dovecot_service_enabled` | `true`  | Enable and start the Dovecot service |

### Package Updates

| Variable                   | Default     | Description                                                       |
| -------------------------- | ----------- | ----------------------------------------------------------------- |
| `dovecot_packages_state`   | `'present'` | `present` installs missing packages only, `latest` updates them   |
| `dovecot_packages_minimum` | `''`        | Lowest acceptable Dovecot version, string or mapping per platform |

A regular run never updates Dovecot. A targeted update, for example for a
security release, is requested on the command line:

```bash
ansible-playbook site.yml --tags dovecot \
  -e dovecot_packages_state=latest \
  -e dovecot_packages_minimum=2.4.5
```

With `latest` the role refreshes the package metadata and updates every
installed Dovecot package in one transaction (on Debian every `dovecot-*`
package, on EL every `dovecot*` package): the protocol and driver packages
pin the exact version of the core package. The role reports the version
change.

`dovecot_packages_minimum` is checked twice. Before the update the role
asks the package manager which version the update would install and fails
without a change when it is older than the minimum, which shows that the
repository does not carry the fix yet. After the update it checks the
installed version again; this check is skipped under `--check`.

The minimum is an upstream version (`2.4.1`, any distribution release of it)
or the full distribution version (`1:2.4.1+dfsg1-6+deb13u7`, `2.4.5-2`).
Versions are compared with the rules of the distribution
(`dpkg --compare-versions`, rpm, `vercmp`); a minimum without an epoch
takes the epoch of the package. For mixed hosts in one run, pass a mapping
per platform; the keys are `<os_family>-<major>` or `<os_family>`, and a
host without a matching key fails before any change:

```yaml
# dovecot-minimum.yml, passed with -e @dovecot-minimum.yml
dovecot_packages_minimum:
  Debian: '1:2.4.1+dfsg1-6+deb13u7'
  RedHat: '2.4.5-2'
  Archlinux: '2.4.5'
```

The packages usually restart Dovecot themselves. When they did not, for
example because of a `policy-rc.d`, the master process still executes the
replaced binary and the role restarts the service, after the new binary
accepted the configuration (`doveconf -n`). When it does not, the run fails
and the running service keeps serving with the old binary.

On Arch Linux `dovecot_packages_state` is ignored: updating single packages
is a partial upgrade there, Dovecot updates with the full system upgrade.
Run the role with `latest` together with the system upgrade (`--tags
system-update,dovecot`) to restart Dovecot after it.

### Repository (EL)

| Variable               | Default  | Description                                     |
| ---------------------- | -------- | ----------------------------------------------- |
| `dovecot_repo_baseurl` | upstream | Address of the Dovecot CE 2.4 repository (EL)   |
| `dovecot_repo_gpgkey`  | upstream | Signing key of the Dovecot CE 2.4 packages (EL) |

```yaml
dovecot_repo_baseurl: 'https://repo.dovecot.org/ce-2.4-latest/rhel/$releasever/RPMS/$basearch'
dovecot_repo_gpgkey: 'https://repo.dovecot.org/DOVECOT-REPO-GPG-2.4'
```

Both apply on EL only; Debian and Arch Linux install Dovecot from the
distribution. For hosts without internet access, point them at an internal
mirror of the repository (Satellite, Pulp), as `https://` or `file://` URL;
keep `$releasever` and `$basearch` literal, dnf expands them. dnf imports the
key from `dovecot_repo_gpgkey` on first use and trusts every package it
signs, so the key is the trust anchor: point it at the upstream key or the
mirror's own signing key from a source you control, for example a `file://`
path your configuration management places.

### Versions

| Variable                  | Default   | Description                                    |
| ------------------------- | --------- | ---------------------------------------------- |
| `dovecot_config_version`  | `'2.4.0'` | `dovecot_config_version` of `dovecot.conf`     |
| `dovecot_storage_version` | `'2.4.0'` | Oldest release that must read the mail storage |

Dovecot 2.4 interprets the configuration with the defaults of
`dovecot_config_version` and writes the storage formats of
`dovecot_storage_version`. `2.4.0`, the lowest 2.4 release, makes the same
configuration behave alike on Debian 13 (2.4.1) and on the newer releases of
Arch Linux and EL. A version above the installed release is fatal for
Dovecot; the role asserts that neither is.

Raising `dovecot_storage_version` lets Dovecot write formats that an older
release cannot read: a later downgrade below that version (a restored
system snapshot, a move to a host with an older release) then fails to open
the mail. Raise it only when every host that may serve the storage runs at
least that release, and keep `dovecot_config_version` at the version the
configuration was written for (`doveconf -n` lists the changed defaults
when it is raised).

### Mail Storage

| Variable              | Default        | Description                                 |
| --------------------- | -------------- | ------------------------------------------- |
| `dovecot_vmail_user`  | `'vmail'`      | Virtual mail user, created by the role      |
| `dovecot_vmail_group` | `'vmail'`      | Its group                                   |
| `dovecot_vmail_uid`   | `5000`         | Its UID                                     |
| `dovecot_vmail_gid`   | `5000`         | Its GID                                     |
| `dovecot_mail_root`   | `'/var/vmail'` | Root of all mailboxes (owner vmail, `0700`) |

All mailboxes belong to the virtual mail user. The home of a user is
`dovecot_mail_root/<maildir>`, where `<maildir>` is the path PostfixAdmin
stores for the mailbox (`mailbox.maildir`, e.g. `example.com/alice/` with
the PostfixAdmin defaults `postfixadmin_domain_path: true` and
`postfixadmin_domain_in_mailbox: false`); the mail is in `Maildir` below it,
the personal Sieve scripts in `sieve`. Changing the PostfixAdmin layout
later does not move existing mailboxes.

The IMAP processes may only run as the virtual mail user
(`first_valid_uid` = `last_valid_uid` = `dovecot_vmail_uid`).

### Database

| Variable                   | Default          | Description                                  |
| -------------------------- | ---------------- | -------------------------------------------- |
| `dovecot_db_type`          | `'postgresql'`   | `postgresql` or `mariadb`                    |
| `dovecot_db_host`          | `'localhost'`    | Host name, IP address or unix socket         |
| `dovecot_db_port`          | `5432` / `3306`  | Port (PostgreSQL also for its unix socket)   |
| `dovecot_db_name`          | `'postfixadmin'` | Database of PostfixAdmin                     |
| `dovecot_db_user`          | `'dovecot'`      | Database user                                |
| `dovecot_db_password`      | `''`             | **REQUIRED** — password of the database user |
| `dovecot_db_tls`           | `false`          | TLS (certificate verified with PostgreSQL)   |
| `dovecot_db_tls_ca_file`   | `''`             | CA file to verify the server certificate     |
| `dovecot_sql_passdb_query` | `''`             | Replaces the default passdb query            |
| `dovecot_sql_userdb_query` | `''`             | Replaces the default userdb query            |

The role takes connection settings only: the database server may run on
another host and does not have to be managed by Ansible. The password is
written to `/etc/dovecot/dovecot-db-password.conf.ext` (`root:dovecot
0640`), which `dovecot.conf` includes inside the database block; it may
contain any character but a line break.

The database user needs `SELECT` on `mailbox` and `domain`. On the
PostfixAdmin host the postfixadmin role creates it:

```yaml
postfixadmin_db_readers:
  - name: 'dovecot'
    password: '{{ vault_postfixadmin_db_dovecot_password }}'
    tables: ['mailbox', 'domain']
    host: '192.0.2.20'   # MariaDB account host of the Dovecot host
```

The default queries read active mailboxes of active domains that are no
backup MX (`mailbox.active`, `domain.active`, `domain.backupmx`):

- passdb: `user` and `password` (the hash with its `{SCHEME}` prefix)
- userdb: `home` (`dovecot_mail_root/<maildir>`), `uid` and `gid` of the
  virtual mail user and, with `dovecot_quota_enabled`, `quota_storage_size`
  (`mailbox.quota` in bytes; `0` is unlimited). The owner lookup of shared
  mailboxes needs `uid` and `gid` in the userdb reply, so an own userdb
  query has to return them as well.

With `dovecot_db_tls` the connection uses TLS. PostgreSQL verifies the
server certificate against `dovecot_db_tls_ca_file` and the host name
(`sslmode=verify-full`).

**MariaDB: encryption without verification.** Dovecot 2.4 does not verify
the server certificate of MariaDB, a regression against 2.3: in the MySQL
driver of 2.4 (`driver-mysql.c`, 2.4.1 to 2.4.5 and the main branch) the
code that sets `MYSQL_OPT_SSL_VERIFY_SERVER_CERT` references an undeclared
variable, so every build compiles it out (2.3.21 still set it). The role
writes `ssl = yes` and `ssl_client_ca_file` (handed to the client library,
which does not enforce it then), but no `ssl_client_require_valid_cert`,
which would claim a verification that does not happen, and prints a warning
for this combination; in a test on EL 10 (Dovecot CE
2.4.5, MariaDB Connector/C 3.4.4) a wrong CA and a host name the
certificate does not name were accepted. Reach a MariaDB server on another
host only over a private network or WireGuard, or use PostgreSQL.

A unix socket (a path, or `localhost` with MariaDB) takes no TLS; without
TLS a TCP connection is unencrypted and belongs on a private network or
WireGuard. The role prints a warning when `dovecot_db_tls` is off and the
database host is neither a unix socket nor the loopback interface
(`localhost`, `127.0.0.0/8`, `::1`).

### Password Scheme

| Variable                        | Default      | Description                      |
| ------------------------------- | ------------ | -------------------------------- |
| `dovecot_password_scheme`       | `'ARGON2ID'` | Scheme of hashes without prefix  |
| `dovecot_auth_worker_vsz_limit` | `'256M'`     | Memory limit of the auth workers |

PostfixAdmin stores every hash with its prefix
(`{ARGON2ID}$argon2id$v=19$m=65536,t=4,p=1$...`), which Dovecot reads;
`dovecot_password_scheme` only applies to hashes without one. Keep it equal
to `postfixadmin_password_scheme` (`ARGON2ID`, `BLF-CRYPT` or
`SHA512-CRYPT`). One `ARGON2ID` verification with the PHP defaults needs
about 64 MB in the auth worker; the default limit of 256 MB allows it.

### Protocols

| Variable                        | Default   | Description                             |
| ------------------------------- | --------- | --------------------------------------- |
| `dovecot_listen`                | `'*, ::'` | Addresses of IMAP, POP3 and ManageSieve |
| `dovecot_imap_starttls_enabled` | `false`   | IMAP with STARTTLS on 143 besides 993   |
| `dovecot_pop3_enabled`          | `false`   | POP3 with implicit TLS on 995           |
| `dovecot_managesieve_enabled`   | `false`   | ManageSieve on 4190 (STARTTLS)          |

IMAP listens with implicit TLS on 993. Authentication needs TLS
(`auth_allow_cleartext = no`, `ssl = required`): on 143 and 4190 a login
before STARTTLS is refused. Dovecot counts a connection from the host to
itself (loopback, or the same address on both ends) as secured. POP3 and
ManageSieve install their packages when enabled; a disabled protocol is not
started. Enabling POP3 or ManageSieve, or changing `dovecot_db_type`,
installs packages, after which the role restarts Dovecot instead of
reloading it: a reload cannot load the new modules, and the restart
disconnects open sessions. The packaged configuration of the distributions is not used (see
[Configuration File](#configuration-file)), so POP3 or submission never
start without being enabled.

ManageSieve is used by SOGo and the Roundcube `managesieve` plugin for
filters and out-of-office replies.

### Postfix

| Variable                | Default | Description                                         |
| ----------------------- | ------- | --------------------------------------------------- |
| `dovecot_postfix_local` | `true`  | Unix listeners in the Postfix queue directory       |
| `dovecot_lmtp_listen`   | `''`    | LMTP over TCP, `<address>:<port>` (usually port 24) |
| `dovecot_auth_listen`   | `''`    | SASL over TCP, `<address>:<port>` (usually 12345)   |

With Postfix on the same host (`dovecot_postfix_local: true`) the role
renders two unix listeners in the Postfix queue directory:

| Socket in `private/`  | Owner, mode            | Postfix role                                        |
| --------------------- | ---------------------- | --------------------------------------------------- |
| `dovecot-lmtp` (LMTP) | `postfix:postfix 0600` | `postfix_lmtp_address: 'unix:private/dovecot-lmtp'` |
| `auth` (SASL)         | `postfix:postfix 0660` | `postfix_sasl_path: 'private/auth'`                 |

The queue directory and the `postfix` user come from the Postfix package,
so the postfix role runs before the dovecot role. The role fails before any
change when `/var/spool/postfix/private` does not exist. Postfix defers
delivery and SASL until Dovecot has created the sockets in the same run.

With Postfix on another host, set `dovecot_postfix_local: false` and the
TCP listeners: `postfix_lmtp_address: 'inet:<dovecot host>:24'` and
`postfix_sasl_path: 'inet:<dovecot host>:12345'` on the Postfix side.
**LMTP and the auth protocol are not encrypted and not authenticated**:
a TCP listener belongs on a private network or WireGuard address. The role
asserts a specific address; a wildcard (`*`, `0.0.0.0`, `::`) is refused.
See [Firewall](#firewall) for the ports.

### Sieve Outgoing Mail

| Variable                  | Default      | Description                              |
| ------------------------- | ------------ | ---------------------------------------- |
| `dovecot_submission_host` | `''`         | `<host>:25` of a Postfix on another host |
| `dovecot_submission_ssl`  | `'starttls'` | `starttls`, `smtps` or `no`              |

Redirects and vacation replies of Sieve go through the local `sendmail` of
Postfix. With Postfix on another host they go to `dovecot_submission_host`
on port 25. The role sets no client TLS settings for this connection, so
Dovecot's defaults apply: `ssl_client_require_valid_cert = yes` requires a
valid certificate for the host name, and without `ssl_client_ca_file` or
`ssl_client_ca_dir` it is verified against the system trust store (the
OpenSSL default paths).
**`dovecot_submission_ssl: 'no'` sends the redirected mail and the vacation
replies unencrypted**: only towards a Postfix on a private network or
WireGuard address.
Dovecot 2.4 has no SMTP AUTH for this connection, so submission on 587
cannot take it: the Postfix role accepts relaying on port 25 from the
Dovecot host's address (`postfix_mynetworks`), never on submission.
Redirected mail keeps the local recipient as envelope sender
(`sieve_redirect_envelope_from = orig_recipient`), so it passes SPF.

### TLS

| Variable                   | Default     | Description                                    |
| -------------------------- | ----------- | ---------------------------------------------- |
| `dovecot_tls_cert_file`    | `''`        | **REQUIRED** — certificate with the chain, PEM |
| `dovecot_tls_key_file`     | `''`        | **REQUIRED** — private key, PEM                |
| `dovecot_tls_min_protocol` | `'TLSv1.2'` | `TLSv1.2` or `TLSv1.3`                         |

Dovecot sends only the certificates of `ssl_server_cert_file`: the
intermediate certificates have to follow the server certificate in
`dovecot_tls_cert_file` (certbot's `fullchain.pem`). A separate chain file
is not possible (`ssl_server_ca_file` only verifies client certificates; in
a test it did not send the chain). The files are read by the Dovecot master
process as root.

The role checks that the certificate, the key and the CA files it is given
exist and fails before any change when one is missing. Check mode skips this
check. A run limited with `--tags` to other roles skips it and the check of
the Postfix queue directory, and so does `--skip-tags` with a sub-tag of the
role, also when the run still selects the other sub-tags.

The role reloads Dovecot on the handler topic `Reload cert services` of
`marcstraube.common.pki` and `marcstraube.server.certbot`. Renewals by the
certbot timer outside Ansible reload Dovecot once per renewal run through the
post hook of `marcstraube.server.certbot`, which `certbot_dovecot_enabled`
adds Dovecot to.

### Mailboxes

`dovecot_mailboxes` lists the folders of every user with their special-use
flag (default: Drafts, Sent, Junk, Trash and Archive, created and subscribed
at the first login):

```yaml
dovecot_mailboxes:
  - name: 'Drafts'
    special_use: '\Drafts'
    auto: 'subscribe'    # 'subscribe', 'create' or 'no'
```

### Quota

| Variable                      | Default | Description                                          |
| ----------------------------- | ------- | ---------------------------------------------------- |
| `dovecot_quota_enabled`       | `true`  | Quota per mailbox from `mailbox.quota`               |
| `dovecot_quota_status_listen` | `''`    | quota-status for Postfix, `<address>:<port>` (12340) |

The quota of a mailbox comes from PostfixAdmin (`mailbox.quota`, bytes;
`0` is unlimited). LMTP refuses a recipient whose mailbox is full at RCPT
(`lmtp_rcpt_check_quota`). Dovecot accepts a last message above the limit
up to `quota_storage_grace` (default 10M).

The quota-status service lets Postfix reject mail for a full mailbox at SMTP
time: add `inet:<dovecot host>:12340` to `postfix_policy_services`. It
answers `DUNNO` for unknown recipients (aliases are checked before their
expansion) and for mailboxes below their quota, so the next restriction
decides, and `552 5.2.2` for a full mailbox or a message above the quota.
**The policy protocol is not encrypted**; a private network or WireGuard
address only, never a wildcard.

### Sieve

| Variable               | Default        | Description                             |
| ---------------------- | -------------- | --------------------------------------- |
| `dovecot_sieve_before` | spam into Junk | Global scripts before the user's script |
| `dovecot_sieve_after`  | `[]`           | Global scripts after the user's script  |

Each entry has a `name` and the script `content`; the scripts run in list
order. The role writes them to `/etc/dovecot/sieve/before.d` and
`after.d` and compiles them with `sievec` (the mail user cannot write the
binaries there); a script removed from the list is deleted. The default
script files mail that rspamd marked as spam (`X-Spam: Yes`) into Junk and
stops, so the personal script (vacation replies included) does not run for
it:

```yaml
dovecot_sieve_before:
  - name: 'spam-to-junk'
    content: |
      require ["fileinto"];
      if header :is "X-Spam" "Yes" {
        fileinto "Junk";
        stop;
      }
```

Users manage their own scripts through ManageSieve (`~/sieve`, active
script `~/.dovecot.sieve`).

### Spam Training

| Variable                             | Default                    | Description                     |
| ------------------------------------ | -------------------------- | ------------------------------- |
| `dovecot_rspamd_learn_enabled`       | `false`                    | Report Junk moves to rspamd     |
| `dovecot_rspamd_controller_url`      | `'http://127.0.0.1:11334'` | URL of the rspamd controller    |
| `dovecot_rspamd_controller_password` | `''`                       | Controller (enable) password    |
| `dovecot_rspamd_controller_ca_file`  | `''`                       | CA for an `https://` controller |

IMAPSieve reports a message copied or moved into the Junk folder (the
mailbox with `\Junk` in `dovecot_mailboxes`) to the rspamd controller as
spam (`/learnspam`) and one moved out of it as ham (`/learnham`), except
into Trash. The report goes over HTTP with `curl` through the Sieve
`extprograms` plugin (`/usr/local/lib/dovecot/sieve-pipe`); `rspamc` is not
needed on this host. The password is stored as a header file
(`/etc/dovecot/rspamd-controller.header`, `root:vmail 0640`) that curl
reads, never on the command line.

A controller on another host requires an `https://` URL (a web server in
front of the controller); the certificate is verified against
`dovecot_rspamd_controller_ca_file` or the system trust store.

### Shared Mailboxes

| Variable                        | Default     | Description                            |
| ------------------------------- | ----------- | -------------------------------------- |
| `dovecot_shared_mailboxes_mode` | `'managed'` | `managed`, `initial` or `disabled`     |
| `dovecot_shared_mailboxes`      | `[]`        | Folders of a mailbox shared with users |

A shared mailbox such as `support@example.com` is a regular PostfixAdmin
mailbox whose folders other users see in their own account under
`shared/<owner>/` (the INBOX as `shared/<owner>`). Dovecot uses the ACL
plugin (`acl_driver = vfile`), a shared namespace (`prefix =
shared/$user/`, listed only when something is shared with the user) and the
shared mailbox map `dovecot_mail_root/shared-mailboxes.db`.

```yaml
dovecot_shared_mailboxes:
  - owner: 'support@example.com'
    user: 'alice@example.com'
    rights: 'lrwstipe'      # ACL letters (RFC 4314), default 'lrws'
    owner_admin: false      # support@ itself loses the admin right
  - owner: 'support@example.com'
    folder: 'Archive'       # default 'INBOX'; created when missing
    user: 'bob@example.com'
    rights: 'lr'
    mode: 'initial'
  - owner: 'support@example.com'
    user: 'carol@example.com'
    state: 'absent'
```

The role applies the entries with `doveadm acl` through the running service:
it reads the current ACL first and writes only what differs; `doveadm acl
set` also fills the shared mailbox map, so the folder is listed for the
user. `managed` entries get exactly the listed rights on every run,
`initial` entries only when the user has no ACL entry yet, `disabled`
entries are skipped, `state: absent` removes the user's entry. ACL entries
that are not listed stay untouched.

Managed shares are locked: the role never grants `a` (admin), so the users
cannot pass the share on or change it. With `owner_admin: false` the owner
entry of the folder becomes `lrwstipekx` (everything but admin), for a
mailbox that only serves as shared mailbox; the role removes this entry
again when no managed entry of the folder sets `owner_admin: false` any
more. Global ACLs in `dovecot.conf` are not used for shares: they do not
fill the shared mailbox map, so the folder would not be listed.

Users share their own folders through IMAP `SETACL` (Roundcube `acl`
plugin, SOGo folder sharing). Sending as the shared address is configured in
the postfix role (`postfix_sender_permissions`), separate from the read
rights.

### AppArmor

| Variable                   | Default | Description                                |
| -------------------------- | ------- | ------------------------------------------ |
| `dovecot_apparmor_enabled` | `true`  | Rules for the Dovecot profiles of AppArmor |

Arch Linux enforces the Dovecot 2.3 profiles of the `apparmor` package,
which do not cover Dovecot 2.4 with this configuration; the role adds the
missing rules (see [AppArmor](#apparmor-1)). `false` removes them.

### Extra Configuration

`dovecot_extra_config` is appended verbatim to `dovecot.conf` (Dovecot 2.4
syntax):

```yaml
dovecot_extra_config: |
  mail_max_userip_connections = 20
  namespace inbox {
    mailbox Trash {
      quota_storage_extra = 100M
    }
  }
```

## Tags

| Tag                 | Description                                                      |
| ------------------- | ---------------------------------------------------------------- |
| `dovecot`           | All Dovecot tasks                                                |
| `dovecot:install`   | Repository (EL), packages, targeted update, version assertion    |
| `dovecot:apparmor`  | AppArmor rules of the Dovecot profiles                           |
| `dovecot:configure` | Mail user, SELinux, Sieve scripts, spam training, `dovecot.conf` |
| `dovecot:service`   | Service state                                                    |
| `dovecot:shared`    | Shared mailbox ACLs                                              |

The AppArmor rules follow the configuration and must be in place before
Dovecot starts, so `dovecot:install`, `dovecot:configure` and
`dovecot:service` run them as well.

## Example Playbook

```yaml
# Postfix, Dovecot and the database on one host
- hosts: mail_servers
  become: true
  roles:
    - role: marcstraube.server.postfix   # creates the queue directory first
    - role: marcstraube.server.dovecot
      vars:
        dovecot_enabled: true
        dovecot_db_password: '{{ vault_dovecot_db_password }}'
        dovecot_tls_cert_file: '/etc/letsencrypt/live/mail.example.com/fullchain.pem'
        dovecot_tls_key_file: '/etc/letsencrypt/live/mail.example.com/privkey.pem'
        dovecot_managesieve_enabled: true
        dovecot_shared_mailboxes:
          - owner: 'support@example.com'
            user: 'alice@example.com'
            rights: 'lrwstipe'
            owner_admin: false
```

### Postfix and Database on Other Hosts

```yaml
- hosts: mail_stores
  become: true
  roles:
    - role: marcstraube.server.dovecot
      vars:
        dovecot_enabled: true
        dovecot_db_host: 'db.example.com'
        dovecot_db_password: '{{ vault_dovecot_db_password }}'
        dovecot_db_tls: true
        dovecot_db_tls_ca_file: '/etc/ssl/certs/internal-ca.pem'
        dovecot_tls_cert_file: '/etc/ssl/certs/mail.example.com.pem'
        dovecot_tls_key_file: '/etc/ssl/private/mail.example.com.key'
        # Postfix on 198.51.100.25 reaches these over WireGuard
        dovecot_postfix_local: false
        dovecot_lmtp_listen: '10.10.0.2:24'
        dovecot_auth_listen: '10.10.0.2:12345'
        dovecot_quota_status_listen: '10.10.0.2:12340'
        dovecot_submission_host: 'mx.example.com:25'
        dovecot_rspamd_learn_enabled: true
        dovecot_rspamd_controller_url: 'https://rspamd.example.com'
        dovecot_rspamd_controller_password: '{{ vault_rspamd_enable_password }}'
```

## Testing

```bash
# PostgreSQL on the instance (one platform at a time)
molecule test -s postgresql -p dovecot-postgresql-debian-trixie

# MariaDB on the instance
molecule test -s mariadb -p dovecot-mariadb-rocky-9

# Database in a second container, LMTP and auth over TCP from it (all
# containers at once)
molecule test -s split
```

The `postgresql` and `mariadb` scenarios share their playbooks
(`molecule/shared`): prepare sets up EPEL (EL), PostgreSQL or MariaDB with
the roles of this collection, PHP and PostfixAdmin
(`marcstraube.server.postfixadmin`) with test mailboxes and the `dovecot`
reader (its password contains `%{`), a test certificate, the `postfix` user
with `/var/spool/postfix/private` (no Postfix), a stand-in for the rspamd
controller and, on Debian, an installed Dovecot started with the packaged
configuration, as on a host where the package was installed before the
role. Check runs precede converge and follow
idempotence. Side effect rolls the Dovecot packages back (Debian: trixie
next to trixie-security; EL and Arch Linux have no older build), checks that
a minimum the repository does not offer and a mapping without a key for the
host fail without a change, and updates with `dovecot_packages_state:
latest` and the full distribution version as minimum.

Verify checks the update (the new build, the service on the new binary,
exactly one start on Debian, where `policy-rc.d` blocks the package
restart), the installed 2.4 release, the listening ports (POP3 off), IMAP
login over TLS with an `{ARGON2ID}` hash written by PostfixAdmin (logged in
the journal with user and remote address), a wrong password (logged
likewise) and an
inactive mailbox refused, LMTP delivery into the Maildir
over the unix socket and TCP, owner, group and mode of the sockets, SASL
through the socket and TCP, quota (LMTP and quota-status), the global
Sieve scripts before and after the personal one, a personal Sieve rule
uploaded over ManageSieve, the subscribed special-use folders, logins
before STARTTLS on 143 and 4190 refused, TLSv1.1 refused by the server
(where the client cannot offer it, as with the crypto policy of EL, the
rendered `ssl_min_protocol` instead), the spam training, the SELinux port
labels, module and mail root label (SELinux enabled only), and the shared
mailboxes: listed for the granted user, `SETACL` refused without admin, the
owner without admin, a folder a user shares himself; a second run with
changed entries (`state: absent` removes a grant, an `initial` entry keeps
its rights, a `disabled` entry applies nothing, dropping `owner_admin:
false` removes the owner entry, the user's own share stays) and a repeat
run without ACL changes. The role fails before any change for a broken
`dovecot_extra_config` (`dovecot.conf` and the running service untouched),
a missing Postfix queue directory, a wildcard TCP listener, a config version
above the installed release and an `http://` URL for an rspamd controller
on another host.

The `split` scenario runs PostgreSQL with TLS only and PostfixAdmin in a
second container that also plays the Postfix host: LMTP, SASL and
quota-status over the TCP listeners, IMAP (login over TLS, refused before
STARTTLS) and POP3 from there; Dovecot verifies the database certificate
(`sslmode=verify-full`), binds the listeners to its own address only and
renders `submission_host`. The Dovecot container has no `policy-rc.d` of
the image, like a Debian host: verify checks that the first install did not
start Dovecot with the packaged configuration (one start, by the role) and
that the role removed its temporary `policy-rc.d`. Side effect leaves the
role's `policy-rc.d` behind on the installed host, as an interrupted first
run does, and runs the role again, which removes it. Runs with a missing TLS
key and without the Postfix queue directory fail with the role tag and with
every sub-tag and pass with an unrelated tag, also on the database container,
which has no Dovecot. A config version above the installed release fails the
runs with `dovecot:configure`, `dovecot:service` and `dovecot:shared`.

In the `mariadb` scenario every platform has AppArmor as far as a container
can (the `apparmor` package, a stand-in for the directory that marks
AppArmor as active, and an `apparmor_parser` that compiles without
loading). On Arch Linux verify checks the rules of converge (master,
config, lmtp with sendmail, imap with the spam training, managesieve; no
others), that the profiles compile with them (with the child profiles
`dovecot-lmtp//sendmail` and `dovecot-imap//rspamd-learn`), one reload per
file, profiles that do not load (new rules that loaded stay, the others go
back to their state before the run, removed rules stay removed) and the
reload of every profile the next run repeats, the toggle off (the whole
role) with a file of the administrator that stays, a file of the
administrator the role needs (the run fails before any change), a host
without AppArmor or without a profile, a disabled profile (no reload), a
profile in force-complain (`-C`), check mode, and the rules that depend on
the variables (mail root, TLS files, database socket and CA files, spam
training off, no global Sieve scripts) with spaces, special characters and
a symlink in the paths. Every step that breaks the instance restores it
also when an assertion fails. Debian (no Dovecot profiles), EL
(a stand-in profile) and the `postgresql` scenario get no rules. AppArmor
does not enforce anything in the containers: whether the rules are
sufficient is not part of the scenarios.

**Manual acceptance check (AppArmor):** on a real Arch Linux host with the
Dovecot profiles in complain mode (`aa-complain`), deliver mail, send a
Sieve redirect and a vacation reply, and move a message into Junk and back
out. The audit log must show no `ALLOWED` or `DENIED` events for the
Dovecot profiles, the child profiles `dovecot-lmtp//sendmail` and
`dovecot-imap//rspamd-learn` included.

**AppArmor on the Molecule host:** containers of rootless podman run
unconfined, so AppArmor profiles of the host attach to the Dovecot binaries
inside them by path. The rules the role writes inside a container do not
reach the profiles of the host: with the Dovecot profiles of the `apparmor`
package enforced on the host, Dovecot 2.4 in the containers is blocked as
on an Arch Linux host without them (see [AppArmor](#apparmor-1)). Put the
profiles into complain mode on the host
before running Molecule, e.g.
`sudo aa-complain /etc/apparmor.d/usr.sbin.dovecot /etc/apparmor.d/usr.lib.dovecot.*`.

## Notes

### Firewall

The role does not manage firewall rules. Open the ports through the
`marcstraube.common.firewalld` inventory; the unencrypted Postfix interfaces
only on a private network or WireGuard zone:

| Port      | Service       | Who connects                         |
| --------- | ------------- | ------------------------------------ |
| 993/tcp   | `imaps`       | Mail clients, SOGo, Roundcube        |
| 143/tcp   | `imap`        | With `dovecot_imap_starttls_enabled` |
| 995/tcp   | `pop3s`       | With `dovecot_pop3_enabled`          |
| 4190/tcp  | `managesieve` | SOGo, Roundcube                      |
| 24/tcp    | `lmtp`        | Postfix on another host (private)    |
| 12345/tcp | —             | Postfix SASL (private)               |
| 12340/tcp | —             | Postfix quota-status (private)       |

```yaml
firewalld_zone_services:
  - zone: public
    services:
      - 'imaps'
      - 'managesieve'
firewalld_zone_ports:
  - zone: internal       # WireGuard / private network
    ports:
      - '24/tcp'
      - '12345/tcp'
      - '12340/tcp'
```

### SELinux

On EL the Dovecot master (`dovecot_t`) may bind ports labeled
`lmtp_port_t`, `mail_port_t`, `pop_port_t`, `sieve_port_t` and `smtp_port_t`
only (24, 110, 143, 993, 995 and 4190 carry such a label). When SELinux is
enabled the role labels the TCP listener ports with
`community.general.seport`: the LMTP port `lmtp_port_t`, the auth and
quota-status ports (12345, 12340 carry no label) `mail_port_t`. Outgoing
connections of `dovecot_t` (submission, rspamd controller) are allowed to
every port, so the rspamd controller port 11334 needs no label on this host.

The auth processes (`dovecot_auth_t`) may connect to `mysqld_port_t`, but
not to `postgresql_port_t` (policy of EL 9 and 10). For a PostgreSQL server
reached over TCP the role loads a policy module `dovecot_ansible`
(`/usr/local/share/selinux/dovecot_ansible.cil`) that allows exactly this
connection, and removes it otherwise. A unix socket is allowed by the
policy.

The mail root is not labeled by the policy: `/var/vmail` and every other
directory below `/var` default to `var_t`, which `dovecot_t` may only
search. The role adds the file context `dovecot_mail_root(/.*)?` →
`mail_spool_t` (`community.general.sefcontext`), on which `dovecot_t` may
create, write and rename, and relabels existing content with `restorecon`
when the rule changed. The shared mailbox map lives below the mail root and
gets the same label.

These rules come from `sesearch` on the EL 9 and 10 policies; the Molecule
containers run with SELinux disabled, so the labels are only checked on a
host with SELinux enabled.

### Configuration File

The role writes `/etc/dovecot/dovecot.conf` in full; the `conf.d` files of
the packages are not included (Debian ships mbox defaults and a self-signed
certificate, the EL packages enable POP3 and submission without their
packages, Arch Linux ships only an example). The rendered file is validated
with `doveconf -n` before it replaces the active one, so a broken setting
never reaches the service. A change reloads Dovecot (`doveadm reload`): new
connections use the new settings. Every change keeps the previous file next
to it (`dovecot.conf.<pid>.<date>@<time>~`), so the first run over a
hand-written `dovecot.conf` does not lose it; remove old copies by hand.

On Debian the package starts Dovecot during its first install with the
packaged configuration (PAM, the system users, every address). The role
keeps it from starting with a temporary `/usr/sbin/policy-rc.d`, removed
right after the install, and starts it itself with its own configuration.
The file only ever blocks Dovecot, never other services; one left behind by
an interrupted first run (it carries the role's marker) is removed on the
next run that includes the install tasks (`dovecot` or `dovecot:install`,
not `dovecot:configure` alone). An existing `policy-rc.d` of the host is
left as it is.

### Logging

Dovecot logs to the journal of the `dovecot` unit (`journalctl -u
dovecot`); the role sets no log file. By default the log has the service
starts and reloads, errors and warnings, one line per successful login and
one per failed login, both with the user name and the remote address
(`auth_verbose` stays off, so the reason of a failure, such as a wrong
password or an unknown user, is not logged):

```text
imap-login: Logged in: user=<alice@example.com>, method=PLAIN, rip=192.0.2.10, lip=192.0.2.1, mpid=4842, TLS, session=<Qj7OI1JgkosKWQAC>
imap-login: Login aborted: Connection closed (auth failed, 1 attempts in 2 secs) (auth_failed): user=<alice@example.com>, method=PLAIN, rip=192.0.2.10
```

Settings such as `auth_verbose = yes` or `log_debug` go into
`dovecot_extra_config`.

### AppArmor

The `apparmor` package of Arch Linux ships profiles for Dovecot 2.3 in
enforce mode (`/etc/apparmor.d/usr.sbin.dovecot`,
`/etc/apparmor.d/usr.lib.dovecot.*`). With Dovecot 2.4 and this
configuration they deny files the processes need: without rules of its own
LMTP cannot read the global Sieve scripts, and every delivery is deferred
(`451 4.2.0 Temporarily unable to access necessary Sieve scripts`). Every
profile includes `/etc/apparmor.d/local/<profile>` if it exists. Where
AppArmor is active and a profile exists, the role writes its rules to these
files and reloads the profiles (`apparmor_parser -r`) before Dovecot starts
or reloads; running processes get the new rules at once. Debian 13 ships the
profiles as extra profiles only (`/usr/share/apparmor/extra-profiles`, not
loaded); EL uses SELinux. Neither gets rules.

Rules per file in `/etc/apparmor.d/local`:

- `usr.sbin.dovecot` and `usr.lib.dovecot.config`: read
  `dovecot_tls_cert_file`, `dovecot_tls_key_file` and the MariaDB
  `dovecot_db_tls_ca_file`; doveconf in the master process and the config
  process read them.
- `usr.lib.dovecot.auth`: read `dovecot_db_tls_ca_file` (with
  `dovecot_db_tls`; libpq reads the PostgreSQL CA here), read and write the
  database socket (`dovecot_db_host` as a path).
- `usr.lib.dovecot.lmtp`: read `/proc/<pid>/stat`; read
  `/etc/dovecot/sieve/before.d` (with `dovecot_sieve_before`) and
  `/etc/dovecot/sieve/after.d` (with `dovecot_sieve_after`); run `sendmail`
  for Sieve redirects and vacation replies (`dovecot_submission_host`
  empty, see below).
- `usr.lib.dovecot.imap`: with `dovecot_rspamd_learn_enabled`, read the
  IMAPSieve scripts and run the spam training programs in a profile of
  their own (see below).
- `usr.lib.dovecot.managesieve` (with `dovecot_managesieve_enabled`): read
  `/proc/<pid>/stat`.
- `usr.lib.dovecot.lmtp`, `imap`, `managesieve` and `pop3` (the last two
  when enabled): read, write and lock `dovecot_mail_root`.

The Dovecot processes switch to the mail user, after which `/proc/<pid>`
belongs to root; the lmtp profile only allows the owner to read `stat`, the
managesieve profile has no rule for it. The rule matches every pid, as the
rules of the packaged imap and pop3 profiles do. The spam training programs
(`/usr/local/lib/dovecot/sieve-pipe/rspamd-learn-*.sh`) run in the child
profile `dovecot-imap//rspamd-learn`: the shell, `curl`, the password
header file, `dovecot_rspamd_controller_ca_file` and the system trust
store, but no mail; imap may stop them with `SIGTERM` or `SIGKILL`. curl
ignores proxy variables (`--noproxy '*'`). `sendmail` runs in the child
profile `dovecot-lmtp//sendmail`, the Postfix part of the sendmail profile
of `usr.lib.dovecot.dovecot-lda`: the Postfix configuration with its map
module definitions (`dynamicmaps.cf.d`), `postdrop` (run in the same
profile), the maildrop queue and the pickup trigger, which AppArmor sees as
a disconnected path (`attach_disconnected`). The
rules for the mail root and the TLS files are always written, also where
the packaged tunables and abstractions already allow the path. A database
over TCP, the TCP listeners and the `dovecot_submission_host` connection
need no rules (the profiles allow TCP).

- The role owns the files it writes; each starts with
  `# Managed by Ansible (marcstraube.server.dovecot)`. It writes those with
  rules in the current configuration and removes its other files. A file
  without that line belongs to you: the role leaves it alone, and fails
  before any change when it needs the file for its rules. Delete such a
  file; the role writes the rules Dovecot needs itself. Only rules that
  belong in every Dovecot profile go into a file in
  `/etc/apparmor.d/abstractions/dovecot-common.d/`, which the
  internet-facing login processes (`imap-login`, `pop3-login`) include as
  well.
- Rules that the configuration no longer needs are removed and reloaded
  before Dovecot gets its new configuration later in the same run, so the
  running service may meet denials until then (e.g. a mail root moved
  away from the old path).
- `apparmor_parser -r` also loads a profile that is not loaded at that
  moment (e.g. one removed with `apparmor_parser -R` but not disabled).
- `dovecot_apparmor_enabled: false` (default `true`) removes its files and
  reloads the profiles; on Arch Linux Dovecot then needs rules of your own.
- When a profile does not load (e.g. a broken file of your own in
  `abstractions/dovecot-common.d`), the run fails and names the profile:
  profiles that loaded keep their new rules, the file of a profile that did
  not load goes back to its state before the run (new rules are removed,
  removed rules stay removed), so the next boot still loads it. A marker
  (`/etc/apparmor.d/local/.dovecot.reload-pending`, which the parser skips),
  set before the first file changes and cleared at the end of the run,
  makes the next run reload every Dovecot profile after a failed or
  interrupted run, also when the rules did not change in between.
- A disabled profile (`/etc/apparmor.d/disable/<profile>`) is not reloaded:
  the role writes or removes its file and reports that the rules apply once
  the profile is enabled. A profile in `/etc/apparmor.d/force-complain` is
  reloaded in complain mode (`apparmor_parser -r -C`).
- The rules name the real paths: the role resolves symlinks (mail root,
  TLS and CA files, socket directory) when it runs. A TLS or CA file that
  is a symlink gets a rule for the configured path and one for its target
  at the time of the run. Certificates of certbot need nothing more: a
  renewal points `/etc/letsencrypt/live` to new files in
  `/etc/letsencrypt/archive`, which the TLS abstractions of the profiles
  allow. A symlink whose target moves elsewhere outside Ansible (another
  ACME client, a hand-made rotation) needs a role run before Dovecot
  reloads the certificate.
- Other paths (e.g. in `dovecot_extra_config`) need rules of your own.

### Removing State

The role never uninstalls packages and never deletes mail. A disabled
feature removes what the role wrote for it (spam training files, Sieve
scripts no longer listed, the SELinux module). To remove Dovecot, stop and
disable the service, remove the packages and delete `dovecot_mail_root`,
`/etc/dovecot`, `/usr/local/lib/dovecot`, the repository file on EL and the
virtual mail user by hand.

## References

- [Dovecot 2.4 Documentation](https://doc.dovecot.org/2.4.1/)
- [Upgrading 2.3 to 2.4](https://doc.dovecot.org/2.4.1/installation/upgrade/2.3-to-2.4.html)
- [SQL Authentication](https://doc.dovecot.org/2.4.1/core/config/auth/databases/sql.html)
- [Shared Mailboxes](https://doc.dovecot.org/2.4.1/core/config/shared_mailboxes.html)
- [Quota Plugin](https://doc.dovecot.org/2.4.1/core/plugins/quota.html)
- [Sieve](https://doc.dovecot.org/2.4.1/core/plugins/sieve.html)
- [Spam Reporting](https://doc.dovecot.org/2.4.1/core/config/spam_reporting.html)
- [Postfix SASL](https://doc.dovecot.org/2.4.1/howto/sasl/postfix.html)
- [Dovecot CE Packages](https://www.dovecot.org/download)

## License

MIT

## Author

Marc Straube
