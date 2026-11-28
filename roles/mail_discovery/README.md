# marcstraube.server.mail_discovery

Publish the discovery data of the mail domains for clients: the account
settings mail clients use for automatic configuration (Autoconfig,
Autodiscover, Apple profile), and for sending mail servers: the MTA-STS
policy and the TLS-RPT record.

## Description

Renders static files into a web root so mail clients configure an account from
the email address alone:

- **Mozilla Autoconfig** (Thunderbird, Thunderbird for Android, Evolution, KMail
  and others): `mail/config-v1.1.xml`, also as
  `.well-known/autoconfig/mail/config-v1.1.xml`
- **Microsoft Autodiscover** (Outlook): `autodiscover/autodiscover.xml`, the POX
  response for IMAP and SMTP accounts
- **Apple configuration profile** (optional): a generic, unsigned
  `apple/<domain>.mobileconfig` per domain without a user address; the device
  asks for the address and the user name on import
- **MTA-STS policy** (optional, RFC 8461): `.well-known/mta-sts.txt`, served
  as `https://mta-sts.<domain>/.well-known/mta-sts.txt`, tells sending mail
  servers that the MX hosts accept mail only over TLS with a valid
  certificate; with the TLS-RPT record (RFC 8460) they send daily reports
  about failed TLS connections (see [MTA-STS and TLS-RPT](#mta-sts-and-tls-rpt))

The files are static (no PHP) and work with any web server, which may run on
another host than Postfix and Dovecot. The role does not manage the web server;
the [Web Server](#web-server) section shows sites for
[`marcstraube.server.nginx`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/nginx/README.md) and
[`marcstraube.server.apache`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/apache/README.md).

The role also prints the DNS records the clients look up for each domain and
checks each one on the controller, reporting it as present, missing or
different from the expected value. A missing record never fails the run.
Finally it requests every published file over HTTPS the way the clients do and
reports each one as reachable or unreachable, which never fails the run
either.

The role is **opt-in**: it does nothing until `mail_discovery_enabled` is set
to `true`.

## Requirements

- ansible-core >= 2.19
- `community.general` collection (`community.general.dig` lookup); a resolver
  port other than 53 (`mail_discovery_dns_resolver_port`) needs
  community.general 9.5.0 or later
- **Controller:** the Python library `dnspython` for the DNS check, installed
  for the Python that runs Ansible (`python-dnspython` on Arch Linux,
  `python3-dnspython` on Debian and EL, or `pip install dnspython` in a
  virtual environment). Without it the role reports that the check could not
  run, prints the records unchecked and goes on;
  `mail_discovery_dns_check_enabled: false` turns the check off.
- A web server with TLS for `autoconfig.<domain>` and `autodiscover.<domain>`,
  with MTA-STS also for `mta-sts.<domain>` (see [Web Server](#web-server) and
  [Certificates](#certificates))

## Supported Platforms

| Platform                  | Notes |
| ------------------------- | ----- |
| Arch Linux                |       |
| Debian Trixie             |       |
| EL 9 (Rocky, Alma, RHEL)  |       |
| EL 10 (Rocky, Alma, RHEL) |       |

Other distributions in the same os_family (EndeavourOS, Manjaro, Ubuntu, Mint,
Fedora) should work but are not actively tested. Use distro-specific vars
overrides if needed.

## Role Variables

See [defaults/main.yml](defaults/main.yml) for all available variables.

### Role Control

| Variable                 | Default | Description                    |
| ------------------------ | ------- | ------------------------------ |
| `mail_discovery_enabled` | `false` | Enable the mail_discovery role |

### Files

| Variable                            | Default                     | Description                           |
| ----------------------------------- | --------------------------- | ------------------------------------- |
| `mail_discovery_web_root`           | `'/var/www/mail-discovery'` | Directory the files are rendered into |
| `mail_discovery_domains`            | `[]`                        | Mail domains served (required)        |
| `mail_discovery_display_name`       | `''`                        | Provider name; empty: first domain    |
| `mail_discovery_display_short_name` | `''`                        | Short name; empty: display name       |

The role checks its settings before any change and fails with a message per
setting: `mail_discovery_domains` must be a non-empty list of domain names,
the IMAP, submission, POP3 (when enabled) and web host names must be fully
qualified, at least one submission mode must be enabled, the ports of the
enabled services must be integers from 1 to 65535 and
`mail_discovery_web_root` must be an absolute path. Internationalized domain
names are expected in their ACE form (`xn--...`).

The role creates a missing web root as `root:root 0755`; missing parent
directories get the same owner and mode (`ansible.builtin.file` applies them
to every directory it creates). An existing web root keeps its owner and mode:
the role never changes them, but fails before any change unless it is a
directory owned by root and not writable by group or others. The files tell
the clients where to send the passwords, so whoever can replace them can
redirect the logins; see [Web Root](#web-root).

All domains share one Mozilla file, which lists every domain in a `<domain>`
element. The file is public on every `autoconfig.<domain>` site, so anyone
who knows one served domain can read all the others. Domains that must not be
linked to each other need separate runs of the role with their own web root
and sites.

### Servers

The login name is always the full email address (`%EMAILADDRESS%` in the
Mozilla file). IMAP and POP3 use implicit TLS.

| Variable                                         | Default | Description                    |
| ------------------------------------------------ | ------- | ------------------------------ |
| `mail_discovery_imap_host`                       | `''`    | IMAP host (required)           |
| `mail_discovery_imap_port`                       | `993`   | IMAP port (implicit TLS)       |
| `mail_discovery_submission_host`                 | IMAP    | Submission host                |
| `mail_discovery_submission_implicit_tls_enabled` | `true`  | Offer submission on 465        |
| `mail_discovery_submission_implicit_tls_port`    | `465`   | Port for implicit TLS          |
| `mail_discovery_submission_starttls_enabled`     | `true`  | Offer submission with STARTTLS |
| `mail_discovery_submission_starttls_port`        | `587`   | Port for STARTTLS              |
| `mail_discovery_pop3_enabled`                    | `false` | Offer POP3 after IMAP          |
| `mail_discovery_pop3_host`                       | IMAP    | POP3 host                      |
| `mail_discovery_pop3_port`                       | `995`   | POP3 port (implicit TLS)       |

IMAP in the Default column: the value of `mail_discovery_imap_host`.

At least one submission mode has to be enabled. Where a format holds one
outgoing server only (Autodiscover, Apple profile), it gets implicit TLS when
enabled and STARTTLS otherwise; the Mozilla file lists both, implicit TLS first
(RFC 8314).

### Apple Configuration Profile

| Variable                               | Default | Description                                     |
| -------------------------------------- | ------- | ----------------------------------------------- |
| `mail_discovery_apple_profile_enabled` | `false` | Render `apple/<domain>.mobileconfig` per domain |

Turning the profile off removes the `apple/` directory below the web root
with every profile in it; the directory belongs to the role, so do not put
other files there.

The payload has no setting for STARTTLS. `OutgoingMailServerUseSSL` is always
`true`: the device then requires TLS on the submission connection and
negotiates it with STARTTLS on port 587 or as implicit TLS on port 465. With
`false` the device would also accept a connection without TLS and send the
password in clear text. The profile names the port of implicit TLS when it is
enabled and the STARTTLS port otherwise.

### MTA-STS and TLS-RPT

| Variable                         | Default     | Description                                      |
| -------------------------------- | ----------- | ------------------------------------------------ |
| `mail_discovery_mta_sts_enabled` | `false`     | Render the MTA-STS policy                        |
| `mail_discovery_mta_sts_mode`    | `'testing'` | Policy mode: `testing`, `enforce` or `none`      |
| `mail_discovery_mta_sts_mx`      | `[]`        | MX host names of the policy (required when on)   |
| `mail_discovery_mta_sts_max_age` | `604800`    | Seconds senders cache the policy (one week)      |
| `mail_discovery_tls_rpt_rua`     | `[]`        | TLS-RPT report URIs; empty: no `_smtp._tls` TXT  |

With MTA-STS enabled the mode must be one of the three values, the MX list a
non-empty list of host names (a leading `*.` matches one label, e.g.
`*.mx.example.net`) and the max age an integer from 1 to 31557600 (one year,
the RFC 8461 maximum). Mode `none` still requires and renders the MX list:
it does no harm while a policy is withdrawn, and switching back needs no
other change. Every report URI must be `mailto:` with an address or `https://`
with a host name, in printable ASCII without quotes or backslashes; commas and
`!` inside a URI must be percent-encoded (they separate URIs in the record). The role checks all of them before any
change. TLS-RPT does not depend on MTA-STS: the reports cover DANE as well, so
the record is expected whenever `mail_discovery_tls_rpt_rua` is set.

The role owns `.well-known/mta-sts.txt` in the web root: unless MTA-STS is
enabled it removes the file, also a policy written there by hand. To withdraw
a published policy, do not turn it off right away; see
[MTA-STS Rollout and Withdrawal](#mta-sts-rollout-and-withdrawal).

### DNS

| Variable                           | Default | Description                                       |
| ---------------------------------- | ------- | ------------------------------------------------- |
| `mail_discovery_dns_check_enabled` | `true`  | Check the records (they are printed either way)   |
| `mail_discovery_dns_resolver`      | `''`    | IPv4 address of the resolver; empty: system's     |
| `mail_discovery_dns_resolver_port` | `53`    | Port of the resolver                              |
| `mail_discovery_web_host`          | FQDN    | Host the discovery and `mta-sts` names target     |

FQDN: `ansible_facts["fqdn"]` of the web host. An empty resolver uses the
system resolver of the controller.

`community.general.dig` takes IPv4 addresses for the resolver; any other value
is resolved as a host name through the system resolver (IPv6 addresses do not
work). Several resolvers are separated by commas.

With several web hosts serving the same files (a cluster behind a load
balancer or several hosts in round robin), set `mail_discovery_web_host` to
the shared name the records point to, the same on every host. The default,
the FQDN of each host, would make every host expect the records to point to
itself and report them as different. The check runs once per host; turning it
off (`mail_discovery_dns_check_enabled: false`) on all but one host avoids
the repeated lookups.

### HTTP

| Variable                                   | Default       | Description                                  |
| ------------------------------------------ | ------------- | -------------------------------------------- |
| `mail_discovery_http_check_enabled`        | `true`        | Request the files over HTTPS and report them |
| `mail_discovery_http_check_delegate`       | `'localhost'` | Host the requests are sent from              |
| `mail_discovery_http_check_validate_certs` | `true`        | Verify the certificates of the sites         |
| `mail_discovery_http_check_ca_path`        | `''`          | CA file on the delegate host; empty: system  |

`localhost` is the controller, like the DNS check. For certificates of an
internal CA set `mail_discovery_http_check_ca_path` instead of turning
verification off: the clients verify the certificates as well. See
[HTTP Check](#http-check).

## Tags

| Tag                    | Description                     |
| ---------------------- | ------------------------------- |
| `mail-discovery`       | All tasks of the role           |
| `mail-discovery:files` | Render the files                |
| `mail-discovery:dns`   | Print and check the DNS records |
| `mail-discovery:http`  | Request the files over HTTPS    |

## Example Playbook

```yaml
- name: Mail discovery
  hosts: web_servers
  become: true
  roles:
    - role: marcstraube.server.mail_discovery
      vars:
        mail_discovery_enabled: true
        mail_discovery_domains:
          - 'example.com'
          - 'example.org'
        mail_discovery_display_name: 'Example Mail'
        mail_discovery_imap_host: 'mail.example.com'
        mail_discovery_web_host: 'web.example.com'
        mail_discovery_apple_profile_enabled: true
```

The role runs on the web host. Run it after the web server and certbot plays,
so the sites and certificates exist.

## Testing

```bash
cd roles/mail_discovery
molecule test -s nginx
molecule test -s apache
```

Driver: `podman` | Platforms: Arch Linux, Debian Trixie, Rocky 9, Rocky 10

Both scenarios set up the web server with the example from
[Web Server](#web-server) and request the files through it (`GET` on the
Autoconfig file and the MTA-STS policy, `POST` on the Autodiscover file). A
dnsmasq instance in the container serves a test zone and is published to the
controller on a port per platform (`15301`-`15304` for nginx, `15401`-`15404`
for Apache), so the DNS check runs against it with present, missing and
different records (the MTA-STS record written without the space after `;`,
the TLS-RPT record split into two strings, an unrelated TXT record beside the
policy record, MX hosts the policy lists and one it does not, a domain
without MX records and one with a null MX). The controller needs `dnspython`.

The HTTP check runs in the container (`mail_discovery_http_check_delegate`
set to the platform): the controller cannot reach the web server there by
name. `etc_hosts` in `molecule.yml` points the `autoconfig`, `autodiscover`
and `mta-sts` names to the container itself, and a CA file with the
self-signed certificates of prepare is passed as
`mail_discovery_http_check_ca_path`. Besides the README sites, prepare sets up
a site that redirects the MTA-STS policy of `example.net`.

Each platform runs another set of toggles (`molecule/shared/vars/main.yml`),
so every toggle is tested on and off: implicit TLS and STARTTLS alone and
together, POP3, the Apple profile, MTA-STS in `testing` and in `enforce` mode
with another max age, TLS-RPT (also without MTA-STS), the DNS and HTTP checks
and the display name fallbacks. Verify checks owner and mode of the web root,
every directory and every file, the MTA-STS policy byte by byte (CRLF line
ends), that the policy id in the DNS report is the start of the SHA-256 of
the file, that the sites serve the policy as `text/plain`, and which MX hosts
the policy lists. It also runs the DNS check with a resolver that cannot be
resolved (reported, the run goes on) and with a broken variable (fails the
run), the HTTP check without the CA file (certificate errors reported, the run
goes on), without certificate verification, with the Autodiscover file moved
away (the POST reported unreachable), with another MTA-STS policy on the site
(reported with different content) and against the redirected policy
(reported with `301`, not followed), turns the Apple profile and MTA-STS off,
lets the role create a new web root with its parents, and runs the role with
a bad value for every setting check, including a group-writable web root and
one owned by another user (refused, left unchanged); on a platform with
MTA-STS off no policy file exists after these runs.

## Notes

### Files and URLs

| Client                 | Request (HTTPS)                                        | File                            |
| ---------------------- | ------------------------------------------------------ | ------------------------------- |
| Thunderbird and others | `GET autoconfig.<domain>/mail/config-v1.1.xml`         | `mail/config-v1.1.xml`          |
| Thunderbird (fallback) | `GET <domain>/.well-known/autoconfig/mail/...`         | `.well-known/autoconfig/mail/…` |
| Outlook                | `POST <domain>/autodiscover/autodiscover.xml`          | `autodiscover/autodiscover.xml` |
| Outlook (second)       | `POST autodiscover.<domain>/autodiscover/...`          | `autodiscover/autodiscover.xml` |
| iOS, iPadOS, macOS     | `GET autoconfig.<domain>/apple/<domain>.mobileconfig`  | `apple/<domain>.mobileconfig`   |
| Sending mail servers   | `GET mta-sts.<domain>/.well-known/mta-sts.txt`         | `.well-known/mta-sts.txt`       |

Thunderbird adds `?emailaddress=<address>` to the first request; the fallback
file is `.well-known/autoconfig/mail/config-v1.1.xml`. The Apple profile is
opened by the user, e.g. from a link on a help page.

The `autoconfig.<domain>`, `autodiscover.<domain>` and `mta-sts.<domain>` sites
serve the whole web root. The requests to `<domain>` itself only reach these files when the site of
the domain serves `/.well-known/autoconfig/` and `/autodiscover/` from the web
root as well (e.g. an `alias` location); the clients fall back to the
subdomains otherwise.

Content types: the XML files are served as `text/xml` (nginx) or
`application/xml` (Apache, from `/etc/mime.types`); neither web server knows
`.mobileconfig`, so the examples add `application/x-apple-aspen-config`. The
MTA-STS policy must be served as `text/plain` (RFC 8461); both web servers do
that for `.txt` from their default MIME types (verified in Molecule).

### Web Root

Give the files a site of their own: a dedicated nginx site or Apache vhost for
the `autoconfig.<domain>` and `autodiscover.<domain>` names (as in the examples
below), whose web root holds only the files of this role. Not a directory of
another site, and nothing the web server or a deploy user can write to: the
files tell the mail clients which servers receive their passwords, so a
compromised web application or deploy account that can replace them redirects
every new account setup to a server of its choice.

The role enforces the part it can see: it refuses an existing web root that is
not owned by root or is writable by group or others, and fails before any
change (in check mode as well). It does not change the owner or mode of an
existing directory, so fix it or point `mail_discovery_web_root` to a path
that does not exist yet, which the role creates as `root:root 0755`.

### Web Server

With MTA-STS enabled, every site also needs the `mta-sts.<domain>` name and
must serve `/.well-known/mta-sts.txt` from the web root with
`Content-Type: text/plain`, without a redirect: senders do not follow
redirects for the policy. The examples below include the name.

Outlook requests the Autodiscover file with `POST`. Apache answers a `POST` on a
static file with the file as is. nginx answers `405 Not Allowed` and needs
`error_page 405 =200 $uri;` to serve the file with `200` (both verified in
Molecule). A plain `GET` in a browser works either way, so the missing line
goes unnoticed until Outlook fails; the [HTTP check](#http-check) sends a
`POST` and reports such a site as unreachable with status `405`.

nginx (`marcstraube.server.nginx`), one site per mail domain. The web host
name (`mail_discovery_web_host`, here `web.example.com`) is the target of the
`_autodiscover._tcp` SRV records of all domains; a name can belong to one site
only, so it goes into the site of the first domain:

```yaml
nginx_sites:
  - name: 'mail-discovery-example.com'
    server_names:
      - 'autoconfig.example.com'
      - 'autodiscover.example.com'
      - 'mta-sts.example.com'
      - 'web.example.com'
    root: '/var/www/mail-discovery'
    ssl:
      enabled: true
      certificate: '/etc/letsencrypt/live/autoconfig.example.com/fullchain.pem'
      certificate_key: '/etc/letsencrypt/live/autoconfig.example.com/privkey.pem'
    http_redirect: true
    locations:
      - path: '/apple/'
        config: |
          types { application/x-apple-aspen-config mobileconfig; }
    extra_config: |
      # Outlook sends a POST to autodiscover.xml; nginx answers 405 on
      # static files and serves the file with 200 instead
      error_page 405 =200 $uri;
```

Apache (`marcstraube.server.apache`), one SSL vhost per mail domain, the web
host name again in the vhost of the first domain:

```yaml
apache_ssl_enabled: true
apache_vhosts_ssl:
  - server_name: 'autoconfig.example.com'
    server_alias:
      - 'autodiscover.example.com'
      - 'mta-sts.example.com'
      - 'web.example.com'
    document_root: '/var/www/mail-discovery'
    certificate_file: '/etc/letsencrypt/live/autoconfig.example.com/fullchain.pem'
    certificate_key_file: '/etc/letsencrypt/live/autoconfig.example.com/privkey.pem'
    certificate_chain_file: ''
    custom_config: |
      AddType application/x-apple-aspen-config .mobileconfig
```

### Certificates

Every mail domain needs a certificate for `autoconfig.<domain>` and
`autodiscover.<domain>`, with MTA-STS also for `mta-sts.<domain>`, the first
domain also for the web host name (the target of the `_autodiscover._tcp` SRV
records, see [DNS Records](#dns-records)). Senders fetch the MTA-STS policy
only over HTTPS with a certificate valid for `mta-sts.<domain>` and ignore it
otherwise. With
[`marcstraube.server.certbot`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/certbot/README.md),
one certificate per domain named after the first name matches the paths
above:

```yaml
certbot_certificates:
  - domains:
      - 'autoconfig.example.com'
      - 'autodiscover.example.com'
      - 'mta-sts.example.com'
      - 'web.example.com'
  - domains:
      - 'autoconfig.example.org'
      - 'autodiscover.example.org'
      - 'mta-sts.example.org'
```

The IMAP, submission and POP3 hosts need certificates of their own on the mail
host (Dovecot, Postfix).

### DNS Records

The role prints these records per domain (values from the variables) on every
run and reports each one as `PRESENT`, `MISSING` or `DIFFERENT`; with the check
off or failed, they are listed as `UNCHECKED`:

```text
autoconfig.example.com.          IN CNAME web.example.com.
autodiscover.example.com.        IN CNAME web.example.com.
_imaps._tcp.example.com.         IN SRV 0 1 993 mail.example.com.
_submissions._tcp.example.com.   IN SRV 0 1 465 mail.example.com.
_submission._tcp.example.com.    IN SRV 0 1 587 mail.example.com.
_pop3s._tcp.example.com.         IN SRV 0 1 995 mail.example.com.
_autodiscover._tcp.example.com.  IN SRV 0 1 443 web.example.com.
mta-sts.example.com.             IN CNAME web.example.com.
_mta-sts.example.com.            IN TXT "v=STSv1; id=1f0c6b9e2a4d8c7e5b3a"
_smtp._tls.example.com.          IN TXT "v=TLSRPTv1; rua=mailto:tls-reports@example.com"
```

- `autoconfig`, `autodiscover` and `mta-sts` may be a CNAME to
  `mail_discovery_web_host` or A/AAAA records with its addresses; both count
  as present.
- With MTA-STS enabled, the check also looks up the MX records of every
  domain and reports each MX host as `LISTED` when it matches an entry of
  `mail_discovery_mta_sts_mx` (case-insensitive; `*.` matches exactly one
  leftmost label) and as `UNLISTED` otherwise, followed by a warning. A
  domain without MX records is compared as its own implicit MX (RFC 5321,
  section 5.1) and printed as `<domain>. (implicit MX, no MX record)`; the
  lookup returns the same empty answer when the resolver times out, so such
  a line can also mean that no answer came. A null MX (`0 .`, RFC 7505) is
  reported as `NULL`: the domain accepts no mail and should not publish an
  MTA-STS policy (the role warns). The comparison never fails the run.
- `mta-sts` and `_mta-sts` are only expected with MTA-STS enabled,
  `_smtp._tls` only with `mail_discovery_tls_rpt_rua` set. The policy id is
  the start of the SHA-256 of the policy (20 hex characters), so it changes
  with every change of the mode, the MX list or the max age; update the
  `_mta-sts` record after such a change: senders with a cached policy fetch
  the new one only when the id changes or the cached one expires.
- A TXT record counts as present when exactly one record of its version
  (`v=STSv1`, `v=TLSRPTv1`) exists and matches; records of other content are
  ignored, as the senders do. Several strings of one record are joined, and
  spaces around `;` and `,` do not matter. Two records of the version count
  as different: senders then use none of them.
- The SRV records follow RFC 6186 (`_imaps`, `_pop3s`, `_submission`) and
  RFC 8314 (`_submissions`). A record is checked for port and target; priority
  and weight are free. `_submission`, `_submissions` and `_pop3s` are only
  expected for the services that are enabled. RFC 6186 allows a target of `.`
  for a service that is not offered; the role reports such a record as
  different and does not expect it.
- `_autodiscover._tcp` lets Outlook find the Autodiscover host when the other
  lookups fail. It points at `mail_discovery_web_host` directly, so the
  `autodiscover.<domain>` name can stay a CNAME for the clients that query it.
  Outlook then requests `https://<web host>/autodiscover/autodiscover.xml`
  (after asking the user to confirm the redirect): the web server has to
  serve the web root under the web host name with a certificate for it.
- SRV targets must have A/AAAA records of their own and must not be a CNAME
  (RFC 2782). The role does not check the record type of the targets.
- The check queries `mail_discovery_dns_resolver` from the controller. The
  lookup returns the same empty answer for a missing record and a resolver that
  does not answer; when nothing is found at all, the role prints a hint to
  check the resolver.
- Each lookup waits up to 5 seconds for an answer (dnspython default: 2
  seconds per attempt, 5 seconds in total; `community.general.dig` has no
  timeout option). The check sends up to 17 lookups per domain and 2 for the
  web host, so a resolver that does not answer delays the run by roughly one
  minute per domain before the role reports that nothing was found. Use a
  resolver that answers from the controller, or turn the check off.
- Only an error of the lookup itself (dnspython missing, a resolver name that
  does not resolve) is reported as a skipped check, with the records printed
  unchecked. Any other error in the check fails the run.

### HTTP Check

The role requests every file it publishes, per mail domain:

| Request                                                            | Reachable when                            |
| ------------------------------------------------------------------ | ----------------------------------------- |
| `GET https://autoconfig.<domain>/mail/config-v1.1.xml`             | `200`, XML content type                   |
| `GET https://autoconfig.<domain>/.well-known/autoconfig/mail/…`    | `200`, XML content type                   |
| `POST https://autodiscover.<domain>/autodiscover/autodiscover.xml` | `200`, XML content type                   |
| `GET https://autoconfig.<domain>/apple/<domain>.mobileconfig`      | `200`, `application/x-apple-aspen-config` |
| `GET https://mta-sts.<domain>/.well-known/mta-sts.txt`             | `200`, `text/plain`, the rendered policy  |

The Apple profile and the MTA-STS policy are requested only when they are
enabled. The policy request follows no redirect, like the senders, and its
body has to equal the rendered policy; another body (a stale copy, a site
with another web root) is reported as `different content`. The `POST` carries a
minimal POX request as Outlook sends it (`Content-Type: text/xml`, an
`EMailAddress` of `autoconfig-check@<domain>`). Each request is printed as
`REACHABLE` or `UNREACHABLE` with the status code and content type of the
answer, or with the error (name resolution, connection, certificate,
timeout). An unreachable file never fails the run; the role prints a hint
after the list. The requests to `<domain>` itself (see
[Files and URLs](#files-and-urls)) are optional fallbacks and not checked.

- The requests are sent from `mail_discovery_http_check_delegate`, by
  default the controller (`localhost`), with `ansible.builtin.uri` and without
  privilege escalation (`become: false`, so the controller asks for no sudo
  password). They see what a client in the controller's network sees: its
  resolver, its routes, its trust store. When the controller cannot reach the
  sites (an internal web host, split DNS), set the delegate to an inventory
  host that can, e.g. the web host itself.
- Certificates are verified (`mail_discovery_http_check_validate_certs`),
  against the system trust store of the delegate host or the CA file in
  `mail_discovery_http_check_ca_path`.
- Each request waits up to 30 seconds (default of `ansible.builtin.uri`), with
  up to 5 requests per domain; a site that drops the packets delays the run
  accordingly. Redirects are followed for the `GET` of the client files, not
  for the `POST` and not for the `GET` of the MTA-STS policy (senders do not
  follow them either).
- The check runs in check mode as well and never reports a change. With
  several web hosts serving the same names, every host sends the same
  requests; turn the check off on all but one.

### MTA-STS Rollout and Withdrawal

One policy covers all mail domains: they share the MX list. Domains with other
MX hosts need a separate run of the role with their own web root and sites.

- **MX list:** every MX host of the domains must match an entry of
  `mail_discovery_mta_sts_mx`, and Postfix on port 25 must present a
  certificate of a public CA that is valid for the MX host name (see
  [`marcstraube.server.postfix`](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/postfix/README.md)).
  In `enforce` mode, senders that support MTA-STS refuse to deliver to an MX
  host that is not listed or whose certificate fails. The DNS check compares
  the list with the MX records of the domains and reports every MX host it
  does not list (see [DNS Records](#dns-records)). The report is advisory:
  the role deploys the policy, `enforce` included, also when an MX host is
  `UNLISTED`; check the report before switching to `enforce`.
- **Rollout:** start with `testing`: senders deliver as before and report
  failed TLS connections to the TLS-RPT URIs. Switch to `enforce` once the
  reports show no failures. The policy id
  changes with the mode; update the `_mta-sts` record with it.
- **Withdrawal:** senders keep a policy cached for its max age and still
  enforce it when the record and the file are gone. To withdraw a policy, set
  `mail_discovery_mta_sts_mode: none` and publish the new id, keep both until
  the old max age has passed, then turn MTA-STS off and delete the
  `mta-sts`/`_mta-sts` records (RFC 8461, section 8.3).
- **Max age:** RFC 8461 recommends weeks or longer; senders refresh the
  policy on a new id anyway. The default is one week.
- **TLS-RPT:** a TXT string holds at most 255 characters; a longer record
  has to be split into several strings in the zone.

### SELinux

On EL the files need the type `httpd_sys_content_t` to be served by nginx or
Apache. Below `/var/www` (the default web root) the policy assigns it, and the
role's files get it when they are created. For a web root elsewhere, add a
file context rule and relabel before the role runs, e.g.:

```bash
semanage fcontext -a -t httpd_sys_content_t '/srv/mail-discovery(/.*)?'
restorecon -R /srv/mail-discovery
```

The role does not manage SELinux file contexts.

### Limitations

- **Outlook login:** Autodiscover gives Outlook the server settings only. The
  user still logs in manually: Outlook asks for the password, and a static
  file cannot name the user's address, so the file has no `LoginName`.
  Microsoft documents the local part of the address as the default then,
  while the mail stack expects the full address, so an Outlook user may have
  to correct the user name once. A dynamic Autodiscover service (reading
  `EMailAddress` from the request) is out of scope of this role.
- **Outlook versions:** POX Autodiscover is documented for Outlook 2007 and
  later. Current Outlook releases may check Microsoft 365 first and use other
  sources for IMAP accounts.
- **Apple profile:** the profile is unsigned, so the device shows it as not
  verified. It carries no address and no user name; the device asks for both
  (the full address as user name) on import.

### Firewall

The role opens no ports. The web server needs `http` and `https` in the
[`marcstraube.common.firewalld`](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/firewalld/README.md)
inventory:

```yaml
firewalld_services:
  - http
  - https
```

## References

Related roles:

- [marcstraube.server.nginx](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/nginx/README.md)
  — web server site for the files
- [marcstraube.server.apache](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/apache/README.md)
  — web server site for the files
- [marcstraube.server.certbot](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/certbot/README.md)
  — certificates of the sites
- [marcstraube.server.postfix](https://github.com/marcstraube/ansible-collection-server/blob/main/roles/postfix/README.md)
  — MX host the MTA-STS policy names
- [marcstraube.common.firewalld](https://github.com/marcstraube/ansible-collection-common/blob/main/roles/firewalld/README.md)
  — `http` and `https` for the web server

External:

- [Thunderbird Autoconfiguration](https://www.bucksch.org/1/projects/thunderbird/autoconfiguration/)
- [Thunderbird config file format](https://wiki.mozilla.org/Thunderbird:Autoconfiguration:ConfigFileFormat)
- [Outlook 2007 Autodiscover XML schema](https://learn.microsoft.com/en-us/previous-versions/office/office-2007-resource-kit/cc511507(v=office.12))
- [POX Autodiscover reference](https://learn.microsoft.com/en-us/exchange/client-developer/web-service-reference/pox-autodiscover-web-service-reference-for-exchange)
- [Apple Mail payload](https://developer.apple.com/documentation/devicemanagement/mail)
- [RFC 6186: Use of SRV Records for Locating Email Submission/Access Services](https://www.rfc-editor.org/rfc/rfc6186)
- [RFC 8314: Cleartext Considered Obsolete](https://www.rfc-editor.org/rfc/rfc8314)
- [RFC 8460: SMTP TLS Reporting](https://www.rfc-editor.org/rfc/rfc8460)
- [RFC 8461: SMTP MTA Strict Transport Security (MTA-STS)](https://www.rfc-editor.org/rfc/rfc8461)
- [community.general.dig lookup](https://docs.ansible.com/ansible/latest/collections/community/general/dig_lookup.html)

## License

MIT

## Author

Marc Straube
