#!/usr/bin/env python3
"""SOGo client of the Molecule verify playbooks (standard library only).

    molecule-sogo-client --base https://mail.example.com --ca /etc/molecule-tls/ca.pem \
        <command> --user alice@example.com [options] < credentials.json

The passwords come as a JSON object on stdin ({"password": ...,
"new_password": ...}), never on the command line.

Talks to SOGo through the web server like the web interface does (JSON
requests, session cookie, XSRF token) and like a CalDAV/CardDAV client
(basic authentication). Every command prints one JSON object and exits
with 0; the playbooks assert on the fields. HTTP errors are reported as a
status, not as a traceback.
"""

import argparse
import base64
import http.cookiejar
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, base, ca_file, follow=True):
        self.base = base.rstrip('/')
        self.jar = http.cookiejar.CookieJar()
        ctx = ssl.create_default_context(cafile=ca_file)
        handlers = [urllib.request.HTTPSHandler(context=ctx),
                    urllib.request.HTTPCookieProcessor(self.jar)]
        if not follow:
            handlers.append(NoRedirect())
        self.opener = urllib.request.build_opener(*handlers)

    def xsrf(self):
        for cookie in self.jar:
            if cookie.name == 'XSRF-TOKEN':
                return cookie.value
        return None

    def request(self, method, path, body=None, headers=None, auth=None):
        headers = dict(headers or {})
        data = None
        if body is not None:
            if isinstance(body, (dict, list)):
                data = json.dumps(body).encode()
                headers.setdefault('Content-Type', 'application/json')
            else:
                data = body.encode() if isinstance(body, str) else body
        token = self.xsrf()
        if token:
            headers['X-XSRF-TOKEN'] = token
        if auth:
            headers['Authorization'] = 'Basic ' + base64.b64encode(
                ('%s:%s' % auth).encode()).decode()
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=120) as resp:
                return resp.status, dict(resp.headers), resp.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as err:
            return err.code, dict(err.headers), err.read().decode('utf-8', 'replace')

    def login(self, user, password):
        status, _, body = self.request('POST', '/SOGo/connect',
                                       {'userName': user, 'password': password, 'rememberLogin': 0})
        return status, body


def parse_json(body):
    try:
        return json.loads(body)
    except ValueError:
        return None


def mailbox_paths(mailboxes, out):
    for mailbox in mailboxes or []:
        out.append(mailbox.get('path'))
        mailbox_paths(mailbox.get('children'), out)
    return out


def molecule_filters(subject):
    """The mail filter of the tests: messages with the subject into Junk."""
    return [{'name': 'molecule', 'active': 1, 'match': 'all',
             'rules': [{'field': 'subject', 'operator': 'contains', 'value': subject}],
             'actions': [{'method': 'fileinto', 'argument': 'Junk'}]}]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True)
    parser.add_argument('--ca', required=True)
    parser.add_argument('command', choices=['get', 'login', 'mailboxes', 'send', 'password',
                                            'filter', 'dav', 'activesync', 'share', 'vacation',
                                            'delete', 'fetch'])
    parser.add_argument('--user')
    parser.add_argument('--path', default='/')
    parser.add_argument('--to')
    parser.add_argument('--folder', default='Archive')
    parser.add_argument('--subject', default='molecule')
    parser.add_argument('--kind', choices=['calendar', 'contact'])
    args = parser.parse_args()
    secrets = {} if args.command == 'get' else json.loads(sys.stdin.read() or '{}')
    args.password = secrets.get('password')
    args.new_password = secrets.get('new_password')

    if args.command == 'get':
        client = Client(args.base, args.ca, follow=False)
        status, headers, body = client.request('GET', args.path)
        print(json.dumps({'status': status, 'location': headers.get('Location', ''),
                          'content_type': headers.get('Content-Type', ''), 'length': len(body),
                          'body': body[:2000]}))
        return

    client = Client(args.base, args.ca)

    if args.command == 'dav':
        auth = (args.user, args.password)
        uid = 'molecule-' + args.kind
        if args.kind == 'calendar':
            path = '/SOGo/dav/%s/Calendar/personal/%s.ics' % (args.user, uid)
            body = ('BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//molecule//EN\r\n'
                    'BEGIN:VEVENT\r\nUID:%s\r\nDTSTAMP:20260101T090000Z\r\n'
                    'DTSTART:20260101T100000Z\r\nDTEND:20260101T110000Z\r\n'
                    'SUMMARY:Molecule event\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n' % uid)
            ctype = 'text/calendar; charset=utf-8'
        else:
            path = '/SOGo/dav/%s/Contacts/personal/%s.vcf' % (args.user, uid)
            body = ('BEGIN:VCARD\r\nVERSION:3.0\r\nUID:%s\r\nFN:Molecule Contact\r\n'
                    'N:Contact;Molecule;;;\r\nEMAIL:contact@example.net\r\nEND:VCARD\r\n' % uid)
            ctype = 'text/vcard; charset=utf-8'
        put, _, _ = client.request('PUT', path, body, {'Content-Type': ctype}, auth=auth)
        get, _, content = client.request('GET', path, auth=auth)
        print(json.dumps({'stored': put, 'fetched': get, 'body': content}))
        return

    if args.command in ('delete', 'fetch'):
        auth = (args.user, args.password)
        uid = 'molecule-' + args.kind
        if args.kind == 'calendar':
            path = '/SOGo/dav/%s/Calendar/personal/%s.ics' % (args.user, uid)
        else:
            path = '/SOGo/dav/%s/Contacts/personal/%s.vcf' % (args.user, uid)
        result = {}
        if args.command == 'delete':
            result['deleted'], _, _ = client.request('DELETE', path, auth=auth)
        result['fetched'], _, result['body'] = client.request('GET', path, auth=auth)
        print(json.dumps(result))
        return

    if args.command == 'activesync':
        status, headers, _ = client.request('OPTIONS', '/Microsoft-Server-ActiveSync',
                                            auth=(args.user, args.password))
        print(json.dumps({'status': status,
                          'versions': headers.get('MS-ASProtocolVersions', ''),
                          'commands': headers.get('MS-ASProtocolCommands', '')}))
        return

    status, body = client.login(args.user, args.password)
    result = {'login': status}
    if args.command == 'login' or status != 200:
        result['body'] = body[:500]
        print(json.dumps(result))
        return

    home = '/SOGo/so/' + urllib.parse.quote(args.user)

    if args.command == 'mailboxes':
        status, _, body = client.request('GET', home + '/Mail/0/view')
        data = parse_json(body) or {}
        result.update({'status': status, 'paths': mailbox_paths(data.get('mailboxes'), [])})

    elif args.command == 'send':
        status, _, body = client.request('GET', home + '/Mail/0/compose')
        draft = parse_json(body) or {}
        result['compose'] = status
        if status in (200, 201) and draft.get('draftId'):
            folder = '/'.join('folder' + part for part in draft['mailboxPath'].split('/'))
            path = '%s/Mail/%s/%s/%s/send' % (home, draft['accountId'], folder, draft['draftId'])
            status, _, body = client.request('POST', path, {
                'from': args.user, 'to': [args.to], 'subject': args.subject,
                'text': 'Sent through SOGo by molecule.', 'isHTML': False})
            result.update({'send': status, 'response': parse_json(body) or body[:500]})

    elif args.command == 'password':
        status, _, body = client.request('POST', '/SOGo/so/changePassword',
                                         {'oldPassword': args.password,
                                          'newPassword': args.new_password})
        result.update({'status': status, 'response': body[:500]})

    elif args.command == 'share':
        # The folder ACL editor of the web interface: add the user, then
        # save the rights; SOGo applies them with IMAP SETACL
        folder = '%s/Mail/0/folder%s' % (home, args.folder)
        status, _, body = client.request(
            'GET', folder + '/addUserInAcls?uid=' + urllib.parse.quote(args.to))
        result['add'] = status
        status, _, body = client.request('POST', folder + '/saveUserRights', [{
            'uid': args.to,
            'rights': {'userCanViewFolder': True, 'userCanReadMails': True,
                       'userCanMarkMailsRead': True}}])
        result.update({'status': status, 'response': body[:500]})

    elif args.command == 'vacation':
        # An out-of-office reply that ended yesterday: SOGo writes it into the
        # Sieve script (with a date condition), sogo-tool update-autoreply
        # turns it off
        yesterday = int(time.time()) - 2 * 86400
        status, _, body = client.request('POST', home + '/Preferences/save', {
            'defaults': {'SOGoSieveFilters': molecule_filters(args.subject), 'Vacation': {
                'enabled': 1, 'endDateEnabled': 1, 'endDate': yesterday,
                'autoReplyText': 'molecule-vacation', 'daysBetweenResponse': 7,
                'autoReplyEmailAddresses': [args.user]}}})
        result.update({'status': status, 'response': body[:500]})

    elif args.command == 'filter':
        # A filter of the preferences: SOGo writes it through ManageSieve
        status, _, body = client.request('POST', home + '/Preferences/save',
                                         {'defaults': {'SOGoSieveFilters': molecule_filters(args.subject)}})
        result.update({'status': status, 'response': body[:500]})

    print(json.dumps(result))


if __name__ == '__main__':
    sys.exit(main())
