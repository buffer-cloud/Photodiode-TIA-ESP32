# Photon Flutter dashboard

Responsive Flutter web dashboard for the ESP32 photodiode/TIA telemetry-v1 WebSocket stream. It shows a live ADC waveform, latest raw count, calibrated pin millivolts, batch range/mean, sample rate, packet gaps, and dropped samples. A browser-only demo mode is explicitly marked **simulated**.

## Run with the ESP32 Dev Module

1. Build and upload `firmware/esp32` for the ESP32 Dev Module. Copy `firmware/esp32/include/secrets.example.h` to `secrets.h` and set the 2.4 GHz Wi-Fi credentials. `secrets.h` is ignored by Git.
2. Open the ESP32 serial monitor at 115200 baud and type `status` to find its IP address. Connect your computer to the same local network.
3. From this directory, run:

   ```bash
   ./run_dashboard.sh YOUR_ESP32_IP
   ```

   Open `http://localhost:57843/` in Chrome. The helper builds the Flutter web app and serves it locally. The dashboard connects automatically when an IP is supplied. You can omit the IP, enter it in the page, and click **Connect**. For Flutter development with hot reload, use `flutter run -d chrome --dart-define=ESP32_HOST=YOUR_ESP32_IP`.
4. The app retries a lost WebSocket connection automatically and marks stale data when no batches arrive. **Stop** cancels retries. **Try demo** intentionally switches to simulated values.

The firmware defaults to 4 kS/s. On the tested local Wi-Fi, the serial command `rate 1000` reduced transport drops while retaining a live waveform. Stream health counters make any missing data visible. The device rate returns to its configured default after a reset.

## Measurement status

GPIO34 is currently unconnected because the photodiode/TIA PCB is not assembled. Live values from the bare ESP32 are floating ADC diagnostics and must **not** be presented as photodiode measurements. The `mv` field is the ESP32 pin calibration result. Optical current, gain accuracy, sensitivity, and noise require the analog board and bench validation.
