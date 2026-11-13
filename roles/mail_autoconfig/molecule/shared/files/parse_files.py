#!/usr/bin/env python3
"""Parse the rendered autoconfiguration files and print their content as JSON.

Usage: parse_files.py <web_root> <domain> [<domain> ...]

Fails (non-zero exit) when a file is not well-formed XML or not a valid
property list, so the verify step catches broken files before comparing
values.
"""

import hashlib
import json
import os
import plistlib
import sys
import xml.etree.ElementTree as ET

AUTODISCOVER_NS = 'http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006'
OUTLOOK_NS = 'http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a'


def local(tag):
    return tag.split('}', 1)[-1]


def server(element):
    data = {child.tag: child.text for child in element}
    data['type'] = element.get('type')
    return data


def mozilla(path):
    root = ET.parse(path).getroot()
    provider = root.find('emailProvider')
    return {
        'root': root.tag,
        'version': root.get('version'),
        'id': provider.get('id'),
        'domains': [d.text for d in provider.findall('domain')],
        'display_name': provider.findtext('displayName'),
        'display_short_name': provider.findtext('displayShortName'),
        'incoming': [server(e) for e in provider.findall('incomingServer')],
        'outgoing': [server(e) for e in provider.findall('outgoingServer')],
    }


def autodiscover(path):
    root = ET.parse(path).getroot()
    ns = {'a': AUTODISCOVER_NS, 'o': OUTLOOK_NS}
    account = root.find('o:Response/o:Account', ns)
    return {
        'root': root.tag,
        'account_type': account.findtext('o:AccountType', namespaces=ns),
        'action': account.findtext('o:Action', namespaces=ns),
        'protocols': [
            {local(child.tag): child.text for child in protocol}
            for protocol in account.findall('o:Protocol', ns)
        ],
    }


def sha256(path):
    with open(path, 'rb') as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def main():
    web_root = sys.argv[1]
    domains = sys.argv[2:]
    mozilla_files = [
        os.path.join(web_root, 'mail', 'config-v1.1.xml'),
        os.path.join(web_root, '.well-known', 'autoconfig', 'mail', 'config-v1.1.xml'),
    ]
    result = {
        'mozilla': mozilla(mozilla_files[0]),
        'mozilla_identical': len({sha256(p) for p in mozilla_files}) == 1,
        'autodiscover': autodiscover(os.path.join(web_root, 'autodiscover', 'autodiscover.xml')),
        'apple': {},
    }
    for domain in domains:
        with open(os.path.join(web_root, 'apple', domain + '.mobileconfig'), 'rb') as handle:
            result['apple'][domain] = plistlib.load(handle, fmt=plistlib.FMT_XML)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
