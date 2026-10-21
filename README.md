# Ansible Collection: marcstraube.server

[![CI](https://github.com/marcstraube/ansible-collection-server/workflows/CI/badge.svg)](https://github.com/marcstraube/ansible-collection-server/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support-ff5e5b?logo=ko-fi&logoColor=white)](https://ko-fi.com/marcstraube)

## Description

Ansible roles for self-hosted server infrastructure: web servers, Let's
Encrypt certificates, PostgreSQL, and n8n workflow automation. The roles
build on [marcstraube.common](https://github.com/marcstraube/ansible-collection-common)
for the base system (podman, pki, firewalld, fail2ban).

## Supported Platforms

- Arch Linux (rolling)
- Debian Trixie (13)
- EL 9 (Rocky, Alma, RHEL)
- EL 10 (Rocky, Alma, RHEL)

## Requirements

- ansible-core >= 2.19
- Collections: `marcstraube.common`, `community.general`,
  `community.postgresql`, `containers.podman`, `ansible.posix`
  (installed automatically with the collection)

## Included Roles

### Web

| Role        | Description                                                      |
| ----------- | ---------------------------------------------------------------- |
| **nginx**   | Nginx web server, reverse proxy, and stream proxy                |
| **apache**  | Apache HTTP Server with MPM selection, HTTP/2, and PHP-FPM       |
| **certbot** | Let's Encrypt certificates with webroot, standalone, and DNS-01  |

### Databases

| Role           | Description                                               |
| -------------- | --------------------------------------------------------- |
| **postgresql** | PostgreSQL server with TLS and the PGDG repository option |

### Applications

| Role    | Description                                             |
| ------- | ------------------------------------------------------- |
| **n8n** | n8n workflow automation as a rootless Podman container  |

## Installation

### From Ansible Galaxy

```bash
ansible-galaxy collection install marcstraube.server
```

### From Git

```bash
ansible-galaxy collection install git+https://github.com/marcstraube/ansible-collection-server.git,main
```

### Requirements File

```yaml
# requirements.yml
collections:
  - name: marcstraube.server
    version: ">=1.0.0"
```

## Usage

### Collection Playbooks

The collection ships one playbook per server type. Each one runs the roles
of the stack in the required order and, on Arch Linux, a full system
upgrade first, so a rolling release never installs packages on an outdated
package database. Other platforms skip the upgrade.

| Playbook                             | Host group    | Stack                               |
| ------------------------------------ | ------------- | ----------------------------------- |
| `marcstraube.server.web_server`      | `web_servers` | nginx or apache, certbot            |
| `marcstraube.server.database_server` | `db_servers`  | pki, postgresql                     |
| `marcstraube.server.n8n`             | `n8n_servers` | podman, postgresql, pki, n8n, nginx |

Every role in a stack is gated on its `<role>_enabled` toggle, so the
inventory decides which parts of a stack run on a host:

```yaml
# group_vars/web_servers.yml
nginx_enabled: true
certbot_enabled: true
```

```bash
ansible-playbook marcstraube.server.web_server -i inventory/
ansible-playbook marcstraube.server.web_server -i inventory/ --tags nginx
```

The roles are imported statically, so their sub-tags stay visible to
`--tags` and `--list-tags`. A play of your own can import the task files
under `playbooks/tasks/` instead: `system_update.yml` for the upgrade and
`web_server.yml`, `database_server.yml` or `n8n.yml` for the stack.

### Single Roles

Roles can also be used on their own with `include_role`:

```yaml
- name: Configure web server
  hosts: web_servers
  become: true

  tasks:
    - name: Include nginx role
      ansible.builtin.include_role:
        name: marcstraube.server.nginx
      when: nginx_enabled | default(false) | bool

    - name: Include certbot role
      ansible.builtin.include_role:
        name: marcstraube.server.certbot
      when: certbot_enabled | default(false) | bool
```

Each role documents its variables in `defaults/main.yml` and `roles/<role>/README.md`.

## Testing

Roles are tested with Molecule using Podman containers across all supported platforms.

```bash
cd roles/<role>
molecule test
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.
Pull requests target the `develop` branch; `main` holds the released state.

## Support

If you find this collection useful, consider [supporting its development](https://github.com/sponsors/marcstraube).

## License

MIT

## Author

Marc Straube (<email@marcstraube.de>)
