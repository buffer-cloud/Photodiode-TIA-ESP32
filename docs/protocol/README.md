# Telemetry v1

The shared [design contract](../design-contract.md) defines electrical and acquisition interfaces. [JSON schema](telemetry-v1.schema.json) documents wire types; equal array lengths and timestamp ordering also require application validation.

The server sends a batch of up to 256 samples. `raw[i]` and `mv[i]` refer to the same ADC conversion at boot time `t0_us + dt_us[i]`. The first offset is zero. `mv` is ADC-pin voltage, with calibration provenance reported separately; it is not the light intensity or an ideal 3.3 V / 4095 conversion. `gain_ohm` is manually configured metadata and must match the installed jumper.

`fs_hz` is nominal cadence. Consumers inspect actual timestamps, sequence gaps and `dropped` before FFT/noise analysis. A boot-time regression starts a new device epoch. Never join two boot epochs into a single uniformly sampled record. Packet sequence numbers are transport diagnostics, not sample timestamps.

JSON is inspectable during bring-up. Batch transport amortizes framing but does not guarantee 8 ksps over Wi-Fi. A future binary packet can store a fixed header and packed uint16 ADC counts with per-sample timing; adopt it only after measuring serialization/transport limits. The initial implementation uses a trusted local network: plain WebSocket provides neither authentication nor encryption.
