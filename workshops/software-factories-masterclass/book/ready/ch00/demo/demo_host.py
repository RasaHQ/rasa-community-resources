"""Runtime-only viewer addresses: loopback or an explicit private tailnet bind."""
import ipaddress
import os
import re

LOOPBACK = '127.0.0.1'


def validate_host(host):
    try:
        valid = host == LOOPBACK or ipaddress.ip_address(host) in ipaddress.ip_network('100.64.0.0/10')
    except ValueError:
        valid = False
    if not valid:
        raise ValueError('Use loopback or a terminal-provided tailnet address.')
    return host


def display_hosts(host):
    validate_host(host)
    name = os.environ.get('BRIEFING_VIEWER_NAME', '')
    if name and host != LOOPBACK:
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,240}[a-z0-9])?\.ts\.net', name):
            raise ValueError('Use a terminal-provided ts.net viewer name.')
        return (host, name)
    return (host,)


def allowed_client(client, host):
    if client == LOOPBACK:
        return True
    try:
        return host != LOOPBACK and ipaddress.ip_address(client) in ipaddress.ip_network('100.64.0.0/10')
    except ValueError:
        return False


def require_viewer_access(host):
    validate_host(host)
    if host != LOOPBACK and os.environ.get('BRIEFING_VIEWER_ACCESS') not in (
            'operator-device-acl', 'operator-accepted'):
        raise ValueError('Inspector is unauthenticated: confirm an operator-device ACL or explicit operator acceptance in BRIEFING_VIEWER_ACCESS before tailnet launch.')
