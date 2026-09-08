# Connection lifecycle measurement

Baseline revision: `88b0299` plus timestamp instrumentation only. No sleep,
authentication wait, query order, retry or selection policy changed for baseline.
Hardware: OnePlus Buds Pro (`060C14`) and Pro 2 (`062014`).

## Method

Set `ONEPLUS_BUDS_LIFECYCLE_TRACE` to an absolute JSONL output path in the helper's
environment. It records monotonic nanoseconds (duration source), Unix nanoseconds
(cross-process/UI correlation), PID, fixed phase names and command numbers.
No address, object path, raw frame, token or error text is recorded. Trace write
failures do not change protocol behaviour. Instrumentation is disabled by default.

Run `scripts/observe_connection.py --output PATH` on the desktop host before
starting a sequence. It subscribes to BlueZ PropertiesChanged/InterfacesAdded
and timestamps receipt on a dedicated GLib event loop. BlueZ does not supply a
controller-radio timestamp: reported latency begins at host signal receipt.
Initial snapshots are labelled separately and never passed off as connect events.
The observer reads the actual widget's IPC lifecycle records; their Date.now()
timestamps are captured inside QML, not assigned at the later IPC poll. Frontend
and UI times have millisecond resolution and wall-clock adjustment uncertainty.
Backend phase durations use the monotonic clock. Observer IPC runs off the BlueZ
loop so IPC latency does not hold up signal receipt.

`python scripts/summarize_connection.py TRACE` prints successful startup phase
boundaries. Failed/interrupted starts remain in raw traces and must be reported
separately. A deployment-triggered helper restart is not a hardware reconnect.

Separate scenarios:

- Cold service startup with the reference device already connected: origin is
  host/service startup, since Bluetooth connection predates observation.
- Device arriving while an empty service is running: origin is BlueZ connect
  signal receipt; include time until the successful discovery attempt.
- Same-device reconnect: disconnect, observe cleared state, reconnect without
  restarting the helper.
- Cross-device switch: disconnect A, observe cleared state, connect B using the
  same helper; verify B's profile and state.

Essential usable state means an authenticated session plus identified profile,
battery and ANC state, with the connected UI controls enabled. Subscription and
firmware may complete immediately afterward on that same session. Case battery
can be absent. This is a state-binding timestamp, not a compositor presentation
or physical display scanout timestamp.

## Baseline source audit

The disconnected runner waits 1, 2, 4, 8, 16, then at most 30 seconds between
attempts; there is no BlueZ event wake-up. Connected event polling is 0.5 seconds.
`read_status` performs capability, product, firmware, battery and ANC queries on
one socket, closes it, then session setup opens another socket. Channel 15 is
already a fixed transport default: there is no runtime SDP/channel-discovery
phase. BlueZ selection runs once per startup attempt, not once per query.

Each baseline query sleeps 150 ms and drains until a 200 ms idle timeout; HELLO
sleeps 2 seconds and REGISTER 1.5 seconds, both also drain. Broadcast-code query
and subscription each sleep 500 ms plus drain. Reopening the socket can trigger
an EBUSY retry with a one-second wait during otherwise successful startup.
Firmware precedes battery/ANC even though it is not needed for controls. There
is no separate wait for case battery and no independent optional-case query.

All operations share one serialized RFCOMM stream. Concurrent independent
readers would race response ownership; any pipelining must retain one parser and
correlate responses, with hardware evidence before adoption.

The event-driven candidate uses BlueZ's Device1 connection property and
ObjectManager interface signals as wake hints, while retaining fresh selection
as the authority. References: [BlueZ Device1 API](https://github.com/bluez/bluez/blob/master/doc/org.bluez.Device.rst),
[dbus-python main-loop integration](https://dbus.freedesktop.org/doc/dbus-python/dbus.mainloop.html),
and [signal subscription tutorial](https://dbus.freedesktop.org/doc/dbus-python/tutorial.html).

## Completed baseline

| Model | Scenario | Notice delay | Backend setup | Origin to usable UI |
|---|---|---:|---:|---:|
| Pro 2 | Cold service | 0.001 s | 8.574 s | 8.655 s |
| Pro 2 | Same-device reconnect | 9.751 s | 8.525 s | 18.335 s |
| Original Pro | Switch from Pro 2 | 29.074 s | 8.944 s | 38.073 s |
| Original Pro | Cold service | 0.018 s | 8.714 s | 8.757 s |
| Original Pro | Same-device reconnect | 19.719 s | 9.014 s | 28.794 s |
| Pro 2 | Switch from original Pro | 23.959 s | 8.663 s | 32.635 s |
| Pro 2 | Arrival at empty service | 13.603 s | 8.832 s | 22.474 s |
| Original Pro | Arrival at empty service | 7.909 s | 8.634 s | 16.591 s |

Cold-service notice delay starts at helper startup; other origins are BlueZ
signal receipts. Notice delay depends on the phase of the existing retry timer,
so one sample is not an average or worst-case guarantee. The large repeated
setup contribution is stable across models and scenarios. Every completed
baseline so far reopened RFCOMM and hit a one-second EBUSY delay. HELLO and
REGISTER together consistently consumed about 3.9 seconds including idle drains;
subscription discovery/setup consumed about 1.4 seconds.

Full baseline timestamps and phase durations are preserved in the adjacent
`2026-09-08-connection-baseline*.json*` artifacts. Eight completed runs cover
all four scenarios on both models; the first deployment-interrupted start is
retained in the trace and excluded from successful-run statistics.

## Optimized implementation

BlueZ Device1/ObjectManager signals now provide availability hints that interrupt
a pending retry wait. Each hint is generation-counted, so an arrival during a
discovery attempt is not lost and repeated Connected/RSSI/ServicesResolved
updates do not create aggressive retry loops. Fresh ObjectManager discovery is
still authoritative on every attempt. The existing 1/2/4/8/16/30-second timer
backoff remains the fallback when the watcher is unavailable and continues to
govern ordinary failures. BlueZ daemon restarts clear the watcher's hint cache.

Startup now retains one RFCOMM channel from product identification through
authentication, essential battery/ANC queries, subscriptions and monitoring.
The capability primer remains, product/battery/ANC use response-correlated
requests, and the verified product selects a fresh profile each lifecycle. This
removes the second socket and its observed one-second EBUSY retry. Firmware and
notification subscription discovery/setup start on the first service poll after
the connected snapshot, on the same serialized session. Their failure still
tears down the session and enters normal recovery. No connection/session state
or physical-device identity is cached.

The conservative HELLO (2 seconds) and REGISTER (1.5 seconds) waits were retained.
They consume about 3.9 seconds including receive drains and are now the main
remaining startup cost. Parallel socket readers were rejected because they would
race the single OPO stream parser. Essential state requests are serialized and
typically complete in tens of milliseconds, so parallelizing them would add
ownership complexity for little measured gain. There is no SDP optimization:
both versions already connect directly to verified channel 15.

## Hardware comparison

| Model | Scenario | Before usable UI | After usable UI | Improvement | After notice delay |
|---|---|---:|---:|---:|---:|
| Pro 2 | Cold service | 8.655 s | 4.869 s | 43.7% | 0.381 s¹ |
| Pro 2 | Arrival at empty service | 22.474 s | 4.481 s | 80.1% | 0.003 s |
| Pro 2 | Same-device reconnect | 18.335 s | 4.504 s | 75.4% | 0.001 s |
| Pro 2 | Switch from original Pro | 32.635 s | 4.485 s | 86.3% | <0.001 s |
| Original Pro | Cold service | 8.757 s | 4.630 s | 47.1% | 0.186 s¹ |
| Original Pro | Arrival at empty service | 16.591 s | 4.597 s | 72.3% | 0.001 s |
| Original Pro | Same-device reconnect | 28.794 s | 4.561 s | 84.2% | 0.001 s |
| Original Pro | Switch from Pro 2 | 38.073 s | 4.476 s | 88.2% | 0.002 s |

¹ Cold-service notice delay begins at process startup and includes watcher/helper
initialization; it is not a BlueZ-event response time.

All eight optimized runs reached the correct model-specific authenticated state,
battery, ANC and controls. Both switch directions included a clean disconnected
gap. Subscription completed about 1.4 seconds after first usable state and
firmware populated on the following poll without opening another socket. No
normal successful run used retry backoff or RFCOMM EBUSY recovery. No matching
plugin runtime errors appeared during the hardware-test window.

Full optimized traces and per-run phase durations are preserved in the adjacent
`2026-09-08-connection-optimized*.json*` artifacts. These are single controlled
samples for each scenario, suitable for identifying phase costs rather than
estimating a population distribution.
