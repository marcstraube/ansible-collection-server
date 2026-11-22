# marcstraube.server.sogo

SOGo as the groupware server of the mail stack: webmail, calendars and
address books over CalDAV and CardDAV, optional ActiveSync.

## Description

The role installs SOGo and owns its configuration (`/etc/sogo/sogo.conf`,
one template for all platforms). Users and their passwords come from the
SOGo view of the PostfixAdmin schema
([`marcstraube.server.postfixadmin`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/postfixadmin/README.md)),
mail goes through Dovecot over IMAP
([`marcstraube.server.dovecot`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/dovecot/README.md))
and Postfix submission
([`marcstraube.server.postfix`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/postfix/README.md)),
filters, forwarding and out-of-office replies through Dovecot's
ManageSieve. The databases, Dovecot and Postfix may run on other hosts;
SOGo reaches Dovecot and Postfix with TLS by default, the databases with
`sogo_db_tls`.

- Debian installs the distribution package, Arch Linux builds the AUR
  packages, Rocky Linux runs a local container image with the Debian package
  under the `sogo` user (rootless podman)
- The periodic jobs (session expiry, e-mail alarms, the end of out-of-office
  replies, the optional backup) run as systemd timers
- memcached is installed and enabled when SOGo uses it on the same host
- The web server is not managed by the role: sogod listens on
  `127.0.0.1:20000`, the web server of the host serves the static
  `WebServerResources` and proxies the rest (see [Web Server](#web-server))

## Requirements

- ansible-core >= 2.19
- A PostgreSQL or MariaDB database for SOGo; the role creates it on a local
  server with `sogo_db_create`
  ([`marcstraube.server.postgresql`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/postgresql/README.md)
  or
  [`marcstraube.server.mariadb`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/mariadb/README.md)
  first)
- The PostfixAdmin database with the SOGo view and a database user for it
  (see [PostfixAdmin](#postfixadmin))
- Dovecot with IMAP and ManageSieve (`dovecot_managesieve_enabled: true`) and
  Postfix submission, with certificates the host trusts for the names in
  `sogo_imap_server`, `sogo_smtp_server` and `sogo_sieve_server`
- A web server on the SOGo host
  ([`marcstraube.server.nginx`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/nginx/README.md)
  or
  [`marcstraube.server.apache`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/apache/README.md))
- Arch Linux: the AUR build user of
  [`marcstraube.common.package_management`](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/package_management/README.md)
  (`aur_builder_user`, default `aur_builder`)
- Rocky Linux: podman
  ([`marcstraube.common.podman`](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/podman/README.md))
  before this role

### Required Collections

```yaml
collections:
  - ansible.mariadb
  - community.general
  - community.postgresql
  - kewlfft.aur
```

## Supported Platforms

| Platform                  | Notes                                                                   |
| ------------------------- | ----------------------------------------------------------------------- |
| Arch Linux                | AUR packages `sogo`, `sope`, `libwbxml` (built with `makepkg`)          |
| Debian Trixie             | Distribution package (SOGo 5.12 with Debian security updates)           |
| EL 9 (Rocky, Alma, RHEL)  | Local image on `debian:trixie` with the Debian package, rootless podman |
| EL 10 (Rocky, Alma, RHEL) | As EL 9                                                                 |

Other distributions in the same os_family (EndeavourOS, Manjaro, Ubuntu, Mint,
Fedora) should work but are not actively tested. Use distro-specific vars
overrides if needed.

EL has no SOGo packages: EPEL carries none, the upstream release packages
for EL 9 need a support contract, there are none for EL 10, and upstream
publishes no container image. The role therefore builds an image on
`sogo_container_base_image` with the `sogo` package of Debian
([templates/sogo-image.sh.j2](templates/sogo-image.sh.j2), run in a
container of the base image and committed as `localhost/sogo:latest`), so all
platforms run SOGo 5.12 with the same `sogo.conf`.

## Role Variables

See [defaults/main.yml](defaults/main.yml) for all available variables.

### Role Control

| Variable               | Default | Description                       |
| ---------------------- | ------- | --------------------------------- |
| `sogo_enabled`         | `false` | Enable the sogo role              |
| `sogo_service_enabled` | `true`  | Enable and start the SOGo service |

### Package Updates

| Variable                | Default     | Description                                                     |
| ----------------------- | ----------- | --------------------------------------------------------------- |
| `sogo_packages_state`   | `'present'` | `present` installs missing packages only, `latest` updates them |
| `sogo_packages_minimum` | `''`        | Lowest acceptable SOGo version, string or mapping per platform  |

A regular run never updates SOGo. A targeted update, for example for a
security release, is requested on the command line:

```bash
ansible-playbook site.yml --tags sogo \
  -e sogo_packages_state=latest \
  -e sogo_packages_minimum=5.12.1-3+deb13u3
```

- **Debian:** the role refreshes the package lists and updates every
  installed package of the SOGo family (`sogo`, `sogo-common`,
  `sogo-activesync`, the SOPE libraries) in one transaction. The package
  restarts SOGo itself; when it did not (`policy-rc.d`), sogod still runs
  the replaced binary and the role restarts it.
- **Rocky Linux:** the role rebuilds the image with a freshly pulled base
  image and fresh package lists, so the security updates of the base image
  are current, copies the `WebServerResources` of the new image and restarts
  SOGo with it. Any change of the build script rebuilds the image as well
  (toggling `sogo_activesync_enabled`, a mirror variable, a role update that
  changes the script): such a rebuild installs the current Debian SOGo and
  restarts SOGo, and the run reports the version change. The replaced image
  stays as `localhost/sogo:previous` (exactly one previous image; an older
  one is removed), see [Rollback on Rocky Linux](#rollback-on-rocky-linux).
- **Arch Linux:** `sogo_packages_state` is ignored; SOGo comes from the AUR
  and updates with the system upgrade through the AUR helper, without a
  version lock: a new upstream release, and with it a change of the
  database schema, arrives with the system upgrade. When the release notes
  of SOGo name a database update script, run it from
  `/usr/lib/sogo/scripts/` after the upgrade. Run the role with `latest`
  together with the system upgrade (`--tags system-update,sogo`) to restart
  a sogod whose binary the upgrade replaced.

When an update and a configuration change come in one run, SOGo restarts
twice: once right after the update (so a failing minimum check never leaves
the old binary running) and once for the new configuration at the end.

`sogo_packages_minimum` is checked before the update (the version the
package manager or the build would install; nothing changes when it is
older) and again after it. It is an upstream version (`5.12.1`) or the full
Debian version (`5.12.1-3+deb13u3`, which also proves a backported fix); on
Rocky Linux it is compared with the Debian package in the image. Versions
are compared with `dpkg --compare-versions` (Debian, Rocky Linux in the base
image) or `vercmp` (Arch Linux, against the installed package or the release
of the AUR). A mapping per platform (`<os_family>-<major>` or
`<os_family>`) covers mixed hosts; a host without a key fails before any
change:

```yaml
# sogo-minimum.yml, passed with -e @sogo-minimum.yml
sogo_packages_minimum:
  Debian: '5.12.1-3+deb13u3'
  RedHat: '5.12.1-3+deb13u3'
  Archlinux: '5.12.13'
```

### Installation

| Variable                     | Default                                      | Description                    |
| ---------------------------- | -------------------------------------------- | ------------------------------ |
| `sogo_activesync_enabled`    | `false`                                      | ActiveSync (built in on Arch)  |
| `sogo_container_base_image`  | `'docker.io/library/debian:trixie'`          | Base image (EL)                |
| `sogo_subid_start`           | `231072`                                     | Subordinate IDs of `sogo` (EL) |
| `sogo_subid_count`           | `65536`                                      | Size of the range              |
| `sogo_web_resources_dir`     | `'/usr/local/share/sogo/WebServerResources'` | Copy of the resources (EL)     |
| `sogo_service_start_timeout` | `600`                                        | Wait for sogod after a start   |

| Variable                                | Default | Description                         |
| --------------------------------------- | ------- | ----------------------------------- |
| `sogo_container_debian_mirror`          | `''`    | Debian mirror of the build (EL)     |
| `sogo_container_debian_security_mirror` | `''`    | Debian security mirror of the build |

The base image is a release tag of Debian, not a pinned digest: the image is
rebuilt only when the build script changes or with `sogo_packages_state:
latest`, so it moves only on request. A host without internet access takes
the base image from an internal registry (`sogo_container_base_image`) and
the packages from an internal Debian mirror
(`sogo_container_debian_mirror`, `sogo_container_debian_security_mirror`,
which replace `http://deb.debian.org/debian` and `.../debian-security` in
the APT sources of the base image during the build). A proxy is passed
with `http_proxy` / `https_proxy` in the environment of the play.

`sogo_subid_start` must not overlap with the ranges of other users in
`/etc/subuid` and `/etc/subgid`; the default follows the ranges of the n8n
(100000) and activepieces (165536) roles.

### Network

| Variable              | Default             | Description                                           |
| --------------------- | ------------------- | ----------------------------------------------------- |
| `sogo_bind`           | `'127.0.0.1:20000'` | Address and port of sogod (`WOPort`)                  |
| `sogo_memcached_host` | `'127.0.0.1'`       | memcached (`SOGoMemcachedHost`); installed when local |

memcached listens on the loopback interface only with the defaults of every
platform. On Debian it is a dependency of the `sogo` package and runs even
with a memcached on another host; the role leaves it alone then. memcached
holds the sessions and cached credentials of SOGo and speaks no TLS: a
memcached on another host is only for a private network or WireGuard. The
container of Rocky Linux reaches memcached over TCP only (no socket path).
A loopback address (`127.0.0.1`, `localhost`, `::1`, `[::1]`, with or
without a port) or a socket path counts as memcached on this host: the role
installs and enables it, and a restore restarts it.

### Database

| Variable              | Default         | Description                                        |
| --------------------- | --------------- | -------------------------------------------------- |
| `sogo_db_type`        | `'postgresql'`  | `postgresql` or `mariadb`                          |
| `sogo_db_host`        | `'127.0.0.1'`   | Host name or IP address (TCP)                      |
| `sogo_db_port`        | `5432` / `3306` | Port                                               |
| `sogo_db_name`        | `'sogo'`        | Database                                           |
| `sogo_db_user`        | `'sogo'`        | Owner of the database                              |
| `sogo_db_password`    | `''`            | **REQUIRED**                                       |
| `sogo_db_tls`         | `false`         | TLS with verification of certificate and host name |
| `sogo_db_tls_ca_file` | `''`            | CA file, required with TLS                         |
| `sogo_db_create`      | `false`         | Create database and owner on a server of this host |

SOGo creates its tables itself at the first start: the user profiles,
the folder list, sessions, e-mail alarms, the admin table and the combined
store, ACL and cache tables (`OCSStoreURL`, `OCSAclURL`, `OCSCacheFolderURL`),
so the user needs to own the database (PostgreSQL) or `ALL` on it (MariaDB).
`sogo_db_create` creates exactly that. SOGo puts the passwords into database
URLs: letters, digits and `- . _ ~ ! $ & ' ( ) * + , ; =` only; the role
rejects other characters before any change.

SOGo connects over TCP on every platform; the container of Rocky Linux
cannot reach the socket of a local server, so `127.0.0.1` is the default
(with MariaDB the account host is `127.0.0.1` then, not `localhost`).

`sogo_db_tls` applies to every database connection of SOGo, the PostfixAdmin
database included. PostgreSQL: SOGo has no TLS setting, the role sets
`PGSSLMODE=verify-full` and `PGSSLROOTCERT` for libpq in a drop-in of the
unit (`/etc/systemd/system/sogo.service.d/ansible.conf`), in the units of the
jobs and, on Rocky Linux, in the container (with a copy of the CA file in
`/etc/sogo`). MariaDB: `MySQL4SSLEnabled` and `MySQL4SSLCaPath` in
`sogo.conf`; the MariaDB client library verifies the host name as well.
Without TLS the passwords and the password hashes of the users cross the
network in cleartext: a database on another host without TLS is only for a
private network or WireGuard, and the role prints a warning for it.

### Users

| Variable                           | Default          | Description                                         |
| ---------------------------------- | ---------------- | --------------------------------------------------- |
| `sogo_postfixadmin_db_host`        | `sogo_db_host`   | PostfixAdmin database server                        |
| `sogo_postfixadmin_db_port`        | `sogo_db_port`   | Port                                                |
| `sogo_postfixadmin_db_name`        | `'postfixadmin'` | PostfixAdmin database                               |
| `sogo_postfixadmin_db_user`        | `'sogo_view'`    | User of the view (see below)                        |
| `sogo_postfixadmin_db_password`    | `''`             | **REQUIRED** (unless `sogo_user_sources` is set)    |
| `sogo_postfixadmin_view`           | `'sogo_users'`   | `postfixadmin_sogo_view_name`                       |
| `sogo_password_scheme`             | `'ARGON2ID'`     | `ARGON2ID`, `BLF-CRYPT` or `SHA512-CRYPT`           |
| `sogo_password_change_enabled`     | `false`          | Users may change their password in SOGo             |
| `sogo_failed_login_count`          | `10`             | Failed logins that block an account (0: off)        |
| `sogo_failed_login_interval`       | `300`            | Lock lasts at most this long after the last failure |
| `sogo_failed_login_block_interval` | `300`            | Counting window from the first failure, lock limit  |
| `sogo_user_sources`                | `[]`             | SOGo sources replacing the PostfixAdmin view        |

The default user source is an SQL source on the view (`canAuthenticate`,
`isAddressBook`) with `userPasswordAlgorithm` set to `sogo_password_scheme`
and `prependPasswordScheme = YES`: SOGo reads the scheme prefix PostfixAdmin
stores with every hash (`{ARGON2ID}$argon2id$...`) and writes a changed
password in the same format, which Dovecot and PostfixAdmin read. Use the
scheme of `postfixadmin_password_scheme`. The Debian package, the image of
Rocky Linux and the AUR build link libsodium, which `ARGON2ID` needs.

`sogo_postfixadmin_db_user` reads the view (`SELECT`) and, with
`sogo_password_change_enabled`, writes `c_password` (`UPDATE` on that
column).

`sogo_password_change_enabled` lets users change their password in SOGo,
which writes the hash straight into the PostfixAdmin database. Such a
change bypasses `postfixadmin_password_validation`, and the next run of the
postfixadmin role sets the password of a mailbox in `managed` mode back to
the one in its inventory: use `mode: 'initial'` or `'disabled'` for
mailboxes whose users change their password in SOGo. The view user then
needs `UPDATE` on `c_password`, so whoever can read `sogo.conf` (root and
the group `sogo`) can set the password of every mailbox.

The brute-force protection counts the failed logins of an account in
memcached (`SOGoMaximumFailedLoginCount`, `SOGoMaximumFailedLoginInterval`,
`SOGoFailedLoginBlockInterval`, as in the SOGo 5.12 source): the count
starts with the first failure and runs for `sogo_failed_login_block_interval`
seconds, then it starts again. Once it reaches `sogo_failed_login_count`,
every login of the account, also with the correct password, is refused
until the earlier of `sogo_failed_login_interval` seconds after the last
failure and `sogo_failed_login_block_interval` seconds after the first one.
The protection is per account, not per client address; it also lets an
attacker lock an account (fail2ban on the web server log covers
addresses).

The role sets `SOGoCacheCleanupInterval` (how long SOGo keeps cached
entries such as the failed-login count and verified passwords in
memcached) to max(300, min(`sogo_failed_login_interval`,
`sogo_failed_login_block_interval`)): long enough for the counter, without
a long block interval keeping a password that was changed elsewhere valid
in the cache for that long. A shorter cleanup than the block interval can
end a lock early; that is the trade-off for not caching passwords longer.

`sogo_user_sources` replaces the source with a list of SOGo sources written
as they are (keys of
[SOGoUserSources](https://www.sogo.nu/files/docs/SOGoInstallationGuide.html)),
for example an LDAP directory.

### Mail

| Variable                     | Default                          | Description                              |
| ---------------------------- | -------------------------------- | ---------------------------------------- |
| `sogo_mail_domain`           | `''`                             | **REQUIRED**, `SOGoMailDomain`           |
| `sogo_imap_server`           | `'imaps://<fqdn>:993'`           | Dovecot IMAP (`SOGoIMAPServer`)          |
| `sogo_smtp_server`           | `'smtp://<fqdn>:587/?tls=YES'`   | Postfix submission (`SOGoSMTPServer`)    |
| `sogo_sieve_server`          | `'sieve://<fqdn>:4190/?tls=YES'` | Dovecot ManageSieve (`SOGoSieveServer`)  |
| `sogo_sieve_scripts_enabled` | `true`                           | Mail filters (`SOGoSieveScriptsEnabled`) |
| `sogo_forward_enabled`       | `true`                           | Forwarding (`SOGoForwardEnabled`)        |
| `sogo_vacation_enabled`      | `true`                           | Vacation (`SOGoVacationEnabled`)         |

`<fqdn>` is `ansible_facts['fqdn']`. SOGo verifies the certificates of
Dovecot and Postfix against the system trust store and the host name in the
URL, so the URLs carry the name in the certificate (not `localhost` or
`127.0.0.1`); on Rocky Linux the role copies the trust store of the host into
`/etc/sogo/ca-bundle.pem`, which replaces the CA bundle of the image. SOGo
logs in to IMAP, submission (`SOGoSMTPAuthenticationType = PLAIN`) and
ManageSieve with the credentials of the user. The three Sieve features need
`sogo_sieve_server`; an empty value turns them off.

The shared mailboxes of Dovecot (`dovecot_shared_mailboxes`) appear in the
folder list of the users they are shared with (`SOGoIMAPAclConformsToIMAPExt
= YES`), and users share their own folders through IMAP ACLs in the folder
properties.

### Settings

| Variable            | Default     | Description                         |
| ------------------- | ----------- | ----------------------------------- |
| `sogo_timezone`     | `'UTC'`     | Default time zone (`SOGoTimeZone`)  |
| `sogo_language`     | `'English'` | Default language (`SOGoLanguage`)   |
| `sogo_workers`      | `3`         | Worker processes (`WOWorkersCount`) |
| `sogo_extra_config` | `{}`        | Further `sogo.conf` keys            |

On Debian the unit of the package passes the worker count from
`/etc/default/sogo` (`PREFORK`), which the role writes; the other platforms
take `WOWorkersCount` from `sogo.conf` (Rocky Linux on the command line of
the container). `sogo_extra_config` takes strings, numbers, booleans, lists
and mappings and writes them in the property list syntax; keys the role
writes from its own variables are rejected:

```yaml
sogo_extra_config:
  SOGoPageTitle: 'Example Mail'
  SOGoMailAuxiliaryUserAccountsEnabled: true
  SOGoCalendarDefaultRoles: ['PublicViewer', 'ConfidentialDAndTViewer']
```

`sogo.conf` (mode `0640`, owner `root`, group `sogo`) holds the database
passwords; `/etc/sogo` is `0750` with the same owner. Debian and Arch Linux
check it with `plparse` before it replaces the active one. Every change
keeps the previous file as `/etc/sogo/sogo.conf.<timestamp>~` (same owner
and mode); the run shows no diff of it, because it holds passwords.

### Periodic Jobs

| Variable                             | Default | Description                                        |
| ------------------------------------ | ------- | -------------------------------------------------- |
| `sogo_session_timeout`               | `60`    | Minutes without activity until a session ends      |
| `sogo_expire_sessions_timer_enabled` | `true`  | `sogo-tool expire-sessions` every minute           |
| `sogo_ealarms_timer_enabled`         | `true`  | E-mail alarms (`sogo-ealarms-notify` every minute) |
| `sogo_autoreply_timer_enabled`       | `true`  | `sogo-tool update-autoreply` every 5 minutes       |
| `sogo_sieve_admin_username`          | `''`    | Sieve administrator for `update-autoreply`         |
| `sogo_sieve_admin_password`          | `''`    | Its password (store it in the vault)               |

The jobs run as systemd timers (`sogo-expire-sessions.timer`,
`sogo-ealarms-notify.timer`, `sogo-vacation-messages.timer`) under the `sogo`
user instead of the cron files of the packages (Arch Linux has no cron by
default); the commented cron file of the Debian package stays unused. On
Rocky Linux every job runs in a container of the image of its own, with
the mounts and the environment of the service.

`sogo-tool update-autoreply` activates out-of-office replies on their start
date and ends them on their end date. It logs in to ManageSieve as every user
with vacation settings, so it needs an administrator that may log in as
another user: a Dovecot master user. The dovecot role has no setting for
master users; add a `passwd-file` passdb through `dovecot_extra_config`:

```yaml
dovecot_extra_config: |
  protocol sieve {
    passdb sieve-masters {
      driver = passwd-file
      passwd_file_path = /etc/dovecot/master-users
      master = yes
      result_success = continue
    }
  }
```

The file holds `sieveadmin:{SHA512-CRYPT}<hash>` (`doveadm pw -s
SHA512-CRYPT`). The `protocol sieve` filter restricts the master login to
ManageSieve (Dovecot 2.4 takes a passdb inside a protocol filter; the
Molecule scenarios check that an IMAP master login is refused). Within
ManageSieve the master user can still log in as every user, and its
password is in `/etc/sogo/sieve.creds` (`0640`, `root:sogo`): readable by
root and the group `sogo`. Without the credentials the timer is stopped and
the file removed.

### Backup

| Variable                    | Default                   | Description                              |
| --------------------------- | ------------------------- | ---------------------------------------- |
| `sogo_backup_enabled`       | `false`                   | Back up on a schedule                    |
| `sogo_backup_dir`           | `'/var/lib/sogo/backups'` | Directory of the sets (`sogo:sogo 0700`) |
| `sogo_backup_keep`          | `7`                       | Sets to keep (count-based)               |
| `sogo_backup_timer_enabled` | `true`                    | Run the backup with `sogo-backup.timer`  |
| `sogo_backup_on_calendar`   | `'daily'`                 | `OnCalendar` of the timer                |
| `sogo_restore`              | `''`                      | Set to restore (`-e` for one run)        |

`sogo_backup_dir` and `sogo_web_resources_dir` take letters, digits, `.`,
`_`, `-` and `/` only (both reach shell commands), no `.` or `..`
segments, and they are at least two levels deep (`/srv/sogo-backups`, not
`/srv` or `/var`): the role owns both directories, and `/var` or
`/var/lib/..` would hand `/var` to the `sogo` user. Both must be dedicated
to SOGo: the role refuses a `sogo_backup_dir` that exists and belongs to
another user (such as `/var/lib`, `/var/backups` or a home directory) instead
of making it `sogo:sogo 0700`, and replaces `sogo_web_resources_dir` only
when it holds the stamp file of an earlier copy. For a mount point that
belongs to root (`/srv/backup`), set a subdirectory (`/srv/backup/sogo`):
the role creates it, also on a fresh host where the `sogo` user does not
exist yet. A symlink as `sogo_backup_dir` is refused as well; set the real
directory.

`/usr/local/bin/sogo-backup` (run by `sogo-backup.service` as `sogo`) writes
`sogo_backup_dir/sogo-<timestamp>/` with one file per user (`sogo-tool
backup ... ALL`: calendars, address books, preferences, filters) and keeps
the newest `sogo_backup_keep` sets; a failed run leaves a `.partial`
directory and removes nothing. `sogo-tool backup ALL` takes the users from
SOGo's folder table; on a new server where no user has logged in yet, or
on an empty SOGo database (a restore after a disaster), there is nothing to
save: `sogo-tool backup` ends with status 255 and no output, and the
script logs that and ends without a set. Every other failure (a message of
the database or the user lookup, another status such as a crash or an OOM
kill) fails the backup. Mail stays in
Dovecot and the users in PostfixAdmin; back them up there. The host backup
copies `sogo_backup_dir` after `sogo-backup.service` ran.

`sogo_restore` names a set of `sogo_backup_dir` for one run (never set in
the inventory):

```bash
ansible-playbook site.yml --tags sogo -e sogo_restore=sogo-20260101-030000
```

The role first takes a fresh backup (the backup script never rotates the
set named for the restore; with nothing to save, as on an empty database,
the restore goes on without one), then restores every user file of the set
with `sogo-tool restore`: all folders, replacing their current content
(`-F ALL`), and the preferences (`-p`, with the Sieve administrator also
the Sieve script). A user of the set that the user source no longer knows
is skipped (unless the output reports an error besides the "user '…' not
found" line, so a user named `errors@example.com` is still just skipped);
the run lists the skipped users in a warning. When no user of
the set could be restored, the run fails: an unreachable user source
answers "not found" for every user. A failure of the backup taken first
aborts the restore before anything is changed. The folders get new IDs,
and memcached would still hand out the old ones (SOGo answers 404 for the
restored objects): whenever a restore command ran, the role restarts a
memcached on this host, restarts SOGo and waits for it, also when a later
user failed, and then sends `flush_all` to a memcached on another host
(the run fails when that host does not answer OK within 20 seconds, with
the answer, "timed out" or "closed the connection" in the message). The
message also says whether the restore is complete. When no user failed for
real and at least one was restored, it is: do **not** run it again (it
would take another backup and restore once more). When a user failed for
real, the message names those users; when no user was restored at all, it
names the users the user source does not know: then the restore is not
complete, fix the cause and run it again. Either way, flush the cache by
hand from a host that reaches memcached, or restart memcached there:

```bash
printf 'flush_all\r\nquit\r\n' | nc mc.example.com 11211
```

When a user fails for real, the run ends with that error, also when other
users of the set were unknown (with a failed flush to another host, with the
flush message naming the failed users). A set without any user file is refused
before anything changes.

A single user or folder
is restored by hand with the same tool (on Rocky Linux with the command
line of `ExecStart` in `/etc/systemd/system/sogo-backup.service`):

```bash
sudo -u sogo sogo-tool restore -f Calendar/personal /var/lib/sogo/backups/sogo-20260101-030000 alice@example.com
```

## Tags

| Tag              | Description                                           |
| ---------------- | ----------------------------------------------------- |
| `sogo`           | All tasks of the role                                 |
| `sogo:install`   | Packages or image, targeted update, memcached         |
| `sogo:database`  | Database and owner (`sogo_db_create`)                 |
| `sogo:configure` | `sogo.conf`, defaults, Sieve credentials, trust store |
| `sogo:backup`    | Backup script and units                               |
| `sogo:restore`   | Restore of `sogo_restore`                             |
| `sogo:service`   | Units, timers, service                                |

## Example Playbook

```yaml
- name: Groupware
  hosts: mail_servers
  become: true
  roles:
    # Rocky Linux: podman for the container of SOGo
    - role: marcstraube.common.podman
      when: ansible_facts['os_family'] == 'RedHat'
    - role: marcstraube.server.sogo
      vars:
        sogo_enabled: true
        sogo_db_password: '{{ vault_sogo_db_password }}'
        sogo_db_create: true
        sogo_postfixadmin_db_password: '{{ vault_postfixadmin_db_sogo_password }}'
        sogo_mail_domain: 'example.com'
        sogo_imap_server: 'imaps://mail.example.com:993'
        sogo_smtp_server: 'smtp://mail.example.com:587/?tls=YES'
        sogo_sieve_server: 'sieve://mail.example.com:4190/?tls=YES'
        sogo_sieve_admin_username: 'sieveadmin'
        sogo_sieve_admin_password: '{{ vault_sogo_sieve_admin_password }}'
        sogo_timezone: 'Europe/Berlin'
    - role: marcstraube.server.nginx
```

On one host the run order of the mail stack is postfixadmin → postfix →
dovecot → rspamd → sogo; the web server can run before or after SOGo.

## Testing

```bash
cd roles/sogo

# Everything on one instance (one platform at a time)
MOLECULE_PLATFORM_NAME=sogo-postgresql-debian-trixie molecule test -s postgresql
MOLECULE_PLATFORM_NAME=sogo-mariadb-rocky-10 molecule test -s mariadb

# SOGo (Rocky Linux 10) in one container, database, PostfixAdmin, Postfix
# and Dovecot (Debian 13) in another
molecule test -s split
```

Driver: `podman` | Scenarios: `postgresql`, `mariadb` (Arch Linux, Debian
Trixie, Rocky 9, Rocky 10), `split` (Rocky 10 and Debian Trixie, two
containers)

Prepare sets up the database, PostfixAdmin with test accounts and the SOGo
view, Postfix, Dovecot with ManageSieve, a shared mailbox and a master user,
nginx with the site of [Web Server](#web-server), a test CA in the trust
store and a dnsmasq test resolver (`mail.example.com`). Arch Linux builds the
AUR packages in converge, which takes a while; Rocky Linux keeps the podman
storage of the `sogo` user on a tmpfs. Debian starts with the oldest SOGo
release of the repositories.

`postgresql` and `mariadb` run a check on the new host before converge and
after idempotence; side effect runs a minimum the repository does not offer
and a mapping without a key for the host (both fail before any change), then
the targeted update with the candidate as minimum; verify checks the
permissions of `/etc/sogo`, the service (rootless container on Rocky Linux),
sogod on the loopback interface, memcached, the login page, a static
resource and the `.well-known` redirects through nginx, the login of a
PostfixAdmin account with an `{ARGON2ID}` hash and a rejected password, a
password change in SOGo stored as `{ARGON2ID}` that Dovecot accepts (and the
old password refused), the IMAP folders and the shared mailbox through SOGo,
a message sent through SOGo and delivered to the recipient, a CalDAV event, a
CardDAV contact, a filter written through ManageSieve, the timers and one run
of every job, and the update: on Debian the new release with one restart by
the role, on Rocky Linux the new image in the container and in the web
resources, on Arch Linux no change. `postgresql` also checks ActiveSync,
`mariadb` the database connection with TLS (the reader of the view may only
connect with TLS) and the backup with its rotation.

`split` runs the same checks with SOGo in the container of Rocky Linux 10
and PostgreSQL, PostfixAdmin, Postfix and Dovecot in a Debian container: the
database connections with TLS (`verify-full`; the server admits the SOGo
users only with TLS and verify reads `pg_stat_ssl`), IMAP, submission and
ManageSieve of the other container by its name.

## Notes

### PostfixAdmin

The user source reads the view `postfixadmin_sogo_view_name` of
`marcstraube.server.postfixadmin` (`postfixadmin_sogo_view_enabled: true`)
with a read-only user of `postfixadmin_db_readers`. SOGo changes a password
with an `UPDATE` of `c_password` on the view, so for
`sogo_password_change_enabled` the user needs `UPDATE` on that column
(leave `update_columns` out while password changes are off):

```yaml
postfixadmin_sogo_view_enabled: true
postfixadmin_db_readers:
  - name: 'sogo_view'
    password: '{{ vault_postfixadmin_db_sogo_password }}'
    # MariaDB: the account host SOGo connects from (TCP)
    host: '127.0.0.1'
    tables: ['sogo_users']
    update_columns: ['sogo_users.c_password']
```

The SOGo database and the PostfixAdmin database usually share the server,
so the owner of the SOGo database (`sogo_db_user`, `sogo`) and the user of
the view (`sogo_postfixadmin_db_user`, `sogo_view`) have different names;
the role fails before any change when both are the same account.

### Database Privileges

| Database          | User                        | Privileges                                        |
| ----------------- | --------------------------- | ------------------------------------------------- |
| SOGo (PostgreSQL) | `sogo_db_user`              | Owner of the database (creates its tables)        |
| SOGo (MariaDB)    | `sogo_db_user`              | `ALL` on `<db>.*`                                 |
| PostfixAdmin      | `sogo_postfixadmin_db_user` | `SELECT` on the view, `UPDATE (c_password)` on it |

A remote server needs a `pg_hba.conf` entry (`hostssl` with `sogo_db_tls`) or
a MariaDB account for the address of the SOGo host.

### Web Server

sogod serves neither TLS nor the static `WebServerResources`; the web server
of the SOGo host serves them from the file system and proxies `/SOGo` and
`/Microsoft-Server-ActiveSync` to `sogo_bind`. The path of the resources
differs per platform:

| Platform | `WebServerResources`                             |
| -------- | ------------------------------------------------ |
| Debian   | `/usr/share/GNUstep/SOGo/WebServerResources`     |
| Arch     | `/usr/lib/GNUstep/SOGo/WebServerResources`       |
| EL       | `sogo_web_resources_dir` (copied from the image) |

The site for `marcstraube.server.nginx` (the Molecule scenarios use it as
it is, with the Debian path):

```yaml
nginx_selinux_network_connect: true
nginx_sites:
  - name: 'sogo'
    server_names:
      - 'mail.example.com'
    type: 'custom'
    ssl:
      enabled: true
      certificate: '/etc/letsencrypt/live/mail.example.com/fullchain.pem'
      certificate_key: '/etc/letsencrypt/live/mail.example.com/privkey.pem'
    http_redirect: true
    client_max_body_size: '50m'
    locations:
      - path: '= /'
        config: 'return 302 /SOGo/;'
      - path: '= /.well-known/caldav'
        config: 'return 301 /SOGo/dav/;'
      - path: '= /.well-known/carddav'
        config: 'return 301 /SOGo/dav/;'
      - path: '^~ /SOGo.woa/WebServerResources/'
        config: |
          alias /usr/share/GNUstep/SOGo/WebServerResources/;
          expires max;
      - path: '^~ /SOGo/WebServerResources/'
        config: |
          alias /usr/share/GNUstep/SOGo/WebServerResources/;
          expires max;
      - path: '^~ /SOGo'
        config: |
          proxy_pass http://127.0.0.1:20000;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
          proxy_set_header x-webobjects-server-protocol HTTP/1.0;
          proxy_set_header x-webobjects-remote-host $remote_addr;
          proxy_set_header x-webobjects-server-name $server_name;
          proxy_set_header x-webobjects-server-url $scheme://$host;
          proxy_set_header x-webobjects-server-port $server_port;
          proxy_read_timeout 300;
      - path: '^~ /Microsoft-Server-ActiveSync'
        config: |
          proxy_pass http://127.0.0.1:20000/SOGo/Microsoft-Server-ActiveSync;
          proxy_set_header Host $host;
          proxy_set_header x-webobjects-server-protocol HTTP/1.0;
          proxy_set_header x-webobjects-remote-host $remote_addr;
          proxy_set_header x-webobjects-server-name $server_name;
          proxy_set_header x-webobjects-server-url $scheme://$host;
          proxy_set_header x-webobjects-server-port $server_port;
          proxy_read_timeout 3600;
```

`nginx_selinux_network_connect` lets nginx connect to sogod on EL (the
proxy locations are not of type `proxy`, so the nginx role does not switch
it on by itself). The same with `marcstraube.server.apache` (not tested in
the scenarios of this role):

```yaml
apache_selinux_network_connect: true
apache_modules_enabled:
  - 'alias'
  - 'proxy'
  - 'proxy_http'
  - 'headers'
apache_vhosts:
  - server_name: 'mail.example.com'
    redirect_to_https: true
apache_vhosts_ssl:
  - server_name: 'mail.example.com'
    document_root: '/var/www/html'
    certificate_file: '/etc/letsencrypt/live/mail.example.com/fullchain.pem'
    certificate_key_file: '/etc/letsencrypt/live/mail.example.com/privkey.pem'
    custom_config: |
      Alias /SOGo.woa/WebServerResources/ /usr/share/GNUstep/SOGo/WebServerResources/
      Alias /SOGo/WebServerResources/ /usr/share/GNUstep/SOGo/WebServerResources/
      <Directory /usr/share/GNUstep/SOGo/WebServerResources/>
        Require all granted
      </Directory>
      Redirect 301 /.well-known/caldav /SOGo/dav/
      Redirect 301 /.well-known/carddav /SOGo/dav/
      ProxyRequests Off
      ProxyPass /SOGo.woa/WebServerResources/ !
      ProxyPass /SOGo/WebServerResources/ !
      ProxyPass /Microsoft-Server-ActiveSync http://127.0.0.1:20000/SOGo/Microsoft-Server-ActiveSync retry=60 timeout=3600
      ProxyPass /SOGo http://127.0.0.1:20000/SOGo retry=0
      <Location /SOGo>
        RequestHeader set "x-webobjects-server-port" "443"
        RequestHeader set "x-webobjects-server-name" "mail.example.com"
        RequestHeader set "x-webobjects-server-url" "https://mail.example.com"
        RequestHeader set "x-webobjects-server-protocol" "HTTP/1.0"
      </Location>
```

A reverse proxy on another host forwards `https://mail.example.com/` to the
web server of the SOGo host, never to sogod directly (sogod stays on the
loopback interface and the resources are files of the SOGo host); it passes
the `Host` header and the client address on, and the web server of the SOGo
host keeps setting the `x-webobjects-*` headers for the public name.

### Firewall

The role does not manage firewall rules, and sogod (`sogo_bind`) and
memcached stay on the loopback interface. Only the web server ports are
opened, through the
[`marcstraube.common.firewalld`](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/firewalld/README.md)
inventory:

```yaml
firewalld_services:
  - 'http'
  - 'https'
```

The ports SOGo connects to (database, memcached on another host, IMAP 993,
submission 587, ManageSieve 4190) are opened on the hosts that offer them.

### SELinux

Not tested with SELinux enforcing (the Molecule containers run without it).
On EL the containers mount `/etc/sogo`, the spool and the backup directory
with `:z`, which relabels them for containers; nginx needs
`nginx_selinux_network_connect: true` to reach sogod, and reads the copied
web resources below `/usr/local/share` (`usr_t`).

### Rollback on Rocky Linux

A rebuild keeps the replaced image as `localhost/sogo:previous`. To go back
to it, as the `sogo` user:

```bash
sudo -u sogo XDG_RUNTIME_DIR=/run/sogo podman tag localhost/sogo:previous localhost/sogo:latest
sudo systemctl restart sogo
```

The web resources stay those of the new image until the next run of the
role, which copies them from the image again (its ID differs from the one
in the copy). The rollback lasts only until the next run that builds an
image: a run with `latest`, or any run while the change behind the
rebuild (an inventory variable such as `sogo_activesync_enabled` or a
mirror, or a new role version) is still in place, since the build script
then differs from the label of the image. Revert that change as well to
stay on the previous image.

### Platform Differences

| Platform | Differences the role covers                                                        |
| -------- | ---------------------------------------------------------------------------------- |
| Debian   | Unit of the package (`/etc/default/sogo` for the workers), `/usr/sbin`             |
| Arch     | AUR build (`libwbxml`, `sope`, `sogo`), unit of the package, own timers            |
| EL       | Local image, own `sogo.service` (rootless podman), jobs in containers of the image |

On Rocky Linux the `sogo` user (home `/var/lib/sogo`, podman storage below
it) builds and runs the image. `--userns=keep-id` maps it onto the `sogo`
user of the image (UID/GID 999), so `/etc/sogo` (`root:sogo 0750`, mounted
read-only) is readable by SOGo through the group and nothing in it is
readable for other users of the host. The trust store of the host
(`/etc/sogo/ca-bundle.pem`) replaces the CA bundle of the image, so SOGo
trusts the same certificate authorities as the host. The build downloads
the packages with APT's sandbox user switched off: the subordinate ID range
of the build may not contain `nogroup` (65534), and the build runs
unprivileged on the host anyway.

### Logging

Debian logs to `/var/log/sogo/sogo.log` (the unit of the package), Arch
Linux and Rocky Linux to the journal (`journalctl -u sogo`). The jobs log
to the journal of their units (`journalctl -u sogo-vacation-messages`).

### Removing State

The role removes what it can identify from the current variables: the Sieve
credentials without an administrator, the environment drop-in and the copy
of the database CA without `sogo_db_tls`. Turning the role off leaves SOGo,
its database and the image installed.

## References

Related roles:

- [marcstraube.server.postfixadmin](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/postfixadmin/README.md)
  — users and the SOGo view (`postfixadmin_sogo_view_enabled`, `postfixadmin_db_readers`)
- [marcstraube.server.dovecot](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/dovecot/README.md)
  — IMAP, ManageSieve, shared mailboxes, the Sieve administrator
- [marcstraube.server.postfix](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/postfix/README.md)
  — submission for the mail SOGo sends
- [marcstraube.server.postgresql](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/postgresql/README.md)
  — SOGo database server (`sogo_db_create`)
- [marcstraube.server.mariadb](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/mariadb/README.md)
  — SOGo database server (`sogo_db_create`)
- [marcstraube.server.nginx](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/nginx/README.md)
  — web server site for SOGo
- [marcstraube.server.apache](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/apache/README.md)
  — web server alternative
- [marcstraube.common.podman](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/podman/README.md)
  — podman on Rocky Linux, prerequisite
- [marcstraube.common.package_management](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/package_management/README.md)
  — AUR build user on Arch Linux
- [marcstraube.common.firewalld](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/firewalld/README.md)
  — firewall rules for the web server ports

External:

- [SOGo documentation](https://www.sogo.nu/support/documentation.html)
- [SOGo source](https://github.com/Alinto/sogo)
- [Debian package](https://tracker.debian.org/pkg/sogo)
- [AUR package](https://aur.archlinux.org/packages/sogo)
- [Dovecot master users](https://doc.dovecot.org/main/core/config/auth/master_users.html)

## License

MIT

## Author

Marc Straube
