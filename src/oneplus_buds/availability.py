"""BlueZ availability hints; fresh discovery remains the selection authority."""
from threading import Condition, Event, Thread
from time import monotonic

from .bluez import DEVICE_INTERFACE, OPO_UUIDS
from .lifecycle_trace import mark


class Availability:
    """Generation-counted wakeups avoid lost signals and repeated early retries."""
    def __init__(self):
        self._condition = Condition()
        self._generation = 0

    def token(self):
        with self._condition:
            return self._generation

    def notify(self):
        with self._condition:
            self._generation += 1
            self._condition.notify_all()

    def wait(self, cancelled: Event, delay: float, token: int) -> bool:
        deadline = monotonic() + delay
        with self._condition:
            while not cancelled.is_set():
                remaining = deadline - monotonic()
                if remaining <= 0 or self._generation != token:
                    return False
                # Cancellation remains bounded even without a BlueZ event.
                self._condition.wait(min(remaining, 0.1))
        return True


class BlueZAvailability(Availability):
    def __init__(self):
        super().__init__()
        self._properties = {}
        self._bus = None
        self._loop = None
        self._thread = None
        self._stopped = Event()

    @staticmethod
    def _eligible(properties):
        return (bool(properties.get('Connected'))
                and 'oneplus' in str(
                    properties.get('Name') or properties.get('Alias') or '').lower()
                and bool(OPO_UUIDS.intersection(
                    str(uuid).lower() for uuid in properties.get('UUIDs', ()))))

    def changed(self, interface, changes, invalidated, path=None):
        if interface != DEVICE_INTERFACE:
            return
        properties = self._properties.setdefault(path, {})
        was_eligible = self._eligible(properties)
        properties.update(changes)
        for key in invalidated:
            properties.pop(key, None)
        if self._eligible(properties) and not was_eligible:
            mark('bluez_availability_notice')
            self.notify()

    def added(self, path, interfaces):
        if DEVICE_INTERFACE in interfaces:
            self.changed(DEVICE_INTERFACE, interfaces[DEVICE_INTERFACE], (), path)

    def removed(self, path, interfaces):
        if DEVICE_INTERFACE in interfaces:
            self._properties.pop(path, None)

    def owner_changed(self, name, old_owner, new_owner):
        if name == "org.bluez":
            self._properties.clear()
            if new_owner:
                # A daemon restart is a fresh availability hint, not cached state.
                self.notify()

    def start(self):
        """Optional host integration; unavailable bindings retain timer recovery."""
        try:
            import dbus
            from dbus.mainloop.glib import DBusGMainLoop, threads_init
            from gi.repository import GLib
            threads_init()
            self._bus = dbus.SystemBus(private=True, mainloop=DBusGMainLoop())
            self._loop = GLib.MainLoop()
            self._stopped.clear()
            self._bus.add_signal_receiver(self.changed, signal_name='PropertiesChanged',
                dbus_interface='org.freedesktop.DBus.Properties', bus_name='org.bluez', path_keyword='path')
            self._bus.add_signal_receiver(self.added, signal_name='InterfacesAdded',
                dbus_interface='org.freedesktop.DBus.ObjectManager', bus_name='org.bluez')
            self._bus.add_signal_receiver(self.removed, signal_name='InterfacesRemoved',
                dbus_interface='org.freedesktop.DBus.ObjectManager', bus_name='org.bluez')
            self._bus.add_signal_receiver(self.owner_changed, signal_name='NameOwnerChanged',
                dbus_interface='org.freedesktop.DBus', arg0='org.bluez')
            manager = dbus.Interface(self._bus.get_object('org.bluez', '/'),
                                     'org.freedesktop.DBus.ObjectManager')
            for path, interfaces in manager.GetManagedObjects().items():
                if DEVICE_INTERFACE in interfaces:
                    self._properties[path] = dict(interfaces[DEVICE_INTERFACE])
            def check_stop():
                if self._stopped.is_set():
                    self._loop.quit()
                    return False
                return True
            # Also handles close racing the thread's first MainLoop.run().
            GLib.timeout_add(100, check_stop)
            self._thread = Thread(target=self._loop.run, name='bluez-availability', daemon=True)
            self._thread.start()
            mark('bluez_watch_ready')
        except Exception:
            mark('bluez_watch_unavailable')
            self.close()

    def close(self):
        self._stopped.set()
        if self._loop is not None:
            self._loop.quit()
        if self._thread is not None:
            self._thread.join()
        if self._bus is not None:
            self._bus.close()
        self._loop = self._thread = self._bus = None
        self._properties.clear()
