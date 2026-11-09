# Ansible Role: wazuh_server

Install and configure a Wazuh all-in-one server: Wazuh indexer, Wazuh
manager, Filebeat and Wazuh dashboard on a single host.

The role installs pinned package versions from the Wazuh repository and
deploys TLS certificates it receives as file paths. It does not generate
certificates; [marcstraube.common.pki](https://github.com/marcstraube/ansible-collection-common/tree/develop/roles/pki)
is the documented way to issue them (see [Certificates](#certificates)).

## Requirements

- ansible-core >= 2.19
- 4 vCPU, 8 GiB RAM and 50 GB storage for up to 25 agents (upstream sizing)

### Required Collections

```yaml
collections:
  - community.crypto
  - community.general
```

## Supported Platforms

| Platform                  | Notes |
| ------------------------- | ----- |
| Debian Trixie             |       |
| EL 9 (Rocky, Alma, RHEL)  |       |
| EL 10 (Rocky, Alma, RHEL) |       |

Arch Linux is not supported: Wazuh ships no packages for it.

Other distributions in the same os_family (Ubuntu, Mint, Fedora) should work
but are not actively tested. Use distro-specific vars overrides if needed.

## Role Variables

### Role Control

| Variable               | Default | Description                  |
| ---------------------- | ------- | ---------------------------- |
| `wazuh_server_enabled` | `false` | Enable the wazuh_server role |

### Installation

| Variable                               | Default     | Description                                          |
| -------------------------------------- | ----------- | ---------------------------------------------------- |
| `wazuh_server_version`                 | `'4.14.10'` | Wazuh release (indexer, manager, dashboard packages) |
| `wazuh_server_filebeat_version`        | `'7.10.2'`  | Filebeat OSS release supported by the Wazuh module   |
| `wazuh_server_filebeat_module_version` | `'0.5'`     | Wazuh Filebeat module release                        |

The role does not update Wazuh. With Wazuh installed, a
`wazuh_server_version` that differs from the installed indexer, manager or
dashboard, or a `wazuh_server_filebeat_version` that differs from the
installed Filebeat, fails the run with both versions. The packages are
locked against a system upgrade, see [Package Lock](#package-lock) under
Notes.

### Certificates

| Variable                           | Default                       | Description                         |
| ---------------------------------- | ----------------------------- | ----------------------------------- |
| `wazuh_server_ca_cert_file`        | `''`                          | CA certificate (required)           |
| `wazuh_server_node_cert_file`      | `''`                          | Indexer node certificate (required) |
| `wazuh_server_node_key_file`       | `''`                          | Indexer node key (required)         |
| `wazuh_server_admin_cert_file`     | `''`                          | Admin client certificate (required) |
| `wazuh_server_admin_key_file`      | `''`                          | Admin client key (required)         |
| `wazuh_server_dashboard_cert_file` | `wazuh_server_node_cert_file` | Dashboard HTTPS certificate         |
| `wazuh_server_dashboard_key_file`  | `wazuh_server_node_key_file`  | Dashboard HTTPS key                 |

### Credentials

| Variable                                     | Default | Description                                                 |
| -------------------------------------------- | ------- | ----------------------------------------------------------- |
| `wazuh_server_indexer_admin_password`        | `''`    | Indexer `admin`: dashboard, Filebeat, manager (required)    |
| `wazuh_server_indexer_kibanaserver_password` | `''`    | Indexer user `kibanaserver`: dashboard backend (required)   |
| `wazuh_server_api_wazuh_password`            | `''`    | Wazuh API user `wazuh`: administrator (required)            |
| `wazuh_server_api_wui_password`              | `''`    | Wazuh API user `wazuh-wui`: dashboard API access (required) |

Keep the passwords in an Ansible Vault. The Wazuh API requires 8 to 64
characters with upper and lower case letters, a digit and a symbol for
both `wazuh_server_api_*_password`. See [Credentials](#credentials-1).

### Wazuh Indexer

| Variable                               | Default       | Description                                             |
| -------------------------------------- | ------------- | ------------------------------------------------------- |
| `wazuh_server_indexer_service_enabled` | `true`        | Enable and start the Wazuh indexer service              |
| `wazuh_server_indexer_network_host`    | `'127.0.0.1'` | Bind address of the indexer                             |
| `wazuh_server_indexer_http_port`       | `9200`        | REST API port                                           |
| `wazuh_server_indexer_node_name`       | `'node-1'`    | Node name                                               |
| `wazuh_server_indexer_cluster_name`    | `'wazuh'`     | Cluster name                                            |
| `wazuh_server_indexer_heap_size`       | `''`          | JVM heap (`Xms`/`Xmx`), empty keeps the package default |

### Indexer Snapshots

| Variable                                   | Default       | Description                                         |
| ------------------------------------------ | ------------- | --------------------------------------------------- |
| `wazuh_server_indexer_snapshot_path`       | `''`          | Snapshot directory (`path.repo`), empty disables    |
| `wazuh_server_indexer_snapshot_repository` | `'local'`     | Name of the filesystem snapshot repository          |
| `wazuh_server_indexer_snapshot_schedule`   | `'0 2 * * *'` | Cron schedule of the snapshot management policy     |
| `wazuh_server_indexer_snapshot_timezone`   | `'UTC'`       | Time zone of the schedule                           |
| `wazuh_server_indexer_snapshot_max_count`  | `14`          | Snapshots to keep, the oldest beyond it are deleted |

See [Snapshots](#snapshots) under Notes.

### Wazuh Manager, Filebeat and Dashboard

| Variable                                   | Default          | Description                                  |
| ------------------------------------------ | ---------------- | -------------------------------------------- |
| `wazuh_server_manager_service_enabled`     | `true`           | Enable and start the Wazuh manager service   |
| `wazuh_server_filebeat_service_enabled`    | `true`           | Enable and start the Filebeat service        |
| `wazuh_server_dashboard_service_enabled`   | `true`           | Enable and start the Wazuh dashboard service |
| `wazuh_server_dashboard_server_host`       | `'0.0.0.0'`      | Dashboard bind address                       |
| `wazuh_server_dashboard_server_port`       | `443`            | Dashboard HTTPS port                         |
| `wazuh_server_dashboard_enrollment_dns`    | `''`             | Agent enrollment address, empty for none     |
| `wazuh_server_dashboard_session_ttl`       | `900000`         | Login session and cookie lifetime in ms      |
| `wazuh_server_dashboard_session_keepalive` | `true`           | Extend the session on every request          |
| `wazuh_server_dashboard_default_route`     | `'/app/wz-home'` | Page the dashboard opens after the login     |

The dashboard offers `wazuh_server_dashboard_enrollment_dns` in the
"Deploy new agent" wizard and puts it into the generated install command.
The role owns the dashboard plugin configuration (`wazuh.yml`), so set the
address here instead of in the dashboard: the next run replaces a value set
in the dashboard.

`wazuh_server_dashboard_session_ttl` sets both the session and its cookie,
so a session never outlives its cookie or the other way round. With
`wazuh_server_dashboard_session_keepalive`, every request extends the
session, so it ends only after that time without activity.

### Agent Enrollment

| Variable                                | Default | Description                                         |
| --------------------------------------- | ------- | --------------------------------------------------- |
| `wazuh_server_enrollment_password`      | `''`    | Enrollment password, empty accepts every agent      |
| `wazuh_server_enrollment_agent_ca_file` | `''`    | CA of the agent certificates, empty for none        |
| `wazuh_server_enrollment_verify_host`   | `false` | Match the agent certificate CN to the agent address |

See [Enrollment Authentication](#enrollment-authentication) under Notes.

### Outgoing Proxy

| Variable                   | Default                   | Description                                      |
| -------------------------- | ------------------------- | ------------------------------------------------ |
| `wazuh_server_http_proxy`  | `''`                      | HTTP proxy of the manager, empty for none        |
| `wazuh_server_https_proxy` | `wazuh_server_http_proxy` | HTTPS proxy of the manager                       |
| `wazuh_server_no_proxy`    | `'localhost,127.0.0.1'`   | Additional hosts that bypass the proxy           |

See [Outgoing Proxy](#outgoing-proxy-1) under Notes.

## Tags

| Tag                      | Description                           |
| ------------------------ | ------------------------------------- |
| `wazuh-server`           | All wazuh_server tasks                |
| `wazuh-server:install`   | Repository and package installation   |
| `wazuh-server:certs`     | Certificate deployment                |
| `wazuh-server:configure` | Configuration deployment              |
| `wazuh-server:service`   | Systemd service management            |
| `wazuh-server:security`  | Indexer users and Wazuh API passwords |
| `wazuh-server:snapshots` | Snapshot repository and policy        |

## Example Playbook

```yaml
- hosts: wazuh_servers
  become: true
  vars:
    pki_ca_enabled: true
    pki_server_certs:
      - name: 'wazuh-node'
        common_name: 'wazuh.example.com'
        san:
          - 'DNS:wazuh.example.com'
          - 'IP:127.0.0.1'
        sign_with_ca: true
    pki_client_certs:
      - name: 'wazuh-admin'
        common_name: 'admin'

    wazuh_server_enabled: true
    wazuh_server_ca_cert_file: '/etc/ssl/ca/certs/ca.crt'
    wazuh_server_node_cert_file: '/etc/ssl/certs/wazuh-node.crt'
    wazuh_server_node_key_file: '/etc/ssl/private/wazuh-node.key'
    wazuh_server_admin_cert_file: '/etc/ssl/certs/wazuh-admin.crt'
    wazuh_server_admin_key_file: '/etc/ssl/private/wazuh-admin.key'
    wazuh_server_indexer_admin_password: '{{ vault_wazuh_server_indexer_admin_password }}'
    wazuh_server_indexer_kibanaserver_password: '{{ vault_wazuh_server_indexer_kibanaserver_password }}'
    wazuh_server_api_wazuh_password: '{{ vault_wazuh_server_api_wazuh_password }}'
    wazuh_server_api_wui_password: '{{ vault_wazuh_server_api_wui_password }}'
  roles:
    - marcstraube.common.pki
    - marcstraube.server.wazuh_server
```

The paths above are the pki defaults (`pki_ca_dir`, `pki_certs_dir`,
`pki_private_dir`). The collection playbook
`marcstraube.server.wazuh_server` runs the same stack on the
`wazuh_servers` group.

## Testing

```bash
# Run full test (one platform at a time)
molecule test -p wazuh-server-rocky-10

# Converge only
molecule converge -p wazuh-server-rocky-10
```

Driver: `podman` | Scenario: `default` (certificates issued by
`marcstraube.common.pki` in `prepare.yml`). The scenario runs with an
outgoing proxy that is never contacted; `side_effect.yml` removes the
proxy, checks that the drop-in is gone and sets it again.

## Notes

### Package Lock

After the install the role holds `wazuh-indexer`, `wazuh-manager`,
`filebeat` and `wazuh-dashboard` at the installed version on every run
(`dpkg` hold on Debian, `dnf versionlock` on EL). A system upgrade
(`apt upgrade`, `dnf upgrade`) leaves these packages untouched, so it can
neither update them outside the upstream order nor make the next run fail
the version check. The role never releases the locks.

For a planned update, release the locks on the host and follow the Wazuh
upgrade guide (see References):

```bash
# Debian
apt-mark unhold wazuh-indexer wazuh-manager filebeat wazuh-dashboard

# EL
dnf versionlock delete wazuh-indexer wazuh-manager filebeat wazuh-dashboard
```

Afterwards set `wazuh_server_version` (and `wazuh_server_filebeat_version`,
if the new release requires another Filebeat) to the installed versions.
The next run passes the version check and sets the locks again.

### Certificates

All certificates must come from one CA. The role copies them into the
certificate directory of each component (`/etc/wazuh-indexer/certs`,
`/etc/filebeat/certs`, `/etc/wazuh-dashboard/certs`, `/var/ossec/etc` for
agent enrollment), because the indexer
only reads certificates inside its configuration directory, and converts
the indexer keys to PKCS#8. The subjects of the node and admin certificates
become `plugins.security.nodes_dn` and `plugins.security.authcz.admin_dn`.

A changed source file changes the copy and restarts the component, so a
renewed certificate needs no extra handler.

### Credentials

After starting the services, the role checks whether the indexer users and
the Wazuh API users accept the configured passwords. Only when they do not,
on the first run or after a password change, it:

- writes `internal_users.yml` with `admin` and `kibanaserver` (the demo
  users of the package are removed) and uploads the security configuration
  with `securityadmin.sh`, authenticated by the admin certificate
- changes the passwords of the Wazuh API users `wazuh` and `wazuh-wui`
  through the API, starting from the package defaults

Filebeat (`/etc/filebeat/filebeat.yml`, `0600`), the dashboard
(`opensearch_dashboards.yml`, `0640`) and the dashboard plugin
(`wazuh.yml`, `0640`) receive the passwords in their configuration files.
The dashboard keystore is not used: its values cannot be read back, so a
changed password could not be detected. The role removes the default
`kibanaserver` credentials the dashboard package seeds into its keystore,
because keystore entries take precedence over `opensearch_dashboards.yml`.

The manager reads its indexer credentials only from its keystore
(`wazuh-keystore -f indexer`), which the package leaves at
`admin`/`admin`. The role writes the `admin` user and
`wazuh_server_indexer_admin_password` there, the account Filebeat uses as
well, and restarts the manager. Because the keystore cannot be read back,
the role records a SHA-512 hash of the written credentials in
`/var/ossec/etc/indexer-keystore.sha512` (`0600`, root) and writes the
keystore again only when the hash differs, on the first run or after a
password change.

### Enrollment Authentication

The enrollment service `wazuh-authd` accepts every agent by default. The
role sets its options in the `<auth>` section of the package
`/var/ossec/etc/ossec.conf` and, apart from the indexer address (see
[Outgoing Proxy](#outgoing-proxy-1)), leaves the rest of the file to the
package:

- With `wazuh_server_enrollment_password`, agents have to send the password
  (`use_password`), which the role writes to `/var/ossec/etc/authd.pass`
  (`0640 root:wazuh`). Set the same password in
  `wazuh_agent_enrollment_password` of `marcstraube.common.wazuh_agent`.
- With `wazuh_server_enrollment_agent_ca_file`, agents have to present a
  certificate issued by this CA (`ssl_agent_ca`), set with
  `wazuh_agent_enrollment_cert_file` and `wazuh_agent_enrollment_key_file`.
  Password and certificate can be combined.
- `wazuh-authd` serves the node certificate instead of the self-signed
  certificate it generates on installation, so agents verify the manager
  with `wazuh_agent_enrollment_ca_cert_file` set to the CA of
  `wazuh_server_ca_cert_file`.

A changed option restarts the Wazuh manager. After setting the options, the
role checks that the `<auth>` section contains them and fails otherwise,
for example when a Wazuh release changes the format of `ossec.conf`.

### Outgoing Proxy

The manager downloads vulnerability content from the Wazuh CTI API
(`cti.wazuh.com`). `ossec.conf` has no proxy option; the manager daemons
take `http_proxy`, `https_proxy` and `no_proxy` from the environment of
the `wazuh-manager` service. With `wazuh_server_http_proxy` set, the role
deploys the drop-in `/etc/systemd/system/wazuh-manager.service.d/proxy.conf`
with the three variables in upper and lower case, reloads systemd and
restarts the manager. An empty proxy removes the drop-in and restarts the
manager without it.

The manager also connects to the indexer to store the vulnerability
state. The role sets this connection in `<indexer><hosts><host>` of
`ossec.conf` to `https://<wazuh_server_indexer_network_host>:<wazuh_server_indexer_http_port>`,
the address Filebeat and the dashboard use, with an IPv6 address in
brackets. It removes the `<certificate>` and `<key>` elements the package
points to a Filebeat client certificate the role does not deploy: the
manager logs in with its keystore credentials and verifies the indexer
against the CA. Afterwards the role checks the `<indexer>` section and
fails if the host differs or a client certificate is still set. A change
restarts the manager.

That connection must not go through the proxy. libcurl matches `no_proxy`
against the host name as written in the URL, so the role writes
`wazuh_server_no_proxy` plus `wazuh_server_indexer_network_host` (without
duplicates) to the drop-in. `wazuh_server_no_proxy` only needs the other
hosts the manager reaches directly:

```yaml
wazuh_server_http_proxy: 'http://proxy.example.com:3128'
wazuh_server_no_proxy: 'localhost,127.0.0.1,wazuh-mirror.example.com'
```

The indexer certificate (`wazuh_server_node_cert_file`) has to cover
`wazuh_server_indexer_network_host` in its subject alternative names,
because Filebeat, the dashboard and the manager verify it against that
address.

The manager starts without contacting the proxy; a content download that
fails is logged in `/var/ossec/logs/ossec.log` and retried with the next
update interval.

### Snapshots

With `wazuh_server_indexer_snapshot_path` the role creates the directory
for the indexer user, renders it as `path.repo` in `opensearch.yml` (a
changed path restarts the indexer), registers it as the filesystem
snapshot repository `wazuh_server_indexer_snapshot_repository` and creates
the snapshot management policy `wazuh` with the schedule and the retention.
The policy takes a snapshot of all indices on every run of the schedule,
including the saved objects of the dashboard, and deletes the oldest
snapshots beyond `wazuh_server_indexer_snapshot_max_count` on the same
schedule. Snapshot names start with `wazuh-` followed by the date. The
indexer API requests authenticate with the admin certificate.

- A file-level backup of the snapshot directory must not run while a
  snapshot is in progress: the repository is only consistent between
  snapshots. Schedule the backup apart from the policy or check
  `GET _snapshot/<repository>/_current` first.
- An empty path deletes the policy and deregisters the repository named
  by the current variables; `path.repo` is left out. The directory and
  the snapshots in it stay on disk; remove them manually when they are no
  longer needed.
- Renaming the repository registers a new one; the previously registered
  repository with its snapshots stays in place. Deregister it manually
  with `DELETE _snapshot/<old name>` when the old snapshots are no longer
  needed.
- The role restores nothing. Restore a snapshot with
  `POST _snapshot/<repository>/<snapshot>/_restore` and the indices to
  restore; see the OpenSearch documentation under References.

### Firewall

The role does not manage firewall rules. Open the Wazuh ports through the
`marcstraube.common.firewalld` inventory:

```yaml
firewalld_zone_ports:
  - zone: public
    ports:
      - '1514/tcp'   # Agent connection
      - '1515/tcp'   # Agent enrollment
      - '443/tcp'    # Dashboard
```

Port `55000/tcp` (Wazuh server API) is only needed when the API is used
from other hosts; the dashboard reaches it locally. The indexer (`9200/tcp`)
binds to loopback by default.

## References

- [Wazuh Documentation](https://documentation.wazuh.com/current/)
- [Wazuh Installation Guide](https://documentation.wazuh.com/current/installation-guide/)
- [Wazuh Upgrade Guide](https://documentation.wazuh.com/current/upgrade-guide/)
- [Wazuh Ansible Deployment](https://documentation.wazuh.com/current/deployment-options/deploying-with-ansible/guide/index.html)
- [OpenSearch Snapshots](https://docs.opensearch.org/latest/tuning-your-cluster/availability-and-recovery/snapshots/snapshot-restore/)
- [OpenSearch Snapshot Management API](https://docs.opensearch.org/latest/tuning-your-cluster/availability-and-recovery/snapshots/sm-api/)

## License

MIT

## Author

Marc Straube
