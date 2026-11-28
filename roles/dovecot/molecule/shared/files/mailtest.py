#!/usr/bin/env python3
"""Protocol checks of the Molecule verify playbooks (standard library only).

Every subcommand prints one JSON object and exits with 0; the playbooks
assert on the fields. A connection error is reported as 'error', not as a
traceback, so a refused connection can be asserted as well.
"""

import argparse
import base64
import imaplib
import json
import poplib
import os
import re
import smtplib
import socket
import ssl
import sys
import warnings

warnings.filterwarnings('ignore', category=DeprecationWarning)


def emit(**fields):
    print(json.dumps(fields))
    sys.exit(0)


def tls_context(ca_file=None, minimum=None, maximum=None, ciphers=None):
    ctx = ssl.create_default_context(cafile=ca_file)
    if ca_file is None:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    if ciphers:
        # Offer only these suites (TLS 1.2 and older); the server has to pick
        # one of them or refuse
        ctx.set_ciphers(ciphers)
    elif minimum in ('TLSv1', 'TLSv1_1'):
        # Allow the client to offer the old versions; the server has to refuse
        ctx.set_ciphers('DEFAULT:@SECLEVEL=0')
    if minimum:
        ctx.minimum_version = getattr(ssl.TLSVersion, minimum)
    if maximum:
        ctx.maximum_version = getattr(ssl.TLSVersion, maximum)
    return ctx


def connect(target, timeout=10, source=None):
    """'host:port', '[v6]:port' or a unix socket path."""
    if target.startswith('/'):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(target)
        return sock
    host, port = target.rsplit(':', 1)
    return socket.create_connection((host.strip('[]'), int(port)), timeout=timeout,
                                    source_address=(source, 0) if source else None)


class SourceIMAP4(imaplib.IMAP4):
    """IMAP4 from a given local address: a connection from an address of the
    host to the same address counts as secured for Dovecot."""

    source = None

    def _create_socket(self, timeout):
        return socket.create_connection((self.host, self.port), timeout,
                                        source_address=(self.source, 0) if self.source else None)


def imap_open(args):
    if args.starttls:
        conn = imaplib.IMAP4(args.host, args.port)
        conn.starttls(ssl_context=tls_context(args.ca))
    else:
        conn = imaplib.IMAP4_SSL(args.host, args.port, ssl_context=tls_context(args.ca))
    conn.login(args.user, args.password)
    return conn


def cmd_imap(args):
    """Login over TLS and run the requested actions."""
    try:
        conn = imap_open(args)
    except (imaplib.IMAP4.error, OSError) as exc:
        emit(login=False, error=str(exc))
    result = {'login': True}
    typ, data = conn.list()
    result['list'] = [line.decode(errors='replace') for line in data if line]
    for action in args.action or []:
        name, _, rest = action.partition('=')
        try:
            if name == 'count':
                typ, data = conn.select(f'"{rest}"', readonly=True)
                result[f'count:{rest}'] = int(data[0]) if typ == 'OK' else None
            elif name == 'search':
                folder, _, text = rest.partition(':')
                conn.select(f'"{folder}"')
                typ, data = conn.search(None, 'SUBJECT', f'"{text}"')
                result[f'search:{rest}'] = len(data[0].split()) if typ == 'OK' else None
            elif name == 'move':
                source, _, target = rest.partition(':')
                source, _, text = source.partition('#')
                conn.select(f'"{source}"')
                typ, data = conn.search(None, 'SUBJECT', f'"{text}"')
                ids = data[0].split()
                typ, data = conn._simple_command('MOVE', b','.join(ids).decode(), f'"{target}"')
                result[f'move:{rest}'] = typ
            elif name == 'myrights':
                typ, data = conn.myrights(f'"{rest}"')
                # '' for a mailbox without rights; None only when the command failed
                result[f'myrights:{rest}'] = (data[0].decode().rsplit(' ', 1)[-1].strip('"')
                                              if typ == 'OK' else None)
            elif name == 'setacl':
                folder, ident, rights = rest.split(':', 2)
                typ, data = conn.setacl(f'"{folder}"', ident, rights)
                result[f'setacl:{folder}:{ident}'] = typ
            elif name == 'create':
                typ, data = conn.create(f'"{rest}"')
                result[f'create:{rest}'] = typ
            elif name == 'lsub':
                typ, data = conn.lsub()
                result['lsub'] = [line.decode(errors='replace').rsplit(' ', 1)[-1].strip('"')
                                  for line in data if line]
            elif name == 'getquota':
                typ, data = conn.getquotaroot('INBOX')
                result['getquota'] = [d.decode() if isinstance(d, bytes) else str(d) for d in data]
            elif name == 'append':
                folder, _, text = rest.partition(':')
                msg = (f'From: test@example.com\r\nTo: test@example.com\r\nSubject: {text}\r\n\r\n'
                       'Molecule test\r\n').encode()
                typ, data = conn.append(f'"{folder}"', None, None, msg)
                result[f'append:{rest}'] = typ
        except imaplib.IMAP4.error as exc:
            result[f'{name}:{rest}'] = f'NO {exc}'
    conn.logout()
    emit(**result)


def cmd_imap_plain(args):
    """LOGIN on the plain IMAP port without STARTTLS must be refused."""
    SourceIMAP4.source = args.source
    try:
        conn = SourceIMAP4(args.host, args.port)
    except OSError as exc:
        emit(connected=False, login=False, error=str(exc))
    caps = list(conn.capabilities)
    try:
        conn.login(args.user, args.password)
        emit(connected=True, login=True, capabilities=caps)
    except imaplib.IMAP4.error as exc:
        emit(connected=True, login=False, capabilities=caps, error=str(exc))


def cmd_pop3(args):
    """Login over POP3 with implicit TLS and count the messages."""
    try:
        conn = poplib.POP3_SSL(args.host, args.port, context=tls_context(args.ca))
        conn.user(args.user)
        conn.pass_(args.password)
        count, _ = conn.stat()
        conn.quit()
        emit(login=True, count=count)
    except (poplib.error_proto, OSError) as exc:
        emit(login=False, error=str(exc))


def cmd_tls(args):
    """TLS handshake limited to one protocol version and, with --cipher, to
    the given suites. A refusal is split into the server's protocol_version
    alert ('server_refused'), its handshake_failure alert when it shares no
    suite with the client ('cipher_refused') and a client that cannot offer
    the version or the suites at all ('client_unsupported', e.g. a system
    crypto policy on EL), so a negative test cannot pass by accident."""
    try:
        ctx = tls_context(None, args.version, args.version, args.cipher)
    except (ValueError, ssl.SSLError) as exc:
        emit(handshake=False, server_refused=False, cipher_refused=False, client_unsupported=True,
             error=str(exc))
    try:
        with connect(f'{args.host}:{args.port}') as raw:
            with ctx.wrap_socket(raw, server_hostname=args.host) as tls:
                emit(handshake=True, version=tls.version(), cipher=tls.cipher()[0], server_refused=False,
                     cipher_refused=False, client_unsupported=False)
    except ssl.SSLError as exc:
        text = str(exc)
        emit(handshake=False, error=text,
             server_refused='ALERT_PROTOCOL_VERSION' in text,
             cipher_refused='ALERT_HANDSHAKE_FAILURE' in text,
             client_unsupported='NO_PROTOCOLS_AVAILABLE' in text or 'NO_CIPHERS_AVAILABLE' in text)
    except OSError as exc:
        emit(handshake=False, server_refused=False, cipher_refused=False, client_unsupported=False,
             error=str(exc))


def cmd_lmtp(args):
    """Deliver one message over LMTP (unix socket or TCP)."""
    with open(args.message, 'rb') as handle:
        message = handle.read()
    try:
        if args.target.startswith('/'):
            lmtp = smtplib.LMTP(args.target)
        else:
            host, port = args.target.rsplit(':', 1)
            lmtp = smtplib.LMTP(host.strip('[]'), int(port))
        refused = lmtp.sendmail(args.sender, args.rcpt, message)
        lmtp.quit()
        emit(delivered=not refused, refused={k: [v[0], v[1].decode()] for k, v in refused.items()})
    except smtplib.SMTPRecipientsRefused as exc:
        emit(delivered=False, refused={k: [v[0], v[1].decode()] for k, v in exc.recipients.items()})
    except (smtplib.SMTPException, OSError) as exc:
        emit(delivered=False, error=str(exc))


def cmd_sasl(args):
    """Dovecot auth protocol (what Postfix speaks): PLAIN for one user."""
    resp = base64.b64encode(f'\0{args.user}\0{args.password}'.encode()).decode()
    data = b''
    try:
        sock = connect(args.target)
        sock.sendall(f'VERSION\t1\t2\nCPID\t{os.getpid()}\n'
                     f'AUTH\t1\tPLAIN\tservice=smtp\tnologin\tsecured\tresp={resp}\n'.encode())
        while not re.search(rb'^(OK|FAIL)\t1', data, re.M):
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        sock.close()
    except OSError as exc:
        emit(ok=False, error=str(exc), raw=data.decode(errors='replace'))
    reply = [line for line in data.decode(errors='replace').splitlines() if re.match(r'(OK|FAIL)\t1', line)]
    emit(ok=bool(reply) and reply[0].startswith('OK'), reply=reply[0] if reply else data.decode(errors='replace'))


def cmd_policy(args):
    """Postfix policy request to the quota-status service."""
    data = b''
    try:
        sock = connect(args.target)
        sock.sendall((f'request=smtpd_access_policy\nprotocol_state=RCPT\nrecipient={args.rcpt}\n'
                      f'size={args.size}\n\n').encode())
        while not data.endswith(b'\n\n'):
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        sock.close()
    except OSError as exc:
        emit(action=None, error=str(exc), raw=data.decode(errors='replace'))
    match = re.search(r'^action=(.*)$', data.decode(), re.M)
    emit(action=match.group(1) if match else None, raw=data.decode())


class ManageSieve:
    def __init__(self, host, port, source=None):
        self.sock = connect(f'{host}:{port}', source=source)
        self.buf = b''

    def line(self):
        while b'\r\n' not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise OSError('connection closed')
            self.buf += chunk
        line, self.buf = self.buf.split(b'\r\n', 1)
        return line.decode(errors='replace')

    def response(self):
        lines = []
        while True:
            line = self.line()
            lines.append(line)
            if re.match(r'^(OK|NO|BYE)', line):
                return line, lines

    def send(self, text):
        self.sock.sendall(text.encode() + b'\r\n')

    def starttls(self):
        self.send('STARTTLS')
        status, _ = self.response()
        self.sock = tls_context().wrap_socket(self.sock, server_hostname='localhost')
        self.buf = b''
        self.response()
        return status


def cmd_managesieve(args):
    """Login without STARTTLS (refused), then over STARTTLS on a new
    connection, storing and activating a script."""
    resp = base64.b64encode(f'\0{args.user}\0{args.password}'.encode()).decode()
    result = {}
    try:
        ms = ManageSieve(args.host, args.port, args.source)
        _, greeting = ms.response()
        result['plain_capabilities'] = greeting
        ms.send(f'AUTHENTICATE "PLAIN" "{resp}"')
        status, _ = ms.response()
        result['plain_login'] = status.startswith('OK')
        ms.sock.close()
        if result['plain_login']:
            emit(**result)
        ms = ManageSieve(args.host, args.port, args.source)
        ms.response()
        result['starttls'] = ms.starttls()
        ms.send(f'AUTHENTICATE "PLAIN" "{resp}"')
        status, _ = ms.response()
        result['tls_login'] = status.startswith('OK')
        if args.script and result['tls_login']:
            with open(args.script, encoding='utf-8') as handle:
                script = handle.read().replace('\r\n', '\n').replace('\n', '\r\n')
            ms.send(f'PUTSCRIPT "{args.name}" {{{len(script.encode())}+}}\r\n{script}')
            status, _ = ms.response()
            result['putscript'] = status
            ms.send(f'SETACTIVE "{args.name}"')
            status, _ = ms.response()
            result['setactive'] = status
        ms.send('LOGOUT')
    except OSError as exc:
        result['error'] = str(exc)
    emit(**result)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('imap')
    p.add_argument('--host', default='localhost')
    p.add_argument('--port', type=int, default=993)
    p.add_argument('--starttls', action='store_true')
    p.add_argument('--ca')
    p.add_argument('--user', required=True)
    p.add_argument('--password', required=True)
    p.add_argument('--action', action='append')
    p.set_defaults(func=cmd_imap)

    p = sub.add_parser('imap-plain')
    p.add_argument('--host', default='localhost')
    p.add_argument('--source')
    p.add_argument('--port', type=int, default=143)
    p.add_argument('--user', required=True)
    p.add_argument('--password', required=True)
    p.set_defaults(func=cmd_imap_plain)

    p = sub.add_parser('pop3')
    p.add_argument('--host', default='localhost')
    p.add_argument('--port', type=int, default=995)
    p.add_argument('--ca')
    p.add_argument('--user', required=True)
    p.add_argument('--password', required=True)
    p.set_defaults(func=cmd_pop3)

    p = sub.add_parser('tls')
    p.add_argument('--host', default='localhost')
    p.add_argument('--port', type=int, default=993)
    p.add_argument('--version', required=True, choices=['TLSv1', 'TLSv1_1', 'TLSv1_2', 'TLSv1_3'])
    p.add_argument('--cipher')
    p.set_defaults(func=cmd_tls)

    p = sub.add_parser('lmtp')
    p.add_argument('--target', required=True)
    p.add_argument('--sender', default='sender@example.org')
    p.add_argument('--rcpt', required=True, action='append')
    p.add_argument('--message', required=True)
    p.set_defaults(func=cmd_lmtp)

    p = sub.add_parser('sasl')
    p.add_argument('--target', required=True)
    p.add_argument('--user', required=True)
    p.add_argument('--password', required=True)
    p.set_defaults(func=cmd_sasl)

    p = sub.add_parser('policy')
    p.add_argument('--target', required=True)
    p.add_argument('--rcpt', required=True)
    p.add_argument('--size', type=int, default=1000)
    p.set_defaults(func=cmd_policy)

    p = sub.add_parser('managesieve')
    p.add_argument('--host', default='localhost')
    p.add_argument('--source')
    p.add_argument('--port', type=int, default=4190)
    p.add_argument('--user', required=True)
    p.add_argument('--password', required=True)
    p.add_argument('--script')
    p.add_argument('--name', default='molecule')
    p.set_defaults(func=cmd_managesieve)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
