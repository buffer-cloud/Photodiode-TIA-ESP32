# ESP32 acquisition firmware

This salvages the initial implementation using the Arduino 2 APIs supplied by the pinned PlatformIO platform. Target: original ESP32 DevKit (`esp32dev`), GPIO34 / ADC1 channel 6, 12 bits, 11 dB attenuation. No analog or protocol interfaces are changed.

## Reproducible build and use

Tested with PlatformIO Core **6.2.0**. `platformio.ini` pins `espressif32@7.1.3`, framework package `platformio/framework-arduinoespressif32@3.20017.241212` (Arduino **2.0.17**) and WebSockets **2.7.3**. Do not substitute Arduino 3 GPTimer/oneshot headers into this build.

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install platformio==6.2.0
.venv/bin/pio run -d firmware/esp32
cp firmware/esp32/include/secrets.example.h firmware/esp32/include/secrets.h
# Edit secrets.h locally with your Wi-Fi credentials.
.venv/bin/pio run -d firmware/esp32 -t upload
.venv/bin/pio device monitor -d firmware/esp32
```

Skip environment creation if `.venv` already exists. A clean checkout builds without credentials using the placeholder example header; real Wi-Fi requires the local `secrets.h`, ignored by the root `.gitignore`. Never commit credentials. Serial is **115200 baud**, newline-terminated commands. The IP is printed after connection. Connect a client to `ws://<esp32-ip>:81/`; other paths are rejected. Plain WebSocket is intended for a trusted local network.

Commands: `help`, `status`, `rate 1000` through `rate 8000`, `gain 10000|100000|1000000`, `avg 1` through `avg 64`, `dcrm on|off`, `print 20`, `wifi on|off`. Default rate is 4000 Hz and gain metadata is 100000 ohms. Rate requests take effect at a batch boundary; status reports the requested rate. Gain metadata is captured at the first sample of each batch. Change physical gain only with power off and exactly one feedback pair selected; the command does not switch hardware. Average/DC removal affect serial diagnostics only.

## Timing, calibration and loss behavior

A 40 MHz hardware timer (APB divider 2) wakes a high-priority task on core 1. ADC conversion occurs in that task; sampling is never delay-paced. Network and serial diagnostic work run separately. Timer periods round to the nearest hardware tick; `fs_hz` is nominal, while `t0_us` and `dt_us` are actual timestamps taken immediately after each conversion, including scheduling and conversion latency. These are not ADC aperture timestamps. Arrays contain 256 conversions; the pool contains ten batches (2560 sample positions), including producer and consumer slots, leaving at least eight queued batches.

`mv[i]` comes from `esp_adc_cal_raw_to_voltage(raw[i])` for the **same conversion**. Provenance is `efuse_two_point` or `efuse_vref`. Chips without calibration fuses use Espressif's characterized 1100 mV reference fallback and explicitly report `default_vref_1100mV`; that fallback is an estimate, not measured calibration. Perform the contract's five-or-more-point DMM calibration across 0.25–2.40 V and apply the correction in Python. The pinned SDK warns that the historical `ADC_ATTEN_DB_11` spelling is deprecated; it is retained to match the locked setting and maps to the same hardware attenuation.

`dropped` includes coalesced acquisition notifications, invalid conversions, overwritten full batches, discarded notifications during rate changes, serialization failure, no-client/disconnected batches, and reported broadcast failure. Actual timestamp gaps additionally estimate deadlines missed while timer interrupts were masked, using the greater of notification loss and whole-period gap loss for each interval rather than adding them. This gap estimate is conservative and affected by task latency; it cannot establish exact hardware missed-deadline counts. Treat measured timestamps as the timing evidence. Counters saturate at 32-bit maximum rather than wrapping silently. Sequence increments for each broadcast attempt; after 2^32 attempts it wraps. A successful socket write does not prove delivery to every client; clients must also check timestamps and sequence gaps. Loss is global, not per-client. Buffer truncation is rejected, never transmitted as malformed JSON.

Wi-Fi toggles and WebSocket access are owned by the streaming task; console commands post atomic requests. A reconnect may block that task for up to 15 seconds, allowing counted ring overflow while acquisition continues. Diagnostic printing can similarly slow streaming and produce counted loss. Timing statistics reset at a rate change.

## Validation and remaining bench work

`pio run -d firmware/esp32` builds the pinned firmware successfully. Build success is compile/link evidence only; no ESP32 was flashed or measured for this change. Hardware tests remain: verify boot/timer cadence at 1/4/8 ksps and an intermediate rate, timestamps and rate-boundary metadata, eFuse provenance and DMM voltage agreement, sustained WebSocket throughput, slow/disconnected clients and cumulative losses, Wi-Fi off/on noise comparison, and serial commands during streaming. Investigate jitter and estimated losses before FFT/noise analysis; 8 ksps JSON transport is not guaranteed.
