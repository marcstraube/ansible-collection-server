#!/usr/bin/env python3
"""Stand-in for the rspamd controller: records every learn request (path,
password header, body size) as one JSON line and answers like rspamd."""

import http.server
import json
import sys

LOG = sys.argv[2]


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        with open(LOG, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps({'path': self.path, 'password': self.headers.get('Password'),
                                     'size': len(body), 'subject': next(
                                         (line[9:].strip() for line in body.decode(errors='replace').splitlines()
                                          if line.lower().startswith('subject: ')), '')}) + '\n')
        reply = b'{"success": true}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, *args):
        pass


http.server.HTTPServer(('127.0.0.1', int(sys.argv[1])), Handler).serve_forever()
