# marcstraube.server.activepieces

Run the Activepieces workflow automation platform as a rootless Podman container.

## Description

[Activepieces](https://www.activepieces.com) is an open source alternative
to Zapier with several hundred integrations ("pieces"). The role runs the
official container image as the dedicated `activepieces` user, with the
API, the frontend and the worker in one container, the embedded PGlite
database or PostgreSQL, and the in-memory queue; the data directory lives
on the host.

## Requirements

- ansible-core >= 2.19
- Podman with pasta (installed by `marcstraube.common.podman` role)
- PostgreSQL (installed by `marcstraube.server.postgresql` role, if using `POSTGRES`)
- A reverse proxy with TLS on its own host name (e.g. `marcstraube.server.nginx`)

The role supports Podman only: the container runs rootless as the dedicated
`activepieces` user without a daemon or a privileged group, which Docker
does not offer in the same way.

The orchestrator playbook `marcstraube.server.activepieces` includes all
required roles in the correct order.

### Required Collections

```yaml
collections:
  - community.general
  - community.postgresql  # If using PostgreSQL
  - containers.podman
```

## Supported Platforms

| Platform                  | Notes |
| ------------------------- | ----- |
| Arch Linux                |       |
| Debian Trixie             |       |
| EL 9 (Rocky, Alma, RHEL)  |       |
| EL 10 (Rocky, Alma, RHEL) |       |

Other distributions in the same os_family (EndeavourOS, Manjaro, Ubuntu, Mint,
Fedora) should work but are not actively tested. Use distro-specific vars
overrides if needed.

## Role Variables

See [defaults/main.yml](defaults/main.yml) for all available variables.

### Key Variables

| Variable                       | Default                     | Description                                   |
| ------------------------------ | --------------------------- | --------------------------------------------- |
| `activepieces_enabled`         | `false`                     | Enable the activepieces role                  |
| `activepieces_service_enabled` | `true`                      | Enable and start the activepieces service     |
| `activepieces_version`         | pinned release              | Image tag pinned in `defaults/main.yml`       |
| `activepieces_podman_image`    | `activepieces/activepieces` | Container image on Docker Hub                 |
| `activepieces_port`            | `8080`                      | Port on `127.0.0.1` (`AP_PORT`)               |
| `activepieces_frontend_url`    | `''`                        | **REQUIRED** — public URL (`AP_FRONTEND_URL`) |
| `activepieces_db_type`         | `'PGLITE'`                  | Database: `PGLITE` or `POSTGRES`              |
| `activepieces_encryption_key`  | `''`                        | **REQUIRED** — connection encryption key      |
| `activepieces_jwt_secret`      | `''`                        | **REQUIRED** — token signing secret           |
| `activepieces_execution_mode`  | `'SANDBOX_CODE_ONLY'`       | Isolation of flow code (`AP_EXECUTION_MODE`)  |

### Version Pinning

`activepieces_version` is the tag of the container image the role runs:
a release (`0.92.3`) or a hotfix of a release (`0.92.3-hotfix.2`). The
default follows the latest GitHub release of Activepieces. The
`update-activepieces-version` workflow checks it weekly and opens a pull
request that bumps the default once the matching image tag is published on
Docker Hub.

A host keeps its version when the inventory pins `activepieces_version`;
a bump of the role default then only reaches hosts without a pin. Raising
the pin updates the host on the next run (see Updates).

### Container

The container runs rootless as the `activepieces` user in its own network
namespace (pasta). Activepieces binds all addresses of that namespace, so
`--network=host` is not an option: it would expose the port on every
interface of the host. The role publishes `activepieces_port` on
`127.0.0.1` of the host only, and a reverse proxy serves it on its own host
name. The image runs Activepieces as `root`; `--userns=keep-id` maps the
`activepieces` user onto container UID 0, so `activepieces_data_dir` on the
host stays owned by `activepieces`. The container drops all capabilities and
privilege escalation.

Rootless Podman needs a subordinate ID range for the `activepieces` user,
which the role writes to `/etc/subuid` and `/etc/subgid`:

| Variable                          | Default   | Description                                          |
| --------------------------------- | --------- | ---------------------------------------------------- |
| `activepieces_subid_start`        | `165536`  | First subordinate UID/GID of the `activepieces` user |
| `activepieces_subid_count`        | `65536`   | Size of the range                                    |
| `activepieces_podman_pull_policy` | `missing` | `missing`, `always` or `never`                       |
| `activepieces_podman_memory`      | `''`      | Memory limit (`--memory`), empty for none            |
| `activepieces_podman_cpus`        | `''`      | CPU limit (`--cpus`), empty for none                 |
| `activepieces_podman_extra_args`  | `[]`      | Additional `podman run` arguments                    |

The range must not overlap with the ranges of other users on the host; the
default starts after the default range of the `n8n` role.

The data directory (`activepieces_data_dir`, `AP_CONFIG_PATH` in the
container) holds the PGlite database and the instance settings. The piece
cache of the worker lives in `/var/lib/activepieces/cache`, survives
restarts and is not part of the backup.

### Updates

A run whose pinned version differs from the installed one is an update.
The role then:

1. stops the Activepieces service,
2. runs the backup script for a pre-update set
   `activepieces-<installed version>-<timestamp>/` in
   `activepieces_backup_dir` (see Backup), keeping the newest
   `activepieces_backup_update_keep` pre-update sets,
3. pulls the pinned image,
4. starts the service and waits up to `activepieces_ready_timeout` seconds
   for `/api/v1/health`, which answers 200 once the database is connected
   and migrated,
5. removes the images of the other releases from the Podman storage of
   the `activepieces` user (`activepieces_update_remove_old_images`): every
   tag of `activepieces_podman_image` except the one the service runs.
   Images of other containers are not touched, and there is no
   `podman image prune`.

Each release keeps about 1.5 GB of image, so without the removal the
storage grows with every update. The removal runs only after the health
check has passed: a failed update keeps the previous image. A restore needs
no local copy of the older image, the role pulls it again.

| Variable                                | Default | Description                              |
| --------------------------------------- | ------- | ---------------------------------------- |
| `activepieces_update_restore`           | `''`    | Backup set to restore (see below)        |
| `activepieces_update_remove_old_images` | `true`  | Remove the images of other releases      |
| `activepieces_ready_timeout`            | `300`   | Seconds to wait for health after a start |
| `activepieces_service_start_timeout`    | `300`   | Start timeout of the unit (seconds)      |

**Downgrades** are refused: Activepieces migrates its database on start and
the migrations are forward-only, so an older release does not start on a
migrated database. A hotfix counts as newer than its release
(`0.92.3-hotfix.2` after `0.92.3`). To go back, restore the backup set
taken before the upgrade (or a scheduled set of that release) and pin its
version in the same run:

```yaml
activepieces_version: '0.91.4'
activepieces_update_restore: 'activepieces-0.91.4-20261014T120000'
```

The role backs up the current state first, replaces the data directory
from the set, recreates the PostgreSQL database from `db.dump`, pulls the
pinned image again (the update removed it) and starts Activepieces; once it
is healthy, the images of the newer release are removed in turn. The
version in the set name must match the pin. `activepieces_update_restore`
is a one-shot setting: remove it after the run, otherwise the next run
restores the set again.

### Backup

The role deploys `/usr/local/bin/activepieces-backup`, which writes one
backup set: a subdirectory of `activepieces_backup_dir` with `data.tar.gz`
(the data directory, entries relative to its parent) and, with
`activepieces_db_type: 'POSTGRES'`, `db.dump` (`pg_dump -Fc` over the local
socket). The version in the set name is the image tag of the deployed
service unit. There are two kinds of sets with a count-based retention
each, so a scheduled set never pushes out the set taken before the last
update, and a failing timer never removes the last good set:

| Kind       | Set name                                       | Written by | Kept                              |
| ---------- | ---------------------------------------------- | ---------- | --------------------------------- |
| scheduled  | `activepieces-scheduled-<version>-<timestamp>` | the timer  | `activepieces_backup_keep`        |
| pre-update | `activepieces-<version>-<timestamp>`           | the update | `activepieces_backup_update_keep` |

A scheduled set is taken with Activepieces stopped
(`activepieces_backup_stop_service`), so the PGlite database and the data
directory are copied in a consistent state. The service starts again when
the script exits, also after a failed dump. With
`activepieces_backup_stop_service: false` the set is taken from the running
instance: the PostgreSQL dump is consistent on its own, the archive of a
running PGlite database is not. `activepieces-backup.service` is a oneshot
unit, so `systemctl start activepieces-backup.service` takes a scheduled
set at any time and returns once the set is written;
`activepieces-backup update` takes a pre-update set instead (the update
calls it with Activepieces stopped).

| Variable                            | Default                       | Description                                  |
| ----------------------------------- | ----------------------------- | -------------------------------------------- |
| `activepieces_backup_enabled`       | `true`                        | Scheduled sets and the pre-update set        |
| `activepieces_backup_dir`           | `'/var/backups/activepieces'` | Directory for the backup sets                |
| `activepieces_backup_keep`          | `7`                           | Scheduled sets to keep                       |
| `activepieces_backup_update_keep`   | `3`                           | Pre-update sets to keep                      |
| `activepieces_backup_stop_service`  | `true`                        | Stop Activepieces while a set is written     |
| `activepieces_backup_timer_enabled` | `true`                        | Enable and start `activepieces-backup.timer` |
| `activepieces_backup_on_calendar`   | `'daily'`                     | Schedule of the timer (systemd `OnCalendar`) |

`activepieces_backup_enabled: false` stops the timer and skips the
pre-update set; the script, the units and the existing sets stay. The role
never removes a set other than through the retention of its kind.

A host backup takes the sets instead of the running data directory: it
runs `systemctl start activepieces-backup.service` as its pre-sync step and
copies `activepieces_backup_dir`. The sets are only as useful as
`activepieces_encryption_key`, which stays in the Ansible vault.

### Database

`activepieces_db_type: 'PGLITE'` (default) runs the embedded PGlite
database in the data directory: no database server, a single instance on
one host. `POSTGRES` connects to a PostgreSQL server; the
`marcstraube.server.postgresql` role must run before this role. With
`activepieces_db_create: true` the role creates the user and the database
(UTF-8, owned by the user) through `community.postgresql`; the migrations
create an ICU collation, which the database owner may do. Activepieces
creates the `vector` extension for its knowledge base when the server
offers pgvector and the user may create it, and starts without the
knowledge base otherwise.

| Variable                   | Default          | Description                               |
| -------------------------- | ---------------- | ----------------------------------------- |
| `activepieces_db_type`     | `'PGLITE'`       | `PGLITE` or `POSTGRES` (`AP_DB_TYPE`)     |
| `activepieces_db_host`     | `'localhost'`    | PostgreSQL host                           |
| `activepieces_db_port`     | `5432`           | PostgreSQL port                           |
| `activepieces_db_name`     | `'activepieces'` | Database name                             |
| `activepieces_db_user`     | `'activepieces'` | Database user                             |
| `activepieces_db_password` | `''`             | **REQUIRED** with `POSTGRES`              |
| `activepieces_db_ssl`      | `false`          | TLS to PostgreSQL (`AP_POSTGRES_USE_SSL`) |
| `activepieces_db_create`   | `true`           | Create the user and the database          |
| `activepieces_db_service`  | `''`             | Local PostgreSQL unit (empty: detect)     |

A server on the host itself (`localhost`, `127.0.0.1` or `::1`) is reached
through a pasta port forward (`-T`) from the loopback of the container to
the loopback of the host, so PostgreSQL keeps listening on `localhost` and
the `host` lines for `127.0.0.1/32` and `::1/128` in `pg_hba.conf` apply.
The unit then requires the PostgreSQL unit of the host: the role detects
`postgresql.service` or, with the PGDG packages on Rocky Linux,
`postgresql-<version>.service`. With several versions installed, set
`activepieces_db_service` to the unit Activepieces depends on.

### Execution and Queue

`activepieces_execution_mode` sets `AP_EXECUTION_MODE`:

| Value               | Isolation                                                    |
| ------------------- | ------------------------------------------------------------ |
| `SANDBOX_CODE_ONLY` | Code steps run in a V8 isolate, no npm packages (default)    |
| `UNSANDBOXED`       | No isolation, npm packages in code steps; single tenant only |

The kernel namespace modes (`SANDBOX_PROCESS`, `SANDBOX_CODE_AND_PROCESS`)
need a privileged container: their sandbox fails to set up its boxes
without capabilities, so the role refuses them. The queue runs in memory
(`AP_REDIS_TYPE=MEMORY`), which supports a single instance without Redis.

### Security (Critical)

- **`activepieces_encryption_key`**: Must be set, 32 hexadecimal characters.
  Generate with `openssl rand -hex 16` and store it in the Ansible vault.
  Losing it means losing all stored connections.
- **`activepieces_jwt_secret`**: Must be set. Generate with
  `openssl rand -hex 32` and store it in the Ansible vault.
- **`activepieces_frontend_url`**: Must be set to the public URL; webhook
  and OAuth redirect URLs are built from it.
- The first account created in the web interface becomes the platform
  administrator; create it right after the first deployment.

### Other Settings

| Variable                         | Default | Description                             |
| -------------------------------- | ------- | --------------------------------------- |
| `activepieces_telemetry_enabled` | `false` | Send telemetry (`AP_TELEMETRY_ENABLED`) |
| `activepieces_extra_env`         | `{}`    | Additional `AP_*` environment variables |

### Reverse Proxy

Activepieces serves its frontend, its API (`/api`) and the WebSocket of the
editor (`/api/socket.io`) from the root of one host name and cannot be
served under a URL path prefix, so the reverse proxy gets a host name of its
own. `activepieces_frontend_url` is that host name; the role refuses a
value with a path. The proxy forwards WebSocket upgrades and keeps
long-lived connections open.

An `nginx_sites` entry for `marcstraube.server.nginx`:

```yaml
nginx_sites:
  - name: 'activepieces.example.com'
    server_names:
      - 'activepieces.example.com'
    type: 'proxy'
    proxy_pass: 'http://127.0.0.1:8080'
    websocket: true
    client_max_body_size: '25m'
    ssl:
      enabled: true
      certificate: '/etc/ssl/certs/activepieces.crt'
      certificate_key: '/etc/ssl/private/activepieces.key'
    http_redirect: true
```

`client_max_body_size` matches the default file size limit of Activepieces
(25 MB).

## Tags

| Tag                      | Description                                      |
| ------------------------ | ------------------------------------------------ |
| `activepieces`           | All Activepieces tasks                           |
| `activepieces:backup`    | Backup script, service and timer                 |
| `activepieces:install`   | Version change, user, directories and image pull |
| `activepieces:database`  | PostgreSQL user and database setup               |
| `activepieces:configure` | Environment file and SELinux port label          |
| `activepieces:service`   | Systemd service, health check and image cleanup  |

The update tasks share `activepieces:install`, so a new image is never
pulled without the downgrade guard, the stop and the pre-update set.

## Example Playbook

```yaml
- hosts: activepieces_servers
  become: true
  roles:
    - role: marcstraube.common.podman

    - role: marcstraube.server.postgresql

    - role: marcstraube.server.activepieces
      vars:
        activepieces_frontend_url: 'https://activepieces.example.com'
        activepieces_encryption_key: '{{ vault_activepieces_encryption_key }}'
        activepieces_jwt_secret: '{{ vault_activepieces_jwt_secret }}'
        activepieces_db_type: 'POSTGRES'
        activepieces_db_password: '{{ vault_activepieces_db_password }}'

    - role: marcstraube.server.nginx
```

## Testing

```bash
# Run full test (one platform at a time)
molecule test -p activepieces-debian-trixie

# PostgreSQL on the host instead of PGlite
molecule test -s postgres -p activepieces-postgres-debian-trixie

# Update, image cleanup, downgrade guard and restore
molecule test -s update
```

The molecule instance is a rootless container itself, so the scenarios set
`activepieces_subid_start` and `activepieces_subid_count` to a range inside
the IDs the instance maps.

All scenarios run `activepieces-backup.service` twice with
`activepieces_backup_keep: 1` in their side effect and verify that exactly
one scheduled set remains, with the archive of the data directory and,
in the `postgres` scenario, the database dump. The update scenario
verifies that the pre-update set of the update survives the scheduled
retention, refuses a downgrade and restores the pre-update set.

## Notes

- The environment file (`/etc/activepieces/activepieces.env`) contains
  secrets and is deployed with mode `0600`
- The container runs rootless as the dedicated `activepieces` system user;
  the service unit creates `/run/user/<uid>` of that user as the Podman
  runtime directory, the path the AppArmor profile of pasta allows for the
  network namespace of the container

### Firewall

Activepieces listens on `127.0.0.1` only and needs no firewall rule of its
own. The reverse proxy in front of it serves HTTPS (and HTTP for the
redirect), which the `marcstraube.common.firewalld` inventory opens:

```yaml
firewalld_services:
  - ssh
  - http
  - https
```

Never open `activepieces_port`: the reverse proxy is the only client.

### Host Backup

The role writes its backup sets to `activepieces_backup_dir` (see Backup);
a host backup copies that directory after
`systemctl start activepieces-backup.service` rather than the running data
directory:

| Data           | Location                    | Notes                                           |
| -------------- | --------------------------- | ----------------------------------------------- |
| Backup sets    | `/var/backups/activepieces` | Data directory archive and PostgreSQL dump      |
| Encryption key | Ansible vault               | **Critical** — without it, connections are lost |

The environment file in `/etc/activepieces` is managed by Ansible and does
not need to be backed up separately.

## References

- [Activepieces Documentation](https://www.activepieces.com/docs)
- [Environment Variables](https://www.activepieces.com/docs/install/reference/environment-variables)
- [Sandboxing](https://www.activepieces.com/docs/install/configure-operate/sandboxing)
- [Activepieces GitHub](https://github.com/activepieces/activepieces)

## License

MIT

## Author

Marc Straube
