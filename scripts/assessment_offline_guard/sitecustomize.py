"""Acceptance-only Python network boundary; not loaded by normal runtime.

Blocks runtime DNS and socket traffic beyond loopback, and proves enforcement
at interpreter startup. No system firewall or other applications are changed.
"""
import ipaddress
import json
import os
import socket
import sys
from pathlib import Path


evidence_path = os.environ.get('NEXUS_OFFLINE_EVIDENCE')
if evidence_path:
    def record(event, address):
        with Path(evidence_path).open('a', encoding='utf-8') as output:
            output.write(json.dumps({'pid': os.getpid(), 'event': event, 'address': str(address)}) + '\n')

    def local(address):
        if not isinstance(address, tuple):
            return False
        host = address[0]
        if host == 'localhost':
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def audit(event, args):
        if event == 'socket.getaddrinfo':
            permitted = local((args[0],))
            address = args[0]
        elif event in {'socket.connect', 'socket.sendto'}:
            address = args[-1]
            permitted = local(address)
        else:
            return
        if not permitted:
            record('blocked:' + event, address)
            raise PermissionError('Assessment acceptance blocks all non-loopback networking')

    sys.addaudithook(audit)
    # These attempts are denied before packets/DNS requests leave this process.
    for probe in ('tcp', 'dns'):
        try:
            if probe == 'tcp':
                with socket.socket() as connection:
                    connection.connect(('192.0.2.1', 443))
            else:
                socket.getaddrinfo('example.com', 443)
        except PermissionError:
            record('guard_verified:' + probe, 'non-loopback denied')
        else:
            os._exit(78)
    record('guard_active', 'loopback only')
