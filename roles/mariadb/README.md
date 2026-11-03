# marcstraube.server.mariadb

Install and configure MariaDB database server.

## Description

MariaDB is a community-developed relational database server derived from
MySQL. The role installs the server from the distribution or the MariaDB
Foundation repository, deploys a configuration drop-in (utf8mb4, InnoDB,
connection and logging settings, optional TLS), locks the root account to
unix socket authentication, removes the anonymous users and the test
database, and manages databases and users. An optional count-based backup
dumps every database on a schedule.

## Requirements

- ansible-core >= 2.19

### Required Collections

```yaml
collections:
  - ansible.mariadb
```

### MariaDB Version

The role requires **MariaDB 10.5 or later**. `mariadb_version` selects the
major version with both package sources (see
[Package source](#mariadb_repo--distribution-packages-vs-upstream)); the
default `'11.8'` is available with `distro` on every platform.

## Supported Platforms

| Platform                  | Notes                                                              |
| ------------------------- | ------------------------------------------------------------------ |
| Arch Linux                | Official repo, `mariadb` or `mariadb-lts` (`mariadb_arch_package`) |
| Debian Trixie             | Debian main or upstream (`mariadb_repo`)                           |
| EL 9 (Rocky, Alma, RHEL)  | AppStream module stream or upstream (`mariadb_repo`)               |
| EL 10 (Rocky, Alma, RHEL) | AppStream package set or upstream (`mariadb_repo`)                 |

Other distributions in the same os_family (EndeavourOS, Manjaro, Ubuntu, Mint,
Fedora) should work but are not actively tested. Use distro-specific vars
overrides if needed.

## Role Variables

See [defaults/main.yml](defaults/main.yml) for all available variables.

### Key Variables

| Variable                          | Default                | Description                                    |
| --------------------------------- | ---------------------- | ---------------------------------------------- |
| `mariadb_enabled`                 | `false`                | Enable the mariadb role                        |
| `mariadb_service_enabled`         | `true`                 | Enable and start the MariaDB service           |
| `mariadb_repo`                    | `'distro'`             | Package source: `distro` or `upstream`         |
| `mariadb_version`                 | `'11.8'`               | Major version (Debian and EL)                  |
| `mariadb_arch_package`            | `'mariadb'`            | Arch Linux package: `mariadb` or `mariadb-lts` |
| `mariadb_bind_address`            | `'127.0.0.1'`          | Listen address                                 |
| `mariadb_port`                    | `3306`                 | Listen port                                    |
| `mariadb_max_connections`         | `151`                  | Maximum connections                            |
| `mariadb_character_set_server`    | `'utf8mb4'`            | Default character set                          |
| `mariadb_collation_server`        | `'utf8mb4_unicode_ci'` | Default collation                              |
| `mariadb_innodb_buffer_pool_size` | `'128M'`               | InnoDB buffer pool                             |
| `mariadb_ssl_enabled`             | `false`                | Enable TLS (see TLS section below)             |
| `mariadb_databases`               | `[]`                   | Databases to create                            |
| `mariadb_users`                   | `[]`                   | Users to create                                |
| `mariadb_backup_enabled`          | `false`                | Enable the scheduled backup                    |
| `mariadb_extra_config`            | `{}`                   | Extra `[mysqld]` options                       |

### `mariadb_repo` — Distribution packages vs. upstream

| Aspect             | `'distro'` (default)                              | `'upstream'`                            |
| ------------------ | ------------------------------------------------- | --------------------------------------- |
| Source             | Debian main, EL AppStream, Arch repo              | deb.mariadb.org / rpm.mariadb.org       |
| Available versions | One per release (EL: streams or package sets)     | Every release from a platform minimum   |
| Version selection  | `mariadb_version`                                 | `mariadb_version`                       |
| Update cadence     | Distro lifecycle                                  | Upstream release day                    |
| Debian packages    | `mariadb-server`, `mariadb-client`                | same names, `+maria~deb13` build        |
| EL packages        | `mariadb-server` / `mariadb11.8-server` (EL 10)   | `MariaDB-server`, `MariaDB-client`      |

The available major versions per platform and source:

| Platform      | `'distro'`                                       | `'upstream'`                           |
| ------------- | ------------------------------------------------ | -------------------------------------- |
| Arch Linux    | rolling (`mariadb` current, `mariadb-lts` LTS)   | not available (setting ignored)        |
| Debian Trixie | 11.8                                             | 11.8 or later                          |
| EL 9          | 10.5 (non-modular), 10.11 and 11.8 (streams)     | 10.11 or later                         |
| EL 10         | 10.11 (`mariadb-*`), 11.8 (`mariadb11.8-*`)      | 10.11 or later                         |

A version the selected source does not carry fails the run with the
available versions of both sources. Paths, service name (`mariadb`) and
the unix socket are the same for every source and version of a platform:
`/etc/mysql/mariadb.conf.d` and `/run/mysqld/mysqld.sock` on Debian,
`/etc/my.cnf.d` and `/var/lib/mysql/mysql.sock` on EL, `/etc/my.cnf.d` and
`/run/mysqld/mysqld.sock` on Arch Linux; the data directory is
`/var/lib/mysql` everywhere.

- **EL 9:** 10.11 and 11.8 are AppStream module streams. On a host without
  an enabled stream the role enables the requested one; when another
  stream is active, the run fails with the commands to switch it
  (`dnf module reset mariadb`, `dnf module enable mariadb:<version>`).
  10.5 is the non-modular default and needs no stream.
- **EL 10:** the version selects the package set; both sets use the same
  paths and service name.
- **Upstream:** the role adds the repository itself — on Debian a deb822
  source for `deb.mariadb.org/<version>/debian` signed with the MariaDB
  release signing key, on EL the `mariadb` repository for
  `rpm.mariadb.org/<version>/rhel/<release>` with `module_hotfixes`. The EL
  packages are named `MariaDB-*` and conflict with the AppStream `mariadb`
  packages; on EL 9 the role disables the AppStream `mariadb` module. The
  role checks only the platform minimum of the version; a version the
  repository does not carry fails in the package task with the message of
  the package manager.
- **Arch Linux:** `mariadb_repo` and `mariadb_version` are ignored.
  `mariadb_arch_package` selects the current release (`mariadb`) or the
  long-term support release (`mariadb-lts`); the two conflict. The role
  runs `mariadb-install-db` before the first start.

**Switching sources or versions on an installed host is a major-version
upgrade**, which the role does not perform. Before any change the role
compares the installed server package with the requested one and fails
when the name (source, EL package set) or the major version differs.
Upgrade by hand: stop the server, install the requested packages, run
`mariadb-upgrade`, then rerun the role. On Arch Linux the rolling
repository moves to a new major version with the system upgrade; the role
runs `mariadb-upgrade` after the server start on every run, which updates
the system tables when the server is newer than the version stamp of the
data directory and does nothing otherwise.

### Package Updates

| Variable                   | Default     | Description                                                       |
| -------------------------- | ----------- | ----------------------------------------------------------------- |
| `mariadb_packages_state`   | `'present'` | `present` installs missing packages only, `latest` updates them   |
| `mariadb_packages_minimum` | `''`        | Lowest acceptable server version, string or mapping per platform  |

A regular run never updates MariaDB. A targeted update, for example for a
security release, is requested on the command line:

```bash
ansible-playbook site.yml --tags mariadb \
  -e mariadb_packages_state=latest \
  -e mariadb_packages_minimum=11.8.6
```

With `latest` the role refreshes the package metadata and updates every
installed MariaDB package in one transaction, including the parts pulled in
as dependencies (on Debian `mariadb-*` and `libmariadb*`, on EL the
AppStream `mariadb*` packages or, with `mariadb_repo: 'upstream'`, the
`MariaDB-*` packages). The role reports the version change. Minor releases
only: the major version stays as selected (see above).

`mariadb_packages_minimum` is checked twice. Before the update the role asks
the package manager which version the update would install and fails without
a change when it is older than the minimum, which shows that the repository
does not carry the fix yet. After the update it checks the installed version
again; this check is skipped under `--check`.

The minimum is an upstream version (`11.8.6`, any distribution release of
it) or the full distribution version (`1:11.8.6-0+deb13u1`,
`3:11.8.8-1.module+el9.8.0+40229+87be66a2`). Debian and EL ship many fixes
as backports that only raise the release, so only the full version proves
such a fix. Versions are compared with the rules of the distribution
(`dpkg --compare-versions`, rpm, `vercmp`); a minimum without an epoch
takes the epoch of the package (1 on Debian, 3 on EL). For mixed hosts in
one run, pass a mapping per platform; the keys are `<os_family>-<major>` or
`<os_family>`, and a host without a matching key fails before any change:

```yaml
# mariadb-minimum.yml, passed with -e @mariadb-minimum.yml
mariadb_packages_minimum:
  Debian: '1:11.8.6-0+deb13u1'
  RedHat-9: '3:11.8.8-1.module+el9.8.0+40229+87be66a2'
  RedHat-10: '3:11.8.8-2.el10_2'
  Archlinux: '13.0.2'
```

The packages usually restart the server themselves. When they did not, for
example because of a `policy-rc.d`, the running server still executes the
replaced binary and the role restarts it.

On Arch Linux `mariadb_packages_state` is ignored: updating single packages
is a partial upgrade there, MariaDB updates with the full system upgrade.
Run the role with `latest` together with the system upgrade
(`--tags system-update,mariadb`) to restart the server after it; the role
then runs `mariadb-upgrade`, so a new major version gets its system tables
updated in the same run.

### Security

The root account authenticates through the unix socket plugin only: a
process running as the root OS user connects without a password, no root
password is set and no `/root/.my.cnf` is written. The anonymous users and
the `test` database with its grants are removed. The server listens on
`127.0.0.1` by default; see [Firewall](#firewall) for remote access.

### Databases and Users

```yaml
mariadb_databases:
  - name: myapp
    encoding: utf8mb4            # default: mariadb_character_set_server
    collation: utf8mb4_unicode_ci # default: mariadb_collation_server

mariadb_users:
  - name: myapp
    host: localhost              # default
    password: '{{ vault_mariadb_myapp_password }}'
    priv: 'myapp.*:ALL'          # ansible.mariadb.mariadb_user format
```

Users and databases are managed through `ansible.mariadb` over the unix
socket; the role installs PyMySQL (`python3-pymysql`, `python3-PyMySQL`,
`python-pymysql`) with the server.

### TLS

TLS is disabled by default (`mariadb_ssl_enabled: false`). Loopback
connections do not benefit from it, and a wrong certificate or key path
keeps the server from starting — the operator opts in explicitly.

| Variable                           | Default             | Description                                        |
| ---------------------------------- | ------------------- | -------------------------------------------------- |
| `mariadb_ssl_cert_file`            | `''`                | Certificate; empty falls back to the OS default    |
| `mariadb_ssl_key_file`             | `''`                | Key; empty falls back to the OS default            |
| `mariadb_ssl_ca_file`              | `''`                | CA certificate (client certificate checks)         |
| `mariadb_tls_version`              | `'TLSv1.2,TLSv1.3'` | Accepted protocol versions                         |
| `mariadb_require_secure_transport` | `false`             | Reject unencrypted TCP connections                 |

When TLS is enabled, the role asserts that certificate and key exist before
deploying the configuration. Only Debian has an OS default: the snakeoil
pair of the `ssl-cert` package (`/etc/ssl/certs/ssl-cert-snakeoil.pem`,
`/etc/ssl/private/ssl-cert-snakeoil.key`; the key is readable by the
`ssl-cert` group, add the `mysql` user to it). EL and Arch Linux have none,
set both paths, for example to a certificate issued by
`marcstraube.common.pki`. The key must be readable by the `mysql` user.

The role subscribes to the `Reload cert services` handler topic of
`marcstraube.server.certbot` and `marcstraube.common.pki` with a `FLUSH SSL`
on the running server, so a certificate issued or renewed inside the same
play takes effect in that run without a restart. Renewal through the
certbot timer runs outside of Ansible — add the MariaDB service unit to
`certbot_reload_services` for that path.

### Backup

| Variable                   | Default                  | Description                            |
| -------------------------- | ------------------------ | -------------------------------------- |
| `mariadb_backup_enabled`   | `false`                  | Enable the scheduled backup            |
| `mariadb_backup_dir`       | `'/var/backups/mariadb'` | Backup directory (mode `0700`, root)   |
| `mariadb_backup_schedule`  | `'0 3 * * *'`            | Schedule (cron format)                 |
| `mariadb_backup_retention` | `7`                      | Dumps to keep per database             |
| `mariadb_backup_databases` | `[]`                     | Databases to dump (empty = all)        |

The script `/usr/local/bin/mariadb-backup.sh` runs as root from cron and
writes one `mariadb-dump --single-transaction --routines --triggers
--events` per database, compressed with gzip, to
`<dir>/<database>_<timestamp>.sql.gz`. An empty `mariadb_backup_databases`
dumps every database except the system schemas (`information_schema`,
`performance_schema`, `mysql`, `sys`). The rotation is count-based: after
each run the newest `mariadb_backup_retention` dumps of every database
stay, so a failing schedule never removes the last good set. The dumps
hold the data of each database, not the users and grants. A cron daemon
must be installed. For encrypted offsite backups consider
`marcstraube.common.restic`.

### Extra Configuration

Options not exposed as role variables go into the `mariadb_extra_config`
dict and are rendered into the `[mysqld]` section:

```yaml
mariadb_extra_config:
  innodb_io_capacity: 2000
  sql_mode: 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION'
```

## Tags

| Tag                 | Description                                        |
| ------------------- | -------------------------------------------------- |
| `mariadb`           | All mariadb tasks                                  |
| `mariadb:install`   | Repository setup, package installation and updates |
| `mariadb:configure` | Configuration deployment                           |
| `mariadb:service`   | Systemd service management                         |
| `mariadb:users`     | Root authentication, anonymous users, users        |
| `mariadb:databases` | Test database removal, databases                   |
| `mariadb:backup`    | Backup script and cron setup                       |

## Example Playbook

```yaml
- hosts: db_servers
  become: true
  roles:
    - role: marcstraube.server.mariadb
      vars:
        mariadb_enabled: true
        mariadb_bind_address: '0.0.0.0'
        mariadb_innodb_buffer_pool_size: '1G'
        mariadb_databases:
          - name: myapp
        mariadb_users:
          - name: myapp
            host: '192.168.1.%'
            password: '{{ vault_mariadb_myapp_password }}'
            priv: 'myapp.*:ALL'
```

## Testing

```bash
# Run full test (one platform at a time)
MOLECULE_PLATFORM_NAME=mariadb-debian-trixie molecule test

# Upstream repository scenario (Arch Linux with mariadb-lts, Debian Trixie, Rocky 9, Rocky 10)
MOLECULE_PLATFORM_NAME=mariadb-upstream-rocky-10 molecule test -s upstream

# Converge only
molecule converge

# Verify only
molecule verify
```

Driver: `podman` | Scenarios: `default` (distribution packages, all
platforms, with the targeted package update), `upstream`
(`mariadb_repo: 'upstream'`, `mariadb-lts` on Arch Linux).

## Notes

### Firewall

The role does not manage firewall rules, and the server listens on
`127.0.0.1` by default. For remote access set `mariadb_bind_address` and
open the port through the `marcstraube.common.firewalld` inventory, either
as the predefined `mysql` service or as the port:

```yaml
firewalld_zone_services:
  - zone: internal
    services:
      - 'mysql'

# or
firewalld_zone_ports:
  - zone: internal
    ports:
      - '3306/tcp'
```

### Configuration Drop-In

The role deploys one file, `zz-ansible.cnf`, next to the files the packages
ship (`/etc/mysql/mariadb.conf.d` on Debian, `/etc/my.cnf.d` on EL and Arch
Linux). The name sorts after them, so the role's settings take precedence
over the package defaults; the package files are left untouched. Settings
the role does not set keep the package or compiled defaults — the error
log goes to `/var/log/mariadb/mariadb.log` on EL and to the journal on
Debian and Arch Linux unless `mariadb_log_error` is set.

### Removing State

The role never uninstalls packages and never deletes data. To remove
MariaDB from a host, stop and disable `mariadb.service`, remove the
packages, and delete `/var/lib/mysql` and the backup directory by hand.

## References

- [MariaDB Server Documentation](https://mariadb.com/kb/en/documentation/)
- [MariaDB Repositories](https://mariadb.org/download/?t=repo-config)
- [Server System Variables](https://mariadb.com/kb/en/server-system-variables/)
- [Authentication Plugin - Unix Socket](https://mariadb.com/kb/en/authentication-plugin-unix-socket/)
- [Securing Connections for Client and Server](https://mariadb.com/kb/en/securing-connections-for-client-and-server/)

## License

MIT

## Author

Marc Straube
