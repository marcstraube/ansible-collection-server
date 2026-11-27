"""Molecule verify helper: one GET request to a PHP-FPM socket over FastCGI.

    python3 fcgi_request.py <socket> <script file> <request URI>

Sends the request the way a web server does and prints the response as JSON:
{"stdout": "<headers and body>", "stderr": "<FastCGI stderr>"}. Stands in for
a web server in front of the pool, so the test needs no web server and no
FastCGI client package.
"""

import json
import os
import socket
import struct
import sys

FCGI_VERSION = 1
FCGI_BEGIN_REQUEST = 1
FCGI_END_REQUEST = 3
FCGI_PARAMS = 4
FCGI_STDIN = 5
FCGI_STDOUT = 6
FCGI_STDERR = 7
FCGI_RESPONDER = 1
REQUEST_ID = 1
HEADER = struct.Struct('>BBHHBx')


def record(record_type, content=b''):
    return HEADER.pack(FCGI_VERSION, record_type, REQUEST_ID, len(content), 0) + content


def pair_length(length):
    if length < 128:
        return struct.pack('B', length)
    return struct.pack('>I', length | 0x80000000)


def encode_params(params):
    body = b''
    for name, value in params.items():
        name, value = name.encode(), value.encode()
        body += pair_length(len(name)) + pair_length(len(value)) + name + value
    return body


def read_exact(conn, length):
    data = b''
    while len(data) < length:
        chunk = conn.recv(length - len(data))
        if not chunk:
            raise EOFError('PHP-FPM closed the connection')
        data += chunk
    return data


def main():
    sock_path, script, uri = sys.argv[1:4]
    params = {
        'GATEWAY_INTERFACE': 'CGI/1.1',
        'REQUEST_METHOD': 'GET',
        'SCRIPT_FILENAME': script,
        'SCRIPT_NAME': uri,
        'REQUEST_URI': uri,
        'DOCUMENT_ROOT': os.path.dirname(script),
        'QUERY_STRING': '',
        'CONTENT_LENGTH': '0',
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'SERVER_NAME': 'localhost',
        'SERVER_PORT': '80',
        'REMOTE_ADDR': '127.0.0.1',
        'HTTP_HOST': 'localhost',
    }
    stdout, stderr = b'', b''
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(30)
        conn.connect(sock_path)
        conn.sendall(
            record(FCGI_BEGIN_REQUEST, struct.pack('>HB5x', FCGI_RESPONDER, 0))
            + record(FCGI_PARAMS, encode_params(params))
            + record(FCGI_PARAMS)
            + record(FCGI_STDIN)
        )
        while True:
            _, record_type, _, length, padding = HEADER.unpack(read_exact(conn, HEADER.size))
            content = read_exact(conn, length)
            read_exact(conn, padding)
            if record_type == FCGI_STDOUT:
                stdout += content
            elif record_type == FCGI_STDERR:
                stderr += content
            elif record_type == FCGI_END_REQUEST:
                break
    print(json.dumps({
        'stdout': stdout.decode('utf-8', 'replace'),
        'stderr': stderr.decode('utf-8', 'replace'),
    }))


if __name__ == '__main__':
    main()
