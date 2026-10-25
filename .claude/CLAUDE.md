# Claude Code — marcstraube.server Collection

## Overview

Server roles for self-hosted infrastructure: web servers, Let's Encrypt
certificates, PostgreSQL, and n8n. Builds on `marcstraube.common` for the base
system (podman, pki, firewalld, fail2ban).
Multi-OS support: Arch Linux (primary), Debian Trixie, Rocky Linux 9/10.

## Coding Standards (ansible-core 2.19+)

- **Facts:** `ansible_facts['os_family']` — never `ansible_os_family` (deprecated)
- **Modules:** Always FQCN (`ansible.builtin.*`, `community.general.*`)
- **Roles:** `ansible.builtin.include_role` — never `import_role`
  (exception: the entry task files, see [Sub-tags must be self-contained](#sub-tags-must-be-self-contained))
- **Tasks:** `ansible.builtin.include_tasks` — never `import_tasks` for conditional dispatch
- **Tag propagation:** Always `apply: tags:` when using `include_tasks` inside blocks
- **Variables:** `<role>_<setting>`, internal: `__<role>_<setting>` (double underscore)
- **Booleans:** `<role>_enabled | default(true/false) | bool`
- **Templates:** `{{ ansible_managed | comment }}` header
- **Comments:** English only

Full reference with YAML quoting rules: see infra project `.claude/CLAUDE.md`.

## Roles

| Role           | Purpose                                                |
| -------------- | ------------------------------------------------------ |
| `nginx`        | Nginx web server, reverse proxy, stream proxy          |
| `apache`       | Apache HTTP Server, MPM selection, HTTP/2, PHP-FPM     |
| `certbot`      | Let's Encrypt certificates and renewal hooks           |
| `postgresql`   | PostgreSQL server, TLS, PGDG repository option         |
| `n8n`          | n8n workflow automation as a rootless Podman container |
| `wazuh_server` | Wazuh all-in-one server (indexer, manager, dashboard)  |

Every role ships with `<role>_enabled: false` in its defaults; the inventory
turns it on per host group.

## Playbook Pattern

This collection ships entry task files in `playbooks/tasks/` that orchestrate
multi-role stacks, and one playbook per stack in `playbooks/` that wraps the
task file with the Arch Linux system update as `pre_tasks`. Consumers run
the playbook by name (`ansible-playbook marcstraube.server.web_server`); the
infra project imports the task files statically from its own plays:

```yaml
# infra: playbooks/site.yml
- name: Web Server Deployment
  hosts: web_servers
  become: true
  tasks:
    - name: Web | Import web server tasks
      ansible.builtin.import_tasks:
        file: ../collections/ansible_collections/marcstraube/server/playbooks/tasks/web_server.yml
```

Available entry task files:

| Task file | Stack |
| ----------- | ----- |
| `web_server.yml` | Nginx/Apache + certbot |
| `database_server.yml` | PostgreSQL with pki-issued certificates |
| `n8n.yml` | N8N workflow automation (podman, postgresql, pki, nginx) |
| `wazuh_server.yml` | Wazuh all-in-one server with pki-issued certificates |
| `system_update.yml` | Arch Linux full upgrade, `pre_tasks` of every collection playbook |

Every role an entry task file references has to exist in the collection build —
a static import resolves at parse time, so a missing role fails the whole play.

### Sub-tags must be self-contained

A role exposes sub-tags (`<role>:<phase>`, e.g. `nginx:configure`) so a single
stage can be run in isolation. For that to work, two rules apply:

1. **The entry task files import roles statically.** `playbooks/tasks/*.yml`
   use `import_role` (not `include_role`) for every role. A dynamic `include_role`
   hides the role's inner sub-tags behind the include statement, so
   `--tags nginx:configure` would skip the whole role. Static `import_role`
   exposes inner tags to `--tags` and `--list-tags`.

2. **Bootstrap tasks are tagged `always`.** Any task a sub-tag path depends on —
   OS-var loaders (`include_vars`), derived-fact `set_fact`s consumed by a later
   stage, validation asserts — must carry `tags: [always]`, not the bare role tag.
   Otherwise an isolated sub-tag run skips the loader and fails on undefined
   `__<role>_*` vars. Feature work keeps `role` + sub-tag; only genuine setup
   is `always`.

```yaml
- name: Main | Load OS-specific variables
  ansible.builtin.include_vars: '{{ item }}'
  with_first_found: ...
  tags:
    - always        # bootstrap — needed by every sub-tag path
```

## systemd Hardening

Server services should use systemd security directives in their unit files:

- `ProtectSystem=strict` / `ProtectHome=yes`
- `NoNewPrivileges=yes`
- `PrivateTmp=yes`
- `ReadWritePaths=` for specific data directories
- `CapabilityBoundingSet=` restricted to needed capabilities

## Role Conventions

Same conventions as `marcstraube.common` — see that collection's CLAUDE.md for
directory structure, variable naming, task patterns, and template rules.

## Security

- Vault files (`vault.yml`) are never accessed — only `vault.yml.example` templates
- Use `{{ vault_* }}` variable references, never hardcode secrets
- See root `.claude/CLAUDE.md` for vault protection rules
