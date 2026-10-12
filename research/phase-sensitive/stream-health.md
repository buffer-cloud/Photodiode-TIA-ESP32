# Live ESP32 stream health (12 October 2026)

These captures use a physical ESP32 Dev Module with GPIO34 **open**. They measure digital acquisition and local Wi-Fi/WebSocket delivery, not photodiode response or optical signal quality. The number of Python receivers was controlled within each capture; local RF conditions and other possible network clients were not.

| Configuration | Duration | Samples delivered per receiver | Missing packet sequences | New device drops | Notes |
|---|---:|---:|---:|---:|---|
| 1 ksps, one receiver, settled | 10 s | 9,984 (998/s) | 0 | 0 | `results/single-client-after-repeat.json` |
| 1 ksps, final flashed firmware after reset | 10 s | 9,984 (998/s) | 0 | 0 | `results/final-firmware-1k.json`; queue stayed empty |
| 1 ksps, three simultaneous Python receivers | 15 s | 14,848 each (990/s) | 0 each | 0 each | `results/three-python-{a,b,c}.json`; 153–154 ms backlog growth |
| 4 ksps, one receiver | 12 s | 42,240 (3,520/s) | 0 | 4,096 | `results/single-client-4k.json`; queue reached 8 batches |
| 4 ksps, Wi-Fi sleep disabled, one receiver | 15 s | 42,496 (2,833/s) | 0 | 17,664 | `results/single-client-4k-no-sleep.json`; queue reached 7 batches |

The `dropped` count covers discarded acquisition batches and transport losses; these captures do not split those causes. At 4 ksps, the longest reported broadcast took 0.44 s in the first run and 4.23 s with Wi-Fi sleep disabled. The ESP32 acquisition timer was independently observed near its 1 ms setting in an earlier serial diagnostic, so the present evidence points to the synchronous WebSocket send path as a major contributor, without proving that it is the only cause. A fresh connection after reset also stalled for roughly 20 seconds before a subsequent 1 ksps capture ran normally (`results/single-client-after.json`). That startup behavior remains unresolved.

For the current live demo, firmware boots at 1 ksps. This is a measured operating point for the stated 10–15 second conditions, **not** a claim of indefinite lossless operation. The 4 ksps design target remains open. The 1 ksps analog anti-alias rejection at 500 Hz Nyquist is only about −6.3 dB, so out-of-band illumination must be controlled before any optical accuracy claim.

Next engineering experiment: replace the synchronous per-client JSON broadcast with a bounded, nonblocking transport or a compact packet format, then repeat long single- and multi-receiver tests with timestamp span, sequence gaps, queue depth, transport duration, and separate acquisition/transport loss counters. The analog front end and photodiode are not yet assembled, so no calibrated optical result is reported.
