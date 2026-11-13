# marcstraube.server.postfixadmin

Install PostfixAdmin and manage its schema, database users and mail accounts.

## Description

[PostfixAdmin](https://github.com/postfixadmin/postfixadmin) manages the
domains, mailboxes and aliases of a mail server in PostgreSQL or MariaDB;
Postfix, Dovecot and SOGo read their lookups from its tables. The role
installs the PostfixAdmin release archive from GitHub, writes
`config.local.php`, lets PostfixAdmin create and upgrade its own schema and
can set up admins, domains, mailboxes, aliases and alias domains from role
variables. Optionally it creates the database with its owner, read-only
database users for the mail services and a view for the SOGo user source.

## Requirements

- ansible-core >= 2.19
- PHP with PHP-FPM, the PDO driver of the database, `iconv` and `mbstring`
  (`marcstraube.common.php`, see [PHP](#php)); PHP 8.1 or newer, with
  Argon2 for the default password scheme
- A web server that serves `postfixadmin_install_dir/public` through
  PHP-FPM (`marcstraube.server.nginx` or `marcstraube.server.apache`, see
  [Web Server](#web-server))
- A PostgreSQL or MariaDB database; on the same host
  `marcstraube.server.postgresql` or `marcstraube.server.mariadb` when the
  role creates the database (`postfixadmin_db_create`)

The role does not manage PHP, the web server or the database server.

### Required Collections

```yaml
collections:
  - ansible.mariadb       # If the role creates a MariaDB database or users
  - ansible.posix
  - community.general
  - community.postgresql  # If the role creates a PostgreSQL database or users
```

## Supported Platforms

| Platform                  | Notes                                                        |
| ------------------------- | ------------------------------------------------------------ |
| Arch Linux                |                                                              |
| Debian Trixie             |                                                              |
| EL 9 (Rocky, Alma, RHEL)  | `ARGON2ID` needs the php:8.3 module stream (see [PHP](#php)) |
| EL 10 (Rocky, Alma, RHEL) |                                                              |

Other distributions in the same os_family (EndeavourOS, Manjaro, Ubuntu, Mint,
Fedora) should work but are not actively tested. Use distro-specific vars
overrides if needed.

## Role Variables

See [defaults/main.yml](defaults/main.yml) for all available variables.

### Key Variables

| Variable                           | Default                   | Description                                   |
| ---------------------------------- | ------------------------- | --------------------------------------------- |
| `postfixadmin_enabled`             | `false`                   | Enable the postfixadmin role                  |
| `postfixadmin_version`             | pinned release            | Release pinned in `defaults/main.yml`         |
| `postfixadmin_install_dir`         | `'/var/www/postfixadmin'` | Installed release; web root is `public/`      |
| `postfixadmin_php_cli`             | `'php'`                   | PHP binary of the PHP-FPM version             |
| `postfixadmin_db_type`             | `'postgresql'`            | `postgresql` or `mariadb`                     |
| `postfixadmin_db_password`         | `''`                      | **REQUIRED** — password of the database owner |
| `postfixadmin_db_create`           | `false`                   | Create database and owner on this host        |
| `postfixadmin_password_scheme`     | `'ARGON2ID'`              | `ARGON2ID`, `BLF-CRYPT` or `SHA512-CRYPT`     |
| `postfixadmin_account_mode`        | `'managed'`               | `managed`, `initial` or `disabled`            |
| `postfixadmin_password_validation` | 12 characters, …          | Password rules (see below)                    |
| `postfixadmin_totp`                | `false`                   | Offer TOTP two-factor login                   |
| `postfixadmin_sogo_view_enabled`   | `false`                   | View for the SOGo user source                 |

### Version Pinning

`postfixadmin_version` is a PostfixAdmin release (`4.0.6`, without the
leading `v`) and `postfixadmin_checksum` the SHA-256 checksum of its
archive `postfixadmin-v<version>-php84.tar.gz`, the build for PHP 8.1 and
newer; the distribution packages lag behind the 4.x releases or do not
exist. The `update-postfixadmin-version` workflow checks the latest GitHub
release weekly and opens a pull request that bumps both. PostfixAdmin
publishes no signature; the workflow takes the checksum from the
downloaded archive and compares it with the digest GitHub publishes for the
asset.

`'latest'` installs the newest release on every run and takes the checksum
from the GitHub API; a release without the php84 archive fails the run.

The role default moves with the collection, so an update of the collection
can update PostfixAdmin and upgrade its schema on the next run. On hosts
under change control, pin `postfixadmin_version` and `postfixadmin_checksum`
in the inventory and change them with the planned update (after the
database backup, see [Updates](#updates)).

**Hosts without internet access.** The role only downloads the archive when
the release changes, and `get_url` skips the download when the file in the
cache directory already has the expected checksum. Copy
`postfixadmin-v<version>-php84.tar.gz` to `/var/cache/postfixadmin/` before
the run; the role removes the archive after it installed the release, so
stage it again before every update (`'latest'` needs the GitHub API and does
not work offline). Alternatively set an HTTP proxy for the play with
`environment` (`https_proxy`).

| Variable                     | Default                   | Description                                 |
| ---------------------------- | ------------------------- | ------------------------------------------- |
| `postfixadmin_version`       | pinned release            | Release, or `latest`                        |
| `postfixadmin_checksum`      | checksum of the pin       | `sha256:<hash>` of the archive              |
| `postfixadmin_install_dir`   | `'/var/www/postfixadmin'` | Directory of the release, owned by the role |
| `postfixadmin_php_cli`       | `'php'`                   | PHP binary for schema upgrade and accounts  |
| `postfixadmin_php_fpm_user`  | `''` (platform default)   | PHP-FPM pool user (`templates_c`)           |
| `postfixadmin_php_fpm_group` | `''` (platform default)   | PHP-FPM pool group (`config.local.php`)     |

The release is owned by `root` and read-only for PHP-FPM. Only
`templates_c` (compiled templates) is writable for the PHP-FPM user;
`config.local.php` lives in `/etc/postfixadmin` (mode `0640`, group of the
PHP-FPM pool) and the release links to it. The role refuses an existing
`postfixadmin_install_dir` it did not install (no `.ansible-release`
marker).

### Updates

A run whose release differs from the installed one is an update. The role
downloads and checks the new archive, unpacks it next to the installed
release, moves the new release into `postfixadmin_install_dir` (same path,
so the web server and PHP-FPM keep their paths) and removes the replaced
release. `config.local.php` stays in `/etc/postfixadmin`; `templates_c`
starts empty, PostfixAdmin compiles the templates of the new release again.
The schema upgrade (see [Schema](#schema)) runs in the same play.

Before the new release replaces the installed one, the role dumps a
database whose server runs on this host (see [Backup](#backup)). A database
on another host is not dumped: back it up before the run that updates
PostfixAdmin. When the release changes without a pre-update dump (database
on another host, or `postfixadmin_backup_enabled: false`), the run prints a
`WARNING` before the schema upgrade and goes on.

An older release than the installed one is refused: PostfixAdmin upgrades
its schema forward only, and the `.ansible-release` marker in
`postfixadmin_install_dir` still names the newer release. To roll back:

1. Restore the database dump taken before the update (commands under
   [Backup](#backup); for a remote database, the operator's backup).
2. Remove `postfixadmin_install_dir` completely, e.g.
   `rm -rf /var/www/postfixadmin`. `config.local.php` in `/etc/postfixadmin`
   and the dumps stay.
3. Run the role with `postfixadmin_version` and `postfixadmin_checksum` of
   the older release (the release in the name of the dump).

The role then installs the older release like a first install (no dump),
and its schema check finds the restored schema version.

**OPcache.** The new release has the same paths as the replaced one, so
PHP-FPM keeps compiled scripts of the replaced release in OPcache until it
checks the files again. With `opcache.validate_timestamps=1` (the
`marcstraube.common.php` default, `opcache.revalidate_freq` 2 seconds) it
picks up the new files on its own. With `opcache.validate_timestamps=0` it
keeps running the old code until PHP-FPM is reloaded; the role does not
manage PHP-FPM, so reload the PHP-FPM service after an update.

### Schema

PostfixAdmin owns its schema. Every run reads the schema version (the
`version` row of the `config` table) and runs PostfixAdmin's own upgrade
(`public/upgrade.php`, the code `setup.php` runs) when it is lower than the
version the installed release requires (`$min_db_version`): on the first
run it creates the tables in the empty database, after a version change it
applies the new upgrades. Neither `setup.php` nor its password is needed
for this. A release that does not name its schema version fails the run.

### Database

| Variable                      | Default          | Description                                                |
| ----------------------------- | ---------------- | ---------------------------------------------------------- |
| `postfixadmin_db_type`        | `'postgresql'`   | `postgresql` (driver `pgsql`) or `mariadb` (`mysqli`)      |
| `postfixadmin_db_host`        | `'localhost'`    | Host name, address or unix socket path                     |
| `postfixadmin_db_port`        | `5432` / `3306`  | Port; PostgreSQL also uses it for a socket                 |
| `postfixadmin_db_name`        | `'postfixadmin'` | Database                                                   |
| `postfixadmin_db_user`        | `'postfixadmin'` | Database owner                                             |
| `postfixadmin_db_password`    | `''`             | **REQUIRED**                                               |
| `postfixadmin_db_tls`         | `false`          | TLS with verification of certificate and host name         |
| `postfixadmin_db_tls_ca_file` | `''`             | CA file, required with TLS (system bundle for a public CA) |
| `postfixadmin_db_create`      | `false`          | Create database and owner on this host                     |
| `postfixadmin_db_readers`     | `[]`             | Read-only users of the mail services (see below)           |

The role only needs connection settings, so a database that is not managed
by Ansible works as well. With MariaDB, `localhost` connects through the
socket of the platform; a path in `postfixadmin_db_host` is a socket
(PostgreSQL: the socket directory, where the socket file is named after
`postfixadmin_db_port`; PHP-FPM does not run as the database
user, so `pg_hba.conf` needs a `local` entry with `scram-sha-256` for it,
where the postgresql role defaults to `peer`).

Without `postfixadmin_db_tls` the connection is unencrypted: the database
password and the password hashes go over it in plain text, so a database
server on another host without TLS is only for a private network or
WireGuard. A unix socket stays on the host and takes no TLS; the role fails
before any change for TLS through a socket. With PostgreSQL and TLS the role
passes `sslmode=verify-full` and the CA file in the connection string,
since PostfixAdmin has no TLS settings for PostgreSQL; with MariaDB it sets
PostfixAdmin's `database_use_ssl`, `database_ssl_ca` and
`database_ssl_verify_server_cert`.

**Required privileges.** PostfixAdmin creates and changes its tables and
the role creates the SOGo view with the PostfixAdmin user:

| Database   | Privileges of `postfixadmin_db_user`                                     |
| ---------- | ------------------------------------------------------------------------ |
| PostgreSQL | Owner of the database (creates tables, indexes and views in `public`)    |
| MariaDB    | `ALL` on `<db>.*` (`CREATE`, `ALTER`, `DROP`, `INDEX`, `CREATE VIEW`, …) |

`postfixadmin_db_create` creates exactly that: the user with the password
and the database (`UTF8` / `utf8mb4`) owned by it (MariaDB: `ALL` on the
database for `localhost` with a socket connection, the loopback address
otherwise). It needs the database server on this host
(`postfixadmin_db_host` a loopback address or a socket) and its role
running before; for a server on another host create database and user with
the role of that host (`postgresql_users` / `postgresql_databases`,
`mariadb_users` / `mariadb_databases`).

### Read-Only Database Users

`postfixadmin_db_readers` creates users for the mail services that read the
PostfixAdmin tables, each with `SELECT` on its tables only. Same
requirement as `postfixadmin_db_create` (a server on this host); for a
remote server grant the privileges there.

| Key        | Default                                      | Description                                      |
| ---------- | -------------------------------------------- | ------------------------------------------------ |
| `name`     | —                                            | Database user                                    |
| `password` | —                                            | **REQUIRED** unless `state: absent`              |
| `host`     | `'localhost'`                                | MariaDB account host (PostgreSQL: `pg_hba.conf`) |
| `tables`   | `domain`, `mailbox`, `alias`, `alias_domain` | Tables (or the SOGo view) with `SELECT`          |
| `state`    | `present`                                    | `absent` revokes the grants and drops the user   |

```yaml
postfixadmin_db_readers:
  - name: 'postfix'
    password: '{{ vault_postfixadmin_db_postfix_password }}'
  - name: 'dovecot'
    password: '{{ vault_postfixadmin_db_dovecot_password }}'
    tables: ['domain', 'mailbox', 'alias_domain']
  - name: 'sogo'
    password: '{{ vault_postfixadmin_db_sogo_password }}'
    tables: ['sogo_users']
```

On MariaDB the grants of a user are replaced by `tables`, so a table taken
out of the list loses its grant; on PostgreSQL the role only grants, a
removed table keeps its grant until it is revoked by hand. `state: absent`
revokes every privilege of the user on the tables and views of the
PostfixAdmin database before it drops the user. A client on
another host needs a `host` entry (MariaDB) or a `pg_hba.conf` entry and
the address the server listens on.

### Password Scheme

`postfixadmin_password_scheme` sets `$CONF['encrypt']` to a scheme of
PostfixAdmin's own hashing library, which stores the hash with the scheme
prefix (`{ARGON2ID}$argon2id$v=19$...`). Dovecot 2.4, SOGo
(`prependPasswordScheme`) and the Roundcube password plugin
(`password_algorithm_prefix`) read the prefix, so the same hash works in
every component of the mail stack.

| Scheme         | Notes                                                                      |
| -------------- | -------------------------------------------------------------------------- |
| `ARGON2ID`     | Default; needs PHP with Argon2 (`PASSWORD_ARGON2ID`), about 64 MB per hash |
| `BLF-CRYPT`    | bcrypt                                                                     |
| `SHA512-CRYPT` | For components without Argon2 or bcrypt                                    |

Not offered: `php_crypt` (no Argon2, no prefix) and `dovecot:*` (needs
`doveadm` and the Dovecot configuration on the web host). The role checks
`PASSWORD_ARGON2ID` before it changes anything when the scheme is
`ARGON2ID`.

A changed scheme applies to new passwords. In `managed` mode the role
rehashes the password of a listed account whose hash has another scheme
(the password check still matches the old hash).

### Configuration

| Variable                              | Default           | `$CONF` key                        |
| ------------------------------------- | ----------------- | ---------------------------------- |
| `postfixadmin_setup_password_hash`    | `''`              | `setup_password` (empty: no login) |
| `postfixadmin_password_validation`    | 12 characters, …  | `password_validation`              |
| `postfixadmin_totp`                   | `false`           | `totp`                             |
| `postfixadmin_admin_email`            | `''`              | `admin_email`                      |
| `postfixadmin_smtp_server`, `_port`   | `localhost`, `25` | `smtp_server`, `smtp_port`         |
| `postfixadmin_domain_path`            | `true`            | `domain_path`                      |
| `postfixadmin_domain_in_mailbox`      | `false`           | `domain_in_mailbox`                |
| `postfixadmin_quota`                  | `true`            | `quota` (mailbox quota)            |
| `postfixadmin_domain_quota`           | `true`            | `domain_quota`                     |
| `postfixadmin_quota_multiplier`       | `1024000`         | `quota_multiplier`                 |
| `postfixadmin_domain_aliases_limit`   | `0`               | `aliases` (0 unlimited)            |
| `postfixadmin_domain_mailboxes_limit` | `0`               | `mailboxes`                        |
| `postfixadmin_domain_maxquota`        | `0`               | `maxquota` (MB per mailbox)        |
| `postfixadmin_domain_quota_default`   | `0`               | `domain_quota_default` (MB)        |
| `postfixadmin_default_aliases`        | `{}`              | `default_aliases`                  |
| `postfixadmin_vacation_enabled`       | `false`           | `vacation`                         |
| `postfixadmin_vacation_domain`        | `''`              | `vacation_domain`                  |
| `postfixadmin_extra_config`           | `{}`              | any other key                      |

The maildir layout decides the `maildir` column that Dovecot's user query
reads (`example.com/alice/` by default); keep it in line with the Dovecot
configuration. The limits apply to new domains. `postfixadmin_extra_config`
takes any further `$CONF` setting; strings, numbers, booleans, lists and
mappings become PHP values:

```yaml
postfixadmin_extra_config:
  site_url: 'https://postfixadmin.example.com/'
```

`postfixadmin_extra_config` is written last, so it could override settings
the role validates. Keys the role writes from its own variables are
rejected before any change, with the variable to set instead: `configured`,
`setup_password`, `encrypt`, `password_validation`, `totp`, every
`database_*` key and the keys of the table above.

The setup password hash comes from
`php -r 'echo password_hash("<password>", PASSWORD_DEFAULT), "\n";'`.
`setup.php` is only needed to check the environment; the role creates the
schema and the accounts without it.

### Accounts

The role applies admins, domains, mailboxes, aliases and alias domains
from role variables. A helper runs the handler classes of PostfixAdmin that
`postfixadmin-cli` uses (same validation, hashing and side effects such as
the default aliases of a new domain); the request goes through stdin, so
passwords never show up in the process list. Entries are created domains
first and alias domains last, and removed in the reverse order.

| Mode       | Behavior                                                           |
| ---------- | ------------------------------------------------------------------ |
| `managed`  | Create the entry and reconcile the attributes it sets on every run |
| `initial`  | Create the entry when it is missing, then leave it alone           |
| `disabled` | Skip the entry (no password needed)                                |

`postfixadmin_account_mode` sets the default; `mode` on an entry overrides
it. `state: absent` removes an entry (in every mode except `disabled`).

- **Only listed entries are touched.** Accounts created in the web
  interface stay, and they do not flow back into the role variables.
- **Only the listed attributes are reconciled.** An attribute an entry
  does not set gets PostfixAdmin's default on creation and is not changed
  afterwards, so a change in the web interface stays.
- **Passwords** have no default and are required for every admin and
  mailbox that is not absent or disabled; the run fails before any change
  otherwise. `managed` checks the password against the stored hash with
  PostfixAdmin's own hashing code (no `doveadm`) and only writes a new hash
  when it differs, so runs stay idempotent. Passwords must meet
  `postfixadmin_password_validation` (see [Password Rules](#password-rules)).
- **Removing a domain** removes all of its mailboxes, aliases, alias
  domains and admin assignments from the database (PostfixAdmin's own
  domain deletion). The maildirs on the mail host stay, as with every
  removed mailbox.
- The role sends no welcome mail for the mailboxes it creates.
- With `mailbox_postpassword_script` in `postfixadmin_extra_config`,
  PostfixAdmin does not let the password of an existing mailbox change
  (the script is meant to update it outside the database), so the role
  sets mailbox passwords on creation only and does not compare them later.
- A failing entry fails the run with PostfixAdmin's message for it; the
  other entries of the same type that came before it are applied.

| List                         | Key            | Attributes                                         |
| ---------------------------- | -------------- | -------------------------------------------------- |
| `postfixadmin_admins`        | `username`     | `password`, `superadmin`, `domains`, `active`      |
| `postfixadmin_domains`       | `domain`       | `description`, `aliases`, `mailboxes`, `maxquota`, |
|                              |                | `quota`, `backupmx`, `active`, `default_aliases`   |
| `postfixadmin_mailboxes`     | `username`     | `password`, `name`, `quota` (MB), `active`         |
| `postfixadmin_aliases`       | `address`      | `goto` (list), `active`                            |
| `postfixadmin_alias_domains` | `alias_domain` | `target_domain`, `active`                          |

`default_aliases` (create the aliases of `postfixadmin_default_aliases`,
default `true`) only applies when the domain is created.
A mailbox needs `quota` when its domain limits `maxquota` or `quota`. Both
domains of an alias domain have to exist in PostfixAdmin; the target of an
existing alias domain can change to any domain that is not an alias domain
itself (the role leaves out a hint of PostfixAdmin's web form that refuses
the only remaining free domain as a target). A superadmin is
recorded with the pseudo domain `ALL`, which the role adds like `setup.php`
does.

```yaml
postfixadmin_admins:
  - username: 'admin@example.com'
    password: '{{ vault_postfixadmin_admin_password }}'
    superadmin: true
postfixadmin_domains:
  - domain: 'example.com'
    maxquota: 10240
postfixadmin_mailboxes:
  - username: 'alice@example.com'
    password: '{{ vault_postfixadmin_alice_password }}'
    name: 'Alice'
    quota: 2048
    mode: 'initial'   # the user changes the password later
postfixadmin_aliases:
  - address: 'info@example.com'
    goto: ['alice@example.com']
postfixadmin_alias_domains:
  - alias_domain: 'example.org'
    target_domain: 'example.com'
```

### Password Rules

`postfixadmin_password_validation` sets PostfixAdmin's password rules
(`$CONF['password_validation']`): a PCRE pattern per rule and the message
key of the language files PostfixAdmin shows when a password does not match
it, optionally with the value of the message after a space. Upstream
requires 5 characters; the role default requires 12, with upstream's
3 letters and 2 digits:

```yaml
postfixadmin_password_validation:
  '/.{12}/': 'password_too_short 12'
  '/([a-zA-Z].*){3}/': 'password_no_characters 3'
  '/([0-9].*){2}/': 'password_no_digits 2'
```

The rules apply to passwords set in the web interface and to the accounts
of the role. An admin or mailbox password from the inventory (vault) that
does not meet them fails the run when the role creates the account or sets
the password, with PostfixAdmin's message (`Password is too short - requires
12 characters`). To relax the rules, set the whole mapping, e.g. 10
characters without the digit rule; `{}` turns the check off. Further message
keys: `password_no_special` (with a pattern for special characters), see
`config.inc.php` of the release.

### Two-Factor Login (TOTP)

`postfixadmin_totp: true` sets `$CONF['totp'] = 'YES'`: PostfixAdmin then
offers TOTP in the security menu of the web interface. TOTP is per account
and opt-in: after the run, every admin (and mailbox user) who should use it
logs in with the password and adds a TOTP secret in that menu (scan the QR
code with an authenticator app); from then on the login asks for the code.
Accounts without a secret keep logging in with the password only, and the
role does not set secrets. Exceptions (addresses of software that does its
own checking) are managed in the same menu.

### SOGo View

`postfixadmin_sogo_view_enabled` creates the view `postfixadmin_sogo_view_name`
(default `sogo_users`) with the PostfixAdmin user, for the SQL user source
of SOGo:

| Column       | Source                                      |
| ------------ | ------------------------------------------- |
| `c_uid`      | `mailbox.username`                          |
| `c_name`     | `mailbox.username`                          |
| `c_password` | `mailbox.password` (with the scheme prefix) |
| `c_cn`       | `mailbox.name`                              |
| `mail`       | `mailbox.username`                          |
| `domain`     | `mailbox.domain` (for `DomainFieldName`)    |

It lists the active mailboxes of active domains. The SOGo database user
needs `SELECT` on the view (`tables: ['sogo_users']` in
`postfixadmin_db_readers`). Turning the option off drops the view, but only
when it still has exactly these columns.

### Vacation

Out-of-office replies of the mail stack run through Sieve: Dovecot's
ManageSieve service stores the rules that SOGo and the Roundcube
`managesieve` plugin write, and Dovecot's Sieve interpreter sends the
reply. That needs nothing from PostfixAdmin, so `postfixadmin_vacation_enabled`
stays `false`.

PostfixAdmin's own vacation feature is only needed when users set their
replies in the PostfixAdmin user interface and no Sieve is available: it
needs PostfixAdmin's `vacation.pl` on the mail host, a Postfix transport for
`postfixadmin_vacation_domain` and the vacation tables, none of which this
role sets up.

## Tags

| Tag                      | Description                                                             |
| ------------------------ | ----------------------------------------------------------------------- |
| `postfixadmin`           | All PostfixAdmin tasks                                                  |
| `postfixadmin:install`   | PHP checks, release, pre-update dump, SELinux labels and schema upgrade |
| `postfixadmin:database`  | Database, owner and read-only users                                     |
| `postfixadmin:configure` | `config.local.php`                                                      |
| `postfixadmin:schema`    | Schema upgrade and SOGo view                                            |
| `postfixadmin:accounts`  | Admins, domains, mailboxes, aliases and alias domains                   |

`postfixadmin:install` includes the schema upgrade, so a release change
under `--tags postfixadmin:install` leaves the schema of the new release in
place. It needs an existing `config.local.php` (a first install runs the
whole role).

## Example Playbook

```yaml
- hosts: mail_admin_servers
  become: true
  roles:
    - role: marcstraube.server.postgresql
      vars:
        postgresql_enabled: true

    - role: marcstraube.common.php
      vars:
        php_versions:
          - version: 'auto'
            extensions: ['pdo_pgsql', 'mbstring']   # Debian, see PHP

    - role: marcstraube.server.postfixadmin
      vars:
        postfixadmin_enabled: true
        postfixadmin_db_password: '{{ vault_postfixadmin_db_password }}'
        postfixadmin_db_create: true
        postfixadmin_admins:
          - username: 'admin@example.com'
            password: '{{ vault_postfixadmin_admin_password }}'
            superadmin: true

    - role: marcstraube.server.nginx
```

## Testing

```bash
# PostgreSQL on the instance (one platform at a time)
molecule test -s postgresql -p postfixadmin-postgresql-debian-trixie

# MariaDB on the instance
molecule test -s mariadb -p postfixadmin-mariadb-rocky-9

# Update from the previous release
molecule test -s update

# PostgreSQL in a second container, over the network with TLS (both
# platforms at once)
molecule test -s split

# The same with MariaDB
molecule test -s split-mariadb
```

The `postgresql` and `mariadb` scenarios share their playbooks
(`molecule/shared`): prepare installs PHP-FPM with `marcstraube.common.php`
(the php:8.3 stream on EL 9) and the database server with the role of this
collection; converge creates the database, the read-only users, the SOGo
view and accounts in both modes; check runs (`--check`) on the fresh
instance and on the converged one come before and after. Side effect
changes accounts in the database behind the role's back (including a hash
of another scheme, which the role rehashes), applies changed accounts
(admin, domain, mailbox and alias domain updates, a new password, removals,
`disabled` on an existing entry), removes a read-only user and the SOGo
view, restores them and runs the role once more without changes; the
helper's check mode with changed accounts then reports the changes and
leaves the database as it is. Verify checks the release, the file
permissions, the schema version, every account type in both modes, the
stored hashes with the `{ARGON2ID}` prefix, the passwords against them, the
read-only grants, the SOGo view, the password rules and `totp` in
`config.local.php` (on in the `mariadb` scenario, off in `postgresql`), and
that the role fails before any change for a mailbox without password,
managed keys in `postfixadmin_extra_config` (`config.local.php` stays as it
is), `ARGON2ID` on PHP without Argon2 (a stub PHP binary, since every test
platform has Argon2), `postfixadmin_db_create` with a remote server and TLS
through a unix socket, and that an entry PostfixAdmin rejects (a mailbox of
an unknown domain, a password shorter than 12 characters) fails the run
without its password in the output.

The `update` scenario installs the previous release with accounts and
updates it: the database is dumped first (with the rotation), a replaced
release left by an interrupted run does not block the swap, the schema
version rises to the one of the new release, `config.local.php` stays
unchanged, the accounts still log in and an older release is refused. A
check run before the update reports it without changing anything. Side
effect then rolls back as described under [Updates](#updates): it restores
the pre-update dump, removes the installation directory and runs the role
with the previous release, which installs without a dump or a schema
upgrade, matches the restored schema version and keeps the accounts; a
second run changes nothing.

The `split` scenario runs PostgreSQL in a second container that accepts the
PostfixAdmin user with TLS only; `split-mariadb` does the same with MariaDB
(`require_secure_transport`). Verify checks that PostfixAdmin's connection
uses TLS and that a connection without TLS or with a host name the
certificate does not name is refused.

## Notes

### PHP

`marcstraube.common.php` installs PHP-FPM and the extensions PostfixAdmin
needs; the extension names differ per platform:

| Platform   | PostgreSQL                                  | MariaDB                 |
| ---------- | ------------------------------------------- | ----------------------- |
| Arch Linux | `pgsql`, `iconv` (+ `pdo_pgsql`, see below) | `pdo_mysql`, `iconv`    |
| Debian     | `pdo_pgsql`, `mbstring`                     | `pdo_mysql`, `mbstring` |
| EL         | `pgsql`, `mbstring`                         | `pdo_mysql`, `mbstring` |

- EL ships `pdo_pgsql` in `php-pgsql` (`pgsql`) and `pdo_mysql` in
  `php-mysqlnd`; Debian and EL compile `iconv` in, Arch Linux builds
  `mbstring` in.
- Arch Linux: `php-pgsql` carries `pdo_pgsql`, but the php role only loads
  `pgsql`; load the PDO driver as well:
  `php_ini_extra_settings: {extension: 'pdo_pgsql'}`.
- EL 9: the default PHP 8.0 is too old for the release, and Argon2
  (`PASSWORD_ARGON2ID`) comes with the php:8.3 module stream only (the
  php:8.1 and php:8.2 streams lack it):
  `php_versions: [{version: '8.3', ...}]`, or choose `BLF-CRYPT`.
- With several PHP versions on a host, set `postfixadmin_php_cli` to the
  binary of the version PHP-FPM runs PostfixAdmin with (e.g. `php8.4`).
- An Argon2 hash needs about 64 MB of memory (PHP's defaults); the default
  `memory_limit` of 128 MB is enough.

The role checks PHP 8.1, the PDO driver, `iconv`, `mbstring` and, for
`ARGON2ID`, `PASSWORD_ARGON2ID` with `postfixadmin_php_cli` before it changes
anything.

### Web Server

The web root is `postfixadmin_install_dir/public`; everything else of the
release (including the link to `config.local.php`) stays outside of it. A
site of `marcstraube.server.nginx` with access limited to the admin
networks:

```yaml
nginx_sites:
  - name: 'postfixadmin'
    server_names:
      - 'postfixadmin.example.com'
    type: 'php'
    root: '/var/www/postfixadmin/public'
    index: 'index.php'
    php:
      enabled: true
      # Debian 13; EL: unix:/run/php-fpm/www.sock,
      # Arch Linux: unix:/run/php-fpm/php-fpm.sock
      socket: 'unix:/run/php/php8.4-fpm.sock'
    allow_ips:
      - '192.0.2.0/24'
      - '2001:db8::/32'
    ssl:
      enabled: true
      certificate: '/etc/letsencrypt/live/postfixadmin.example.com/fullchain.pem'
      certificate_key: '/etc/letsencrypt/live/postfixadmin.example.com/privkey.pem'
    http_redirect: true
```

For forward authentication (e.g. Authentik) put the PostfixAdmin site
behind the authenticating proxy: `marcstraube.server.nginx` applies its
`authentik` forward auth to `proxy` sites only, so a `proxy` site with
`authentik` in front of an internal `php` site (listening on the loopback
address) does it. `basic_auth` on the `php` site is the simpler option.

On EL with SELinux the role labels the release for PHP-FPM
(`httpd_sys_content_t`, `templates_c` `httpd_sys_rw_content_t`) and turns on
`httpd_can_network_connect_db` for a TCP database connection.

### Backup

The database holds every account; it has to be part of the database
backups (`postgresql_backup_enabled` / `mariadb_backup_enabled`, or the
backup of an external server). The release is reinstalled by the role and
`config.local.php` comes from the inventory; neither needs a backup.

| Variable                          | Default                       | Description                   |
| --------------------------------- | ----------------------------- | ----------------------------- |
| `postfixadmin_backup_enabled`     | `true`                        | Dump the database on update   |
| `postfixadmin_backup_dir`         | `'/var/backups/postfixadmin'` | Directory of the dumps (0700) |
| `postfixadmin_backup_update_keep` | `3`                           | Dumps to keep                 |

Before a version change replaces the release and upgrades the schema, the
role runs `/usr/local/bin/postfixadmin-backup` when the database server runs
on this host (`postfixadmin_db_host` a loopback address or a unix socket):
`pg_dump` as the `postgres` user or `mariadb-dump` as `root`, through the
socket of the server, written to
`postfixadmin-<installed release>-<timestamp>.sql.gz`. A failed dump stops
the update before anything changes. The newest
`postfixadmin_backup_update_keep` dumps stay. To go back after an update:

```bash
# PostgreSQL: recreate the database, then load the dump
runuser -u postgres -- dropdb postfixadmin
runuser -u postgres -- createdb -O postfixadmin -T template0 -E UTF8 postfixadmin
gunzip -c /var/backups/postfixadmin/postfixadmin-4.0.5-<ts>.sql.gz \
  | runuser -u postgres -- psql -d postfixadmin
# MariaDB
mariadb -e 'DROP DATABASE postfixadmin; CREATE DATABASE postfixadmin CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
gunzip -c /var/backups/postfixadmin/postfixadmin-4.0.5-<ts>.sql.gz | mariadb postfixadmin
```

Then remove `postfixadmin_install_dir` completely, e.g.
`rm -rf /var/www/postfixadmin` (otherwise the role refuses the older
release), and run the role with `postfixadmin_version` and
`postfixadmin_checksum` of the release in the name of the dump (see
[Updates](#updates)). A database on another host (or a server the
`postgres` user or `root` cannot reach through the socket, e.g. in a
container; set `postfixadmin_backup_enabled: false` there) has to be backed
up by its operator before the update.

### Firewall

The role opens no port. The web server serves PostfixAdmin (HTTPS in the
`marcstraube.common.firewalld` inventory of the web server); a remote
database server needs its port open for the PostfixAdmin host and the
mail hosts of the read-only users only.

## References

- [PostfixAdmin GitHub](https://github.com/postfixadmin/postfixadmin)
- [Password hashing](https://github.com/postfixadmin/postfixadmin/blob/master/DOCUMENTS/HASHING.md)
- [Upgrading](https://github.com/postfixadmin/postfixadmin/blob/master/DOCUMENTS/UPGRADE.txt)
- [Dovecot 2.4 integration](https://github.com/postfixadmin/postfixadmin/blob/master/DOCUMENTS/DOVECOT-2.4.md)

## License

MIT

## Author

Marc Straube
