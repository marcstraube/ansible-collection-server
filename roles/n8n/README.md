# marcstraube.server.n8n

Run the n8n workflow automation platform as a rootless Podman container.

## Description

[n8n](https://n8n.io) is a self-hosted alternative to Zapier/Make.com with
200+ integrations. The role runs the official container image as the
dedicated `n8n` user; the data directory lives on the host.

## Requirements

- ansible-core >= 2.19
- Podman (installed by `marcstraube.common.podman` role)
- PostgreSQL (installed by `marcstraube.server.postgresql` role, if using `postgresdb`)
- TLS certificates (managed by `marcstraube.common.pki` role)

The role supports Podman only: the container runs rootless as the dedicated
`n8n` user without a daemon or a privileged group, which Docker does not
offer in the same way.

The orchestrator playbook `playbooks/servers/n8n.yml` includes all required
roles in the correct order.

### Required Collections

```yaml
collections:
  - community.general
  - community.postgresql  # If using PostgreSQL
  - ansible.posix
  - containers.podman
```

## Supported Platforms

| Platform                  | Notes |
|---------------------------|-------|
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

| Variable                 | Default       | Description                                            |
| ------------------------ | ------------- | ------------------------------------------------------ |
| `n8n_enabled`            | `false`       | Enable the n8n role                                    |
| `n8n_service_enabled`    | `true`        | Enable and start the n8n service                       |
| `n8n_version`            | pinned stable | Image tag pinned in `defaults/main.yml`                |
| `n8n_podman_image`       | `n8nio/n8n`   | Container image (`docker.io/n8nio/n8n`)                |
| `n8n_host`               | `'127.0.0.1'` | Listen address                                         |
| `n8n_port`               | `5678`        | Listen port                                            |
| `n8n_db_type`            | `'sqlite'`    | Database: `sqlite`, `postgresdb`, `mysqldb`, `mariadb` |
| `n8n_encryption_key`     | `''`          | **REQUIRED** — credential encryption key               |
| `n8n_runners_auth_token` | `''`          | **REQUIRED** — shared secret of n8n and task runners   |
| `n8n_firewalld_enabled`  | `true`        | Manage firewalld rule for n8n port                     |

### Version Pinning

`n8n_version` is the tag of the container image the role runs. The default
follows the n8n **stable** npm channel: n8n moves `latest` with every
weekly release and `stable` a few weeks later. The `update-n8n-version`
workflow checks the stable channel weekly and opens a pull request that
bumps the default once the matching image tag is published on Docker Hub.

A host keeps its version when the inventory pins `n8n_version`; a bump of
the role default then only reaches hosts without a pin. Raising the pin
updates the host on the next run (see Updates).

### Container

The container runs rootless as the `n8n` user with `--network=host`, so
n8n listens on `n8n_host:n8n_port` of the host like any other service. The
image runs n8n as its user `node` (UID 1000); `--userns=keep-id` maps the
`n8n` user onto it, so `n8n_data_dir` on the host stays owned by `n8n`.

Rootless Podman needs a subordinate ID range for the `n8n` user, which the
role writes to `/etc/subuid` and `/etc/subgid`:

| Variable                     | Default    | Description                                      |
| ---------------------------- | ---------- | ------------------------------------------------ |
| `n8n_subid_start`            | `100000`   | First subordinate UID/GID of the `n8n` user      |
| `n8n_subid_count`            | `65536`    | Size of the range                                |
| `n8n_podman_pull_policy`     | `missing`  | `missing`, `always` or `never`                   |
| `n8n_podman_network`         | `host`     | Podman network of the container                  |
| `n8n_podman_memory`          | `''`       | Memory limit (`--memory`), empty for none        |
| `n8n_podman_cpus`            | `''`       | CPU limit (`--cpus`), empty for none             |
| `n8n_podman_extra_args`      | `[]`       | Additional `podman run` arguments                |

The range must not overlap with the ranges of other users on the host.
`n8n_http_proxy` applies to the image pull and, through the environment
file, to the HTTP traffic of workflows.

### Updates

A run whose pinned version differs from the installed one is an update.
The role then:

1. stops the n8n service,
2. writes a backup set `n8n-<installed version>-<timestamp>/` to
   `n8n_update_backup_dir` with `data.tar.gz` (the data directory,
   entries relative to `n8n_user_home`) and, with `n8n_db_type:
   'postgresdb'`, `db.dump` (`pg_dump -Fc` over the local socket),
   keeping the newest `n8n_update_backup_keep` sets,
3. pulls the pinned image,
4. starts the service and waits up to `n8n_ready_timeout` seconds for
   `/healthz/readiness`, which answers 200 once the database is connected
   and migrated.

| Variable                     | Default               | Description                                   |
| ---------------------------- | --------------------- | --------------------------------------------- |
| `n8n_update_backup_enabled`  | `true`                | Backup before a version change or a restore   |
| `n8n_update_backup_dir`      | `'/var/backups/n8n'`  | Directory for the backup sets                 |
| `n8n_update_backup_keep`     | `3`                   | Backup sets to keep                           |
| `n8n_update_restore`         | `''`                  | Backup set to restore (see below)             |
| `n8n_ready_timeout`          | `300`                 | Seconds to wait for readiness after a start   |

**Downgrades** are refused: n8n migrates its database on start and the
migrations are forward-only, so an older release does not start on a
migrated database. To go back, restore the backup set taken before the
upgrade and pin its version in the same run:

```yaml
n8n_version: '2.42.0'
n8n_update_restore: 'n8n-2.42.0-20261014T120000'
```

The role backs up the current state first, replaces the data directory
from the set, recreates the PostgreSQL database from `db.dump`, pulls the
pinned image and starts n8n. The version in the set name must match
the pin. `n8n_update_restore` is a one-shot setting: remove it after the
run, otherwise the next run restores the set again.

### Task Runners

The Code node runs in task runners. n8n deprecates the internal mode, so
the role runs the task runner launcher from the `n8nio/runners` image as a
second container, `n8n-runner.service`, bound to `n8n.service` and in the
release of `n8n_version`. The launcher connects to the task broker of n8n
on `127.0.0.1:5679`; both share `n8n_runners_auth_token`, which is
**required**.

| Variable                                   | Default           | Description                                    |
| ------------------------------------------ | ----------------- | ---------------------------------------------- |
| `n8n_runners_auth_token`                   | `''`              | **REQUIRED** — shared secret with launcher     |
| `n8n_runners_broker_port`                  | `5679`            | Task broker port on localhost                  |
| `n8n_runners_health_check_port`            | `5680`            | Launcher health check port                     |
| `n8n_runners_max_concurrency`              | `5`               | Tasks a runner executes at a time              |
| `n8n_runners_task_timeout`                 | `300`             | Seconds a Code node task may run               |
| `n8n_runners_auto_shutdown_timeout`        | `15`              | Seconds an idle runner waits before it exits   |
| `n8n_runners_launcher_log_level`           | `info`            | Launcher log level                             |
| `n8n_runners_node_function_allow_builtin`  | `''`              | Node.js built-in modules the Code node may use |
| `n8n_runners_node_function_allow_external` | `''`              | External Node.js modules the Code node may use |
| `n8n_runners_stdlib_allow`                 | `''`              | Python stdlib modules the Code node may use    |
| `n8n_runners_external_allow`               | `''`              | External Python modules the Code node may use  |
| `n8n_runners_extra_env_vars`               | `{}`              | Additional launcher environment variables      |
| `n8n_runners_podman_image`                 | `n8nio/runners`   | Launcher image (`docker.io/n8nio/runners`)     |
| `n8n_runners_podman_image_tag_suffix`      | `-distroless`     | Image variant suffix of the tag, `''` = Alpine |
| `n8n_runners_podman_memory`                | `1g`              | Memory limit (`--memory`), empty for none      |
| `n8n_runners_podman_cpus`                  | `1`               | CPU limit (`--cpus`), empty for none           |
| `n8n_runners_podman_pids_limit`            | `512`             | Process limit (`--pids-limit`)                 |
| `n8n_runners_podman_tmp_size`              | `256m`            | Size of the tmpfs on `/tmp`                    |
| `n8n_runners_podman_extra_args`            | `[]`              | Additional `podman run` arguments              |

The launcher environment lives in `/etc/n8n/n8n-runner.env` and inherits
`n8n_timezone` and the outgoing proxy settings. The task broker listens on
localhost only; the launcher's health check server binds all interfaces,
so keep `n8n_runners_health_check_port` closed in the firewall.

The Code node sandbox denies every module import by default. The
`*_allow` variables take comma-separated module names or `*`; third-party
Python modules must exist in the runner image.

#### Hardening

The runners execute the code of Code nodes, so the launcher container
follows the n8n [hardening recommendations](https://docs.n8n.io/deploy/host-n8n/configure-n8n/security/harden-task-runners/):
the distroless image variant without shell and package manager, a
read-only root filesystem with a tmpfs on `/tmp`, all capabilities
dropped, `no-new-privileges`, and process, memory and CPU limits. Both
containers run rootless as the `n8n` user with keep-id, so the container
UID 1000 is the host user `n8n` and no other host user is mapped. The
n8n container drops its capabilities and privilege escalation as well.

A workflow that needs more than the limits allow raises them in the
inventory; `n8n_runners_podman_extra_args` adds options such as
`--cap-add` after the role's `--cap-drop=all`.

### Community Packages and Compression

n8n announces changed defaults for these settings at startup; the role sets
them explicitly.

| Variable                                           | Default     | Description                                      |
| -------------------------------------------------- | ----------- | ------------------------------------------------ |
| `n8n_unverified_packages_enabled`                  | `false`     | Install community nodes n8n has not verified     |
| `n8n_compression_node_max_decompressed_size_bytes` | `268435456` | Decompressed size limit of the Compression node  |
| `n8n_compression_node_max_zip_entries`             | `1000`      | Archive entry limit of the Compression node      |

### Security (Critical)

- **`n8n_encryption_key`**: Must be set. Generate with `openssl rand -base64 32`.
  Store in Ansible vault. Losing this key means losing all stored credentials.
- **`n8n_runners_auth_token`**: Must be set. Generate with `openssl rand -hex 32`
  and store it in Ansible vault.
- **`n8n_webhook_url`**: Must use HTTPS in production.
- Use PostgreSQL for production, not SQLite.
- Default listen address is localhost — use a reverse proxy for external access.

### Database Configuration

When using `n8n_db_type: postgresdb`, the `marcstraube.server.postgresql` role
must run before this role. The n8n role creates its own database and user via
`database.yml` (controlled by `n8n_db_create: true`). Required PostgreSQL
configuration (pg_hba scram-sha-256, service start) is handled by the
postgresql role.

### TLS Certificates

TLS certificates are managed by the `marcstraube.common.pki` role. Configure
`pki_server_certs` in the inventory to generate certificates for n8n. The
orchestrator playbook includes the pki role automatically.

### OpenTelemetry (n8n >= 2.15)

Set `n8n_otel_enabled: true` and point `n8n_otel_exporter_otlp_endpoint` at
an OTLP-compatible collector (Grafana Tempo, Jaeger, Datadog, Honeycomb,
New Relic, Splunk) to emit workflow-execution traces. All
`n8n_otel_*` variables are passed through to the matching `N8N_OTEL_*`
environment variables; defaults match n8n upstream. See
[defaults/main.yml](defaults/main.yml) for the full list.

### Insights Retention (n8n >= 2.20)

`n8n_insights_max_age_days` controls how long insights data is kept
(self-hosted maximum is 730 days). Leave empty to use the n8n upstream
default of 365 days.

## Tags

| Tag              | Description                        |
|------------------|------------------------------------|
| `n8n`            | All n8n tasks                      |
| `n8n:install`    | User, directories and image pulls  |
| `n8n:database`   | PostgreSQL user and database setup |
| `n8n:configure`  | Configuration deployment           |
| `n8n:service`    | Systemd service management         |
| `n8n:firewall`   | Firewalld rule management          |

## Example Playbook

```yaml
- hosts: n8n_servers
  become: true
  roles:
    - role: marcstraube.common.podman

    - role: marcstraube.server.postgresql

    - role: marcstraube.common.pki
      vars:
        pki_server_certs:
          - name: 'n8n'
            common_name: 'n8n.example.com'
            san: ['DNS:n8n.example.com']

    - role: marcstraube.server.n8n
      vars:
        n8n_encryption_key: '{{ vault_n8n_encryption_key }}'
        n8n_runners_auth_token: '{{ vault_n8n_runners_auth_token }}'
        n8n_basic_auth_password: '{{ vault_n8n_admin_password }}'
        n8n_webhook_url: 'https://n8n.example.com'
        n8n_db_type: 'postgresdb'
        n8n_db_password: '{{ vault_n8n_db_password }}'
```

## Testing

```bash
# Run full test (one platform at a time)
molecule test -p n8n-debian-trixie

# Update, downgrade guard and restore
molecule test -s update
```

The molecule instance is a rootless container itself, so the scenarios
set `n8n_subid_start` and `n8n_subid_count` to a range inside the IDs the
instance maps, and `ignore_chown_errors` in the podman storage options
because that range cannot map the UID 65532 owning `/home/nonroot` in the
distroless runner image.

## Notes

- The environment files (`/etc/n8n/n8n.env`, `/etc/n8n/n8n-runner.env`)
  contain secrets and are deployed with mode `0600`
- The container runs rootless as the dedicated `n8n` system user; the
  service unit creates `/run/n8n` as the Podman runtime directory

### Backup

This role does not manage backups. The following data must be included in your
backup solution:

| Data                          | Location             | Notes                                            |
|-------------------------------|----------------------|--------------------------------------------------|
| Workflow data and credentials | `/var/lib/n8n/.n8n`  | Encrypted with `n8n_encryption_key`              |
| PostgreSQL database           | `pg_dump -U n8n n8n` | Only if `n8n_db_type: postgresdb`                |
| Encryption key                | Ansible vault        | **Critical** — without it, credentials are lost  |

The environment files in `/etc/n8n` are managed by Ansible and do not need
to be backed up separately.

## References

- [n8n Documentation](https://docs.n8n.io)
- [n8n Community](https://community.n8n.io)
- [n8n GitHub](https://github.com/n8n-io/n8n)
- [n8n Integrations](https://n8n.io/integrations)
- [n8n Workflow Templates](https://n8n.io/workflows)

## License

MIT

## Author

Marc Straube
