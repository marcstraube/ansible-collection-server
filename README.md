# Ansible Collection: marcstraube.server

[![CI](https://github.com/marcstraube/ansible-collection-server/workflows/CI/badge.svg)](https://github.com/marcstraube/ansible-collection-server/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support-ff5e5b?logo=ko-fi&logoColor=white)](https://ko-fi.com/marcstraube)

## Description

Ansible roles for self-hosted server infrastructure: web servers, Let's
Encrypt certificates, PostgreSQL, MariaDB, and n8n and Activepieces workflow
automation. The roles build on
[marcstraube.common](https://github.com/marcstraube/ansible-collection-common)
for the base system (podman, pki, firewalld, fail2ban).

## Supported Platforms

- Arch Linux (rolling)
- Debian Trixie (13)
- EL 9 (Rocky, Alma, RHEL)
- EL 10 (Rocky, Alma, RHEL); `certbot` is currently unsupported there, see
  its README

## Requirements

- ansible-core >= 2.19
- Collections: `marcstraube.common`, `community.crypto`, `community.general`,
  `community.postgresql`, `ansible.mariadb`, `containers.podman`,
  `ansible.posix` (installed automatically with the collection)

## Included Roles

### Web

| Role        | Description                                                      |
| ----------- | ---------------------------------------------------------------- |
| **nginx**   | Nginx web server, reverse proxy, and stream proxy                |
| **apache**  | Apache HTTP Server with MPM selection, HTTP/2, and PHP-FPM       |
| **certbot** | Let's Encrypt certificates with webroot, standalone, and DNS-01  |

### Databases

| Role           | Description                                                 |
| -------------- | ----------------------------------------------------------- |
| **postgresql** | PostgreSQL server with TLS and the PGDG repository option   |
| **mariadb**    | MariaDB server with TLS and the upstream repository option  |
| **valkey**     | Valkey key-value store with ACL users, unix socket and TLS  |

### Mail

| Role                | Description                                                     |
| ------------------- | --------------------------------------------------------------- |
| **postfixadmin**    | PostfixAdmin with its schema, read-only users and mail accounts |
| **dovecot**         | Dovecot 2.4: IMAP, LMTP, SASL, ManageSieve and shared mailboxes |
| **postfix**         | Postfix MTA with PostfixAdmin lookups, Dovecot LMTP and SASL    |
| **rspamd**          | rspamd mail filter: milter, DKIM/ARC signing, clamd, Valkey     |
| **roundcube**       | Roundcube webmail with Sieve filters, sharing, password change  |
| **sogo**            | SOGo groupware: webmail, CalDAV, CardDAV, optional ActiveSync   |
| **mail_discovery**  | Autoconfig, Autodiscover, Apple profile, MTA-STS, TLS-RPT       |

### Applications

| Role             | Description                                                     |
| ---------------- | --------------------------------------------------------------- |
| **n8n**          | n8n workflow automation as a rootless Podman container          |
| **activepieces** | Activepieces workflow automation as a rootless Podman container |

### Security

| Role             | Description                                                    |
| ---------------- | -------------------------------------------------------------- |
| **wazuh_server** | Wazuh all-in-one server: indexer, manager, Filebeat, dashboard |

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

| Playbook                             | Host group             | Stack                                        |
| ------------------------------------ | ---------------------- | -------------------------------------------- |
| `marcstraube.server.web_server`      | `web_servers`          | nginx or apache, certbot                     |
| `marcstraube.server.database_server` | `db_servers`           | pki, postgresql, mariadb                     |
| `marcstraube.server.mail_server`     | `mail_servers`         | pki, certbot, the mail roles (below)         |
| `marcstraube.server.n8n`             | `n8n_servers`          | podman, postgresql, pki, n8n, nginx          |
| `marcstraube.server.activepieces`    | `activepieces_servers` | podman, postgresql, pki, activepieces, nginx |
| `marcstraube.server.wazuh_server`    | `wazuh_servers`        | pki, wazuh_server                            |

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
`web_server.yml`, `database_server.yml`, `mail_server.yml`, `n8n.yml`,
`activepieces.yml` or `wazuh_server.yml` for the stack.

### Mail Server

The mail stack builds on other plays: PostfixAdmin, SOGo and Roundcube
need their databases (`database_server`), PostfixAdmin and Roundcube a web
server (`web_server`) and PHP
([`marcstraube.common.php`](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/php/README.md) of
the base system). Run those plays before `mail_server`:

```yaml
# site.yml
- name: Base system
  ansible.builtin.import_playbook: marcstraube.common.base_system

- name: Database servers
  ansible.builtin.import_playbook: marcstraube.server.database_server

- name: Web servers
  ansible.builtin.import_playbook: marcstraube.server.web_server

- name: Mail servers
  ansible.builtin.import_playbook: marcstraube.server.mail_server
```

Within the mail play the roles run in this order: pki and certbot (the
certificates exist before Postfix and Dovecot check them; a mail host
without a web server uses a DNS authenticator of certbot), Valkey,
PostfixAdmin (creates and upgrades the schema the other roles read),
Postfix (its queue directory holds the local LMTP and SASL sockets of
Dovecot), Dovecot, rspamd, then SOGo, Roundcube and the mail
discovery data. Until Dovecot and rspamd are up in the same run,
Postfix defers delivery and holds incoming mail back
(`postfix_milter_default_action: 'tempfail'`), so no mail passes
unfiltered.

Every host that runs one of the mail roles belongs to `mail_servers`, each
role is gated on its `<role>_enabled` toggle. clamd comes from
[`marcstraube.common.clamav`](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/clamav/README.md)
of the base system (`clamav_enabled`), so a clamd host needs no mail role.

A single mail host runs all plays:

```yaml
# inventory/hosts.yml
all:
  children:
    db_servers:
      hosts:
        mail.example.com:
    web_servers:
      hosts:
        mail.example.com:
    mail_servers:
      hosts:
        mail.example.com:
```

```yaml
# host_vars/mail.example.com.yml
php_enabled: true
clamav_enabled: true
postgresql_enabled: true
nginx_enabled: true
certbot_enabled: true
valkey_enabled: true
postfixadmin_enabled: true
postfixadmin_db_create: true
# The user source of SOGo
postfixadmin_sogo_view_enabled: true
dovecot_enabled: true
rspamd_enabled: true
rspamd_antivirus_enabled: true
mta_enabled: false
postfix_enabled: true
sogo_enabled: true
sogo_db_create: true
roundcube_enabled: true
roundcube_db_create: true
mail_discovery_enabled: true
```

Both examples show which role runs where, not a complete inventory. Each
role asserts its required variables on the first run: the certificate and
key files of Postfix and Dovecot (`postfix_tls_cert_file`,
`dovecot_tls_cert_file`, ...) and the certificates of certbot
(`certbot_certificates`), the database passwords and the read-only users
of PostfixAdmin (`postfixadmin_db_readers`), the Valkey user of rspamd (and of
Roundcube with `roundcube_session_storage: 'redis'`), the nginx sites of PostfixAdmin, Roundcube and SOGo
(`nginx_sites`) and the domains of the mail discovery data. The role
READMEs describe them; the inventory of the stack scenario
(`extensions/molecule/mail_server/inventory`) is a complete, tested
example of the split setup.

In a split setup the mail host runs Postfix, Dovecot and rspamd, a
database host PostgreSQL or MariaDB, a web host PostfixAdmin, SOGo and
Roundcube, and a clamd host clamd for rspamd. The hosts reach each other
on a private network (here `10.0.0.0/24`: mail `10.0.0.2`, database
`10.0.0.3`, web `10.0.0.4`, clamd `10.0.0.5`):

```yaml
# inventory/hosts.yml
all:
  children:
    db_servers:
      hosts:
        db.example.com:
    web_servers:
      hosts:
        web.example.com:
    mail_servers:
      hosts:
        mail.example.com:
        web.example.com:
  hosts:
    clamd.example.com:
```

```yaml
# host_vars/mail.example.com.yml
valkey_enabled: true
dovecot_enabled: true
dovecot_db_host: 'db.example.com'
dovecot_db_tls: true
# The CA bundle of Debian and Arch Linux; EL: /etc/pki/tls/certs/ca-bundle.crt
dovecot_db_tls_ca_file: '/etc/ssl/certs/ca-certificates.crt'
rspamd_enabled: true
rspamd_antivirus_enabled: true
rspamd_clamd_address: '10.0.0.5:3310'
mta_enabled: false
postfix_enabled: true
postfix_db_host: 'db.example.com'
postfix_db_tls: true
postfix_db_tls_ca_file: '/etc/ssl/certs/ca-certificates.crt'

# host_vars/db.example.com.yml
postgresql_enabled: true
postgresql_ssl_enabled: true
# A certificate for db.example.com that the clients' CA file verifies
postgresql_ssl_cert_file: '/etc/ssl/certs/db.example.com.crt'
postgresql_ssl_key_file: '/etc/ssl/private/db.example.com.key'
postgresql_listen_addresses: 'localhost,10.0.0.3'
postgresql_firewalld_zone: 'internal'
# hostssl: the server accepts these users with TLS only
postgresql_hba_additional:
  - {type: 'hostssl', database: 'postfixadmin', user: 'postfixadmin', address: '10.0.0.4/32', method: 'scram-sha-256'}
  - {type: 'hostssl', database: 'postfixadmin', user: 'postfix', address: '10.0.0.2/32', method: 'scram-sha-256'}
  - {type: 'hostssl', database: 'postfixadmin', user: 'dovecot', address: '10.0.0.2/32', method: 'scram-sha-256'}
  - {type: 'hostssl', database: 'postfixadmin', user: 'sogo_view', address: '10.0.0.4/32', method: 'scram-sha-256'}
  - {type: 'hostssl', database: 'roundcube', user: 'roundcube', address: '10.0.0.4/32', method: 'scram-sha-256'}
  - {type: 'hostssl', database: 'sogo', user: 'sogo', address: '10.0.0.4/32', method: 'scram-sha-256'}

# host_vars/web.example.com.yml
php_enabled: true
nginx_enabled: true
postfixadmin_enabled: true
postfixadmin_db_host: 'db.example.com'
postfixadmin_db_tls: true
postfixadmin_db_tls_ca_file: '/etc/ssl/certs/ca-certificates.crt'
# The user source of SOGo
postfixadmin_sogo_view_enabled: true
sogo_enabled: true
sogo_db_host: 'db.example.com'
sogo_db_tls: true
sogo_db_tls_ca_file: '/etc/ssl/certs/ca-certificates.crt'
sogo_imap_server: 'imaps://mail.example.com:993'
roundcube_enabled: true
roundcube_db_host: 'db.example.com'
roundcube_db_tls: true
roundcube_db_tls_ca_file: '/etc/ssl/certs/ca-certificates.crt'
roundcube_imap_host: 'mail.example.com'
roundcube_smtp_host: 'mail.example.com'

# host_vars/clamd.example.com.yml
clamav_enabled: true
clamav_tcp_socket: '3310'
clamav_tcp_addr: '10.0.0.5'
```

The clients verify the certificate of the database server against their
`*_db_tls_ca_file`: the system bundle for a publicly signed certificate,
the private CA otherwise (deployed with
[`marcstraube.common.pki`](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/pki/README.md),
as in the stack scenario). `db.example.com` has to resolve to the private
address on the mail and web host, which the `pg_hba` entries allow.

Only the mail ports face the internet: SMTP (25), submission (465, 587),
IMAPS (993), ManageSieve (4190) where clients use it, and HTTP/HTTPS (80,
443) for the web host. clamd (3310) has no authentication; it, PostgreSQL
(5432) or MariaDB (3306) and Valkey (6379) belong on the private network.
Bind them to the private address as above and restrict the ports with
[`marcstraube.common.firewalld`](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/firewalld/README.md).
The postgresql role opens its port in `postgresql_firewalld_zone` (default
`public`), so the example points it to the zone of the private network;
the mariadb role leaves its port to `marcstraube.common.firewalld`.

With the database on its own host, the databases, their owners and the
read-only users of Postfix, Dovecot and SOGo are created by the database
role there (`postgresql_databases`, `postgresql_users`), since
`postfixadmin_db_readers` of
[`marcstraube.server.postfixadmin`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/postfixadmin/README.md#read-only-database-users)
needs the database server on the PostfixAdmin host. The database role does
not grant privileges. PostfixAdmin creates its tables only in the mail
play, so a play between the database and the mail play grants `SELECT` on
the tables the PostfixAdmin user creates from then on (PostgreSQL, as in
the stack scenario):

```yaml
# site.yml, between the database_server and the mail_server play
- name: Read-only users of the PostfixAdmin database
  hosts: db_servers
  gather_facts: false
  tasks:
    - name: Grant SELECT on the PostfixAdmin tables to the read-only users
      community.postgresql.postgresql_privs:
        login_db: 'postfixadmin'
        type: 'default_privs'
        target_roles: 'postfixadmin'
        schema: 'public'
        objs: 'TABLES'
        privs: 'SELECT'
        roles: 'postfix,dovecot,sogo_view'
      become: true
      become_user: postgres
```

This covers every table of PostfixAdmin, also `admin` (the password hashes
of the administrators) and `fetchmail` (the passwords of remote
mailboxes). To limit the readers to the tables they use, grant `SELECT`
per table after the mail play instead (Postfix: `domain`, `mailbox`,
`alias`, `alias_domain`; Dovecot: `domain`, `mailbox`; SOGo: the view
`sogo_users`). The postfix role
replaces `marcstraube.common.mta` of the base system on its host
(`mta_enabled: false`).

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

The mail server playbook has a stack scenario of its own in
`extensions/molecule/mail_server`: the split setup of
[Mail Server](#mail-server) in four containers, with mail from outside
through Postfix, rspamd and clamd, the logins in Roundcube and SOGo and a
shared mailbox. It runs from the collection root and needs all four
containers at once:

```bash
molecule test -s mail_server
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
