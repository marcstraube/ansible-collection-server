# Changelog

All notable changes to this collection will be documented in this file.

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
