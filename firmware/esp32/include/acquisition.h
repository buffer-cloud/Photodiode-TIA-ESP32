#pragma once
#include <Arduino.h>
#include "config.h"

// One emitted telemetry batch worth of data. Only `raw` + `dt_us` are
// captured in real time by the acquisition ISR/task path; `mv` is computed
// on demand from the stored raw counts (acquisition::rawToMv) at
// serialization time, so it is never re-read from the pin.
struct Batch {
  uint16_t raw[BATCH_SIZE];
  uint32_t dt_us[BATCH_SIZE];
  uint16_t count;      // valid entries in raw/dt_us (== BATCH_SIZE when queued for send)
  uint32_t seq;
  uint64_t t0_us;
  uint32_t fs_hz;
  uint32_t gain_ohm;
  uint32_t dropped;    // cumulative dropped-sample count at the time this batch closed
};

struct TimingStats {
  double meanPeriodUs;
  double minPeriodUs;
  double maxPeriodUs;
  uint32_t periodSamples;
};

namespace acquisition {

// Sets up the ADC, eFuse calibration, ring buffer and the timer-driven
// acquisition task. Call once from setup().
void begin();

// Sample rate is clamped to [SAMPLE_RATE_HZ_MIN, SAMPLE_RATE_HZ_MAX] and
// requests a timer change at the next batch boundary. Safe from any task.
void setSampleRateHz(uint32_t hz);
uint32_t getSampleRateHz();

// gain_ohm is manual metadata only (no hardware effect); caller validates
// against the allowed set {10000, 100000, 1000000} before calling.
void setGainOhm(uint32_t ohm);
uint32_t getGainOhm();

uint32_t getDroppedCumulative();
void recordTransportLoss(uint32_t count);
TimingStats getTimingStats();

// eFuse calibration provenance: "efuse_two_point", "efuse_vref" or "default_vref_1100mV".
const char *getCalibrationProvenance();

// Converts a previously-captured raw ADC count to calibrated millivolts.
// Never re-reads the ADC pin.
uint32_t rawToMv(uint16_t raw);

// Ring buffer consumer API used by the telemetry task. takeFilledBatch()
// blocks up to timeoutMs waiting for a completed batch; releaseBatch()
// must be called after the caller is done reading it to return the slot
// to the free pool.
bool takeFilledBatch(Batch **outBatch, uint32_t timeoutMs);
void releaseBatch(Batch *b);

// --- Diagnostics tap (console-controlled, serial-only; never touches the
//     streamed raw/mv arrays above) -----------------------------------
void setDiagAveraging(uint16_t n);
uint16_t getDiagAveraging();
void setDiagDcRemove(bool enabled);
bool getDiagDcRemove();
float getDiagReadingMv();
uint16_t getLatestRaw();

} // namespace acquisition
