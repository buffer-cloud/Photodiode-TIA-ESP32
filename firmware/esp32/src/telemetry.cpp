// WebSocket streaming of acquisition batches as telemetry-v1 JSON.
//
// Runs as its own low-priority FreeRTOS task (see config.h) on the core
// that also hosts the Wi-Fi/lwIP stack, deliberately separate from the
// high-priority acquisition task on the other core. If Wi-Fi/streaming
// stalls, the acquisition task simply keeps filling ring buffer slots
// (see acquisition.cpp) until it must start dropping samples -- it never
// waits on the network.

#include "telemetry.h"

#include <atomic>
#include <stdarg.h>
#include <WiFi.h>
#include <WebSocketsServer.h>

#include "acquisition.h"
#include "config.h"
#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"
#endif

namespace telemetry {
namespace {

WebSocketsServer g_webSocket(WEBSOCKET_PORT);
TaskHandle_t g_telemetryTaskHandle = nullptr;
std::atomic<bool> g_wifiEnabled{true};
std::atomic<size_t> g_clientCount{0};
std::atomic<uint16_t> g_serialPrintRemaining{0};
uint32_t g_sequence = 0;
char g_jsonBuf[JSON_BUFFER_BYTES];

void onWsEvent(uint8_t num, WStype_t type, uint8_t *payload, size_t length) {
  if (type == WStype_CONNECTED && (length != 1 || payload[0] != '/')) {
    g_webSocket.disconnect(num);
  }
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("[wifi] connecting to '%s'", WIFI_SSID);
  uint32_t startMs = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - startMs) < 15000) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[wifi] connected, ip=%s rssi=%ld dBm\n", WiFi.localIP().toString().c_str(),
                   (long)WiFi.RSSI());
  } else {
    Serial.println("[wifi] connect timed out; will keep retrying in background");
  }
}

// Serializes one batch into g_jsonBuf and returns the number of bytes
// written (excluding the terminating NUL). mv[] is computed here from the
// stored raw counts via acquisition::rawToMv -- the ADC pin itself is
// never re-read.
size_t serializeBatch(const Batch &b) {
  size_t pos = 0;
  bool ok = true;
  auto append = [&](const char *format, ...) {
    if (!ok) return;
    va_list args;
    va_start(args, format);
    int n = vsnprintf(g_jsonBuf + pos, sizeof(g_jsonBuf) - pos, format, args);
    va_end(args);
    if (n < 0 || static_cast<size_t>(n) >= sizeof(g_jsonBuf) - pos) ok = false;
    else pos += static_cast<size_t>(n);
  };

  append(
                   "{\"v\":1,\"seq\":%lu,\"t0_us\":%llu,\"fs_hz\":%lu,\"gain_ohm\":%lu,"
                   "\"dropped\":%lu,\"raw\":[",
                   static_cast<unsigned long>(b.seq), static_cast<unsigned long long>(b.t0_us),
                   static_cast<unsigned long>(b.fs_hz), static_cast<unsigned long>(b.gain_ohm),
                   static_cast<unsigned long>(b.dropped));

  for (uint16_t i = 0; i < b.count; i++) {
    append( "%s%u", i ? "," : "", b.raw[i]);
  }
  append( "],\"mv\":[");
  for (uint16_t i = 0; i < b.count; i++) {
    uint32_t mv = acquisition::rawToMv(b.raw[i]);
    append( "%s%lu", i ? "," : "",
                     static_cast<unsigned long>(mv));
  }
  append( "],\"dt_us\":[");
  for (uint16_t i = 0; i < b.count; i++) {
    append( "%s%lu", i ? "," : "",
                     static_cast<unsigned long>(b.dt_us[i]));
  }
  append( "],\"calibration\":\"%s\"}",
                   acquisition::getCalibrationProvenance());
  return ok ? pos : 0;
}

void maybePrintSamples(const Batch &b) {
  uint16_t remainingPrint = g_serialPrintRemaining.exchange(0);
  if (remainingPrint == 0) return;
  uint16_t n = remainingPrint < b.count ? remainingPrint : b.count;
  for (uint16_t i = 0; i < n; i++) {
    uint32_t mv = acquisition::rawToMv(b.raw[i]);
    Serial.printf("raw=%u mv=%lu dt_us=%lu\n", b.raw[i], static_cast<unsigned long>(mv),
                  static_cast<unsigned long>(b.dt_us[i]));
  }
  if (remainingPrint > n) g_serialPrintRemaining.fetch_add(remainingPrint - n);
}

void telemetryTaskFn(void * /*arg*/) {
  bool appliedWifi = true;
  for (;;) {
    bool requestedWifi = g_wifiEnabled.load();
    if (requestedWifi != appliedWifi) {
      appliedWifi = requestedWifi;
      if (appliedWifi) {
        connectWifi();
        g_webSocket.begin();
      } else {
        g_webSocket.close();
        WiFi.disconnect(true);
        WiFi.mode(WIFI_OFF);
        Serial.println("[wifi] radio off (A/B noise test mode)");
      }
    }
    if (appliedWifi) g_webSocket.loop();
    g_clientCount = appliedWifi ? g_webSocket.connectedClients() : 0;

    Batch *b = nullptr;
    if (acquisition::takeFilledBatch(&b, 5)) {
      b->seq = g_sequence;
      b->dropped = acquisition::getDroppedCumulative();
      size_t len = serializeBatch(*b);
      if (len && appliedWifi && WiFi.status() == WL_CONNECTED && g_clientCount.load()) {
        // A broadcast attempt is an emitted sequence; TCP receipt is not guaranteed.
        ++g_sequence;
        if (!g_webSocket.broadcastTXT(reinterpret_cast<uint8_t *>(g_jsonBuf), len))
          acquisition::recordTransportLoss(b->count);
      } else {
        acquisition::recordTransportLoss(b->count);
      }
      maybePrintSamples(*b);
      acquisition::releaseBatch(b);
    }
  }
}

} // namespace

void begin() {
  connectWifi();
  g_webSocket.begin();
  g_webSocket.onEvent(onWsEvent);

  BaseType_t created = xTaskCreatePinnedToCore(telemetryTaskFn, "telemetry_task", TELEMETRY_TASK_STACK, nullptr,
                           TELEMETRY_TASK_PRIORITY, &g_telemetryTaskHandle, TELEMETRY_TASK_CORE);
  configASSERT(created == pdPASS);
}

void setWifiEnabled(bool enabled) { g_wifiEnabled = enabled; }

bool isWifiEnabled() { return g_wifiEnabled; }

size_t getClientCount() { return g_clientCount.load(); }

int32_t getRssiDbm() { return WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0; }

IPAddress getIp() { return WiFi.localIP(); }

void requestSerialPrint(uint16_t n) { g_serialPrintRemaining = n; }

} // namespace telemetry
