#!/usr/bin/env python3
"""Record BlueZ signal receipt and actual QML lifecycle timestamps, read-only.

Requires host dbus-python/PyGObject and an instrumented installed plugin.
Never records Bluetooth addresses, object paths, names, or raw protocol data.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from threading import Event, Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from oneplus_buds.lifecycle_trace import mark
from oneplus_buds.bluez import DEVICE_INTERFACE, OPO_UUIDS


def main():
    import os
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    os.environ['ONEPLUS_BUDS_LIFECYCLE_TRACE'] = args.output
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus(private=True)
    manager = dbus.Interface(bus.get_object('org.bluez', '/'),
                             'org.freedesktop.DBus.ObjectManager')
    properties = {}
    def compatible(props):
        return 'oneplus' in str(props.get('Name', '')).lower() and bool(
            OPO_UUIDS.intersection(str(x).lower() for x in props.get('UUIDs', [])))
    def changed(interface, changes, invalidated, path=None):
        if interface != DEVICE_INTERFACE:
            return
        props = properties.setdefault(path, {})
        props.update(changes)
        for key in invalidated:
            props.pop(key, None)
        if compatible(props) and 'Connected' in changes:
            mark('bluez_connected_signal' if changes['Connected'] else 'bluez_disconnected_signal')
    def added(path, interfaces):
        if DEVICE_INTERFACE in interfaces:
            changed(DEVICE_INTERFACE, interfaces[DEVICE_INTERFACE], [], path)
    bus.add_signal_receiver(changed, signal_name='PropertiesChanged',
        dbus_interface='org.freedesktop.DBus.Properties', bus_name='org.bluez', path_keyword='path')
    bus.add_signal_receiver(added, signal_name='InterfacesAdded',
        dbus_interface='org.freedesktop.DBus.ObjectManager', bus_name='org.bluez')
    for path, interfaces in manager.GetManagedObjects().items():
        if DEVICE_INTERFACE in interfaces:
            properties[path] = dict(interfaces[DEVICE_INTERFACE])
            if compatible(properties[path]):
                mark('bluez_initial_snapshot', connected=bool(properties[path].get('Connected')))
    stopped = Event()
    def qml_observer():
        seen = set()
        while not stopped.is_set():
            try:
                result = subprocess.run(['omarchy-shell', 'oneplus-buds.control', 'status'],
                    capture_output=True, text=True, timeout=2)
                data = json.loads(result.stdout)
                for event in data.get('lifecycle', []):
                    key = (event['phase'], event['unix_ms'], event.get('product_id'))
                    if key not in seen:
                        seen.add(key)
                        mark(event['phase'], observed_unix_ms=event['unix_ms'],
                             product_id=event.get('product_id') or 'none')
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass
            stopped.wait(0.2)
    worker = Thread(target=qml_observer, daemon=True)
    worker.start()
    mark('observer_ready')
    print('Observer ready', flush=True)
    try:
        GLib.MainLoop().run()
    except KeyboardInterrupt:
        pass
    finally:
        stopped.set()
        worker.join(3)
        bus.close()


if __name__ == '__main__':
    main()
