#!/usr/bin/env python3
"""SMTP test client of the rspamd molecule scenarios.

Reads one session as JSON on stdin, sends one message and prints the
replies as JSON; it never raises, a failed step ends the session with
'error' and 'error_code'.

Session keys:
  host, port   Postfix (default 127.0.0.1:25)
  xclient      XCLIENT attributes, e.g. {"ADDR": "192.0.2.25",
               "NAME": "mx.example.net"}: the milter sees this client
               instead of the local connection (smtpd_authorized_xclient_hosts)
  mail_from    envelope sender
  rcpt         list of recipients
  data         message text

Output keys: ehlo, xclient, mail, rcpt (list), data, error, error_code.
"""

import json
import smtplib
import sys


def reply(code_msg):
    code, msg = code_msg
    if isinstance(msg, bytes):
        msg = msg.decode('utf-8', 'replace')
    return [code, msg]


def main():
    req = json.load(sys.stdin)
    out = {}
    smtp = None
    try:
        smtp = smtplib.SMTP(req.get('host', '127.0.0.1'), req.get('port', 25), timeout=60)
        out['ehlo'] = reply(smtp.ehlo('client.example.net'))
        if req.get('xclient'):
            attrs = ' '.join('%s=%s' % item for item in req['xclient'].items())
            out['xclient'] = reply(smtp.docmd('XCLIENT', attrs))
            if out['xclient'][0] != 220:
                raise smtplib.SMTPResponseException(*out['xclient'])
            smtp.ehlo_resp = None
            smtp.does_esmtp = False
            smtp.ehlo(req['xclient'].get('HELO', 'client.example.net'))
        out['mail'] = reply(smtp.mail(req['mail_from']))
        if out['mail'][0] != 250:
            raise smtplib.SMTPResponseException(*out['mail'])
        out['rcpt'] = [reply(smtp.rcpt(rcpt)) for rcpt in req['rcpt']]
        if not any(code == 250 for code, _ in out['rcpt']):
            raise smtplib.SMTPResponseException(*out['rcpt'][-1])
        out['data'] = reply(smtp.data(req['data'].encode('utf-8')))
        if out['data'][0] != 250:
            raise smtplib.SMTPResponseException(*out['data'])
    except smtplib.SMTPResponseException as err:
        out['error'] = err.smtp_error.decode('utf-8', 'replace') \
            if isinstance(err.smtp_error, bytes) else str(err.smtp_error)
        out['error_code'] = err.smtp_code
    except (OSError, smtplib.SMTPException) as err:
        out['error'] = str(err)
        out['error_code'] = 0
    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except (OSError, smtplib.SMTPException):
                pass
    print(json.dumps(out))


if __name__ == '__main__':
    main()
