// Serial diagnostics console at 115200 baud. Runs from the Arduino
// loop() task (core 1, default priority) which is fine: it never blocks
// the higher-priority acquisition task, and Serial.available()/read() are
// non-blocking so there is no delay() on the sampling path.

#include "console.h"

#include <Arduino.h>
#include <WiFi.h>

#include "acquisition.h"
#include "config.h"
#include "telemetry.h"

namespace console {
namespace {

String g_lineBuf;

bool isAllowedGain(uint32_t ohm) {
  return ohm == 10000u || ohm == 100000u || ohm == 1000000u;
}

void printHelp() {
  Serial.println(F(
      "Commands:\n"
      "  help              show this text\n"
      "  status            fs, timing jitter, dropped, heap, Wi-Fi, clients\n"
      "  rate <hz>         set sample rate, clamped to [1000,8000]\n"
      "  gain <ohm>        set gain_ohm metadata (10000|100000|1000000), must match jumper\n"
      "  avg <n>           diagnostic boxcar average length (1..64), display only\n"
      "  dcrm on|off       diagnostic DC-offset removal, display only\n"
      "  print [n]         print next n samples (default 20) to serial\n"
      "  wifi on|off       toggle Wi-Fi radio for noise A/B testing"));
}

void printStatus() {
  TimingStats ts = acquisition::getTimingStats();
  Serial.println(F("--- status ---"));
  Serial.printf("fs_hz (nominal)   : %lu\n", static_cast<unsigned long>(acquisition::getSampleRateHz()));
  Serial.printf("period mean/min/max (us): %.2f / %.2f / %.2f (n=%lu)\n", ts.meanPeriodUs,
                ts.minPeriodUs, ts.maxPeriodUs, static_cast<unsigned long>(ts.periodSamples));
  Serial.printf("dropped cumulative: %lu\n", static_cast<unsigned long>(acquisition::getDroppedCumulative()));
  Serial.printf("gain_ohm          : %lu\n", static_cast<unsigned long>(acquisition::getGainOhm()));
  Serial.printf("calibration       : %s\n", acquisition::getCalibrationProvenance());
  Serial.printf("free heap         : %lu bytes\n", static_cast<unsigned long>(ESP.getFreeHeap()));
  Serial.printf("wifi              : %s\n", telemetry::isWifiEnabled() ? "on" : "off");
  Serial.printf("wifi status       : %s\n", WiFi.status() == WL_CONNECTED ? "connected" : "disconnected");
  Serial.printf("ip                : %s\n", telemetry::getIp().toString().c_str());
  Serial.printf("rssi              : %ld dBm\n", static_cast<long>(telemetry::getRssiDbm()));
  Serial.printf("ws clients        : %lu\n", static_cast<unsigned long>(telemetry::getClientCount()));
  Serial.printf("diag avg N        : %u\n", acquisition::getDiagAveraging());
  Serial.printf("diag dcrm         : %s\n", acquisition::getDiagDcRemove() ? "on" : "off");
  Serial.printf("diag reading (mV) : %.2f\n", acquisition::getDiagReadingMv());
}

void handleLine(const String &lineIn) {
  String line = lineIn;
  line.trim();
  if (line.length() == 0) return;

  int sp = line.indexOf(' ');
  String cmd = (sp < 0) ? line : line.substring(0, sp);
  String arg = (sp < 0) ? String() : line.substring(sp + 1);
  cmd.toLowerCase();
  arg.trim();

  if (cmd == "help") {
    printHelp();
  } else if (cmd == "status") {
    printStatus();
  } else if (cmd == "rate") {
    long hz = arg.toInt();
    if (hz <= 0) {
      Serial.println(F("usage: rate <hz>  (1000..8000)"));
    } else {
      acquisition::setSampleRateHz(static_cast<uint32_t>(hz));
      Serial.printf("rate set to %lu Hz\n", static_cast<unsigned long>(acquisition::getSampleRateHz()));
    }
  } else if (cmd == "gain") {
    long ohm = arg.toInt();
    if (!isAllowedGain(static_cast<uint32_t>(ohm))) {
      Serial.println(F("usage: gain <10000|100000|1000000>  -- must match installed jumper"));
    } else {
      acquisition::setGainOhm(static_cast<uint32_t>(ohm));
      Serial.printf("gain_ohm set to %lu (verify jumper matches!)\n", static_cast<unsigned long>(ohm));
    }
  } else if (cmd == "avg") {
    long n = arg.toInt();
    if (n <= 0) {
      Serial.println(F("usage: avg <n>  (1..64)"));
    } else {
      acquisition::setDiagAveraging(static_cast<uint16_t>(n));
      Serial.printf("diagnostic avg N set to %u\n", acquisition::getDiagAveraging());
    }
  } else if (cmd == "dcrm") {
    if (arg == "on") {
      acquisition::setDiagDcRemove(true);
      Serial.println(F("diagnostic dcrm on"));
    } else if (arg == "off") {
      acquisition::setDiagDcRemove(false);
      Serial.println(F("diagnostic dcrm off"));
    } else {
      Serial.println(F("usage: dcrm on|off"));
    }
  } else if (cmd == "print") {
    long n = arg.length() ? arg.toInt() : 20;
    if (n <= 0) n = 20;
    telemetry::requestSerialPrint(static_cast<uint16_t>(n));
    Serial.printf("printing next %ld samples...\n", n);
  } else if (cmd == "wifi") {
    if (arg == "on") {
      telemetry::setWifiEnabled(true);
    } else if (arg == "off") {
      telemetry::setWifiEnabled(false);
    } else {
      Serial.println(F("usage: wifi on|off"));
    }
  } else {
    Serial.printf("unknown command '%s' (try 'help')\n", cmd.c_str());
  }
}

} // namespace

void begin() {
  g_lineBuf.reserve(64);
  Serial.println(F("Photodiode-TIA-ESP32 firmware ready. Type 'help' for commands."));
}

void poll() {
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());
    if (c == '\n' || c == '\r') {
      if (g_lineBuf.length() > 0) {
        handleLine(g_lineBuf);
        g_lineBuf = "";
      }
    } else if (g_lineBuf.length() < 96) {
      g_lineBuf += c;
    }
  }
}

} // namespace console
