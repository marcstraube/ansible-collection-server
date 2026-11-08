# marcstraube.server.postgresql

Install and configure PostgreSQL database server.

## Description

PostgreSQL is an advanced open-source relational database management system
supporting SQL compliance, extensibility, and data integrity.

## Requirements

- ansible-core >= 2.19

### Required Collections

```yaml
collections:
  - community.postgresql
  - ansible.posix # For firewalld management
```

### PostgreSQL Version

This role requires **PostgreSQL 15 or later**. The version comes from the
package source selected with `postgresql_repo` (see
[Package source](#postgresql_repo--distribution-packages-vs-pgdg)):

- `'distro'` (default): Debian Trixie and Arch Linux ship PostgreSQL 17,
  EL 10 ships 16. On EL 9 the default AppStream stream is PostgreSQL 13,
  which is EOL — enable a newer module stream before running this role:

  ```bash
  dnf module enable postgresql:16
  ```

- `'pgdg'`: the upstream PGDG repository provides every supported major
  version; `postgresql_version` selects the one to install.

## Supported Platforms

| Platform                  | Notes                                               |
| ------------------------- | --------------------------------------------------- |
| Arch Linux                | Official repo (`postgresql_repo` ignored)           |
| Debian Trixie             | Debian main or PGDG (`postgresql_repo`)             |
| EL 9 (Rocky, Alma, RHEL)  | AppStream module stream or PGDG (`postgresql_repo`) |
| EL 10 (Rocky, Alma, RHEL) | AppStream or PGDG (`postgresql_repo`)               |

EL 9 with `postgresql_repo: 'distro'` requires enabling a module stream
(`dnf module enable postgresql:16`) as the default AppStream provides
PostgreSQL 13 which is EOL.

Other distributions in the same os_family (EndeavourOS, Manjaro, Ubuntu, Mint,
Fedora) should work but are not actively tested. Use distro-specific vars
overrides if needed.

## Role Variables

See [defaults/main.yml](defaults/main.yml) for all available variables.

### Key Variables

| Variable                         | Default           | Description                             |
| -------------------------------- | ----------------- | --------------------------------------- |
| `postgresql_enabled`             | `false`           | Enable the postgresql role              |
| `postgresql_service_enabled`     | `true`            | Enable and start the PostgreSQL service |
| `postgresql_version`             | `'17'`            | Major version (Debian; EL with PGDG)    |
| `postgresql_repo`                | `'distro'`        | Package source: `distro` or `pgdg`      |
| `postgresql_listen_addresses`    | `'localhost'`     | Listen addresses                        |
| `postgresql_port`                | `5432`            | Listen port                             |
| `postgresql_max_connections`     | `100`             | Maximum connections                     |
| `postgresql_password_encryption` | `'scram-sha-256'` | Password encryption method              |
| `postgresql_shared_buffers`      | `'256MB'`         | Shared buffer memory                    |
| `postgresql_ssl_enabled`         | `false`           | Enable SSL/TLS (see SSL section below)  |
| `postgresql_firewalld_enabled`   | `true`            | Manage firewalld rule                   |
| `postgresql_backup_enabled`      | `false`           | Scheduled dumps (see Backup below)      |

The role connects to the server on `postgresql_port` through the first
entry of `postgresql_unix_socket_directories` (default
`'/var/run/postgresql'`): the `community.postgresql` tasks for users,
databases, extensions and the restore, and `psql`, `pg_dump` and
`pg_dumpall` in the backup script and the restore. A non-default port or
socket directory needs no further settings.

### `postgresql_repo` — Distribution packages vs. PGDG

| Aspect             | `'distro'` (default)                      | `'pgdg'`                                          |
| ------------------ | ----------------------------------------- | ------------------------------------------------- |
| Source             | Debian main, EL AppStream, Arch repo      | apt.postgresql.org / download.postgresql.org      |
| Available versions | One per release (EL: module streams)      | Every supported major version                     |
| Version selection  | Distro release or active module stream    | `postgresql_version`                              |
| Update cadence     | Distro lifecycle                          | Upstream release day                              |
| Debian packages    | `postgresql` (metapackage)                | `postgresql-<NN>`                                 |
| EL packages        | `postgresql-server`, `postgresql-contrib` | `postgresql<NN>-server`, `postgresql<NN>-contrib` |
| EL service         | `postgresql`                              | `postgresql-<NN>`                                 |
| EL paths           | `/var/lib/pgsql/data`, `/usr/bin`         | `/var/lib/pgsql/<NN>/data`, `/usr/pgsql-<NN>/bin` |

Debian paths are the same for both sources (`/etc/postgresql/<NN>/main`,
`/var/lib/postgresql/<NN>/main`). On Arch Linux the setting is ignored.

With `'pgdg'` the role adds the repository itself: on Debian a deb822
source for `<release>-pgdg` signed with the PGDG key, on EL the
`pgdg-common` and `pgdg<NN>` repositories for the requested version only.

**Switching sources or versions on an installed host is a major-version
upgrade**, which the role does not perform. Two guards make this explicit:

- Before changing anything the role scans the cluster root
  (`/var/lib/postgresql`, `/var/lib/pgsql`) and fails if a cluster exists
  outside the data directory it manages.
- After package installation it compares the cluster's `PG_VERSION` with
  the installed server and fails on a mismatch. This catches a rolling
  distro update on Arch Linux or a changed EL module stream, where the
  binaries move to a new major version while the data directory stays.

Upgrade the cluster by hand (`pg_upgrade`, on Debian `pg_upgradecluster`,
on Arch Linux with the previous binaries from `postgresql-old-upgrade`),
remove the old data directory afterwards, then rerun the role.

### Package Updates

| Variable                      | Default     | Description                                                     |
| ----------------------------- | ----------- | --------------------------------------------------------------- |
| `postgresql_packages_state`   | `'present'` | `present` installs missing packages only, `latest` updates them |
| `postgresql_packages_minimum` | `''`        | Lowest acceptable server version, checked after the packages    |

A regular run never updates PostgreSQL. A targeted update, for example for a
security release, is requested on the command line:

```bash
ansible-playbook site.yml --tags postgresql \
  -e postgresql_packages_state=latest \
  -e postgresql_packages_minimum=17.7
```

With `latest` the role refreshes the package metadata and updates every
installed PostgreSQL package in one transaction. The packages usually
restart the server themselves; when they did not, for example because of a
`policy-rc.d`, the running server still executes the replaced binary and
the role restarts it. The update covers the parts pulled in as
dependencies: on Debian the `postgresql-*` packages and `libpq5`, on EL the
AppStream `postgresql*` packages or, with `postgresql_repo: 'pgdg'`, the
`postgresql<NN>*` packages of the configured version. Minor releases only:
the major version stays as selected (see above).

`postgresql_packages_minimum` then fails the run when the installed server
is still older, which shows that the repository does not carry the fix yet.
The check is skipped under `--check`.

On Arch Linux the rolling repository moves to a new major version without
notice, and the server does not start on the cluster of the previous one.
The role therefore places a pacman drop-in
(`/etc/pacman.d/ignore.d/postgresql.conf`, `IgnorePkg = postgresql
postgresql-libs`) that keeps the system upgrade away from PostgreSQL.
pacman reads it when `pacman.conf` includes `/etc/pacman.d/ignore.d/*.conf`,
as `marcstraube.common.package_management` sets up; otherwise the role
prints a warning. With `latest` the role installs the version of the
package databases of the last system upgrade, so run the update together
with it, and fails when that is a new major version:

```bash
ansible-playbook marcstraube.server.database_server --tags system-update,postgresql \
  -e postgresql_packages_state=latest
```

A new major version needs a manual cluster upgrade (`pg_upgrade` with the
previous binaries from `postgresql-old-upgrade`) before the role updates
the packages.

### Backup

The role deploys `/usr/local/bin/postgresql-backup`, which writes one
compressed plain-format dump per database
(`<database>_<YYYYmmdd_HHMMSS>.sql.gz`, `pg_dump`) and one of the roles and
tablespaces (`globals_<YYYYmmdd_HHMMSS>.dumpall.sql.gz`,
`pg_dumpall --globals-only`) into `postgresql_backup_dir`. Without
`postgresql_backup_databases` it dumps every database except the templates
and `postgres`. The client programs run as `postgres` over the first socket
directory on `postgresql_port`; the directory and the dumps belong to root
(`0700`, `0600`).

A database dump always ends in `_<HHMMSS>.sql.gz`, so no database name,
not even `globals`, yields the name of a globals dump. Earlier role
versions named the globals dumps `globals_<YYYYmmdd_HHMMSS>.sql.gz`, the
name of the dumps of a database called `globals`. The script tells them
apart by the header `pg_dumpall` writes: such a dump rotates together with
the new globals dumps and ages out, never with a database.

`postgresql-backup.service` is a oneshot unit ordered after the PostgreSQL
service, and `postgresql-backup.timer` starts it on
`postgresql_backup_on_calendar` (`Persistent=true`, so a run missed while
the host was down follows at the next boot).
`systemctl start postgresql-backup.service` takes the dumps at any time and
returns once they are written.

The retention is count-based: the newest `postgresql_backup_keep` dumps of
every database and of the globals stay, older ones are removed after a
successful dump. A dump is written to a temporary file first, so a failed
dump never removes an older one and a failing timer never removes the last
good dump. When the dump of one database fails, the script continues with
the next one and the service fails at the end.

| Variable                          | Default                     | Description                                   |
| --------------------------------- | --------------------------- | --------------------------------------------- |
| `postgresql_backup_enabled`       | `false`                     | Scheduled dumps                               |
| `postgresql_backup_dir`           | `'/var/backups/postgresql'` | Directory for the dumps                       |
| `postgresql_backup_keep`          | `7`                         | Dumps to keep per database and of the globals |
| `postgresql_backup_databases`     | `[]`                        | Databases to dump (empty: all but templates)  |
| `postgresql_backup_timer_enabled` | `true`                      | Enable and start `postgresql-backup.timer`    |
| `postgresql_backup_on_calendar`   | `'*-*-* 03:00:00'`          | Schedule of the timer (systemd `OnCalendar`)  |
| `postgresql_restore`              | `''`                        | Dump to restore, passed with `-e` for one run |

The script and the units are always deployed. `postgresql_backup_enabled:
false` or `postgresql_backup_timer_enabled: false` stops and disables the
timer; the script, the units and the existing dumps stay. The role never
removes a dump other than through the retention.

> **Deprecation:** `postgresql_backup_schedule` (cron format) and
> `postgresql_backup_retention` (days) will be removed in the next major
> version. Use `postgresql_backup_on_calendar` and `postgresql_backup_keep`
> instead. While `postgresql_backup_schedule` is set, the role keeps
> running the backup from a cron job (`PostgreSQL backup` in the crontab of
> root, `systemctl start postgresql-backup.service`) instead of the timer.
> Without it, the role removes the cron job it created (in the crontab of
> root, or of `postgres` from earlier role versions) and the timer takes
> over at the same time of day as the former default schedule `0 3 * * *`
> (`*-*-* 03:00:00`).
> A set `postgresql_backup_retention` takes effect as the number of dumps
> to keep per database. Both print a deprecation warning on every run
> while they are set.

Earlier role versions deployed the script as
`/usr/local/bin/postgresql-backup.sh`. The role leaves it in place; nothing
runs it any more, remove it by hand.

A host backup takes the dumps instead of the running data directory: it
runs `systemctl start postgresql-backup.service` as its pre-sync step and
copies `postgresql_backup_dir`.

#### Restore

`postgresql_restore` names a dump in `postgresql_backup_dir` and restores
that database. Pass it with `-e` for one run, never set it in the
inventory:

```bash
ansible-playbook site.yml --tags postgresql -l db1 \
  -e postgresql_restore=myapp_20261104_000000.sql.gz
```

The database in the name must be managed through `postgresql_databases`;
otherwise the run fails before anything changes. The role does not restore
the globals dumps, neither `globals_<YYYYmmdd_HHMMSS>.dumpall.sql.gz` nor
the `globals_<YYYYmmdd_HHMMSS>.sql.gz` dumps of earlier role versions
(recognized by their `pg_dumpall` header, so the dumps of a database called
`globals` still restore). The role then

1. dumps the current state of the database (rotated as usual; the named
   dump is never rotated),
2. drops the database, terminating its connections
   (`DROP DATABASE … WITH (FORCE)`),
3. recreates it with the owner, encoding and locale of its
   `postgresql_databases` entry, and
4. loads the dump with `psql` in one transaction (`ON_ERROR_STOP`).

The roles the dump refers to must exist (`postgresql_users`). When a
statement fails, the database stays empty; the dump of step 1 restores the
previous state. Applications reconnect on their own; stop them first when
they must not see the empty database during the load.

### Authentication

The default `pg_hba.conf` entries use `scram-sha-256` for host connections
and `peer` for local socket connections. Additional entries for remote access
can be added via `postgresql_hba_additional`.

### Performance Tuning

Production servers should adjust memory settings based on available RAM:

```yaml
postgresql_shared_buffers: '{{ (ansible_facts["memtotal_mb"] * 0.25) | int }}MB'
postgresql_effective_cache_size: '{{ (ansible_facts["memtotal_mb"] * 0.5) | int }}MB'
postgresql_work_mem: '16MB'
postgresql_maintenance_work_mem: '128MB'
```

### SSL / TLS

SSL is disabled by default (`postgresql_ssl_enabled: false`). Loopback
connections do not benefit from TLS, and a wrong cert/key path causes
PostgreSQL to fail at startup — the operator opts in explicitly.

When enabling SSL, supply cert and key files. The role asserts both
files exist before deploying `postgresql.conf` and aborts with a clear
message if they are missing.

| Variable                   | Default | Description                                              |
| -------------------------- | ------- | -------------------------------------------------------- |
| `postgresql_ssl_cert_file` | `''`    | Cert path; empty falls back to the OS default in `vars/` |
| `postgresql_ssl_key_file`  | `''`    | Key path; empty falls back to the OS default in `vars/`  |

OS-specific defaults applied when the inventory variables are empty:

| OS     | Cert default                                | Key default                                 |
| ------ | ------------------------------------------- | ------------------------------------------- |
| Debian | `/etc/ssl/certs/ssl-cert-snakeoil.pem`      | `/etc/ssl/private/ssl-cert-snakeoil.key`    |
| RHEL   | `server.crt` (relative to `data_directory`) | `server.key` (relative to `data_directory`) |
| Arch   | `server.crt` (relative to `data_directory`) | `server.key` (relative to `data_directory`) |

On Debian the `ssl-cert` package places the snakeoil cert
automatically. On RHEL and Arch no system-wide snakeoil exists — the
operator must place `server.crt` + `server.key` in `data_directory`
(or override the inventory variables) before enabling SSL. The assert
task makes this explicit by failing early with the resolved absolute
paths in the error message.

The configuration reload handler of this role subscribes to the
`Reload cert services` handler topic of `marcstraube.server.certbot` and
`marcstraube.common.pki`. PostgreSQL rereads its SSL certificate and key on
a configuration reload, so a certificate issued or renewed inside the same
play takes effect in that run. Renewal through the certbot timer runs
outside of Ansible — add the PostgreSQL service unit to
`certbot_reload_services` for that path.

### Extra Configuration

Parameters not exposed as role variables can be set via the
`postgresql_extra_config` dict. This is useful for version-specific
settings (e.g., `scram_iterations` for PG 16+, `transaction_timeout`
for PG 17+):

```yaml
postgresql_extra_config:
  autovacuum_max_workers: 4
  scram_iterations: 4096
```

## Tags

| Tag                    | Description                       |
| ---------------------- | --------------------------------- |
| `postgresql`           | All postgresql tasks              |
| `postgresql:install`   | Package installation              |
| `postgresql:configure` | Configuration deployment          |
| `postgresql:users`     | User/role management              |
| `postgresql:databases` | Database and extension management |
| `postgresql:service`   | Systemd service management        |
| `postgresql:backup`    | Backup script, service and timer  |
| `postgresql:restore`   | Restore of `postgresql_restore`   |
| `postgresql:firewall`  | Firewalld rule management         |

## Example Playbook

```yaml
- hosts: db_servers
  become: true
  roles:
    - role: marcstraube.server.postgresql
      vars:
        postgresql_listen_addresses: '*'
        postgresql_shared_buffers: '1GB'
        postgresql_databases:
          - name: myapp
            owner: myapp
        postgresql_users:
          - name: myapp
            password: '{{ vault_postgresql_myapp_password }}'
        postgresql_hba_additional:
          - type: host
            database: myapp
            user: myapp
            address: '192.168.1.0/24'
            method: scram-sha-256
```

## Testing

```bash
# Run full test (one platform at a time)
MOLECULE_PLATFORM_NAME=postgresql-debian-trixie molecule test

# PGDG repository scenario (Debian Trixie, Rocky 9, Rocky 10)
MOLECULE_PLATFORM_NAME=postgresql-pgdg-rocky-10 molecule test -s pgdg

# Converge only
molecule converge

# Verify only
molecule verify
```

Driver: `podman` | Scenarios: `default` (distribution packages, all
platforms), `pgdg` (`postgresql_repo: 'pgdg'`, Debian Trixie and EL).
In the `default` scenario, Debian Trixie runs on `postgresql_port: 5433`,
so the users, databases, backup and restore are tested against a
non-default port.

## Notes

- Configuration files are deployed with mode `0600` owned by the `postgres`
  system user
- On Debian, the PostgreSQL version is embedded in file paths
  (`/etc/postgresql/<version>/main`). The role defaults to version 17 for
  Debian Trixie. With `postgresql_repo: 'distro'` the metapackage decides
  the installed version, so `postgresql_version` must match the release;
  with `'pgdg'` it selects the package
- The backup writes plain SQL dumps compressed with gzip, unencrypted. For
  encrypted offsite copies, let a host backup such as
  `marcstraube.common.restic` copy `postgresql_backup_dir` (see Backup)
- `password_encryption` is explicitly set to `scram-sha-256` for consistent
  security across all supported PostgreSQL versions

## References

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [PostgreSQL Wiki - Tuning](https://wiki.postgresql.org/wiki/Tuning_Your_PostgreSQL_Server)
- [PostgreSQL Wiki - Security](https://wiki.postgresql.org/wiki/Security)
- [pg_hba.conf Documentation](https://www.postgresql.org/docs/current/auth-pg-hba-conf.html)

## License

MIT

## Author

Marc Straube
