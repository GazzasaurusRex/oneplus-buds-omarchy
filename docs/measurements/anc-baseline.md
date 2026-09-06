# ANC latency baseline

## Pro 2 — 2026-09-06

User confirmed both earbuds ready for two Off → Transparency → On → Off
cycles, ending Off. Product `062014`, firmware `196.196.101`; initial state Off.
The serialized controller measurement completed with exit status 0 and shutdown.
All eight requests verified with SET status `00`, including six actual mode
transitions and two already-Off requests. Both On requests read back On/Smart.
Final independently verified state: Off.

[Sanitized per-request records](2026-09-06-pro2-anc-baseline.jsonl) contain no
addresses or raw frames. Statistics below include all eight requests.

| Phase | Median | Range |
| --- | ---: | ---: |
| Controller total | 15.134 s | 14.126–15.158 s |
| Backend through independent verification | 8.429 s | 7.419–8.438 s |
| Monitoring resumption | 6.702 s | 6.696–6.735 s |
| Write connection | 1.045 s | 0.025–1.056 s |
| Independent verifier connection | 1.050 s | 1.041–1.056 s |
| HELLO exchange | 2.201 s | 2.201–2.202 s |
| REGISTER exchange | 1.701 s | 1.701–1.701 s |
| SET exchange | 1.201 s | 1.201–1.201 s |
| Verifier query | 0.501 s | 0.501–0.501 s |

Totals contain the phases below them; do not sum the whole table. This direct
controller test excludes bridge dispatch and QML rendering. Lock contention was
negligible because this harness does not run a concurrent service polling thread.

Monitoring resumption accounts for about 44% of median response time, after the
requested state has already been independently verified. A possible future
improvement is delivering verified state before monitoring resumes, while retaining
serialized ownership and explicit monitoring failure handling. This is a proposal,
not an implemented or proven-safe change. Simply moving reconnection after return
would require additional lifecycle work.

The second Transparency request connected in 25 ms rather than approximately
1.05 seconds, accounting for most of its one-second improvement. The timings
include connection retries but do not count attempts, so they do not prove why
connection setup was faster. Exchange durations closely track existing waits plus
the receive-burst timeout; reducing those requires new controlled evidence.

## Original Buds Pro — 2026-09-06

User confirmed the same two-cycle sequence with original Pro. Product `060C14`,
firmware `541.541.510`; initial state Off. All eight requests verified with SET
status `00`, including six actual transitions and two already-Off requests.
Both On requests read back On/Deep. Final independently verified state: Off.
The process exited with status 0 and shut down its controller.

[Sanitized per-request records](2026-09-06-pro-anc-baseline.jsonl).

| Phase | Median | Range |
| --- | ---: | ---: |
| Controller total | 15.130 s | 15.120–15.144 s |
| Backend through independent verification | 8.426 s | 8.422–8.437 s |
| Monitoring resumption | 6.699 s | 6.696–6.708 s |
| Write connection | 1.046 s | 1.045–1.054 s |
| Independent verifier connection | 1.048 s | 1.042–1.060 s |
| HELLO exchange | 2.201 s | 2.201–2.201 s |
| REGISTER exchange | 1.701 s | 1.701–1.702 s |
| SET exchange | 1.201 s | 1.201–1.201 s |
| Verifier query | 0.501 s | 0.501–0.501 s |

## Baseline comparison and optimization target

Both reference models passed the baseline: 16 verified requests, 12 actual
transitions, no failed or mismatched read-back. Median controller durations differ
by under 5 ms. Neither hardware model accounts for the reported slow response:
the measured delay is dominated by the shared conservative control path.

About 6.7 seconds (44%) occur after independent verification on both models.
Prioritize separating verified command delivery from monitoring resumption before
experimenting with shorter protocol waits. This could make verified confirmation
available around 8.4 seconds in these conditions; it would not make the physical
write itself faster or eliminate the remaining reconnect work. This is a measured
opportunity, not a tested latency improvement.

The implementation requirements derived from this baseline were:

- Keep one controller/RFCOMM owner and serialize reconnects with subsequent writes.
- Deliver a verified result and matching snapshot before monitoring reconnection;
  bridge snapshot acquisition must not block behind a polling-thread reconnect.
- Keep verified ANC outcome separate from a later monitoring failure. Reconnect
  failures must enter normal service recovery without falsely claiming ANC failed
  or that monitoring is connected.
- Preserve shutdown/cancellation and independent query-after-write verification.
- Test response ordering, reconnect failure, concurrent requests, and shutdown
  using fake sessions before a new, specifically agreed live UI timing check.

Do not repeat these baseline cycles. Do not infer that shorter HELLO/REGISTER or
receive waits are safe from these unchanged-delay measurements. The next change
should preserve them and target when verified results become visible.

## Verified optimization — persistent session

The persistent-session path is now the default for main ANC On, Off, and
Transparency commands on a running controller, hardware-verified on both reference
models. `reuse_session=False` retains the legacy path for explicit comparisons. It reuses the authenticated subscription session, sends
SET immediately, and waits for command/sequence-matched responses without the
legacy sleep or 200 ms idle-burst drain. It then independently queries ANC state
on the same channel. No successful-path socket close, discovery, profile query,
authentication, verifier reconnect, or subscription restoration remains.

Service polling now drains available data without waiting inside the controller
lock and waits its 0.5-second interval outside that lock. The response/snapshot
are captured atomically so response delivery cannot acquire a second lock behind
a polling-thread monitoring recovery. Expected control failures close the uncertain
session and invalidate cached ANC; they never replay the write. Subsequent poll
recovery owns reconnect, and does not delay a failed command response.

Original Pro first trial exposed a real settling race: already-Off verified in
58 ms, but a Transparency request's immediate fresh query mismatched after 63 ms.
The harness stopped. A separate read-only session subsequently returned Transparency.
[Failed trial records](2026-09-06-pro-session-immediate.jsonl) are preserved.

The corrected verifier sends SET once and issues response-paced, fresh state
queries until state matches, with a two-second deadline and 32-query ceiling.
Every query has a new transaction sequence. Unknown notifications are still
redacted and retained for monitoring, never treated as verification. SET timeout
may proceed to verification (some firmware omits acknowledgements); other transport
failures abort. No setting write is retried.

[Original Pro corrected run](2026-09-06-pro-session-reuse.jsonl): eight verified
requests, seven actual transitions (starting Transparency after the failed trial),
all SET statuses `00`, final Off. Same session and advertised subscriptions survived
all requests, with normal service polling concurrent throughout. Process exited 0.

| Original Pro phase | Median | Range |
| --- | ---: | ---: |
| SET sent, elapsed from session call | 0.148 ms | 0.122–0.227 ms |
| SET response | 55.496 ms | 44.650–66.698 ms |
| Fresh verification queries | 205.556 ms | 20.088–214.145 ms |
| Verified state, elapsed from session call | 259.251 ms | 86.818–272.356 ms |
| Controller total | 259.503 ms | 87.042–272.780 ms |
| Controller lock wait | 0.018 ms | 0.016–0.021 ms |
| Monitoring restoration | none | session retained |

Actual transitions used 11–19 queries; the already-Off request used one. This is
bounded response-paced settling detection, not continuous background polling.
The audible change time cannot be measured by a socket send or acknowledgement;
user listening observations are requested separately. Original Pro result is about
58× faster / 98.3% shorter to verified completion than its baseline.

The original HELLO 2.0 s and REGISTER 1.5 s waits remain for initial session setup
and the legacy one-shot path: this experiment removes repeated authentication,
it does not establish safe shorter cold-start authentication. Connection retry
policy (1 s on EBUSY) and service failure backoff (1–30 s) remain failure-only;
there is no connection or retry in a healthy persistent-session command.

## Pro 2 optimized verification

The [first Pro 2 run](2026-09-06-pro2-session-incomplete.jsonl) completed four
verified requests, then the harness stopped outside the timed ANC-error handler.
The original harness did not retain enough detail to distinguish a session change,
monitoring failure, or another harness exception. Do not infer a cause or count
that run as a completed pass. Instrumentation was extended to preserve phase,
exception type, service lifecycle states, and successful control timings even
when a subsequent monitoring check fails. A final monitoring check also prevents
loss during the last listening pause from being silently counted as completion.

The [unchanged control-path rerun](2026-09-06-pro2-session-reuse.jsonl) completed
all eight verified requests, six actual transitions, with the original session
and all ten advertised subscription codes retained. Every request used one fresh
state query and SET status `00`; On read back Smart. Final state Off, exit 0.
No protocol, retry, or wait setting changed between those two Pro 2 runs.

| Pro 2 phase | Median | Range |
| --- | ---: | ---: |
| SET sent, elapsed from session call | 0.139 ms | 0.121–0.216 ms |
| SET response | 65.503 ms | 31.688–150.804 ms |
| Fresh verification query | 43.055 ms | 22.059–100.030 ms |
| Verified state, elapsed from session call | 107.046 ms | 55.595–250.861 ms |
| Controller total | 107.304 ms | 55.856–251.086 ms |
| Controller lock wait | 0.017 ms | 0.016–0.039 ms |
| Monitoring restoration | none | session retained |

### Before/after, separating actual transitions from already-active requests

| Reference model | Baseline median, all requests | Optimized median, all requests | Baseline median, actual transitions | Optimized median, actual transitions |
| --- | ---: | ---: | ---: | ---: |
| Buds Pro | 15.130 s | 0.260 s | 15.132 s | 0.260 s |
| Buds Pro 2 | 15.134 s | 0.107 s | 15.138 s | 0.167 s |

Actual-transition latency fell by about 98.3% and 98.9%, respectively. The
successful optimized runs include 16 requests and 13 actual transitions (original
Pro began Transparency after its preliminary trial). Baselines included 12 actual
transitions. These are controller measurements with concurrent service polling in
the optimized runs; they do not include QML rendering or measured audible timing.

### Where each source of delay went

- **Deliberate sleeps:** no fixed sleep in the warm main-mode command. Legacy
  SET's 1.0 s wait, verifier's 0.3 s wait, and 0.2 s idle drain per exchange are
  replaced by bounded socket reads that finish on correlated replies. Fresh
  queries handle real settling; original Pro proves the delay cannot be removed
  merely by accepting its early acknowledgement.
- **Repeated handshake:** removed from healthy warm commands; existing HELLO and
  REGISTER run once when opening the monitoring session, not twice per change.
- **RFCOMM setup/teardown:** removed from healthy warm commands. Baseline write and
  verifier setup were about 1.05 s each; closes were less than 1 ms. Their timing
  included EBUSY retries but did not count attempts, so exact retry counts are
  unknown. Same-session assertions prove neither connection was needed afterward.
- **Subscription teardown/restoration:** eliminated on success, saving about
  6.7 s. Notifications arriving alongside replies are still redacted and consumed;
  the original session and subscription code list survive each measured command.
- **Verification:** retained as separate state-query transactions, not a SET
  acknowledgement, cache update, or inferred notification. A new physical socket
  was redundant for these verified models; a fresh sequence-matched query on the
  same socket independently reports the applied state. Only original Pro needed
  repeated settling queries; Pro 2 matched the first query in the completed run.
- **Polling:** the previous service held the controller lock through a 0.5 s
  sleep plus up to 0.2 s idle drain. The service now drains immediately available
  frames under the lock and waits 0.5 s outside it. Request replies are handled
  directly, without waiting for the next monitoring poll. Drains are bounded to
  16 reads of 512 bytes so a notification flood cannot monopolize the controller.
- **Retry/backoff:** healthy warm changes have none. EBUSY connection retries and
  1–30 s service backoff are retained for genuine recovery. No uncertain setting
  write is automatically replayed. Missing SET acknowledgement can time out after
  3 s, then still requires a fresh verified state; verification itself is bounded
  by 2 s and 32 queries.
- **Notifications:** already-used subscriptions remain alive and preserve safe
  state updates. Unmapped event payloads are not promoted to ANC proof. Further
  reducing the original Pro's settling-query count would require validated
  notification semantics; no guessed event ID or unverified audible timing is used.

### Scope and remaining limits

Main modes on the live service use the optimized path. Initial authentication,
standalone one-shot CLI requests, explicit ANC level commands, and disconnected
recovery retain the proven conservative path. Cold startup was not shortened by
these warm-session measurements. The UI receives its verified result and matching
snapshot atomically, with no successful-path monitoring restoration to wait for;
a later monitoring failure cannot force a second snapshot lock acquisition before
that response. No QML or desktop configuration was changed in this milestone.

Regression coverage: 79 tests pass, including response correlation, fragmentation,
deadlines, no write replay, bounded settling, privacy, subscription/session reuse,
command serialization, cancellation/shutdown ownership, nonblocking service polls,
and atomic bridge response/snapshot delivery. Omarchy plugin validation passes.
Keep the incomplete and rejected runs as evidence; do not repeat the baselines.


Final [default-bridge integration check](2026-09-06-pro2-default-bridge.jsonl)
used the already-active Off mode on Pro 2 with concurrent service polling. It
verified in 59.448 ms, retained the same session through a further ten-second
monitoring hold, reported no service errors, and exited 0 after shutdown. This
checks the actual default bridge/controller path, not a QML rendering benchmark.
