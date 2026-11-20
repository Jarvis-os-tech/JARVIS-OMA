#!/usr/bin/env python3
"""Reconnect an authorized Android phone and its shared-executor tunnel over Wi-Fi."""
import argparse
import ipaddress
import subprocess
import sys
import importlib.util
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def adb(*args):
    result = subprocess.run(['adb', *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--address', required=True, help='Phone IP on the same trusted Wi-Fi/hotspot')
    parser.add_argument('--port', type=int, default=5555)
    parser.add_argument('--enable-from-usb', metavar='SERIAL', help='First-time setup using an already-authorized USB phone')
    args = parser.parse_args()
    ip = ipaddress.ip_address(args.address)
    if not ip.is_private or not 1 <= args.port <= 65535:
        parser.error('Use the phone address on your private network and a valid port')
    if args.enable_from_usb:
        if adb('-s', args.enable_from_usb, 'shell', 'getprop', 'ro.adb.secure') != '1':
            parser.error('Device must require authenticated ADB')
        adb('-s', args.enable_from_usb, 'tcpip', str(args.port))
    endpoint = f'[{ip}]:{args.port}' if ip.version == 6 else f'{ip}:{args.port}'
    connected = adb('connect', endpoint)
    model = adb('-s', endpoint, 'shell', 'getprop', 'ro.product.model')
    if not model:
        parser.error('Phone did not authenticate; enable debugging and authorize this PC')
    adb('-s', endpoint, 'reverse', 'tcp:8766', 'tcp:8766')
    # Keep this setup helper usable with system Python, without the AI runtime dependencies.
    spec = importlib.util.spec_from_file_location('jarvis_phone_link', Path(__file__).resolve().parents[1] / 'jarvis_control/phone_control.py')
    link = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(link)
    serial = adb('-s', endpoint, 'shell', 'getprop', 'ro.serialno')
    if not serial:
        parser.error('Phone identity unavailable; link was not saved')
    link.save_link(endpoint, serial, model)
    print(f'Wireless JARVIS ready on {model}. Shared PC execution tunnel restored.')
    print('The USB cable can be removed. Keep the phone and PC on this trusted network.')


if __name__ == '__main__':
    main()
