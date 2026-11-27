#!/usr/bin/env python3
"""SMTP test client of the postfix molecule scenarios.

Reads one session as JSON on stdin and prints the reply of every step as
JSON; it never raises, a failed step ends the session with 'error'.

Session keys:
  host, port             server (required)
  mode                   'plain', 'starttls' or 'tls' (implicit TLS)
  helo                   EHLO name (default client.example.net)
  source                 source address of the connection (optional)
  auth_before_tls        send AUTH PLAIN before STARTTLS (starttls mode)
  auth                   [login, password] for AUTH PLAIN (optional)
  mail_from              envelope sender ('' for the null sender)
  mail_options           MAIL FROM parameters, e.g. ['SIZE=5000000']
  rcpt                   list of recipients
  data                   message text (sent when a recipient was accepted)
  tls_version            'TLSv1_1', 'TLSv1_2', ...: only the TLS handshake
                         with exactly this version, then QUIT
  tls_ciphers            OpenSSL cipher list the client offers (TLS 1.2
                         and older; with tls_version)

Output keys: connect, ehlo, starttls, auth, mail, rcpt (list), data,
tls (negotiated version), cipher (negotiated suite), error, error_code (the
reply that ended the session), client_error (the local TLS library refused
the version or the suites itself), cipher_refused (the server shares no
suite with the client: handshake_failure alert).
"""

import base64
import json
import smtplib
import ssl
import sys


def context(version=None, ciphers=None):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    if version:
        ctx.set_ciphers(ciphers or 'DEFAULT:@SECLEVEL=0')
        ctx.minimum_version = getattr(ssl.TLSVersion, version)
        ctx.maximum_version = getattr(ssl.TLSVersion, version)
    return ctx


def reply(code_msg):
    code, msg = code_msg
    if isinstance(msg, bytes):
        msg = msg.decode('utf-8', 'replace')
    return [code, msg]


def main():
    req = json.load(sys.stdin)
    out = {}
    mode = req.get('mode', 'plain')
    version = req.get('tls_version')
    ciphers = req.get('tls_ciphers')
    source = (req['source'], 0) if req.get('source') else None
    smtp = None
    try:
        if mode == 'tls':
            smtp = smtplib.SMTP_SSL(timeout=20, context=context(version, ciphers), source_address=source)
        else:
            smtp = smtplib.SMTP(timeout=20, source_address=source)
        # SMTP_SSL.connect() and starttls() pass the host of the constructor
        # as server_hostname; current Python releases refuse the empty one of
        # a constructor without host
        smtp._host = req['host']
        out['connect'] = reply(smtp.connect(req['host'], int(req['port'])))
        if mode == 'tls':
            out['tls'] = smtp.sock.version()
            out['cipher'] = smtp.sock.cipher()[0]
        out['ehlo'] = reply(smtp.ehlo(req.get('helo', 'client.example.net')))
        if mode == 'starttls':
            if req.get('auth_before_tls'):
                token = base64.b64encode(b'\0dummy@example.com\0dummy').decode()
                out['auth'] = reply(smtp.docmd('AUTH', 'PLAIN ' + token))
                return out
            out['starttls'] = reply(smtp.starttls(context=context(version, ciphers)))
            out['tls'] = smtp.sock.version()
            out['cipher'] = smtp.sock.cipher()[0]
            out['ehlo'] = reply(smtp.ehlo(req.get('helo', 'client.example.net')))
        if version:
            return out
        if req.get('auth'):
            login, password = req['auth']
            token = base64.b64encode(('\0%s\0%s' % (login, password)).encode()).decode()
            out['auth'] = reply(smtp.docmd('AUTH', 'PLAIN ' + token))
        out['mail'] = reply(smtp.mail(req.get('mail_from', ''), req.get('mail_options', [])))
        out['rcpt'] = [reply(smtp.rcpt(rcpt)) for rcpt in req.get('rcpt', [])]
        if any(code == 250 for code, _ in out['rcpt']) and 'data' in req:
            try:
                out['data'] = reply(smtp.data(req['data'].encode()))
            except smtplib.SMTPDataError as exc:
                out['data'] = [exc.smtp_code, exc.smtp_error.decode('utf-8', 'replace')]
    except ssl.SSLError as exc:
        out['error'] = str(exc)
        out['client_error'] = any(text in str(exc) for text in ('NO_PROTOCOLS_AVAILABLE', 'no protocols available',
                                                                 'NO_CIPHERS_AVAILABLE', 'no ciphers available'))
        out['cipher_refused'] = 'ALERT_HANDSHAKE_FAILURE' in str(exc)
    except smtplib.SMTPResponseException as exc:
        # A reply that ends the session (e.g. 421 at the greeting)
        out['error'] = '%s: %s' % (type(exc).__name__, exc)
        out['error_code'] = exc.smtp_code
    except (smtplib.SMTPException, OSError) as exc:
        out['error'] = '%s: %s' % (type(exc).__name__, exc)
    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except (smtplib.SMTPException, OSError):
                pass
    return out


if __name__ == '__main__':
    print(json.dumps(main()))
