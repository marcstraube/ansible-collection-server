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

| Variable                               | Default    | Description                                          |
| -------------------------------------- | ---------- | ---------------------------------------------------- |
| `wazuh_server_version`                 | `'4.14.9'` | Wazuh release (indexer, manager, dashboard packages) |
| `wazuh_server_filebeat_version`        | `'7.10.2'` | Filebeat OSS release supported by the Wazuh module   |
| `wazuh_server_filebeat_module_version` | `'0.5'`    | Wazuh Filebeat module release                        |

The role does not update Wazuh. With Wazuh installed, a
`wazuh_server_version` that differs from the installed packages fails the
run with both versions.

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
| `wazuh_server_indexer_admin_password`        | `''`    | Indexer user `admin`: dashboard login, Filebeat (required)  |
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

### Wazuh Manager, Filebeat and Dashboard

| Variable                                 | Default     | Description                                  |
| ---------------------------------------- | ----------- | -------------------------------------------- |
| `wazuh_server_manager_service_enabled`   | `true`      | Enable and start the Wazuh manager service   |
| `wazuh_server_filebeat_service_enabled`  | `true`      | Enable and start the Filebeat service        |
| `wazuh_server_dashboard_service_enabled` | `true`      | Enable and start the Wazuh dashboard service |
| `wazuh_server_dashboard_server_host`     | `'0.0.0.0'` | Dashboard bind address                       |
| `wazuh_server_dashboard_server_port`     | `443`       | Dashboard HTTPS port                         |
| `wazuh_server_dashboard_enrollment_dns`  | `''`        | Agent enrollment address, empty for none     |

The dashboard offers `wazuh_server_dashboard_enrollment_dns` in the
"Deploy new agent" wizard and puts it into the generated install command.
The role owns the dashboard plugin configuration (`wazuh.yml`), so set the
address here instead of in the dashboard: the next run replaces a value set
in the dashboard.

## Tags

| Tag                      | Description                           |
| ------------------------ | ------------------------------------- |
| `wazuh_server`           | All wazuh_server tasks                |
| `wazuh_server:install`   | Repository and package installation   |
| `wazuh_server:certs`     | Certificate deployment                |
| `wazuh_server:configure` | Configuration deployment              |
| `wazuh_server:service`   | Systemd service management            |
| `wazuh_server:security`  | Indexer users and Wazuh API passwords |

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
`marcstraube.common.pki` in `prepare.yml`).

## Notes

### Certificates

All certificates must come from one CA. The role copies them into the
certificate directory of each component (`/etc/wazuh-indexer/certs`,
`/etc/filebeat/certs`, `/etc/wazuh-dashboard/certs`), because the indexer
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
The keystores are not used: their values cannot be read back, so a changed
password could not be detected. The role removes the default
`kibanaserver` credentials the dashboard package seeds into its keystore,
because keystore entries take precedence over `opensearch_dashboards.yml`.

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
- [Wazuh Ansible Deployment](https://documentation.wazuh.com/current/deployment-options/deploying-with-ansible/guide/index.html)

## License

MIT

## Author

Marc Straube
