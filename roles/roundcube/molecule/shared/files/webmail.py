#!/usr/bin/env python3
"""Roundcube and IMAP checks of the Molecule verify playbooks (standard
library only).

Every subcommand prints one JSON object and exits with 0; the playbooks
assert on the fields. Passwords come on stdin as JSON ({"password": ...,
"new_password": ...}), never from the command line.
"""

import argparse
import http.cookiejar
import imaplib
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request


def emit(**fields):
    print(json.dumps(fields))
    sys.exit(0)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    """A browser session against Roundcube: cookies, tokens, no redirects."""

    def __init__(self, base, host):
        self.base = base.rstrip('/')
        self.host = host
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar), NoRedirect())
        self.token = None

    def request(self, path, data=None, headers=None):
        body = urllib.parse.urlencode(data, doseq=True).encode() if data is not None else None
        req = urllib.request.Request(self.base + path, data=body)
        req.add_header('Host', self.host)
        for name, value in (headers or {}).items():
            req.add_header(name, value)
        try:
            with self.opener.open(req, timeout=60) as resp:
                return resp.status, dict(resp.headers), resp.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as err:
            return err.code, dict(err.headers), err.read().decode('utf-8', 'replace')

    def login(self, user, password):
        status, _, page = self.request('/?_task=login')
        match = re.search(r'name="_token" value="([^"]+)"', page)
        if status != 200 or not match:
            return {'login_page': status, 'login_ok': False, 'login_status': None}
        status, headers, page = self.request('/?_task=login', {
            '_token': match.group(1), '_task': 'login', '_action': 'login',
            '_timezone': 'UTC', '_url': '', '_user': user, '_pass': password})
        location = headers.get('Location', '')
        ok = status == 302 and '_task=mail' in location
        return {'login_page': 200, 'login_ok': ok, 'login_status': status,
                'login_location': location,
                'login_message': 'loginfailed' if 'Login failed' in page else ''}

    def mail_page(self):
        status, _, page = self.request('/?_task=mail&_mbox=INBOX')
        match = re.search(r'"request_token":"([^"]+)"', page)
        self.token = match.group(1) if match else None
        folders = sorted(set(re.findall(r'<a href="[^"]*_mbox=[^"]*"[^>]*\brel="([^"]+)"', page)))
        return status, folders


def credentials():
    data = json.load(sys.stdin)
    return data['password'], data.get('new_password', '')


def cmd_page(args):
    """GET a path without logging in."""
    client = Client(args.base, args.host)
    status, headers, page = client.request(args.path)
    emit(status=status, location=headers.get('Location', ''),
         product=bool(re.search(r'<title>[^<]*' + re.escape(args.product), page)) if args.product else None,
         body_start=page[:200])


def cmd_login(args):
    """Log in and read the folder list."""
    password, _ = credentials()
    client = Client(args.base, args.host)
    result = client.login(args.user, password)
    if result['login_ok']:
        status, folders = client.mail_page()
        result.update(mail_status=status, folders=folders, token=bool(client.token))
    emit(**result)


def cmd_password(args):
    """Log in and change the password through the password plugin."""
    password, new_password = credentials()
    client = Client(args.base, args.host)
    result = client.login(args.user, password)
    if result['login_ok']:
        client.mail_page()
        status, _, page = client.request('/?_task=settings&_action=plugin.password-save', {
            # Without _framed: the plugin does not load in framed requests
            # (noframe), the settings page posts the form as a whole page
            '_token': client.token, '_curpasswd': password,
            '_newpasswd': new_password, '_confpasswd': new_password})
        result.update(status=status, saved='Successfully saved' in page,
                      error=re.findall(r'display_message\("([^"]+)"', page))
    emit(**result)


def cmd_sieve(args):
    """Log in and save a filter through the managesieve plugin: every
    message is filed into the given folder."""
    password, _ = credentials()
    client = Client(args.base, args.host)
    result = client.login(args.user, password)
    if result['login_ok']:
        client.mail_page()
        status, _, page = client.request('/?_task=settings&_action=plugin.managesieve-save', {
            '_token': client.token, '_framed': '1', '_fid': '', '_name': args.name,
            '_join': 'any', '_enabled': '1',
            '_action_type[0]': 'fileinto', '_action_mailbox[0]': args.folder})
        result.update(status=status, saved='Filter saved successfully' in page,
                      error=re.findall(r'display_message\("([^"]+)"', page))
    emit(**result)


def cmd_acl(args):
    """Log in and share a folder with another user through the acl plugin
    (an AJAX request, as the settings page sends it)."""
    password, _ = credentials()
    client = Client(args.base, args.host)
    result = client.login(args.user, password)
    if result['login_ok']:
        client.mail_page()
        status, _, page = client.request(
            '/?_task=settings&_action=plugin.acl',
            {'_act': 'save', '_mbox': args.folder, '_user': args.grantee,
             '_acl': args.rights, '_remote': '1'},
            {'X-Roundcube-Request': client.token or '', 'X-Requested-With': 'XMLHttpRequest'})
        result.update(status=status, shared='acl_update' in page, response=page[:300])
    emit(**result)


def cmd_imap(args):
    """Log in to IMAP over TLS (certificate verified) and list folders."""
    password, _ = credentials()
    ctx = ssl.create_default_context(cafile=args.ca)
    try:
        conn = imaplib.IMAP4_SSL(args.imap_host, args.imap_port, ssl_context=ctx)
        conn.login(args.user, password)
    except (imaplib.IMAP4.error, OSError) as err:
        emit(login=False, error=str(err))
    _, lines = conn.list('""', args.pattern)
    folders = []
    for line in lines or []:
        if line is None:
            continue
        match = re.search(rb'"[^"]*" "?([^"]*)"?$', line)
        if match:
            folders.append(match.group(1).decode())
    conn.logout()
    emit(login=True, folders=sorted(folders))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1')
    parser.add_argument('--host', default='localhost')
    sub = parser.add_subparsers(dest='cmd', required=True)

    page = sub.add_parser('page')
    page.add_argument('path')
    page.add_argument('--product', default='')
    page.set_defaults(func=cmd_page)

    for name, func in (('login', cmd_login), ('password', cmd_password),
                       ('sieve', cmd_sieve), ('acl', cmd_acl)):
        cmd = sub.add_parser(name)
        cmd.add_argument('--user', required=True)
        cmd.set_defaults(func=func)
        if name == 'sieve':
            cmd.add_argument('--name', required=True)
            cmd.add_argument('--folder', required=True)
        if name == 'acl':
            cmd.add_argument('--folder', required=True)
            cmd.add_argument('--grantee', required=True)
            cmd.add_argument('--rights', required=True)

    imap = sub.add_parser('imap')
    imap.add_argument('--user', required=True)
    imap.add_argument('--imap-host', default='localhost')
    imap.add_argument('--imap-port', type=int, default=993)
    imap.add_argument('--ca', required=True)
    imap.add_argument('--pattern', default='*')
    imap.set_defaults(func=cmd_imap)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
