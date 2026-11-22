# marcstraube.server.roundcube

Install Roundcube Webmail as the webmail client of the mail stack.

## Description

[Roundcube](https://roundcube.net/) is the lightweight webmail of the mail
stack, next to SOGo. It logs in to Dovecot over IMAP, sends through the
submission port of Postfix with the credentials of the user, manages
filters, forwarding and out-of-office replies through Dovecot's ManageSieve
and, with the `password` plugin (off by default), changes passwords in the
PostfixAdmin database. The role installs the
release archive from GitHub with one directory per release and a `current`
link, writes `config.inc.php`, creates and upgrades the schema with
Roundcube's own scripts, optionally creates the database and runs the
database cleanup on a timer. Dovecot, Postfix, Valkey and the databases may
run on other hosts.

## Requirements

- ansible-core >= 2.19
- PHP 8.1 or newer with PHP-FPM and the extensions of Roundcube
  ([`marcstraube.common.php`](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/php/README.md),
  see [PHP](#php)): DOM, Intl, Mbstring,
  OpenSSL, PDO with the driver of the database; Argon2 for the default
  password scheme, `redis` (phpredis) for sessions in Valkey. A PHP-FPM pool
  of its own is recommended (see [PHP-FPM Pool](#php-fpm-pool))
- A web server that serves `roundcube_install_dir/current/public_html`
  through PHP-FPM
  ([`marcstraube.server.nginx`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/nginx/README.md)
  or [`marcstraube.server.apache`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/apache/README.md),
  see [Web Server](#web-server))
- A PostgreSQL or MariaDB database, or SQLite; on the same host
  [`marcstraube.server.postgresql`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/postgresql/README.md)
  or [`marcstraube.server.mariadb`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/mariadb/README.md)
  when the role creates the database (`roundcube_db_create`)
- Dovecot with IMAP and ManageSieve
  ([`marcstraube.server.dovecot`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/dovecot/README.md)),
  Postfix with submission
  ([`marcstraube.server.postfix`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/postfix/README.md))
  and, for the password plugin, the PostfixAdmin schema
  ([`marcstraube.server.postfixadmin`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/postfixadmin/README.md))

The role does not manage PHP, the web server or the database server.

### Required Collections

```yaml
collections:
  - ansible.mariadb       # If the role creates a MariaDB database
  - ansible.posix
  - community.general
  - community.postgresql  # If the role creates a PostgreSQL database
```

## Supported Platforms

| Platform                  | Notes                                                              |
| ------------------------- | ------------------------------------------------------------------ |
| Arch Linux                |                                                                    |
| Debian Trixie             |                                                                    |
| EL 9 (Rocky, Alma, RHEL)  | PHP 8.3 module stream (see [PHP](#php)); Valkey sessions need Remi |
| EL 10 (Rocky, Alma, RHEL) |                                                                    |

Other distributions in the same os_family (EndeavourOS, Manjaro, Ubuntu, Mint,
Fedora) should work but are not actively tested. Use distro-specific vars
overrides if needed.

## Role Variables

See [defaults/main.yml](defaults/main.yml) for all available variables.

### Key Variables

| Variable                         | Default                 | Description                                |
| -------------------------------- | ----------------------- | ------------------------------------------ |
| `roundcube_enabled`              | `false`                 | Enable the roundcube role                  |
| `roundcube_version`              | pinned release          | Release pinned in `defaults/main.yml`      |
| `roundcube_install_dir`          | `'/var/www/roundcube'`  | Releases; web root `current/public_html`   |
| `roundcube_db_type`              | `'postgresql'`          | `postgresql`, `mariadb` or `sqlite`        |
| `roundcube_db_password`          | `''`                    | **REQUIRED** (not with SQLite)             |
| `roundcube_des_key`              | `''`                    | **REQUIRED** — session key, 32+ characters |
| `roundcube_imap_host`            | `'localhost'`           | Dovecot (name in its certificate), 993     |
| `roundcube_smtp_host`            | `'localhost'`           | Postfix (name in its certificate), 587     |
| `roundcube_plugins`              | `managesieve`, `acl`, … | Bundled plugins; `password` is off         |
| `roundcube_password_db_password` | `''`                    | **REQUIRED** with the password plugin      |
| `roundcube_session_storage`      | `'db'`                  | `db` or `redis` (Valkey)                   |

Set the mail hosts to the names in the certificates of Dovecot and
Postfix: the role verifies certificate and host name, and a certificate of
a public CA does not name `localhost`. The run warns when a host is
`localhost` while `roundcube_tls_ca_file` is empty (system trust store).

### Version Pinning

`roundcube_version` is a Roundcube release (`1.7.6`) of the stable series
and `roundcube_checksum` the SHA-256 checksum of its complete archive
`roundcubemail-<version>-complete.tar.gz` (with the PHP and JavaScript
dependencies). The distribution packages are spread over three release
series or no longer supported: EPEL on EL 9 ships 1.5 (end of life), EPEL on
EL 10 and Debian 13 ship 1.6 (LTS), Arch Linux ships 1.7. The role installs
the same release from upstream on every platform.

The `update-roundcube-version` workflow checks the latest GitHub release
weekly, verifies the signature of the archive (`.asc` next to it) with the
Roundcube release key (fingerprint
`F3E4 C04B B3DB 5D42 15C4 5F7F 5AB2 BAA1 41C4 F7D5`, published on
roundcube.net) and its checksum against the digest GitHub publishes, and
opens a pull request that bumps both.

`'latest'` installs the newest release and takes the checksum from the
GitHub API; a release without the complete archive fails the run. The
checksum then comes from the same source as the archive and no signature
is checked, so `'latest'` is not for hosts under change control.

The role default moves with the collection, so an update of the collection
can update Roundcube and upgrade its schema on the next run. On hosts under
change control, pin `roundcube_version` and `roundcube_checksum` in the
inventory and change them with the planned update.

**Hosts without internet access.** The role only downloads the archive for
a release that is not unpacked yet, and `get_url` skips the download when the
file in the cache directory already has the expected checksum. Copy
`roundcubemail-<version>-complete.tar.gz` to `/var/cache/roundcube/` before
the run; the role removes it after it unpacked the release (`'latest'`
needs the GitHub API and does not work offline). Alternatively set an HTTP
proxy for the play with `environment` (`https_proxy`).

| Variable                  | Default                 | Description                                   |
| ------------------------- | ----------------------- | --------------------------------------------- |
| `roundcube_version`       | pinned release          | Release, or `latest`                          |
| `roundcube_checksum`      | checksum of the pin     | `sha256:<hash>` of the complete archive       |
| `roundcube_install_dir`   | `'/var/www/roundcube'`  | `releases/<version>` and the `current` link   |
| `roundcube_php_cli`       | `'php'`                 | PHP binary for the schema and the maintenance |
| `roundcube_php_fpm_user`  | `''` (platform default) | PHP-FPM pool user (`temp`, `logs`)            |
| `roundcube_php_fpm_group` | `''` (platform default) | PHP-FPM pool group (`config.inc.php`)         |

### Release Layout

```text
/var/www/roundcube/
├── current -> releases/1.7.6
└── releases/
    ├── 1.7.5/          previous release, kept for a rollback
    └── 1.7.6/
        ├── config/config.inc.php -> /etc/roundcube/config.inc.php
        ├── logs/       writable for the PHP-FPM user
        ├── public_html/  web root
        └── temp/       writable for the PHP-FPM user
```

Every release belongs to `root` and is read-only for PHP-FPM; only `temp`
and `logs` belong to the PHP-FPM user (mode `0750`). `config.inc.php` lives
in `/etc/roundcube` (mode `0640`, group of the PHP-FPM pool) and every
release links to it. Set the PHP-FPM user and group to the ones of a
dedicated pool (see [PHP-FPM Pool](#php-fpm-pool)); empty, they are the
user and group of the platform's `www` pool. The role refuses a `current`
that is not a link into `releases/`.

### Updates

A run whose release differs from the one `current` points to is an update:

1. The role downloads and checks the archive, unpacks it into a staging
   directory and moves it to `releases/<version>` when it is complete.
2. The new release links to `config.inc.php`, so the configuration and the
   plugin settings carry over unchanged.
3. When the new release brings schema updates, the role dumps a database on
   this host (see [Backup](#backup)) and runs `bin/updatedb.sh` of the new
   release. A failed upgrade stops the run while `current` still points to
   the previous release.
4. `current` switches to the new release. The previous release stays in
   `releases/`, every older one is removed.

A database on another host is not dumped: back it up before the run that
updates Roundcube. When the schema is upgraded without a pre-update dump
(database on another host, or `roundcube_backup_enabled: false`), the run
prints a `WARNING` and goes on.

**Rollback.** Set `roundcube_version` and `roundcube_checksum` back to the
previous release. Without a schema change between the two releases the run
only switches `current` back to the kept directory. After a schema upgrade
the role refuses the previous release (Roundcube upgrades forward only) until
the pre-update dump is restored (commands under [Backup](#backup)); then
the run switches back without a download.

**PHP-FPM and the switch.** PHP-FPM caches resolved paths
(`realpath_cache_ttl`, 120 seconds by default) and OPcache keeps compiled
scripts per path. The nginx example below passes the resolved web root
(`$realpath_root`), so every request after the switch runs the new release
at once. With Apache, or a web server that passes the `current` path, reload
the PHP-FPM service after an update; the role does not manage PHP-FPM.

### Schema

Roundcube owns its schema. Every run reads the schema version (the
`roundcube-version` row of the `system` table) with the code of the release
and compares it with the newest update the release ships (`SQL/<driver>/`):

| Database state                    | Action                                                                |
| --------------------------------- | --------------------------------------------------------------------- |
| No tables                         | `bin/initdb.sh --dir=SQL` (SQLite: Roundcube on the first connection) |
| Older schema                      | Pre-update dump, `bin/updatedb.sh --package=roundcube --dir=SQL`      |
| Schema of the release             | Nothing                                                               |
| Newer schema than the release     | Fails (see Rollback)                                                  |
| Tables without the `system` table | Fails: not a Roundcube database                                       |

With `db_prefix` in `roundcube_extra_config` only the tables with that
prefix count.

### Database

| Variable                   | Default                             | Description                                |
| -------------------------- | ----------------------------------- | ------------------------------------------ |
| `roundcube_db_type`        | `'postgresql'`                      | `postgresql`, `mariadb` or `sqlite`        |
| `roundcube_db_host`        | `'localhost'`                       | Host name, address or unix socket path     |
| `roundcube_db_port`        | `5432` / `3306`                     | Port; PostgreSQL also uses it for a socket |
| `roundcube_db_name`        | `'roundcube'`                       | Database                                   |
| `roundcube_db_user`        | `'roundcube'`                       | Database owner                             |
| `roundcube_db_password`    | `''`                                | **REQUIRED** with PostgreSQL and MariaDB   |
| `roundcube_db_tls`         | `false`                             | TLS, certificate and host name verified    |
| `roundcube_db_tls_ca_file` | `''`                                | CA file, required with TLS                 |
| `roundcube_db_path`        | `'/var/lib/roundcube/roundcube.db'` | SQLite file                                |
| `roundcube_db_create`      | `false`                             | Create database and owner on this host     |

The role only needs connection settings, so a database that is not managed
by Ansible works as well; it maps the type to Roundcube's DSN (`pgsql://`,
`mysql://`, `sqlite:///`) and URL-encodes user and password. With MariaDB,
`localhost` connects through the socket of the platform; a path in
`roundcube_db_host` is a socket (PostgreSQL: the socket directory, where
the socket file is named after `roundcube_db_port`; PHP-FPM does not run as
the database user, so `pg_hba.conf` needs a `local` entry with
`scram-sha-256` for it, where the postgresql role defaults to `peer`).

Without `roundcube_db_tls` the connection is unencrypted: the database
password, the address books and the settings of the users go over it in
plain text, so a database server on another host without TLS is only for a
private network or WireGuard. A unix socket stays on the host and takes no
TLS; the role fails before any change for TLS through a socket. With TLS the
DSN carries `sslmode=verify-full` and `sslrootcert` (PostgreSQL) or `ca` and
`verify_server_cert` (MariaDB).

SQLite suits a small installation on one host: the role creates the file and
its directory for the PHP-FPM user (`0640`, `0750`). The directory has to be
one of its own (the default `/var/lib/roundcube`): the role refuses, before
any change, a system directory (`/var/lib`, `/var`, `/srv`, …), a path of
the role itself or below one (`roundcube_install_dir`, `/etc/roundcube`,
`/var/cache/roundcube`, `/var/log/roundcube`, `/usr/local/lib/roundcube-ansible`,
the backup directory) and an existing directory of another owner, because
it would take over owner, mode and SELinux label. When the pool user
changes (`roundcube_php_fpm_user`), the existing SQLite directory still
belongs to the former one; the run fails and names the fix,
`chown -R <pool user>: <directory>`. `roundcube_backup_dir` follows the same
rules (owner root): the role creates it when it is missing and accepts an
existing one only when it already is root's with mode `0700`; it never
tightens a shared directory. No database role backs up the SQLite file, see
[Backup](#backup).

**Required privileges.** Roundcube creates and changes its tables:

| Database   | Privileges of `roundcube_db_user`                    |
| ---------- | ---------------------------------------------------- |
| PostgreSQL | Owner of the database (creates tables and sequences) |
| MariaDB    | `ALL` on `<db>.*`; the database with `utf8mb4`       |

`roundcube_db_create` creates exactly that (MariaDB: `ALL` on the database
for `localhost` with a socket connection, the loopback address otherwise).
It needs the database server on this host (`roundcube_db_host` a loopback
address or a socket) and its role running before; for a server on another
host create database and user with the role of that host
(`postgresql_users` / `postgresql_databases`, `mariadb_users` /
`mariadb_databases`).

### Mail Servers

| Variable                | Default       | Description                            |
| ----------------------- | ------------- | -------------------------------------- |
| `roundcube_imap_host`   | `'localhost'` | Dovecot, host name of its certificate  |
| `roundcube_imap_port`   | `993`         | IMAP port                              |
| `roundcube_imap_tls`    | `'implicit'`  | `implicit`, `starttls` or `none`       |
| `roundcube_smtp_host`   | `'localhost'` | Postfix submission                     |
| `roundcube_smtp_port`   | `587`         | Submission port (465 with `implicit`)  |
| `roundcube_smtp_tls`    | `'starttls'`  | `implicit`, `starttls` or `none`       |
| `roundcube_tls_ca_file` | `''`          | CA file for IMAP, SMTP and ManageSieve |

Roundcube logs in to IMAP with the address and password of the user and
sends with the same credentials (`smtp_user` `%u`, `smtp_pass` `%p`), which
Postfix checks through Dovecot SASL. Every TLS connection verifies the
certificate and the host name (`verify_peer`, `verify_peer_name`) against
`roundcube_tls_ca_file`, or the system trust store when it is empty, so the
host names have to be the ones in the server certificates. `none` sends the
passwords in plain text and is only accepted for a server on this host
(`localhost`, `127.0.0.1`, `::1`).

### Configuration

| Variable                     | Default               | `config.inc.php` key              |
| ---------------------------- | --------------------- | --------------------------------- |
| `roundcube_des_key`          | `''` (**REQUIRED**)   | `des_key`                         |
| `roundcube_cipher_method`    | `'AES-256-CBC'`       | `cipher_method`                   |
| `roundcube_product_name`     | `'Roundcube Webmail'` | `product_name`                    |
| `roundcube_username_domain`  | `''`                  | `username_domain`                 |
| `roundcube_max_message_size` | `'25M'`               | `max_message_size`                |
| `roundcube_log_driver`       | `'syslog'`            | `log_driver` (`syslog` or `file`) |
| `roundcube_extra_config`     | `{}`                  | any other key                     |

`roundcube_des_key` encrypts the IMAP password in the session; it has no
default (the upstream default is public) and needs at least 32 characters,
the key length of the AES-256 cipher.
Generate it once and keep it in the vault:

```bash
openssl rand -base64 24
```

A new key or cipher logs out every user. The role never prints the key and
writes `config.inc.php` without a diff. Further settings go into
`roundcube_extra_config`; strings, numbers, booleans, lists and mappings
become PHP values:

```yaml
roundcube_extra_config:
  trusted_host_patterns: ['webmail.example.com']
  support_url: 'https://www.example.com/support'
```

`roundcube_extra_config` is written last, so it could override settings
the role validates. Keys the role writes from its own variables are
rejected before any change, with the variable to set instead (`db_dsnw`,
`des_key`, `imap_host`, `smtp_host`, the plugin settings below, every
`redis_*` key, …). Security settings the role writes as constants are
rejected as well: `enable_installer` (always `false`, the installer is not
needed), `password_confirm_current` (always `true`), `smtp_user` /
`smtp_pass` (the credentials of the user), `syslog_id` and `log_dir`.

**Logs.** With `roundcube_log_driver: 'syslog'` (default) Roundcube logs to
the journal with the identifier `roundcube`. With `'file'` it writes to
`/var/log/roundcube` (owned by the PHP-FPM user, `0750`), outside the
releases, so removing an old release keeps the logs; where
`/etc/logrotate.d` exists, the role adds a drop-in that rotates them weekly
(12 weeks). Login traceability: `log_logins: true` in
`roundcube_extra_config` logs every successful and failed login with user
and client address (`userlogins.log` or the journal); these are personal
data, so keep them in line with the retention rules of the site.

Roundcube reads `config.inc.php` on every request, so a change applies
without a reload while OPcache checks the file (`opcache.validate_timestamps`
on, the `marcstraube.common.php` default); with it off, reload PHP-FPM.

`roundcube_max_message_size` limits the attachments of a composed message;
PHP (`upload_max_filesize`, `post_max_size`), the web server
(`client_max_body_size`) and Postfix (`message_size_limit`) need at least
the same limit, with some room for the encoding overhead.

### Sessions

| Variable                      | Default                | Description                              |
| ----------------------------- | ---------------------- | ---------------------------------------- |
| `roundcube_session_storage`   | `'db'`                 | `db` or `redis`                          |
| `roundcube_redis_host`        | `'127.0.0.1:6379'`     | `<host>:<port>` or a unix socket path    |
| `roundcube_redis_user`        | `''`                   | ACL user (`valkey_users`)                |
| `roundcube_redis_password`    | `''`                   | Its password                             |
| `roundcube_redis_database`    | `0`                    | Database number                          |
| `roundcube_redis_prefix`      | `'roundcube:session:'` | Key prefix of the sessions               |
| `roundcube_redis_tls`         | `false`                | TLS with certificate and host name check |
| `roundcube_redis_tls_ca_file` | `''`                   | CA file (`''` = system trust store)      |

Sessions live in the Roundcube database by default. `redis` stores them in
Valkey
([`marcstraube.server.valkey`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/valkey/README.md))
or Redis. Roundcube's own redis
driver authenticates with a password only (the `default` user) and has no
TLS, so the role uses the session handler of the PHP extension `redis`
(phpredis) instead: Roundcube runs with `session_storage` `php`, and
`config.inc.php` points `session.save_handler` and `session.save_path` to
Valkey with the ACL user (`auth[]`), the database, the key prefix and, with
TLS, the certificate check. The sessions expire after Roundcube's
`session_lifetime`.

```yaml
# marcstraube.server.valkey on the Valkey host
valkey_users:
  - name: 'roundcube'
    password: '{{ vault_valkey_roundcube_password }}'
    keys: ['roundcube:*']

# marcstraube.server.roundcube
roundcube_session_storage: 'redis'
roundcube_redis_host: 'valkey.example.com:6380'
roundcube_redis_user: 'roundcube'
roundcube_redis_password: '{{ vault_valkey_roundcube_password }}'
roundcube_redis_tls: true
```

The ACL user needs the default commands of the valkey role (`+@all
-@dangerous`) and the key pattern of `roundcube_redis_prefix`. Without TLS
the session data and the password go over the network in plain text: only
for a private network or WireGuard, or a unix socket on the same host
(`/run/valkey/valkey.sock`, the PHP-FPM user in the socket group).

### Plugins

`roundcube_plugins` enables bundled plugins of the release in loading order
(default `managesieve`, `password`, `acl`, `markasjunk`); a name the release
does not ship fails the run. The role writes the settings of `managesieve`
and `password` from the variables below into `config.inc.php`; settings of
other plugins go into `roundcube_extra_config`. The plugins read their
settings from there, since the release ships only `config.inc.php.dist`
files for them.

**managesieve** — filters, forwarding and out-of-office replies through
Dovecot's ManageSieve service (`dovecot_managesieve_enabled`). The
out-of-office replies need nothing from PostfixAdmin (see its README).

| Variable                         | Default               | `config.inc.php` key       |
| -------------------------------- | --------------------- | -------------------------- |
| `roundcube_managesieve_host`     | `roundcube_imap_host` | `managesieve_host`         |
| `roundcube_managesieve_port`     | `4190`                | port of `managesieve_host` |
| `roundcube_managesieve_tls`      | `'starttls'`          | `tls://` prefix            |
| `roundcube_managesieve_vacation` | `1`                   | `managesieve_vacation`     |
| `roundcube_managesieve_forward`  | `1`                   | `managesieve_forward`      |

`1` adds a section for out-of-office replies and forwarding next to the
filters, `2` hides the filters, `0` leaves only the filters.

**acl** — users share their own folders with other users (IMAP `SETACL`)
and see the shared mailboxes of Dovecot's `shared/` namespace.

**markasjunk** — moves mail into and out of the Junk folder. The spam
training runs in Dovecot (IMAPSieve, `dovecot_rspamd_learn_enabled`), so the
plugin needs no learning driver.

### Password Plugin

The `password` plugin changes the password of the user in the PostfixAdmin
`mailbox` table (`sql` driver), with a connection of its own. It is **off by
default** (a decision for the whole mail stack); add `password` to
`roundcube_plugins` to offer the password change in Roundcube, and only then
the variables below are required:

- A password changed in Roundcube bypasses `postfixadmin_password_validation`
  (letters, digits, special characters): Roundcube only checks
  `roundcube_password_minimum_length`.
- The postfixadmin role resets the password of a mailbox in `managed` mode on
  its next run to the one of the inventory. List mailboxes whose users change
  their own password with `mode: 'initial'`, or do not list them.

| Variable                            | Default                | Description                             |
| ----------------------------------- | ---------------------- | --------------------------------------- |
| `roundcube_password_db_type`        | `'postgresql'`         | `postgresql` or `mariadb`               |
| `roundcube_password_db_host`        | `'localhost'`          | Host, address or socket path            |
| `roundcube_password_db_port`        | `5432` / `3306`        | Port                                    |
| `roundcube_password_db_name`        | `'postfixadmin'`       | PostfixAdmin database                   |
| `roundcube_password_db_user`        | `'roundcube_password'` | User with the grants below              |
| `roundcube_password_db_password`    | `''`                   | **REQUIRED**                            |
| `roundcube_password_db_tls`         | `false`                | TLS as for the Roundcube database       |
| `roundcube_password_db_tls_ca_file` | `''`                   | CA file, required with TLS              |
| `roundcube_password_scheme`         | `'ARGON2ID'`           | `ARGON2ID`, `BLF-CRYPT`, `SHA512-CRYPT` |
| `roundcube_password_query`          | `''` (role query)      | Update query                            |
| `roundcube_password_minimum_length` | `12`                   | Minimum length of a new password        |

The new hash carries the scheme prefix like the ones PostfixAdmin writes
(`{ARGON2ID}$argon2id$v=19$...`), so Dovecot, SOGo and PostfixAdmin read a
password changed in Roundcube. The plugin's own default prefix is empty;
the role sets `password_algorithm_prefix`:

| Scheme         | `password_algorithm` | Stored as                 |
| -------------- | -------------------- | ------------------------- |
| `ARGON2ID`     | `hash-argon2id`      | `{ARGON2ID}$argon2id$...` |
| `BLF-CRYPT`    | `hash-bcrypt`        | `{BLF-CRYPT}$2y$...`      |
| `SHA512-CRYPT` | `sha512-crypt`       | `{SHA512-CRYPT}$6$...`    |

Keep `roundcube_password_scheme` equal to `postfixadmin_password_scheme`.
The user has to confirm the current password. The default query is:

```sql
UPDATE mailbox SET password = %P, modified = NOW() WHERE username = %u
```

`%P` is the new hash, `%u` the login name (the address, with
`roundcube_username_domain` appended where the login has no domain).
Roundcube checks only the minimum length; the rules of
`postfixadmin_password_validation` (letters, digits) do not apply to a
password changed in Roundcube.

**Database user.** The plugin needs `SELECT` on `username` and `UPDATE` on
`password` and `modified` of the `mailbox` table, nothing else. The role
does not create the user: the PostfixAdmin database belongs to the
postfixadmin role. On the PostfixAdmin host:

```sql
-- PostgreSQL (the user, e.g. with postgresql_users, then in the database)
GRANT SELECT (username), UPDATE (password, modified) ON mailbox TO roundcube_password;
-- MariaDB
CREATE USER 'roundcube_password'@'192.0.2.20' IDENTIFIED BY '...';
GRANT SELECT (username), UPDATE (password, modified) ON postfixadmin.mailbox
  TO 'roundcube_password'@'192.0.2.20';
```

### Maintenance

| Variable                            | Default   | Description                            |
| ----------------------------------- | --------- | -------------------------------------- |
| `roundcube_timer_enabled`           | `true`    | Enable and start the maintenance timer |
| `roundcube_maintenance_on_calendar` | `'daily'` | Schedule (systemd `OnCalendar`)        |
| `roundcube_cleandb_days`            | `7`       | Days a deleted record stays            |

`roundcube-maintenance.timer` starts `roundcube-maintenance.service`, which
runs `bin/cleandb.sh <days>` (contacts, groups, identities and responses
marked as deleted) and `bin/gc.sh` (expired sessions in the database,
caches, old files in `temp`) of the active release as the PHP-FPM user,
in a hardened unit: `UMask=0077`, a read-only file system except `temp` and
`logs` of the active release, `/var/log/roundcube` with file logs and the
SQLite directory, `SystemCallFilter=@system-service`, only `AF_UNIX`,
`AF_INET` and `AF_INET6` sockets, no capabilities, namespaces or realtime
scheduling. The units are always deployed; the toggle starts or stops the
timer.

## Tags

| Tag                     | Description                                                      |
| ----------------------- | ---------------------------------------------------------------- |
| `roundcube`             | All Roundcube tasks                                              |
| `roundcube:install`     | PHP checks, release, SELinux, schema, pre-update dump, `current` |
| `roundcube:configure`   | `config.inc.php`, log directory, logrotate drop-in               |
| `roundcube:database`    | Database and owner (`roundcube_db_create`), SQLite file          |
| `roundcube:maintenance` | Maintenance units and timer                                      |

The schema of a release (`initdb.sh` / `updatedb.sh` with the pre-update
dump) and the switch of `current` run together under `roundcube:install`
only: a schema upgrade never runs without the switch to the release it
belongs to, and `roundcube:database` never touches the schema. A release
change under `--tags roundcube:install` needs an existing `config.inc.php`
and database (a first install runs the whole role).

## Example Playbook

```yaml
- hosts: webmail_servers
  become: true
  roles:
    - role: marcstraube.server.postgresql
      vars:
        postgresql_enabled: true

    # The pool user and group exist already (see PHP-FPM Pool)
    - role: marcstraube.common.php
      vars:
        php_versions:
          - version: 'auto'
            extensions: ['pdo_pgsql', 'intl', 'mbstring', 'xml']  # Debian, see PHP
            fpm_pools:
              - name: 'roundcube'
                user: 'roundcube'
                group: 'roundcube'
                listen_owner: 'www-data'
                listen_group: 'www-data'

    - role: marcstraube.server.roundcube
      vars:
        roundcube_enabled: true
        roundcube_php_fpm_user: 'roundcube'
        roundcube_php_fpm_group: 'roundcube'
        roundcube_db_password: '{{ vault_roundcube_db_password }}'
        roundcube_db_create: true
        roundcube_des_key: '{{ vault_roundcube_des_key }}'
        roundcube_imap_host: 'mail.example.com'
        roundcube_smtp_host: 'mail.example.com'
        roundcube_username_domain: 'example.com'
        # The password change in Roundcube (off by default, see Password Plugin)
        roundcube_plugins: ['managesieve', 'password', 'acl', 'markasjunk']
        roundcube_password_db_host: 'mail.example.com'
        roundcube_password_db_password: '{{ vault_roundcube_password_db_password }}'
        roundcube_password_db_tls: true
        roundcube_password_db_tls_ca_file: '/etc/ssl/certs/ca-certificates.crt'

    - role: marcstraube.server.nginx
```

## Testing

```bash
# PostgreSQL on the instance
molecule test -s postgresql

# MariaDB on the instance
molecule test -s mariadb

# Update from the previous release and rollback (Debian)
molecule test -s update

# Database, PostfixAdmin, Dovecot and Valkey in a second container, every
# connection with TLS (both platforms at once)
molecule test -s split
```

The `postgresql` and `mariadb` scenarios share their playbooks
(`molecule/shared`) and run on Arch Linux, Debian 13, Rocky Linux 9 and
Rocky Linux 10. Prepare sets up nginx (the site of
[Web Server](#web-server)), PHP-FPM with a dedicated `roundcube` pool (the
php:8.3 stream on EL 9), the database server, PostfixAdmin with test
mailboxes and the password plugin user with the grants above (the
scenarios enable the `password` plugin), a test
certificate and Dovecot with ManageSieve and shared folders; check runs
(`--check`) on the fresh instance and on the converged one come before and
after converge. In the `mariadb` scenario Roundcube connects over TCP with
TLS (certificate of `127.0.0.1` verified; verify requires TLS for the
user before the logins). Verify checks the release layout and its permissions (only
`temp` and `logs` writable), `config.inc.php`, the schema version, the
workers of the pool, and through nginx: the login page, that `config`,
`temp`, `logs`, `bin` and `SQL` are not served, a rejected wrong password
(HTTP 401), the login of a PostfixAdmin mailbox with `username_domain`, the
folder list from Dovecot, the session in the database, a filter saved
through the `managesieve` plugin (active script in Dovecot), a folder
shared through the `acl` plugin (the ACL in Dovecot and the folder in the
`shared/` namespace of the other user over IMAP), a password change through
the `password` plugin that stores an `{ARGON2ID}` hash, followed by an IMAP
login with the new password (and a refused one with the old), the timer and
a run of the maintenance service as the pool user. The role fails before
any change, with `config.inc.php` unchanged, without `des_key`, with a
`des_key` of 31 characters, a managed key (`des_key`,
`password_confirm_current`) in `roundcube_extra_config`, IMAP without TLS to
another host, the password plugin without a password, database TLS through
a socket, a Valkey host without a port, an SQLite file in a system directory,
in a directory of another owner, in the directory of a former pool user (the
message names the `chown`) or in `/var/log/roundcube`, a backup directory in
a system directory, in `/etc/roundcube`, below `roundcube_install_dir` or in
a shared root directory with mode `0755`, and a plugin the release does not
ship. A check run with the default plugins
needs no settings of the PostfixAdmin database.

The `update` scenario installs the previous release (1.6, the LTS series)
and updates it: the pre-update dump (with the rotation), the schema version
of the new release, `config.inc.php` unchanged, the previous release kept
and older ones removed, an incomplete staging directory removed, and the
login through the new release. A check run before the update reports it
without changing anything. Side effect then rolls back: the role refuses
the previous release while the schema is newer, the dump is restored, and
the role switches back to the kept release without a download or a schema
change; a second run changes nothing. It then switches the database to
SQLite with file logs: the role creates the file and its directory for the
pool user, Roundcube creates the schema in the empty file when the role
reads the schema state as that user, the login works,
`roundcube-backup --label` writes a consistent copy (`VACUUM INTO`, `0600`)
and rotates the manual dumps without touching a pre-update dump, the
maintenance job succeeds with the SQLite directory writable, and the logins
land in `/var/log/roundcube` (`log_logins`) with every file owned by the
pool user.

The `split` scenario runs PostgreSQL, PostfixAdmin, Dovecot and Valkey in a
second container. Roundcube connects to all of them with TLS and
certificate checks against a test CA: the Roundcube database and the
password plugin database (PostgreSQL accepts both users with TLS only),
IMAP, ManageSieve and the sessions in Valkey with an ACL user (no session in
the database). Verify logs in, saves a filter and changes a password that
Dovecot accepts afterwards.

Sending mail is not part of the scenarios (no Postfix); the SMTP settings
are checked in `config.inc.php` only.

## Notes

### PHP

`marcstraube.common.php` installs PHP-FPM and the extensions Roundcube
needs; the extension names differ per platform:

| Platform   | PostgreSQL                             | MariaDB                                |
| ---------- | -------------------------------------- | -------------------------------------- |
| Arch Linux | `pdo_pgsql`, `intl`                    | `pdo_mysql`, `intl`                    |
| Debian     | `pdo_pgsql`, `intl`, `mbstring`, `xml` | `pdo_mysql`, `intl`, `mbstring`, `xml` |
| EL         | `pdo_pgsql`, `intl`, `mbstring`, `xml` | `pdo_mysql`, `intl`, `mbstring`, `xml` |

- SQLite: `pdo_sqlite`. Sessions in Valkey: `redis` (phpredis).
- Upstream requires PCRE, DOM, Session, XML, Intl, JSON, PDO, Mbstring,
  OpenSSL, Filter and Ctype; Debian and EL build most of them in, DOM comes
  with `xml`, Arch Linux builds all of them in except Intl and the PDO
  drivers. Optional: GD or Imagick (thumbnails, QR codes), Zip, Fileinfo,
  Exif, Iconv.
- EL 9: the default PHP 8.0 is too old for Roundcube 1.7, and Argon2
  (`PASSWORD_ARGON2ID`) comes with the php:8.3 module stream only:
  `php_versions: [{version: '8.3', ...}]` (8.2 runs Roundcube, but without
  Argon2), or choose `BLF-CRYPT`. The `redis` extension of EPEL is built for
  the default PHP only; sessions in Valkey on EL 9 need the Remi repository
  (`php_redhat_repo: 'remi'`). EL 10 ships `php-pecl-redis6` in AppStream.
- Roundcube 1.7 supports PHP 8.1 and newer (8.6 since 1.7.6).
- With several PHP versions on a host, set `roundcube_php_cli` to the
  binary of the version PHP-FPM runs Roundcube with (e.g. `php8.4`).

The role checks the PHP version, the extensions, the PDO drivers of both
databases, `PASSWORD_ARGON2ID` for the `ARGON2ID` scheme and `redis` for
Valkey sessions with `roundcube_php_cli` before it changes anything.

### PHP-FPM Pool

Run Roundcube in a PHP-FPM pool of its own. Its workers then run under a
user that alone may write `temp` and `logs` and read `config.inc.php` (the
database passwords and `des_key`); the `www` pool and the pools of other
PHP applications on the host cannot read them:

```yaml
# marcstraube.common.php
php_versions:
  - version: 'auto'
    extensions: ['pdo_pgsql', 'intl', 'mbstring', 'xml']
    fpm_pools:
      - name: 'roundcube'
        user: 'roundcube'
        group: 'roundcube'
        # The web server user connects to the socket (Debian 'www-data',
        # Arch Linux 'http', EL 'nginx' or 'apache')
        listen_owner: 'www-data'
        listen_group: 'www-data'
        admin_values:
          upload_max_filesize: '25M'
          post_max_size: '30M'

# marcstraube.server.roundcube
roundcube_php_fpm_user: 'roundcube'
roundcube_php_fpm_group: 'roundcube'
```

- The pool user and group have to exist before `marcstraube.common.php`
  writes the pool; neither role creates them. Create them as system
  accounts without a login shell, e.g. with
  [`marcstraube.common.users`](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/users/README.md).
- The pool listens on a socket of its own next to the one of the `www`
  pool (`listen` in the entry chooses another path):

  | Platform       | Socket of the `roundcube` pool                     |
  | -------------- | -------------------------------------------------- |
  | Arch Linux     | `/run/php-fpm/php-fpm-roundcube.sock`              |
  | Debian         | `/run/php/php<X.Y>-fpm-roundcube.sock`             |
  | EL (AppStream) | `/run/php-fpm/roundcube.sock`                      |
  | EL (Remi)      | `/var/opt/remi/php<XX>/run/php-fpm/roundcube.sock` |

- The role runs `bin/initdb.sh`, `bin/updatedb.sh`, its schema helper and the
  maintenance timer as the pool user with `roundcube_php_cli` (they need
  only `config.inc.php`, which the pool group reads); the pre-update dump
  runs as root.

Without a dedicated pool (both variables empty) Roundcube runs in the
`www` pool of the platform (Arch Linux `http`, Debian `www-data`, EL
`apache`), shared with every other PHP application served through it.

### Web Server

The web root is `public_html` of the active release,
`roundcube_install_dir/current/public_html`; `config`, `temp`, `logs`, `bin`,
`SQL` and the rest of the release stay outside of it, so the web server
cannot serve them. A `custom` site of `marcstraube.server.nginx` (the `php`
site type passes the `current` path instead of the resolved release, see
[Updates](#updates)):

```yaml
nginx_sites:
  - name: 'roundcube'
    server_names:
      - 'webmail.example.com'
    type: 'custom'
    root: '/var/www/roundcube/current/public_html'
    index: 'index.php'
    # roundcube_max_message_size plus the encoding overhead
    client_max_body_size: '35m'
    ssl:
      enabled: true
      certificate: '/etc/letsencrypt/live/webmail.example.com/fullchain.pem'
      certificate_key: '/etc/letsencrypt/live/webmail.example.com/privkey.pem'
    http_redirect: true
    locations:
      - path: '/'
        config: |
          try_files $uri $uri/ /index.php$is_args$args;
      - path: '= /installer.php'
        config: |
          return 404;
      - path: '~ \.php(/|$)'
        config: |
          fastcgi_split_path_info ^(.+?\.php)(/.*)$;
          try_files $fastcgi_script_name =404;
          set $path_info $fastcgi_path_info;
          # The roundcube pool on Debian 13 (PHP 8.4), see PHP-FPM Pool
          fastcgi_pass unix:/run/php/php8.4-fpm-roundcube.sock;
          fastcgi_index index.php;
          include fastcgi_params;
          # The release behind 'current' at the time of the request
          fastcgi_param SCRIPT_FILENAME $realpath_root$fastcgi_script_name;
          fastcgi_param DOCUMENT_ROOT $realpath_root;
          fastcgi_param PATH_INFO $path_info;
```

`static.php` serves the skins and plugin assets through `PATH_INFO`, hence
the `(/|$)` pattern. The installer stays disabled (`enable_installer`
`false`); the extra location also hides the file.

The same with `marcstraube.server.apache`; a vhost's `php_fpm_socket`
overrides the global handler, so the Roundcube vhost reaches its own pool:

```yaml
apache_php_fpm_enabled: true
apache_vhosts:
  - server_name: 'webmail.example.com'
    redirect_to_https: true
apache_vhosts_ssl:
  - server_name: 'webmail.example.com'
    document_root: '/var/www/roundcube/current/public_html'
    # The roundcube pool on EL; Debian 13 (PHP 8.4):
    # unix:/run/php/php8.4-fpm-roundcube.sock, Arch Linux:
    # unix:/run/php-fpm/php-fpm-roundcube.sock (see PHP-FPM Pool)
    php_fpm_socket: 'unix:/run/php-fpm/roundcube.sock'
    certificate_file: '/etc/letsencrypt/live/webmail.example.com/fullchain.pem'
    certificate_key_file: '/etc/letsencrypt/live/webmail.example.com/privkey.pem'
    custom_config: |
      # roundcube_max_message_size plus the encoding overhead
      LimitRequestBody 36700160
      <Files "installer.php">
          Require all denied
      </Files>
```

`public_html/.htaccess` of the release sets caching and security headers
when the vhost allows overrides. Apache passes the `current` path to
PHP-FPM; reload PHP-FPM after an update (see [Updates](#updates)).

### SELinux

On EL with SELinux the role labels the releases for PHP-FPM
(`httpd_sys_content_t`; `temp`, `logs` and an SQLite directory
`httpd_sys_rw_content_t`), `/var/log/roundcube` with file logs
(`httpd_log_t`, PHP-FPM appends to the logs) and turns on the booleans of its connections:
`httpd_can_sendmail` (IMAP and SMTP ports), `httpd_can_network_connect_db`
for a database over TCP, and `httpd_can_network_connect` for ManageSieve
(port 4190 has no boolean of its own) and Valkey over TCP. The booleans
apply to the whole `httpd_t` domain, which the web server and every PHP-FPM
pool share.

### Backup

The database holds the users, their identities, address books and settings;
it has to be part of the database backups (`postgresql_backup_enabled` /
`mariadb_backup_enabled`, or the backup of an external server). The releases
are reinstalled by the role and `config.inc.php` comes from the inventory;
neither needs a backup.

**SQLite.** No database role backs up the SQLite file, and a copy of the
live file during a write can be inconsistent. Run the backup script before
the host backup (e.g. from its pre-hook) and back up the dump:
`/usr/local/bin/roundcube-backup --label <label>` writes a consistent copy
(`VACUUM INTO`) to `roundcube_backup_dir`, named
`roundcube-manual-<label>-<timestamp>.db.gz`. Manual dumps rotate on their
own (the newest `roundcube_backup_update_keep`), apart from the pre-update
dumps, so a nightly run never removes the dump of an update. The script
exists only with `roundcube_backup_enabled: true` (the default).

| Variable                       | Default                    | Description                         |
| ------------------------------ | -------------------------- | ----------------------------------- |
| `roundcube_backup_enabled`     | `true`                     | Dump the database before an upgrade |
| `roundcube_backup_dir`         | `'/var/backups/roundcube'` | Directory of the dumps (0700)       |
| `roundcube_backup_update_keep` | `3`                        | Dumps to keep                       |

Before a schema upgrade the role runs `/usr/local/bin/roundcube-backup`
when the database is on this host (`roundcube_db_host` a loopback address
or a unix socket, or SQLite): `pg_dump` as the `postgres` user or
`mariadb-dump` as `root` through the socket of the server, or a copy of the
SQLite file (`VACUUM INTO`), written to
`roundcube-<active release>-<timestamp>.sql.gz` (`.db.gz`). A failed dump
stops the update before anything changes. The newest
`roundcube_backup_update_keep` pre-update dumps stay; manual dumps
(`--label`, see above) are counted separately. To go back after an update:

```bash
# PostgreSQL: recreate the database, then load the dump
runuser -u postgres -- dropdb roundcube
runuser -u postgres -- createdb -O roundcube -T template0 -E UTF8 roundcube
gunzip -c /var/backups/roundcube/roundcube-1.7.5-<ts>.sql.gz \
  | runuser -u postgres -- psql -d roundcube
# MariaDB
mariadb -e 'DROP DATABASE roundcube; CREATE DATABASE roundcube CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
gunzip -c /var/backups/roundcube/roundcube-1.7.5-<ts>.sql.gz | mariadb roundcube
# SQLite (stop PHP-FPM first)
gunzip -c /var/backups/roundcube/roundcube-1.7.5-<ts>.db.gz > /var/lib/roundcube/roundcube.db
```

Then run the role with `roundcube_version` and `roundcube_checksum` of the
release in the name of the dump (see [Updates](#updates)). A database on
another host (or a server the `postgres` user or `root` cannot reach
through the socket; set `roundcube_backup_enabled: false` there) has to be
backed up by its operator before the update.

### Removal

`roundcube_enabled: false` skips the role. Removing Roundcube is manual:
the maintenance timer and service in `/etc/systemd/system`,
`roundcube_install_dir`, `/etc/roundcube`, `/usr/local/lib/roundcube-ansible`,
`/usr/local/bin/roundcube-backup`, `/etc/logrotate.d/roundcube`, the file logs
in `/var/log/roundcube`, and the database with its user (the role never
drops data).

### Firewall

The role opens no port. The web server serves Roundcube (HTTPS in the
[`marcstraube.common.firewalld`](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/firewalld/README.md)
inventory of the web server, e.g.
`firewalld_services: ['https']`). Roundcube connects out to IMAP (993),
submission (587), ManageSieve (4190), the databases and Valkey; the hosts of
those services need their ports open for the Roundcube host only.

## References

Related roles:

- [marcstraube.common.php](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/php/README.md)
  — PHP, PHP-FPM and the pool of Roundcube, prerequisite
- [marcstraube.server.nginx](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/nginx/README.md)
  — web server site for Roundcube
- [marcstraube.server.apache](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/apache/README.md)
  — web server vhost for Roundcube, alternative to nginx
- [marcstraube.server.postgresql](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/postgresql/README.md)
  — PostgreSQL database and user for Roundcube
- [marcstraube.server.mariadb](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/mariadb/README.md)
  — MariaDB database and user for Roundcube
- [marcstraube.server.dovecot](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/dovecot/README.md)
  — IMAP and ManageSieve server Roundcube logs in to
- [marcstraube.server.postfix](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/postfix/README.md)
  — submission server Roundcube sends through
- [marcstraube.server.postfixadmin](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/postfixadmin/README.md)
  — mailbox schema the password plugin writes to
- [marcstraube.server.valkey](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/valkey/README.md)
  — session store for Roundcube
- [marcstraube.common.users](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/users/README.md)
  — system user and group of the PHP-FPM pool
- [marcstraube.common.firewalld](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/firewalld/README.md)
  — opens HTTPS on the web server

External:

- [Roundcube](https://roundcube.net/) and its
  [GitHub releases](https://github.com/roundcube/roundcubemail/releases)
- [Installation](https://github.com/roundcube/roundcubemail/blob/master/docs/INSTALL.md)
  and [upgrading](https://github.com/roundcube/roundcubemail/blob/master/docs/UPGRADING.md)
- [Configuration defaults](https://github.com/roundcube/roundcubemail/blob/master/config/defaults.inc.php)
- [Password plugin](https://github.com/roundcube/roundcubemail/tree/master/plugins/password)
- [phpredis session handler](https://github.com/phpredis/phpredis#php-session-handler)

## License

MIT

## Author

Marc Straube
