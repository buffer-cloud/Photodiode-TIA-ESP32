#pragma once
#include <Arduino.h>
#include <IPAddress.h>

namespace telemetry {

// Connects Wi-Fi STA, starts the WebSocket server (port WEBSOCKET_PORT,
// path "/") and spawns the lower-priority streaming task that drains
// completed batches from acquisition:: and broadcasts them as JSON.
// Streaming runs on a separate task/core from acquisition so a slow or
// disconnected network never blocks sampling.
void begin();

// Wi-Fi on/off toggle for the Wi-Fi-noise A/B test (serial command
// `wifi on|off`). off fully disables the radio.
void setWifiEnabled(bool enabled);
bool isWifiEnabled();

size_t getClientCount();
int32_t getRssiDbm();
IPAddress getIp();

// Prints the next `n` streamed samples (raw, mv, dt_us) to Serial as they
// are batched, for `print` diagnostics. Does not alter what is streamed.
void requestSerialPrint(uint16_t n);

} // namespace telemetry
