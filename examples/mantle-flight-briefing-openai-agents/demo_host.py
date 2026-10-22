"""Explicit class bind addresses; never an arbitrary interface or public bind."""
import ipaddress

LOOPBACK = '127.0.0.1'
TAILNET = '100.123.206.49'
TAILNET_DNS = 'mac-mini.tail29b7b0.ts.net'


def validate_host(host):
    if host not in (LOOPBACK, TAILNET):
        raise ValueError('Use loopback or the approved Mac mini tailnet address.')
    return host


def display_hosts(host):
    return (host, TAILNET_DNS) if validate_host(host) == TAILNET else (host,)


def allowed_client(client, host):
    if client == LOOPBACK:
        return True
    try:
        return host == TAILNET and ipaddress.ip_address(client) in ipaddress.ip_network('100.64.0.0/10')
    except ValueError:
        return False
