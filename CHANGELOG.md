# Changelog

All notable changes to this collection will be documented in this file.

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
