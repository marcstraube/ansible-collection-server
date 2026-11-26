# marcstraube.server.rspamd

rspamd as the filter of the mail stack: spam scoring, SPF/DKIM/DMARC/ARC
checks, DKIM and ARC signing, virus scanning through clamd, greylisting and
rate limits, connected to Postfix as milter.

## Description

The role installs rspamd (on Debian and EL from the stable repository of the
rspamd project, which it sets up) and configures it through files in
`/etc/rspamd/local.d` only; the configuration the package ships stays
untouched, so the layout is the same on every platform. Every change is
rendered into a staging copy of `local.d`, `override.d` and the local
configuration files (`rspamd.conf.local`, `rspamd.conf.local.override`,
`rspamd.conf.override`) and checked with `rspamadm configtest` before it
replaces the active files and rspamd reloads. Every changed file keeps its
previous version next to it in `local.d`
(`<name>.<pid>.<YYYY-MM-DD@HH:MM:SS>~`); the role keeps only the newest
backup per file and removes the backups of a file that left
`rspamd_local_config` together with it. rspamd includes the `local.d` files
by name, never by pattern, so it never loads these copies.

- A proxy worker in milter mode for Postfix (`marcstraube.server.postfix`,
  `postfix_milters`) and the controller with a read and an enable password,
  stored as hashes. The enable password is the one Dovecot
  (`marcstraube.server.dovecot`) uses for the spam training.
- Bayes, greylisting, rate limits, replies and DMARC reports keep their data
  in Valkey (`marcstraube.server.valkey`) with an ACL user, optionally over
  TLS.
- DKIM and ARC signing for the mail domains with keys the role creates and
  never replaces; mail from authenticated users and from the signing
  networks is signed.
- Virus scanning through clamd (`marcstraube.common.clamav`).
- Optional DMARC aggregate reports, sent by a systemd timer.
- The role prints the DKIM and DMARC records and checks whether they are
  set.

Postfix, Valkey, clamd and Dovecot may run on other hosts.

## Requirements

- ansible-core >= 2.19
- Valkey or Redis with an ACL user for rspamd (`marcstraube.server.valkey`,
  see [Valkey](#valkey))
- EL: EPEL (`marcstraube.common.package_management`); the upstream packages
  need `libsodium` from EPEL, on EL 9 also `jemalloc` and `hyperscan`. The
  role fails before any change when no enabled repository provides them.
- For virus scanning: clamd (`marcstraube.common.clamav`, see
  [clamd](#clamd))
- On the controller: the Python library `dnspython` for the DNS check
  (`community.general.dig`)

### Required Collections

```yaml
collections:
  - community.general
```

## Supported Platforms

| Platform                  | Notes                                                   |
| ------------------------- | ------------------------------------------------------- |
| Arch Linux                | `rspamd` from the official repository (extra)           |
| Debian Trixie             | Stable repository of the rspamd project, set up by role |
| EL 9 (Rocky, Alma, RHEL)  | Stable repository of the rspamd project, set up by role |
| EL 10 (Rocky, Alma, RHEL) | Stable repository of the rspamd project, set up by role |

Other distributions in the same os_family (EndeavourOS, Manjaro, Ubuntu, Mint,
Fedora) should work but are not actively tested. Use distro-specific vars
overrides if needed.

| Platform      | Source                         | Version (November 2026) | Service user |
| ------------- | ------------------------------ | ----------------------- | ------------ |
| Arch Linux    | extra                          | 4.2.3                   | `rspamd`     |
| Debian Trixie | `rspamd.com/apt-stable`        | 4.3.0                   | `_rspamd`    |
| EL 9          | `rspamd.com/rpm-stable` + EPEL | 4.3.0                   | `_rspamd`    |
| EL 10         | `rspamd.com/rpm-stable` + EPEL | 4.3.0                   | `_rspamd`    |

Debian 13 ships rspamd 3.12 itself; the rspamd project supports only its own
packages, and the repository carries the current release for Debian and EL,
so every platform runs the 4.x series. The role uses the stable repository
on Debian, the Debian package is not used. The configuration directory
`/etc/rspamd`, the data directory `/var/lib/rspamd` and the log
`/var/log/rspamd/rspamd.log` are the same everywhere.

The EL packages of rspamd 4.3.0 do not create the service user `_rspamd`
([rspamd/rspamd#6385](https://github.com/rspamd/rspamd/issues/6385)); the
unit runs as `_rspamd` and fails to start without it. The role creates the
user and group while they are missing and hands `/var/lib/rspamd` and
`/var/log/rspamd` to them; an existing user stays as it is.

## Role Variables

See [defaults/main.yml](defaults/main.yml) for all available variables.

### Role Control

| Variable                 | Default | Description                         |
| ------------------------ | ------- | ----------------------------------- |
| `rspamd_enabled`         | `false` | Enable the rspamd role              |
| `rspamd_service_enabled` | `true`  | Enable and start the rspamd service |

### Package Updates

| Variable                  | Default     | Description                                                      |
| ------------------------- | ----------- | ---------------------------------------------------------------- |
| `rspamd_packages_state`   | `'present'` | `present` installs missing packages only, `latest` updates them  |
| `rspamd_packages_minimum` | `''`        | Lowest acceptable rspamd version, string or mapping per platform |

A regular run never updates rspamd. A targeted update, for example for a
security release, is requested on the command line:

```bash
ansible-playbook site.yml --tags rspamd \
  -e rspamd_packages_state=latest \
  -e rspamd_packages_minimum=4.3.1
```

With `latest` the role refreshes the package metadata and updates every
installed rspamd package in one transaction (`rspamd` and, where installed,
the debug and ASAN builds that require its exact version). The role reports
the version change.

`rspamd_packages_minimum` is checked twice. Before the update the role asks
the package manager which version the update would install and fails without
a change when it is older than the minimum, which shows that the repository
does not carry the fix yet. After the update it checks the installed version
again; this check is skipped under `--check`.

The minimum is an upstream version (`4.3.1`, any build of it) or the full
package version (`4.3.1-1~<commit>~trixie`, `4.3.1-1.el9`). Versions are
compared with the rules of the distribution (`dpkg --compare-versions`, rpm,
`vercmp`). For mixed hosts in one run, pass a mapping per platform; the keys
are `<os_family>-<major>` or `<os_family>`, and a host without a matching key
fails before any change:

```yaml
# rspamd-minimum.yml, passed with -e @rspamd-minimum.yml
rspamd_packages_minimum:
  Debian: '4.3.1'
  RedHat: '4.3.1'
  Archlinux: '4.3.1'
```

The packages usually restart rspamd themselves. When they did not, for
example because of a `policy-rc.d`, the main process still executes the
replaced binary and the role restarts it after `rspamadm configtest` passed
with the new binary; when the test fails, the old process keeps running and
the run fails with the output.

The stable repository of the rspamd project lists only its newest build,
so a package cannot be rolled back to an earlier build from it. To be able
to roll back, install from an internal mirror or snapshot that keeps older
builds (`rspamd_repo_uris` on Debian, `rspamd_repo_baseurl` on EL, see
[Repository](#repository)).

On Arch Linux `rspamd_packages_state` is ignored: updating single packages
is a partial upgrade there, rspamd updates with the full system upgrade. Run
the role with `latest` together with the system upgrade (`--tags
system-update,rspamd`) to restart rspamd after it.

### Repository

| Variable                | Default  | Description                       |
| ----------------------- | -------- | --------------------------------- |
| `rspamd_repo_uris`      | upstream | Repository address (Debian)       |
| `rspamd_repo_signed_by` | upstream | Signing key, URL or file (Debian) |
| `rspamd_repo_baseurl`   | upstream | Repository address (EL)           |
| `rspamd_repo_gpgkey`    | upstream | Signing key (EL)                  |

```yaml
rspamd_repo_uris: 'https://rspamd.com/apt-stable/'
rspamd_repo_signed_by: 'https://rspamd.com/apt-stable/gpg.key'
rspamd_repo_baseurl: 'https://rspamd.com/rpm-stable/centos-$releasever/$basearch'
rspamd_repo_gpgkey: 'https://rspamd.com/rpm/rspamd.asc'
```

Hosts without internet access point these at an internal mirror of the
repository (aptly, Nexus, Satellite, Pulp), as `https://` or `file://` URL.
On EL dnf imports the key from `rspamd_repo_gpgkey` on first use and checks
the packages and the repository metadata with it (`repo_gpgcheck`). Arch
Linux ignores these variables.

### Workers

| Variable                            | Default             | Description                               |
| ----------------------------------- | ------------------- | ----------------------------------------- |
| `rspamd_milter_bind`                | `'127.0.0.1:11332'` | Milter (proxy worker) for Postfix         |
| `rspamd_controller_bind`            | `'127.0.0.1:11334'` | Controller (web interface, spam training) |
| `rspamd_controller_password`        | `''`                | Read password (**required**)              |
| `rspamd_controller_enable_password` | `''`                | Enable password (**required**)            |
| `rspamd_controller_secure_ips`      | `[]`                | Addresses trusted without a password      |

Both listeners take `<address>:<port>`; the role asserts the address, so an
unauthenticated milter never binds every interface by accident. Neither
listener encrypts: a milter for a Postfix on another host binds an address of
a private network or WireGuard.

The read password opens the web interface and the statistics; the enable
password also allows learning and changes. The role stores both as hashes
(`rspamadm pw`, in `local.d/worker-controller.inc`, readable by the service
group only). On every run it checks the stored hashes against the passwords
(`rspamadm pw --check`; the password reaches rspamadm on stdin, never on a
command line or in the environment of the remote command) and creates a new
hash only when one no longer matches, so a run without a password change
changes nothing.

rspamd trusts `127.0.0.1` and `::1` without a password by default
(`secure_ip`). The role replaces that list with
`rspamd_controller_secure_ips`, empty by default: a web server in front of
the controller connects from the loopback interface, and with the upstream
default every visitor of the web interface would pass without a password.
A `/0` network fails the run; the role warns about a loopback address and
about any network wider than a single host in the list.

The role turns `allow_file_and_shm_inputs` off on the normal, proxy and
controller workers: clients may not make rspamd read a file or shared memory
of their choice (upstream keeps it on until the next major release).

### Valkey

| Variable                   | Default              | Description                                 |
| -------------------------- | -------------------- | ------------------------------------------- |
| `rspamd_redis_servers`     | `['127.0.0.1:6379']` | `<host>:<port>` or unix socket paths        |
| `rspamd_redis_username`    | `'rspamd'`           | ACL user                                    |
| `rspamd_redis_password`    | `''`                 | ACL password; empty connects without AUTH   |
| `rspamd_redis_db`          | `0`                  | Database number                             |
| `rspamd_redis_tls`         | `false`              | Connect with TLS (verifies the certificate) |
| `rspamd_redis_tls_ca_file` | `''`                 | CA for the certificate; empty: system store |

One setting serves all modules that keep data in Valkey: Bayes, greylisting,
rate limits, replies, DMARC reports and the neural network. The matching
ACL user of `marcstraube.server.valkey`:

```yaml
valkey_users:
  - name: 'rspamd'
    password: '{{ vault_valkey_rspamd_password }}'
```

A Valkey unix socket on the same host (`valkey_unix_socket`) goes into
`rspamd_redis_servers` as its path; the service user joins the socket group
with `rspamd_socket_groups: ['<valkey_unix_socket_group>']`.

The default command rules (`+@all`, `-@dangerous`) are enough for rspamd
(tested with Bayes, greylisting and rate limits). Without TLS the password
and the data cross the network in cleartext; the role warns about a
connection to another host without TLS. Use TLS (`valkey_tls_enabled`) or a
private network or WireGuard.

### Classification

| Variable                         | Default             | Description                       |
| -------------------------------- | ------------------- | --------------------------------- |
| `rspamd_actions`                 | upstream            | Thresholds; `null` disables one   |
| `rspamd_bayes_autolearn`         | `false`             | Learn Bayes from the actions      |
| `rspamd_greylisting_enabled`     | `true`              | Greylisting above its score       |
| `rspamd_ratelimits`              | `{}`                | Rates of the ratelimit module     |
| `rspamd_milter_headers`          | `['x-spam-status']` | Headers added to the mail         |
| `rspamd_milter_extended_headers` | `false`             | X-Spamd-Result and server headers |

`rspamd_actions` takes `reject`, `add_header`, `rewrite_subject` and
`greylist`; the defaults are the upstream ones. For the action
`add_header` the milter adds `X-Spam: Yes`, which the Sieve script of the
dovecot role files into Junk. `x-spam-status` adds `X-Spam-Status: Yes|No,
score=...`. Further routines of the milter_headers module go into the list,
e.g. `authentication-results`. rspamd adds the headers to mail from other
hosts only, not to mail from the loopback interface or from authenticated
users (upstream defaults `skip_local`, `skip_authenticated`).

`rspamd_actions` defaults to the upstream thresholds `reject: 15`,
`add_header: 6` and `greylist: 4`.

Without `rspamd_bayes_autolearn` Bayes learns from the spam training of the
users only (Dovecot moves into and out of Junk). Rate limits:

```yaml
rspamd_ratelimits:
  to:
    bucket:
      burst: 100
      rate: '1 / 1m'
  user:
    selector: 'user.lower'
    bucket:
      burst: 200
      rate: '10 / 1m'
```

### DNS

| Variable                 | Default | Description                                    |
| ------------------------ | ------- | ---------------------------------------------- |
| `rspamd_dns_nameservers` | `[]`    | Resolvers of rspamd; empty: `/etc/resolv.conf` |

SPF, DKIM, DMARC and ARC checks run with the upstream defaults. DNS
blocklists refuse queries from public resolvers (Google, Cloudflare, Quad9
and most providers' resolvers): run a local recursive resolver such as
`marcstraube.common.unbound` and point `rspamd_dns_nameservers` (or the
system resolver) at it.

### DKIM and ARC Signing

| Variable                  | Default                  | Description                                |
| ------------------------- | ------------------------ | ------------------------------------------ |
| `rspamd_dkim_domains`     | `[]`                     | Domains with selector and RSA key size     |
| `rspamd_signing_networks` | `['127.0.0.0/8', '::1']` | Clients whose mail is signed without login |

```yaml
rspamd_dkim_domains:
  - domain: 'example.com'
    selector: '2026'
    key_size: 2048   # default; 1024-4096
```

1024 bits is only the minimum that verifiers accept (RFC 8301), which asks
signers for at least 2048; the role warns about a smaller key.

The role creates one RSA key per domain and selector with `rspamadm
dkim_keygen` in `/var/lib/rspamd/dkim/<domain>.<selector>.key` (owner the
service user, mode `0600`, directory `root:<service group>` `0750`) when the
file does not exist. It never replaces a key: `rspamadm dkim_keygen` itself
overwrites an existing file, the role does not call it then. The public
record goes into `<domain>.<selector>.txt` next to it. For a key placed by
hand (`<domain>.<selector>.key`, an RSA key in PEM) the role rebuilds that
file from the private key with `openssl` on every run while it is missing,
and installs `openssl` for it; a key of another type (Ed25519) fails the
run with a request to write the record file by hand.

Mail from authenticated users and from `rspamd_signing_networks` is signed
with the key of the domain of its `From` header (subdomains with the key of
their registered domain); the loopback interface covers mail that Postfix
receives from local programs. The upstream default would also sign mail from
every private network (`sign_local`), which the role turns off. Forwarded
mail to the mail domains gets an ARC seal with the key of the recipient
domain (upstream rules of the arc module).

Key rotation: set a new selector for the domain. The role creates the new
key and signs with it; the old key stays on the host. Publish the new
record before the run, keep the old one published for a few days until
mail signed with it has been delivered and checked, then remove it.

### Antivirus

| Variable                    | Default                    | Description                                              |
| --------------------------- | -------------------------- | -------------------------------------------------------- |
| `rspamd_antivirus_enabled`  | `false`                    | Scan mail through clamd                                  |
| `rspamd_socket_groups`      | `[]`                       | Groups of the service user for local sockets             |
| `rspamd_clamd_address`      | `'/run/clamav/clamd.sock'` | Unix socket or `<host>:<port>`                           |
| `rspamd_antivirus_action`   | `'reject'`                 | `reject`, `add header`, `rewrite subject`, `soft reject` |
| `rspamd_antivirus_max_size` | `20000000`                 | Largest part in bytes sent to clamd                      |

Virus scanning is off until `rspamd_antivirus_enabled` is set and a clamd
is reachable at `rspamd_clamd_address`. The module sends attachments and
other non-text parts to clamd (upstream `scan_mime_parts`) and adds
`CLAM_VIRUS` with the name of the signature.

A clamd failure fails open: when clamd cannot be reached or does not
answer, rspamd adds `CLAM_VIRUS_FAIL` (score 0) and the mail is delivered
unscanned. Monitor for it, e.g. `CLAM_VIRUS_FAIL` in
`/var/log/rspamd/rspamd.log` or in the symbol statistics of the web
interface, and the clamd service itself. See [clamd](#clamd).

### DMARC Reports

| Variable                            | Default       | Description                              |
| ----------------------------------- | ------------- | ---------------------------------------- |
| `rspamd_dmarc_reporting_enabled`    | `false`       | Collect data and send aggregate reports  |
| `rspamd_dmarc_reporting_email`      | `''`          | Sender address of the reports (required) |
| `rspamd_dmarc_reporting_domain`     | `''`          | Reporting domain (required)              |
| `rspamd_dmarc_reporting_org_name`   | `''`          | Organization name (required)             |
| `rspamd_dmarc_reporting_smtp_host`  | `'127.0.0.1'` | SMTP server for the reports              |
| `rspamd_dmarc_reporting_smtp_port`  | `25`          | Its port                                 |
| `rspamd_dmarc_report_timer_enabled` | `true`        | Enable and start the report timer        |
| `rspamd_dmarc_report_on_calendar`   | `'daily'`     | Schedule (systemd `OnCalendar`)          |

rspamd collects the DMARC results of incoming mail in Valkey;
`rspamd-dmarc-report.timer` runs `rspamadm dmarc_report` as the service user,
which sends the aggregate reports of the previous day to the domains that
ask for them (`rua`). The units are always deployed; the timer runs while
reporting is enabled. The SMTP server must accept the reports from this host
without login (Postfix: the address in `postfix_mynetworks`).

### DNS Records

| Variable                   | Default                    | Description                                     |
| -------------------------- | -------------------------- | ----------------------------------------------- |
| `rspamd_dns_check_enabled` | `true`                     | Check the records (they are printed either way) |
| `rspamd_dns_resolver`      | `''`                       | IPv4 address of the resolver; empty: system's   |
| `rspamd_dns_resolver_port` | `53`                       | Port of the resolver                            |
| `rspamd_dns_dmarc`         | `'v=DMARC1; p=quarantine'` | Expected DMARC record; `''` skips it            |

See [DNS Records](#dns-records-1).

### Extra Configuration

| Variable              | Default | Description                              |
| --------------------- | ------- | ---------------------------------------- |
| `rspamd_local_config` | `{}`    | Further `local.d` files: name -> content |

```yaml
rspamd_local_config:
  'phishing.conf': |
    openphish_enabled = true;
  'mx_check.conf': |
    enabled = true;
```

The files take part in the `rspamadm configtest` of the staging directory.
A file of the role (`worker-proxy.inc`, `worker-normal.inc`,
`worker-controller.inc`, `redis.conf`, `options.inc`, `actions.conf`,
`classifier-bayes.conf`, `greylist.conf`, `ratelimit.conf`,
`milter_headers.conf`, `dkim_signing.conf`, `arc.conf`, `antivirus.conf`,
`dmarc.conf`) cannot be replaced here; use `override.d` by hand for a
setting the role does not offer. The files carry a marker line; a file
whose name leaves the mapping is deleted (a check run reports it). Other
files in `local.d` and `override.d` stay as they are.

## Tags

| Tag                | Description                                                  |
| ------------------ | ------------------------------------------------------------ |
| `rspamd`           | All tasks of the role                                        |
| `rspamd:install`   | Repository, packages, service user, targeted update          |
| `rspamd:dkim`      | DKIM keys                                                    |
| `rspamd:configure` | Password hashes, `local.d` files (staged, tested, activated) |
| `rspamd:service`   | Service and DMARC report timer                               |
| `rspamd:dns`       | Print and check the DNS records                              |

## Example Playbook

```yaml
- name: Mail server
  hosts: mail_servers
  become: true
  roles:
    - role: marcstraube.server.valkey
      vars:
        valkey_enabled: true
        valkey_users:
          - name: 'rspamd'
            password: '{{ vault_valkey_rspamd_password }}'
    # Before rspamd: the group of the clamd socket has to exist
    - role: marcstraube.common.clamav
      vars:
        clamav_freshclam_enabled: true
    - role: marcstraube.server.rspamd
      vars:
        rspamd_enabled: true
        rspamd_controller_password: '{{ vault_rspamd_password }}'
        rspamd_controller_enable_password: '{{ vault_rspamd_enable_password }}'
        rspamd_redis_password: '{{ vault_valkey_rspamd_password }}'
        rspamd_dns_nameservers:
          - '127.0.0.1'
        rspamd_antivirus_enabled: true
        rspamd_socket_groups:
          - 'clamav'
        rspamd_dkim_domains:
          - domain: 'example.com'
            selector: '2026'
```

On one host the run order is valkey → postfix → dovecot → clamav → rspamd.
Include the role once per play and host: a second include in the same play
decides the restart anew before the handlers of the first one have run.

## Testing

```bash
cd roles/rspamd

# Everything on one instance
molecule test

# rspamd in one container, Valkey, clamd and Postfix in another
molecule test -s split
```

Driver: `podman` | Scenarios: `default` (Arch Linux, Debian Trixie, Rocky
9, Rocky 10), `split` (Debian Trixie, two containers)

`default` sets up Valkey with the ACL user of rspamd
(`marcstraube.server.valkey`), clamd with a test signature database
(`marcstraube.common.clamav`, the EICAR signature only, reached through
its unix socket with `rspamd_socket_groups`), Postfix with the
milter and XCLIENT for the loopback interface, and a dnsmasq test resolver
for the instance and the controller (published on `15511`-`15514`; the
controller needs `dnspython`). It runs a check before converge and after
idempotence and checks `rspamadm configtest`, owner and mode of the files
and keys, GTUBE and EICAR rejected through Postfix and the milter (EICAR as
attachment, found by clamd), a clean message from an outside client
delivered with `X-Spam-Status: No` and an SPF pass and without signature, a
message from the signing network delivered with a DKIM signature that rspamd
verifies against the published key, spam training through the controller
with the enable password (Bayes tokens in Valkey), requests refused without
a password, with a wrong one and with the read password for learning, the
password hashes and the DKIM keys unchanged by another run, a public DKIM
record rebuilt from its key, the DMARC report service run once, the DNS
report (present, a DKIM record without `v=DKIM1`, missing, different; a
broken resolver), a run without the controller passwords (fails before any
change), a `local.d` file that `rspamadm configtest` rejects (the active
file and the process stay), and the removal of a file that left
`rspamd_local_config` (reported by a check run first, then deleted). Side
effect runs the targeted update with a minimum the repository does not
offer, with a mapping without a key for the host, and with the installed
version (no change, no restart), then renames a copy of the binary over the
running one as a package update does: the role with `latest` tests the
configuration with the new binary and restarts rspamd exactly once. The
repository of the rspamd project lists only its newest build and Arch Linux
has a single version, so no real rollback is possible.

`split` runs rspamd on one container and Valkey (TLS only, certificate of a
test CA), clamd (TCP) and Postfix on the other: Postfix uses the milter on
the address of the rspamd container, GTUBE and EICAR are rejected, the
signed message arrives, and Bayes learns into the Valkey of the other
container. The rspamd container has no `policy-rc.d` of the image, like a
Debian host; side effect leaves the role's own `policy-rc.d` behind, runs the
role with only `rspamd:dkim`, `rspamd:configure`, `rspamd:service` and
`rspamd:dns`, and runs it again in full, which removes the leftover.

## Notes

### Postfix

`marcstraube.server.postfix` sends every message through
`postfix_milters` (default `inet:127.0.0.1:11332`) with
`postfix_milter_default_action: tempfail`, so mail waits while rspamd is
down. For a Postfix on another host:

```yaml
# rspamd host
rspamd_milter_bind: '10.0.0.20:11332'
# Postfix host
postfix_milters:
  - 'inet:10.0.0.20:11332'
```

The milter protocol has no authentication or encryption: only over a
private network or WireGuard, and the firewall opens the port for the
Postfix host only.

### clamd

`marcstraube.common.clamav` on the same host: rspamd connects to the unix
socket (`clamav_socket`, default `/run/clamav/clamd.sock`, mode `0660`) as
its service user, so that user joins the group of the socket, the group of
the clamav service user:

```yaml
rspamd_socket_groups:
  - 'clamav'     # 'clamscan' on EL
```

The group must exist, so the clamav role runs before rspamd; the role
restarts rspamd while its running main process lacks one of the groups
(systemd sets the groups at the start), also on the run after one that
failed before the restart. `clamav_socket_group` does not help here: clamd changes the group of
the socket after it dropped its privileges and fails for a group its own
user is not a member of. `clamav_rspamd_integration_enabled` of the clamav
role adds `_rspamd` to the clamav group, but only when rspamd is installed
before clamav runs, never `rspamd` (Arch Linux), and without restarting
rspamd.

A clamd on another host listens on TCP:

```yaml
# clamd host
clamav_tcp_socket: '3310'
clamav_tcp_addr: '10.0.0.30'
# rspamd host
rspamd_clamd_address: '10.0.0.30:3310'
```

The clamd protocol has no authentication or encryption; anyone who reaches
the port can use the scanner and send it data. A remote clamd belongs on a
private network or WireGuard, with the port open for the rspamd host only.

### Dovecot

The spam training of `marcstraube.server.dovecot` posts messages moved into
or out of Junk to `/learnspam` and `/learnham` of the controller with the
enable password:

```yaml
dovecot_rspamd_learn_enabled: true
dovecot_rspamd_controller_url: 'http://127.0.0.1:11334'
dovecot_rspamd_controller_password: '{{ vault_rspamd_enable_password }}'
```

A Dovecot on another host needs an `https://` URL: put a web server in front
of the controller (below).

### Web Interface

The controller serves the web interface on `rspamd_controller_bind`. For
access from other hosts, put a web server with TLS in front of it and keep
the controller on the loopback interface. With
`marcstraube.server.nginx`:

```yaml
nginx_sites:
  - name: 'rspamd.example.com'
    server_names:
      - 'rspamd.example.com'
    type: 'proxy'
    proxy_pass: 'http://127.0.0.1:11334'
    ssl:
      enabled: true
      certificate: '/etc/letsencrypt/live/rspamd.example.com/fullchain.pem'
      certificate_key: '/etc/letsencrypt/live/rspamd.example.com/privkey.pem'
```

With `marcstraube.server.apache`:

```yaml
apache_modules_enabled:
  - 'proxy'
  - 'proxy_http'
apache_vhosts_ssl:
  - server_name: 'rspamd.example.com'
    certificate_file: '/etc/letsencrypt/live/rspamd.example.com/fullchain.pem'
    certificate_key_file: '/etc/letsencrypt/live/rspamd.example.com/privkey.pem'
    custom_config: |
      ProxyPass "/" "http://127.0.0.1:11334/"
      ProxyPassReverse "/" "http://127.0.0.1:11334/"
```

On EL, Apache and nginx need the SELinux boolean `httpd_can_network_connect`
for the proxy (`apache_selinux_network_connect: true`,
`nginx_selinux_network_connect: true`).

Keep `rspamd_controller_secure_ips` empty: the web server connects from the
loopback interface, so a trusted loopback would open the interface to every
visitor. Both passwords travel in every request; send them over TLS only.

### Remote Setups

- Postfix: `rspamd_milter_bind: '<private address>:11332'` here,
  `postfix_milters: ['inet:<rspamd>:11332']` on the Postfix host.
- Valkey: `rspamd_redis_servers: ['<valkey>:6380']` and `rspamd_redis_tls:
  true` here, `valkey_tls_enabled: true` and the ACL user on the Valkey host.
- clamd: `rspamd_clamd_address: '<clamd>:3310'` here, `clamav_tcp_socket:
  '3310'` and `clamav_tcp_addr` on the clamd host.
- Dovecot: the controller behind a web server with TLS here,
  `dovecot_rspamd_controller_url: 'https://...'` on the Dovecot host.

### DNS Records

The role prints the records rspamd is responsible for and checks each one
from the controller with `community.general.dig`, reported as `PRESENT`,
`MISSING` or `DIFFERENT` with the values found. A missing record never fails
the run.

| Record                                   | Expected                                                     |
| ---------------------------------------- | ------------------------------------------------------------ |
| `<selector>._domainkey.<domain>. IN TXT` | The DKIM record of the key (compared by its public key `p=`) |
| `_dmarc.<domain>. IN TXT`                | `rspamd_dns_dmarc` (see below)                               |

DKIM counts the TXT records with a `p=` tag (`v=DKIM1` is optional, RFC
6376 3.6.1) and compares the public key; DMARC counts the records starting
with `v=DMARC1` and compares them without whitespace and case.

A DKIM record is listed without its value and unchecked while the key does
not exist yet (check mode on a new host) or while `openssl` cannot rebuild
its record. When the lookup itself fails (no `dnspython`, a
resolver name that does not resolve), the records are listed as unchecked
with a warning and the run goes on. MX, SPF, A and PTR belong to the postfix
role.

### Firewall

The role does not manage firewall rules. The milter (11332) and the
controller (11334) only need a rule when another host uses them, and then
only for that host, through the `marcstraube.common.firewalld` inventory,
for example:

```yaml
firewalld_zone_ports:
  - zone: 'internal'
    ports:
      - '11332/tcp'   # milter for the Postfix host
```

Keep the controller on the loopback interface behind a web server (443)
instead of opening 11334.

### SELinux

Neither the packages of the rspamd project nor the targeted policy of EL 9
and 10 carry an SELinux module for rspamd (no rspamd types in
`selinux-policy-targeted`), so systemd starts it unconfined
(`unconfined_service_t`): the unlabeled ports 11332 and 11334 need no label
and rspamd may connect to Valkey and clamd. The role labels nothing.

### Platform Differences

| Platform | Differences the role covers                                               |
| -------- | ------------------------------------------------------------------------- |
| Debian   | Repository of the rspamd project (deb822); first install without a start  |
| EL       | Repository of the rspamd project, EPEL dependencies; service user created |
| Arch     | Distribution package, service user `rspamd`                               |

On Debian the package starts rspamd during its first install with the
packaged configuration (controller password `q1`, trusted from the loopback
interface). The role keeps it from starting with a temporary
`/usr/sbin/policy-rc.d`, removed right after the install, and starts it
itself with its own configuration. The file only ever blocks rspamd; one
left behind by an interrupted first run (it carries the role's marker) is
removed on the next run that includes the install tasks. An existing
`policy-rc.d` of the host is left as it is.

### Logging

rspamd logs to `/var/log/rspamd/rspamd.log` (rotated by the logrotate file
of the package). Every scanned message ends in one line with the action,
the score and the symbols, for example a message from the signing network (shortened):

<!-- markdownlint-disable MD013 -->
```text
rspamd_task_write_log: id: <signed.342282@example.com>, ip: 127.0.0.1, from: <alice@example.com>, (default: F (no action): [1.50/15.00] [INVALID_DATE(1.50){},MIME_GOOD(-0.10){text/plain;},RCVD_NO_TLS_LAST(0.10){},ARC_NA(0.00){},DKIM_SIGNED(0.00){example.com:s=molecule;},FROM_EQ_ENVFROM(0.00){},LOCAL_OUTBOUND(0.00){},...]), len: 1398, time: 75.373ms, dns req: 2, mime_rcpts: <molecule@localhost>
```
<!-- markdownlint-enable MD013 -->

### Removing State

The role removes what it can identify from the current variables: files of
`rspamd_local_config` that left the mapping, the DKIM and ARC domain maps
without domains, the antivirus rule without `rspamd_antivirus_enabled`.
DKIM keys are never deleted (an old selector may still be published).
Turning the role off leaves rspamd installed and configured.

## References

- [rspamd documentation](https://docs.rspamd.com/)
- [rspamd downloads (repositories)](https://docs.rspamd.com/downloads)
- [Milter headers module](https://docs.rspamd.com/modules/milter_headers)
- [DKIM signing module](https://docs.rspamd.com/modules/dkim_signing)
- [Antivirus module](https://docs.rspamd.com/modules/antivirus)
- [DMARC module](https://docs.rspamd.com/modules/dmarc)
- [Controller worker](https://docs.rspamd.com/workers/controller)

## License

MIT

## Author

Marc Straube
