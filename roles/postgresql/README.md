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
| `postgresql_backup_enabled`      | `false`           | Enable automated backup via cron        |

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
| `postgresql:backup`    | Backup script and cron setup      |
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

## Notes

- Configuration files are deployed with mode `0600` owned by the `postgres`
  system user
- On Debian, the PostgreSQL version is embedded in file paths
  (`/etc/postgresql/<version>/main`). The role defaults to version 17 for
  Debian Trixie. With `postgresql_repo: 'distro'` the metapackage decides
  the installed version, so `postgresql_version` must match the release;
  with `'pgdg'` it selects the package
- The backup script uses plain SQL dumps compressed with gzip. For
  production environments, consider using `marcstraube.common.restic` for
  encrypted offsite backups
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
