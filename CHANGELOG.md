# Changelog

All notable changes to this collection will be documented in this file.

## 1.1.3 (2026-11-12)

<!-- Release notes generated using configuration in .github/release.yml at main -->

## What's Changed
### Bug Fixes
* fix(n8n,activepieces): delegate the cgroup to rootless podman by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/155


**Full Changelog**: https://github.com/marcstraube/ansible-collection-server/compare/v1.1.2...v1.1.3

## 1.1.2 (2026-11-12)

<!-- Release notes generated using configuration in .github/release.yml at main -->

## What's Changed
### Bug Fixes
* fix(certbot): fail on EL 10 while the EPEL packages are not installable by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/148


**Full Changelog**: https://github.com/marcstraube/ansible-collection-server/compare/v1.1.1...v1.1.2

## 1.1.1 (2026-11-11)

<!-- Release notes generated using configuration in .github/release.yml at main -->

## What's Changed
### Bug Fixes
* fix(wazuh_server): remove plugin index replicas on a single node by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/138
* fix(wazuh_server): keep indexer config mode across an update by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/141


**Full Changelog**: https://github.com/marcstraube/ansible-collection-server/compare/v1.1.0...v1.1.1

## 1.1.0 (2026-11-09)

<!-- Release notes generated using configuration in .github/release.yml at main -->

## What's Changed
### Features
* feat(apache): allow raising the open file limit of the service by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/4
* feat(apache): allow setting ServerLimit for the event and worker MPM by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/7
* feat(apache): bind virtual hosts to a specific address by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/35
* feat(apache): support mod_remoteip behind a reverse proxy by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/36
* feat(apache): give HTTP vhosts their own PHP-FPM handler by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/37
* feat(wazuh_server): add Wazuh all-in-one server role by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/43
* feat(apache): add document_root_policy for vhost document roots by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/58
* feat(wazuh_server): manage the dashboard's agent enrollment address by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/64
* feat(wazuh_server): require authentication for agent enrollment by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/69
* feat(postgresql): add a targeted package update by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/71
* feat(nginx): add a targeted package update by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/72
* feat(apache): add a targeted package update by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/73
* feat(wazuh_server): support an outbound HTTP proxy for the manager by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/83
* feat(wazuh_server): configure indexer snapshots by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/85
* feat(n8n): remove superseded container images after an update by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/86
* feat(mariadb): add a MariaDB role by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/87
* feat(n8n): document and test the editor under a URL path prefix by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/88
* feat(n8n): add a scheduled backup by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/92
* feat(activepieces): add an Activepieces role by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/96
* feat(mariadb): run the backup from a systemd timer and add a restore by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/106
* feat(postgresql): run the backup from a systemd timer, rotate by count and add a restore by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/107
* feat(wazuh_server): update Wazuh in the upstream order by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/131
### Bug Fixes
* fix(wazuh_server): make check mode runs pass by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/66
* fix(nginx): ignore a missing rpm epoch in the version report by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/80
* fix(wazuh_server): connect the manager to the configured indexer address by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/101
* fix(nginx): keep the site port in redirects and label site ports for SELinux by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/103
* fix(n8n): detect the PostgreSQL unit, deprecate the firewall tasks and remove MySQL by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/105
* fix(wazuh_server): lock the Wazuh packages against system upgrades by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/114
* fix(nginx): extend the SELinux setup to Authentik and stream, add http2 to the default site by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/117
* fix(postgresql): connect on the configured port and socket, rename the globals dump by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/118
* fix(wazuh_server): connect the manager to the indexer, make the dashboard session configurable by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/122
* fix(apache): start Apache after network-online.target by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/127

## New Contributors
* @dependabot[bot] made their first contribution in https://github.com/marcstraube/ansible-collection-server/pull/81

**Full Changelog**: https://github.com/marcstraube/ansible-collection-server/compare/v1.0.3...v1.1.0

## 1.0.3 (2026-11-05)

<!-- Release notes generated using configuration in .github/release.yml at main -->

## What's Changed
### Bug Fixes
* fix(apache): neutralize the package ssl.conf instead of deleting it by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/109


**Full Changelog**: https://github.com/marcstraube/ansible-collection-server/compare/v1.0.2...v1.0.3

## 1.0.2 (2026-10-23)

<!-- Release notes generated using configuration in .github/release.yml at main -->

## What's Changed
### Bug Fixes
* fix(apache): test the configuration after vhosts are pruned by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/30
* fix(apache): label additional listen ports for SELinux by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/33


**Full Changelog**: https://github.com/marcstraube/ansible-collection-server/compare/v1.0.1...v1.0.2

## 1.0.1 (2026-10-22)

<!-- Release notes generated using configuration in .github/release.yml at main -->

## What's Changed
### Bug Fixes
* fix(apache): skip the reload right after a restart in the same handler run by @marcstraube in https://github.com/marcstraube/ansible-collection-server/pull/9


**Full Changelog**: https://github.com/marcstraube/ansible-collection-server/compare/v1.0.0...v1.0.1

## [1.0.0] - 2026-10-20

### Summary

Initial public release of the `marcstraube.server` collection.

Ansible roles for self-hosted server infrastructure supporting Arch Linux,
Debian Trixie, and Rocky Linux 9/10, built on `marcstraube.common`.

### Roles

- **apache** - Apache HTTP Server with MPM selection, HTTP/2, and PHP-FPM
- **certbot** - Let's Encrypt certificates with webroot, standalone, and DNS-01
- **n8n** - n8n workflow automation as a rootless Podman container
- **nginx** - Nginx web server, reverse proxy, and stream proxy
- **postgresql** - PostgreSQL server with TLS and the PGDG repository option

### Playbooks

- **web_server** - nginx or apache with certbot
- **database_server** - pki and postgresql
- **n8n** - podman, postgresql, pki, n8n, and nginx
