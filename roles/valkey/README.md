# marcstraube.server.valkey

Install and configure the Valkey key-value store.

## Description

Valkey is the open-source, Redis-compatible key-value store. The role
installs it from the distribution packages and deploys `valkey.conf` with
the listeners (TCP, optional unix socket, optional TLS), ACL users for the
applications, memory limit and eviction policy, RDB snapshots and the
append-only file. One instance can serve several applications, such as
rspamd (Bayes, fuzzy hashes, rate limits) and Roundcube sessions, on the
same host or over the network; each application gets its own ACL user and
key pattern.

## Requirements

- ansible-core >= 2.19
- `community.general` collection (SELinux port labels on EL)

## Supported Platforms

| Platform                  | Notes                                    |
| ------------------------- | ---------------------------------------- |
| Arch Linux                | `valkey` (extra), service `valkey`       |
| Debian Trixie             | `valkey-server`, service `valkey-server` |
| EL 9 (Rocky, Alma, RHEL)  | `valkey` (AppStream), service `valkey`   |
| EL 10 (Rocky, Alma, RHEL) | `valkey` (AppStream), service `valkey`   |

Other distributions in the same os_family (EndeavourOS, Manjaro, Ubuntu, Mint,
Fedora) should work but are not actively tested. Use distro-specific vars
overrides if needed.

All platforms ship Valkey in their base repositories (on EL 9 in AppStream,
no EPEL needed); the versions follow the distribution: 8.0 on EL 9 and
EL 10, 8.1 on Debian Trixie, the current release on Arch Linux.
The configuration lives in `/etc/valkey/valkey.conf` and the data in
`/var/lib/valkey` on every platform.

## Role Variables

See [defaults/main.yml](defaults/main.yml) for all available variables.

### Role Control

| Variable                 | Default | Description                         |
| ------------------------ | ------- | ----------------------------------- |
| `valkey_enabled`         | `false` | Enable the valkey role              |
| `valkey_service_enabled` | `true`  | Enable and start the Valkey service |

### Package Updates

| Variable                  | Default     | Description                                                      |
| ------------------------- | ----------- | ---------------------------------------------------------------- |
| `valkey_packages_state`   | `'present'` | `present` installs missing packages only, `latest` updates them  |
| `valkey_packages_minimum` | `''`        | Lowest acceptable Valkey version, string or mapping per platform |

A regular run never updates Valkey. A targeted update, for example for a
security release, is requested on the command line:

```bash
ansible-playbook site.yml --tags valkey \
  -e valkey_packages_state=latest \
  -e valkey_packages_minimum=8.1.4
```

With `latest` the role refreshes the package metadata and updates every
installed Valkey package in one transaction, including the parts pulled in
as dependencies (on Debian `valkey-server` and `valkey-tools`, on EL
`valkey*`). The role reports the version change.

`valkey_packages_minimum` is checked twice. Before the update the role asks
the package manager which version the update would install and fails without
a change when it is older than the minimum, which shows that the repository
does not carry the fix yet. After the update it checks the installed version
again; this check is skipped under `--check`.

The minimum is an upstream version (`8.1.4`, any distribution release of it)
or the full distribution version (`8.1.1+dfsg1-3+deb13u3`,
`8.0.10-1.el9_8`). Debian and EL ship many fixes as backports that only
raise the release, so only the full version proves such a fix. Versions are
compared with the rules of the distribution (`dpkg --compare-versions`, rpm,
`vercmp`); a minimum without an epoch takes the epoch of the package. For
mixed hosts in one run, pass a mapping per platform; the keys are
`<os_family>-<major>` or `<os_family>`, and a host without a matching key
fails before any change:

```yaml
# valkey-minimum.yml, passed with -e @valkey-minimum.yml
valkey_packages_minimum:
  Debian: '8.1.1+dfsg1-3+deb13u3'
  RedHat-9: '8.0.10-1.el9_8'
  RedHat-10: '8.0.11-1.el10_2'
  Archlinux: '9.1.3'
```

The packages usually restart Valkey themselves. When they did not, for
example because of a `policy-rc.d`, the running server still executes the
replaced binary and the role restarts it. `valkey-server` has no
configuration test (nothing like `nginx -t`), so the restart is not
preceded by one.

On Arch Linux `valkey_packages_state` is ignored: updating single packages is
a partial upgrade there, Valkey updates with the full system upgrade. Run the
role with `latest` together with the system upgrade (`--tags
system-update,valkey`) to restart Valkey after it.

### Network

| Variable                   | Default       | Description                                                       |
| -------------------------- | ------------- | ----------------------------------------------------------------- |
| `valkey_bind`              | `'127.0.0.1'` | Listen addresses for TCP and TLS, space-separated                 |
| `valkey_port`              | `6379`        | Plain TCP port, `0` disables plain TCP                            |
| `valkey_unix_socket`       | `''`          | Unix socket path in `/run/valkey`, `''` disables it               |
| `valkey_unix_socket_perm`  | `'770'`       | Socket permissions (`unixsocketperm`), a quoted string            |
| `valkey_unix_socket_group` | `''`          | Socket group, `''` keeps the group of the service user (`valkey`) |

`protected-mode` is always on: while the `default` user is enabled without
a password (no `valkey_users`), only loopback and unix socket clients are
accepted, whatever `valkey_bind` says. Defining `valkey_users` disables the
`default` user, and clients from other hosts are accepted once they
authenticate.

`valkey_bind` applies to the plain and the TLS port alike; Valkey has no
separate bind address for TLS. To offer only TLS to other hosts, set
`valkey_port: 0` and let local clients use the unix socket.

**Plain TCP is unencrypted.** Serve other hosts over `valkey_port` only on a
private network or WireGuard; otherwise use TLS.

#### Unix Socket Group

The socket lives in `/run/valkey`, the runtime directory of the service
(the only place below `/run` the service user can write). With
`valkey_unix_socket_group` set, the role creates the group if it is
missing, adds the service user `valkey` to it (Valkey can only hand the
socket to a group it belongs to) and sets `unixsocketgroup`. The local
clients join that group through their own role or `users_list`; the role
does not add them.

A dedicated group (e.g. `valkey-clients`) is preferable to adding clients
to the `valkey` group: members of `valkey` can read `users.conf` (ACL
hashes) and, on Debian, write to `/etc/valkey`.

On Debian `valkey-server.service` runs with `PrivateUsers=true` and a system
call filter that excludes `@chown`, so the socket group cannot be set (the
service is killed with `SIGSYS`). While a socket group is set, the role
deploys `/etc/systemd/system/valkey-server.service.d/socket-group.conf`
with `PrivateUsers=false` and `SystemCallFilter=@chown`, and removes it
again otherwise. Arch Linux and EL need no drop-in.

### TLS

| Variable                  | Default             | Description                                    |
| ------------------------- | ------------------- | ---------------------------------------------- |
| `valkey_tls_enabled`      | `false`             | Enable the TLS listener                        |
| `valkey_tls_port`         | `6380`              | TLS port, on the addresses of `valkey_bind`    |
| `valkey_tls_cert_file`    | `''`                | Server certificate (PEM), required with TLS    |
| `valkey_tls_key_file`     | `''`                | Private key (PEM), required with TLS           |
| `valkey_tls_ca_file`      | `''`                | CA to verify client certificates               |
| `valkey_tls_auth_clients` | `'no'`              | Client certificates: `no`, `optional` or `yes` |
| `valkey_tls_protocols`    | `'TLSv1.2 TLSv1.3'` | Accepted protocol versions                     |

With `valkey_tls_auth_clients: 'no'` clients authenticate with their ACL
user only and no CA is needed; `optional` and `yes` require
`valkey_tls_ca_file`. The role checks that the files exist before it
changes the configuration. Certificate and key must be readable by the
service user `valkey`, which the package creates. With
`marcstraube.common.pki`, issue the certificate with `owner: 'valkey'` (or a
group the service user belongs to, except on Debian, see below) into a
directory the service user can traverse — `/etc/ssl/private` is root-only.
The user exists only after the package is installed, so on a new host run
the valkey role (TLS still off) before the certificate is issued, or
install the package first with `--tags valkey:install`.

On Debian `valkey-server.service` runs with `PrivateUsers=true`: every group
but the service user's own is mapped to `nobody`, so a key readable through
a supplementary group of `valkey` (e.g. `ssl-cert`) cannot be read at the
start. There the key has to belong to the owner `valkey` or the group
`valkey` (mode `0640` or `0600`); certificate and CA may also be
world-readable. The role asserts this before it changes the configuration.
The socket group drop-in (see [Unix Socket Group](#unix-socket-group)) sets
`PrivateUsers=false`; while it is deployed, supplementary groups work and
the check is skipped — a key permission that relies on it breaks once the
socket group is removed.

The restart handler of the role subscribes to the `Reload cert services`
topic of `marcstraube.common.pki` and the certbot role: Valkey reads the
certificate at the start only (or on `CONFIG SET` of a `tls-*` directive,
which needs an admin connection the role does not hold), so a renewed
certificate takes effect with a restart in the same play. A certificate
and a configuration change in the same play restart Valkey once. Without
`valkey_tls_enabled` the topic does not restart Valkey.

The topic is shared by every service that uses a certificate, and the
handler cannot tell which certificate changed: with `valkey_tls_enabled`,
any certificate change notified in the same play (for example a renewal for
the web server on the same host) restarts Valkey too, not only a change of
its own certificate. Without RDB snapshots and AOF the data is lost with the
restart (see [Persistence](#persistence)).

### Authentication

| Variable       | Default | Description                    |
| -------------- | ------- | ------------------------------ |
| `valkey_users` | `[]`    | ACL users, one per application |

| Key           | Required | Default                    | Description                                        |
| ------------- | -------- | -------------------------- | -------------------------------------------------- |
| `name`        | yes      |                            | User name (no whitespace or quotes, not `default`) |
| `password`    | yes      |                            | Password, no default; stored as SHA-256 hash       |
| `permissions` | no       | `['+@all', '-@dangerous']` | ACL command rules                                  |
| `keys`        | no       | `['*']`                    | Key patterns (`~` is added; `%R~`/`%W~` as is)     |
| `channels`    | no       | `[]`                       | Pub/Sub channel patterns                           |

When `valkey_users` is not empty, the `default` user is disabled
(`user default reset`) and every connection has to authenticate as one of
the listed users. The role asserts a password for every entry. Names, rules
and patterns become tokens of a `user` line in `users.conf`: whitespace,
line breaks and quotes are refused. A password may contain anything; only
its hash reaches the file. The list is
the complete set of users: a user removed from the list is gone after the
restart. Without `valkey_users` the `default` user keeps the package
behavior (no password, all commands), limited to local clients by
`protected-mode`: **any local account or process can read, change and flush
all data**. The role warns on every run while `valkey_users` is empty; in
production define at least one ACL user per application.

The `user` lines live in `/etc/valkey/users.conf`, which `valkey.conf`
pulls in with `include` (see [Configuration File](#configuration-file)).

`-@dangerous` excludes commands such as `FLUSHALL`, `KEYS`, `CONFIG`,
`DEBUG` and `SHUTDOWN`. An application that needs one adds it explicitly
(e.g. `+keys`); restrict the key patterns to the prefix the application
uses.

### Memory

| Variable                  | Default        | Description                               |
| ------------------------- | -------------- | ----------------------------------------- |
| `valkey_maxmemory`        | `'0'`          | Memory limit (`256mb`, `1gb`; `0` = none) |
| `valkey_maxmemory_policy` | `'noeviction'` | Eviction policy when the limit is reached |

### Persistence

| Variable            | Default                             | Description                                 |
| ------------------- | ----------------------------------- | ------------------------------------------- |
| `valkey_save`       | `['3600 1', '300 100', '60 10000']` | RDB snapshot rules, `[]` disables snapshots |
| `valkey_appendonly` | `false`                             | Append-only file (AOF)                      |

Every change of `valkey.conf` or `users.conf` (users, listeners, memory)
restarts the service. Valkey writes an RDB snapshot on shutdown when
`valkey_save` is not empty; with `valkey_save: []` and `valkey_appendonly: false` the data
is lost with every restart.

### Backup

The role deploys `/usr/local/bin/valkey-backup`, which writes one RDB
snapshot of the whole instance to
`<valkey_backup_dir>/valkey-<YYYYmmddTHHMMSS>.rdb` (root, mode `0600`). The
snapshot holds every database of the instance; Valkey has no backup of a
single database or key pattern, so the snapshot always covers all
applications that share the instance. The script fetches it with
`valkey-cli --rdb` from the running server (a replication sync), so the
service keeps running and serving its clients.

The script connects locally: through the unix socket when one is
configured, else on the plain port, else over TLS (verified against
`valkey_tls_ca_file` or the system trust store, without a client
certificate) on the first address of `valkey_bind`. Once `valkey_users`
disables the `default` user, it authenticates as `valkey_backup_user`, an
entry of `valkey_users` that needs the commands of a replication sync and
no key patterns. Its password is stored root-only in
`/usr/local/etc/valkey-backup.auth` and reaches `valkey-cli` in the
environment, not on the command line:

```yaml
valkey_backup_enabled: true
valkey_backup_user: 'backup'
valkey_users:
  - name: 'backup'
    password: '{{ vault_valkey_backup_password }}'
    permissions:
      - '+ping'
      - '+replconf'
      - '+sync'
    keys: []
```

`valkey-backup.timer` starts the oneshot `valkey-backup.service` on
`valkey_backup_on_calendar` (`Persistent=true`, so a run missed while the
host was down follows at the next boot). `systemctl start
valkey-backup.service` takes a snapshot at any time and returns once it is
written. The rotation is count-based: after each snapshot the newest
`valkey_backup_keep` snapshots stay, so a failing schedule never removes the
last good snapshot.

| Variable                      | Default                 | Description                                          |
| ----------------------------- | ----------------------- | ---------------------------------------------------- |
| `valkey_backup_enabled`       | `false`                 | Run the backup from the timer                        |
| `valkey_backup_dir`           | `'/var/backups/valkey'` | Backup directory (mode `0700`, root)                 |
| `valkey_backup_keep`          | `7`                     | Snapshots to keep                                    |
| `valkey_backup_user`          | `''`                    | ACL user of the backup, required with `valkey_users` |
| `valkey_backup_timer_enabled` | `true`                  | Enable and start `valkey-backup.timer`               |
| `valkey_backup_on_calendar`   | `'daily'`               | Schedule of the timer (systemd `OnCalendar`)         |
| `valkey_restore`              | `''`                    | Snapshot to restore, passed with `-e` (see below)    |

The backup is off by default: the role cannot know whether the instance
holds data worth a backup or only a cache that the applications rebuild.
The script and the units are deployed on every run, also with
`valkey_backup_enabled: false`, which stops and disables the timer; the
existing snapshots stay. The role never removes a snapshot other than
through the rotation. Without a TCP port and with
`valkey_tls_auth_clients: 'yes'` the backup needs the unix socket, since it
presents no client certificate.

A host backup takes the snapshots instead of the running data directory:
it runs `systemctl start valkey-backup.service` as its pre-backup step and
copies `valkey_backup_dir`, for example with `marcstraube.common.restic`:

```yaml
restic_jobs:
  - name: 'valkey'
    repository: '/backup/restic'
    password: '{{ vault_restic_password }}'
    paths:
      - '/var/backups/valkey'
    pre_backup: |
      systemctl start valkey-backup.service
```

#### Restore

`valkey_restore` names a snapshot in `valkey_backup_dir`. It is passed with
`-e` for one run, never set in the inventory:

```bash
ansible-playbook site.yml --tags valkey -l cache1 \
  -e valkey_restore=valkey-20261104T030000.rdb
```

The service must run (`valkey_service_enabled`); otherwise the run fails
before any change. The role first takes a fresh snapshot (`valkey-backup
valkey-20261104T030000.rdb`, whose rotation never removes the named
snapshot), stops Valkey and replaces `dump.rdb` with the snapshot. With
`valkey_appendonly` Valkey loads the append-only file instead of
`dump.rdb`, so the role replaces the AOF directory with one whose base is
the snapshot. Then it starts Valkey and waits until it answers `PING`
(`valkey-backup --ping`: the connection and the password file of the
backup, so no password passes through Ansible).
Every database of the instance returns to the state of the snapshot; data
written after it is gone. Keys with an expiry (TTL) keep their absolute
expiry time: a key that expired since the snapshot does not come back. To
undo a restore, restore the fresh snapshot the same way.

### Extra Configuration

| Variable              | Default | Description                      |
| --------------------- | ------- | -------------------------------- |
| `valkey_extra_config` | `{}`    | Further `valkey.conf` directives |

Booleans are written as `yes`/`no`, a list writes the directive once per
item; values are written as given:

```yaml
valkey_extra_config:
  tcp-keepalive: 60
  notify-keyspace-events: '"Ex"'
```

## Tags

| Tag                | Scope                                                                           |
| ------------------ | ------------------------------------------------------------------------------- |
| `valkey`           | All role tasks                                                                  |
| `valkey:install`   | Package installation and updates                                                |
| `valkey:configure` | TLS checks, socket group, systemd drop-in, SELinux, `valkey.conf`, `users.conf` |
| `valkey:service`   | Service management                                                              |
| `valkey:backup`    | Backup script, units, timer                                                     |
| `valkey:restore`   | Restore of `valkey_restore`                                                     |

## Example Playbook

```yaml
- name: Include valkey role
  ansible.builtin.include_role:
    name: marcstraube.server.valkey
  tags:
    - valkey
  when: valkey_enabled | default(false) | bool
```

### rspamd and Roundcube on the Same Host

```yaml
valkey_enabled: true
valkey_unix_socket: '/run/valkey/valkey.sock'
valkey_unix_socket_group: 'valkey-clients'
valkey_users:
  - name: 'rspamd'
    password: '{{ vault_valkey_rspamd_password }}'
    keys:
      - '*'
  - name: 'roundcube'
    password: '{{ vault_valkey_roundcube_password }}'
    keys:
      - 'roundcube:*'
```

### TLS for Other Hosts Only

```yaml
valkey_enabled: true
valkey_bind: '0.0.0.0'
valkey_port: 0
valkey_unix_socket: '/run/valkey/valkey.sock'
valkey_tls_enabled: true
valkey_tls_cert_file: '/etc/valkey/tls/valkey.crt'
valkey_tls_key_file: '/etc/valkey/tls/valkey.key'
valkey_users:
  - name: 'rspamd'
    password: '{{ vault_valkey_rspamd_password }}'
```

## Testing

```bash
cd roles/valkey

# Run full test (one platform at a time)
MOLECULE_PLATFORM_NAME=valkey-debian-trixie molecule test

# Server and client in two containers on one podman network
molecule test -s split
```

Driver: `podman` | Scenarios: `default` (Arch Linux, Debian Trixie, Rocky
9, Rocky 10: a check run before the install, ACL users, rejected `default`
user and wrong password, a line break in a password, unix socket group,
`users.conf` apart from `valkey.conf`, TLS with its protocol versions,
memory and persistence settings, one message per invalid setting, a TLS
key readable only through another group on Debian, one restart for a
certificate and a configuration change, backup, rotation and restore, the
targeted package update with one restart), `split` (Debian Trixie server
and client: TLS with an ACL user from the other host and a key of the group
`valkey`, refused plain port, unix socket on the server).

## Notes

### Firewall

The role does not manage firewall rules, and Valkey listens on `127.0.0.1`
by default. For other hosts set `valkey_bind` and open the port through
the `marcstraube.common.firewalld` inventory — the TLS port, or the plain
port on a private network or WireGuard only. firewalld ships a `redis`
service for 6379/tcp; the TLS port is opened as a port:

```yaml
firewalld_zone_ports:
  - zone: internal
    ports:
      - '6380/tcp'

# plain TCP, private network only
firewalld_zone_services:
  - zone: internal
    services:
      - 'redis'
```

### SELinux

On EL `valkey-server` runs as `redis_t`, which may only bind ports labeled
`redis_port_t` (6379, 16379, 26379). The role labels any other plain or TLS
port (e.g. the default TLS port 6380) with `community.general.seport` when
SELinux is enabled. Keep certificate and key where `redis_t` may read
them, e.g. below `/etc/valkey` (`redis_conf_t`).

### Configuration File

The role writes `valkey.conf` in full; directives it does not set keep the
compiled defaults (the comments of the packaged file are not kept). The ACL
users with the SHA-256 hashes of their passwords are in a second file the
role writes in full, `/etc/valkey/users.conf`, which `valkey.conf` pulls in
with `include`. Valkey reads an included file as part of the configuration,
so the `user` lines behave as if they were in `valkey.conf`. The users file
is deployed with `no_log`; `valkey.conf` holds no secret and shows its diff
under `--check --diff`. A change of either file restarts the service.

Both files are readable by the service user only, with owner and group as
the package sets them for `valkey.conf`: `valkey:valkey 0600` on Debian,
`root:valkey 0640` on Arch Linux (the service user reads them through the
group) and `valkey:root 0640` on EL (the package's tmpfiles.d entry
`Z /etc/valkey ~0750 valkey root` applies recursively and sets 0640 on both
files on every boot; the group is root, so it adds no reader).

`include` is not `aclfile`: the users stay part of the configuration, `ACL
SAVE` and `ACL LOAD` keep failing (no ACL file), and users changed with
`ACL SETUSER` at runtime are gone after the next restart. `CONFIG REWRITE`
keeps the `include` line, but writes every current user, hash included,
into `valkey.conf` itself; the next run of the role writes `valkey.conf`
without them again, and the diff of that run shows the removed hashes. The
role never runs `CONFIG REWRITE`; avoid it on a host the role manages.
Logs go to `/var/log/valkey` on Debian and EL (packaged logrotate
configuration) and to the journal on Arch Linux.

### Removing State

The role never uninstalls packages and never deletes data; the backup
rotation is the only removal. To remove Valkey from a host, stop and
disable the service and `valkey-backup.timer`, remove the packages and
delete `/var/lib/valkey`, `/etc/valkey/users.conf`, `valkey_backup_dir`,
`/usr/local/bin/valkey-backup`, `/usr/local/etc/valkey-backup.auth` and
the backup units by hand. A socket group the role created stays.

## References

- [Valkey Documentation](https://valkey.io/docs/)
- [Valkey Configuration (valkey.conf)](https://valkey.io/topics/valkey.conf/)
- [ACL](https://valkey.io/topics/acl/)
- [TLS](https://valkey.io/topics/encryption/)
- [Security](https://valkey.io/topics/security/)
- [Persistence](https://valkey.io/topics/persistence/)

## License

MIT

## Author

Marc Straube
