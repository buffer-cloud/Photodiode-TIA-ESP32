// Photodiode-TIA-ESP32 Rev A firmware entry point.
// See README.md for build/flash instructions and the timing/protocol
// design rationale, and docs/design-contract.md for the electrical and
// wire-protocol contract this implements.

#include <Arduino.h>

#include "acquisition.h"
#include "config.h"
#include "console.h"
#include "telemetry.h"

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(100); // let the USB-serial bridge settle before the first prints

  acquisition::begin();
  telemetry::begin();
  console::begin();
}

void loop() {
  console::poll();
  // Nothing time-critical runs here: acquisition happens in its own
  // high-priority task driven by a hardware timer ISR, and streaming
  // happens in its own lower-priority task. This loop only services the
  // serial console, so a short yield is fine.
  delay(1);
}
