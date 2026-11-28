#!/usr/bin/env python3
"""AppArmor profile drift check for the drift-detection workflow.

A separate file rather than inline Python in the workflow: it is too long
to review inside a YAML block scalar, and it can be run against sample
drift-targets.yml content and probe output without a workflow run.

Reads the `profiles` list of .github/drift-targets.yml and works in two
steps around a container probe:

  plan <targets>          Validate the entries and print the GitHub step
                          outputs `packages` (space separated) and `files`
                          (one path per line) for the probe.
  compare <targets> <out> Compare the probe output against the recorded
                          SHA-256 values and print the outputs `drift`
                          (matrix, one entry per role) and `has_drift`.

The probe output has one record per line:

  PKG <name> <version>    from `pacman -Q <name>`
  SHA <sha256>  <path>    from `sha256sum <path>`
  NOTFILE <path>          the path exists but is not a regular file
  MISSING <path>          the package did not install the file

A missing file counts as drift. NOTFILE means the entry points at a
directory or similar, which is an error in drift-targets.yml.

Invalid entries and an incomplete probe output exit non-zero, so the job
fails visibly instead of opening issues.
"""

import json
import os
import re
import sys

import yaml

ROLE_RE = re.compile(r'^[a-z0-9_]+$')
PACKAGE_RE = re.compile(r'^[a-z0-9@._+-]+$')
# A file under /etc/apparmor.d/ (profiles, abstractions/...), no trailing /.
PROFILE_RE = re.compile(r'^/etc/apparmor\.d/[A-Za-z0-9._/-]*[A-Za-z0-9._-]$')
VERSION_RE = re.compile(r'^[0-9A-Za-z.:+~_-]+$')
NOTFILE = object()
SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
REQUIRED = ('role', 'package', 'profile', 'sha256')

TITLE = 'Drift detected: AppArmor profile changed for role `{role}`'


def fail(msg):
    print(f'::error::{msg}', file=sys.stderr)
    sys.exit(1)


def load_profiles(path):
    with open(path, encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    entries = data.get('profiles') or []
    if not isinstance(entries, list):
        fail('drift-targets.yml: `profiles` must be a list')
    seen = set()
    for i, entry in enumerate(entries):
        where = f'drift-targets.yml: profiles[{i}]'
        if not isinstance(entry, dict):
            fail(f'{where}: entry must be a mapping')
        for key in REQUIRED:
            if not isinstance(entry.get(key), str) or not entry[key]:
                # An all-digit hash parses as a number: quote it.
                fail(f'{where}: `{key}` is missing or not a (quoted) string')
        if not ROLE_RE.match(entry['role']):
            fail(f'{where}: invalid role {entry["role"]!r}')
        if not PACKAGE_RE.match(entry['package']):
            fail(f'{where}: invalid package {entry["package"]!r}')
        profile = entry['profile']
        if not PROFILE_RE.match(profile) or '..' in profile or '//' in profile:
            fail(f'{where}: profile must be a file under /etc/apparmor.d/')
        if not SHA256_RE.match(entry['sha256']):
            fail(f'{where}: sha256 must be 64 lowercase hex characters')
        version = entry.get('version')
        if version is not None and (
                not isinstance(version, str) or not VERSION_RE.match(version)):
            fail(f'{where}: version must be a (quoted) package version string')
        key = (entry['role'], entry['profile'])
        if key in seen:
            fail(f'{where}: duplicate entry for {key[0]} / {key[1]}')
        seen.add(key)
    return entries


def unique(values):
    return list(dict.fromkeys(values))


def cmd_plan(targets):
    entries = load_profiles(targets)
    packages = unique(e['package'] for e in entries)
    files = unique(e['profile'] for e in entries)
    print(f'packages={" ".join(packages)}')
    print('files<<EOF')
    for f in files:
        print(f)
    print('EOF')


def parse_probe(path):
    versions, hashes = {}, {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            parts = line.split()
            if len(parts) == 3 and parts[0] == 'PKG':
                versions[parts[1]] = parts[2]
            elif len(parts) == 3 and parts[0] == 'SHA':
                hashes[parts[2]] = parts[1]
            elif len(parts) == 2 and parts[0] == 'NOTFILE':
                hashes[parts[1]] = NOTFILE
            elif len(parts) == 2 and parts[0] == 'MISSING':
                hashes[parts[1]] = None
    return versions, hashes


def cmd_compare(targets, probe):
    entries = load_profiles(targets)
    versions, hashes = parse_probe(probe)
    for e in entries:
        if e['package'] not in versions:
            fail(f'probe output lacks the version of {e["package"]}')
        if not VERSION_RE.match(versions[e['package']]):
            fail(f'unexpected version of {e["package"]}: {versions[e["package"]]!r}')
        if e['profile'] not in hashes:
            fail(f'probe output lacks a result for {e["profile"]}')
        if hashes[e['profile']] is NOTFILE:
            fail(f'{e["profile"]} exists but is not a regular file — fix the entry')

    by_role = {}
    for e in entries:
        actual = hashes[e['profile']]
        if actual == e['sha256']:
            print(f'::notice::{e["role"]}: {e["profile"]} unchanged', file=sys.stderr)
            continue
        state = 'missing' if actual is None else 'changed'
        print(f'::warning::{e["role"]}: {e["profile"]} {state}', file=sys.stderr)
        by_role.setdefault(e['role'], []).append((e, actual))

    run_url = os.environ.get('RUN_URL', '')
    include = []
    for role, drifted in by_role.items():
        packages = unique(e['package'] for e, _ in drifted)
        lines = [
            f'The drift-detection workflow found that the AppArmor profiles '
            f'which `{role}` extends changed in their package. The local '
            f'overrides of the role may now be redundant or no longer fit.',
            '',
            '| File | Package | Recorded SHA-256 | Current SHA-256 |',
            '| --- | --- | --- | --- |',
        ]
        for e, actual in drifted:
            current = '*file missing*' if actual is None else f'`{actual}`'
            now = versions[e['package']]
            if e.get('version'):
                package = f'recorded at `{e["package"]}` {e["version"]}, now {now}'
            else:
                package = f'recorded at `{e["package"]}` (version not recorded), now {now}'
            lines.append(f'| `{e["profile"]}` | {package} | `{e["sha256"]}` | {current} |')
        lines += [
            '',
            f'- Role: `{role}`',
        ]
        lines += [f'- Package: `{p}` {versions[p]}' for p in packages]
        if run_url:
            lines.append(f'- Workflow run: {run_url}')
        lines += [
            '',
            f'To resolve: check the AppArmor overrides of `roles/{role}` '
            f'against the new profile (adjust or drop rules the profile now '
            f'covers, or follow a rename or removal), then update the '
            f'`sha256` and `version` of the entries above in '
            f'`.github/drift-targets.yml`.',
        ]
        include.append({
            'role': role,
            'title': TITLE.format(role=role),
            'body': '\n'.join(lines),
        })

    print(f'drift={json.dumps({"include": include}, separators=(",", ":"))}')
    print(f'has_drift={"true" if include else "false"}')


def main(argv):
    if len(argv) == 3 and argv[1] == 'plan':
        cmd_plan(argv[2])
    elif len(argv) == 4 and argv[1] == 'compare':
        cmd_compare(argv[2], argv[3])
    else:
        fail('usage: profile_drift.py plan <targets> | compare <targets> <probe-output>')


if __name__ == '__main__':
    main(sys.argv)
