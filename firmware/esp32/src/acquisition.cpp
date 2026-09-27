// Hardware timer ISR wakes the acquisition task; timestamps follow each ADC read.
#include "acquisition.h"

#include <atomic>
#include "driver/adc.h"
#include "esp_adc_cal.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

namespace acquisition {
namespace {

Batch g_pool[RING_BUFFER_SLOTS];
QueueHandle_t g_freeQ = nullptr;
QueueHandle_t g_filledQ = nullptr;
TaskHandle_t g_acqTaskHandle = nullptr;
hw_timer_t *g_timer = nullptr;

std::atomic<uint32_t> g_sampleRateHz = SAMPLE_RATE_HZ_DEFAULT;
std::atomic<uint32_t> g_gainOhm = GAIN_OHM_DEFAULT;
uint32_t g_appliedRateHz = SAMPLE_RATE_HZ_DEFAULT;

portMUX_TYPE g_statsMux = portMUX_INITIALIZER_UNLOCKED;
uint32_t g_droppedCumulative = 0;
double g_meanPeriodUs = 0.0;
double g_minPeriodUs = 1e9;
double g_maxPeriodUs = 0.0;
uint32_t g_periodSamples = 0;
int64_t g_lastSampleTimeUs = -1;

// Characterization is immutable after begin(), safe for both tasks.
esp_adc_cal_characteristics_t g_calibration;
const char *g_caliProvenance = "default_vref_1100mV";

// Diagnostics tap. Read/written only from the acquisition task except for
// the setters below, which the console task calls; values are simple
// scalars use atomics; the averaging buffer belongs exclusively to acquisition.
std::atomic<uint16_t> g_diagAvgN = 1;
std::atomic<bool> g_diagDcRemove = false;
float g_diagBuf[DIAG_AVG_N_MAX];
uint16_t g_diagBufIdx = 0;
uint16_t g_diagBufCount = 0;
float g_diagDcEstimate = 0.0f;
std::atomic<float> g_diagLastReading = 0.0f;
std::atomic<uint16_t> g_latestRaw = 0;

void configureTimerAlarm(uint32_t hz) {
  // 40 MHz timer ticks avoid microsecond rounding at arbitrary rates.
  timerAlarmWrite(g_timer, (40000000ULL + hz / 2) / hz, true);
}

void IRAM_ATTR onTimerAlarm() {
  BaseType_t highTaskAwoken = pdFALSE;
  vTaskNotifyGiveFromISR(g_acqTaskHandle, &highTaskAwoken);
  if (highTaskAwoken) portYIELD_FROM_ISR();
}

void recordLoss(uint32_t count) {
  portENTER_CRITICAL(&g_statsMux);
  // Saturate rather than silently wrap a cumulative counter.
  g_droppedCumulative += count > UINT32_MAX - g_droppedCumulative
      ? UINT32_MAX - g_droppedCumulative : count;
  portEXIT_CRITICAL(&g_statsMux);
}

void updateDiagnostics(uint16_t raw) {
  float mv = static_cast<float>(rawToMv(raw));

  uint16_t n = g_diagAvgN;
  if (n < 1) n = 1;
  if (n > DIAG_AVG_N_MAX) n = DIAG_AVG_N_MAX;

  static uint16_t previousN = 0;
  if (n != previousN) {
    g_diagBufCount = 0;
    g_diagBufIdx = 0;
    previousN = n;
  }
  g_diagBuf[g_diagBufIdx] = mv;
  g_diagBufIdx = static_cast<uint16_t>((g_diagBufIdx + 1) % n);
  if (g_diagBufCount < n) g_diagBufCount++;

  float sum = 0.0f;
  for (uint16_t i = 0; i < g_diagBufCount; i++) sum += g_diagBuf[i];
  float avg = sum / static_cast<float>(g_diagBufCount);

  if (g_diagDcRemove) {
    // Slow exponential moving average used only as a display baseline.
    g_diagDcEstimate += (avg - g_diagDcEstimate) * 0.01f;
    g_diagLastReading = avg - g_diagDcEstimate;
  } else {
    g_diagLastReading = avg;
  }
}

void acquisitionTaskFn(void * /*arg*/) {
  Batch *current = nullptr;
  xQueueReceive(g_freeQ, &current, portMAX_DELAY);
  current->count = 0;
  current->dropped = 0;
  bool haveT0 = false;
  int64_t lastAttemptUs = -1;

  for (;;) {
    // Only the acquisition owner changes the timer, at a batch boundary.
    if (current->count == 0 && g_sampleRateHz.load() != g_appliedRateHz) {
      timerStop(g_timer);
      timerAlarmDisable(g_timer);
      recordLoss(ulTaskNotifyTake(pdTRUE, 0));
      g_appliedRateHz = g_sampleRateHz.load();
      configureTimerAlarm(g_appliedRateHz);
      timerWrite(g_timer, 0);
      timerAlarmEnable(g_timer);
      timerStart(g_timer);
      lastAttemptUs = -1;
      portENTER_CRITICAL(&g_statsMux);
      g_meanPeriodUs = 0.0;
      g_minPeriodUs = 1e9;
      g_maxPeriodUs = 0.0;
      g_periodSamples = 0;
      g_lastSampleTimeUs = -1;
      portEXIT_CRITICAL(&g_statsMux);
    }
    uint32_t ticks = ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
    uint32_t missed = (ticks > 1) ? (ticks - 1) : 0;

    int rawVal = adc1_get_raw(ADC1_CHANNEL_6);
    int64_t now = esp_timer_get_time();
    // Notification counts are exact for serviced IRQs. A long measured
    // interval also exposes masked IRQs; count only the larger estimate
    // so the same stalled interval is not charged twice.
    if (lastAttemptUs >= 0) {
      uint64_t periodTicks = (40000000ULL + g_appliedRateHz / 2) / g_appliedRateHz;
      uint64_t periods = static_cast<uint64_t>(now - lastAttemptUs) * 40 / periodTicks;
      uint64_t gapMissed = periods > 1 ? periods - 1 : 0;
      if (gapMissed > missed) missed = gapMissed > UINT32_MAX ? UINT32_MAX : gapMissed;
    }
    recordLoss(missed);
    lastAttemptUs = now;
    if (rawVal < 0 || rawVal > 4095) {
      recordLoss(1);
      continue;
    }
    uint16_t raw16 = static_cast<uint16_t>(rawVal);
    g_latestRaw = raw16;

    portENTER_CRITICAL(&g_statsMux);
    if (g_lastSampleTimeUs >= 0) {
      double period = static_cast<double>(now - g_lastSampleTimeUs);
      if (g_periodSamples < UINT32_MAX) g_periodSamples++;
      g_meanPeriodUs += (period - g_meanPeriodUs) / static_cast<double>(g_periodSamples);
      if (period < g_minPeriodUs) g_minPeriodUs = period;
      if (period > g_maxPeriodUs) g_maxPeriodUs = period;
    }
    g_lastSampleTimeUs = now;
    portEXIT_CRITICAL(&g_statsMux);

    updateDiagnostics(raw16);

    if (haveT0 && static_cast<uint64_t>(now) - current->t0_us > UINT32_MAX) {
      recordLoss(current->count);
      current->count = 0;
      haveT0 = false;
    }
    if (!haveT0) {
      current->t0_us = static_cast<uint64_t>(now);
      current->fs_hz = g_appliedRateHz;
      current->gain_ohm = g_gainOhm.load();
      haveT0 = true;
    }


    uint16_t idx = current->count;
    current->raw[idx] = raw16;
    current->dt_us[idx] = static_cast<uint32_t>(now - static_cast<int64_t>(current->t0_us));
    current->count = static_cast<uint16_t>(idx + 1);

    if (current->count >= BATCH_SIZE) {

      portENTER_CRITICAL(&g_statsMux);
      current->dropped = g_droppedCumulative;
      portEXIT_CRITICAL(&g_statsMux);

      // Grab the next free slot before handing this one off so the
      // producer never has to block. If no free slot is available, the
      // telemetry/streaming consumer has fallen behind by the whole ring
      // buffer depth; drop this completed batch's samples entirely
      // (counted cumulatively) rather than block acquisition.
      Batch *next = nullptr;
      if (xQueueReceive(g_freeQ, &next, 0) == pdTRUE) {
        configASSERT(xQueueSend(g_filledQ, &current, 0) == pdTRUE);
        current = next;
      } else {
        recordLoss(current->count);
      }

      current->count = 0;
      current->dropped = 0;
      haveT0 = false;
    }
  }
}

} // namespace

void begin() {
  ESP_ERROR_CHECK(adc1_config_width(ADC_WIDTH_BIT_12));
  ESP_ERROR_CHECK(adc1_config_channel_atten(ADC1_CHANNEL_6, ADC_INPUT_ATTEN));
  esp_adc_cal_value_t source = esp_adc_cal_characterize(
      ADC_UNIT_1, ADC_INPUT_ATTEN, ADC_WIDTH_BIT_12, 1100, &g_calibration);
  if (source == ESP_ADC_CAL_VAL_EFUSE_TP) g_caliProvenance = "efuse_two_point";
  else if (source == ESP_ADC_CAL_VAL_EFUSE_VREF) g_caliProvenance = "efuse_vref";

  g_freeQ = xQueueCreate(RING_BUFFER_SLOTS, sizeof(Batch *));
  g_filledQ = xQueueCreate(RING_BUFFER_SLOTS, sizeof(Batch *));
  configASSERT(g_freeQ && g_filledQ);
  for (uint32_t i = 0; i < RING_BUFFER_SLOTS; i++) {
    Batch *p = &g_pool[i];
    xQueueSend(g_freeQ, &p, 0);
  }

  g_timer = timerBegin(0, 2, true);
  configASSERT(g_timer);
  timerStop(g_timer);
  timerAttachInterrupt(g_timer, &onTimerAlarm, false);
  configureTimerAlarm(g_sampleRateHz.load());
  BaseType_t created = xTaskCreatePinnedToCore(acquisitionTaskFn, "acq_task", ACQUISITION_TASK_STACK,
      nullptr, ACQUISITION_TASK_PRIORITY, &g_acqTaskHandle, ACQUISITION_TASK_CORE);
  configASSERT(created == pdPASS);
  timerWrite(g_timer, 0);
  timerAlarmEnable(g_timer);
  timerStart(g_timer);
}

void setSampleRateHz(uint32_t hz) {
  if (hz < SAMPLE_RATE_HZ_MIN) hz = SAMPLE_RATE_HZ_MIN;
  if (hz > SAMPLE_RATE_HZ_MAX) hz = SAMPLE_RATE_HZ_MAX;
  g_sampleRateHz = hz;
}

uint32_t getSampleRateHz() { return g_sampleRateHz; }

void setGainOhm(uint32_t ohm) { g_gainOhm = ohm; }
uint32_t getGainOhm() { return g_gainOhm; }

void recordTransportLoss(uint32_t count) { recordLoss(count); }

uint32_t getDroppedCumulative() {
  portENTER_CRITICAL(&g_statsMux);
  uint32_t v = g_droppedCumulative;
  portEXIT_CRITICAL(&g_statsMux);
  return v;
}

TimingStats getTimingStats() {
  TimingStats s;
  portENTER_CRITICAL(&g_statsMux);
  s.meanPeriodUs = g_meanPeriodUs;
  s.minPeriodUs = (g_periodSamples > 0) ? g_minPeriodUs : 0.0;
  s.maxPeriodUs = g_maxPeriodUs;
  s.periodSamples = g_periodSamples;
  portEXIT_CRITICAL(&g_statsMux);
  return s;
}

const char *getCalibrationProvenance() { return g_caliProvenance; }

uint32_t rawToMv(uint16_t raw) {
  return esp_adc_cal_raw_to_voltage(raw, &g_calibration);
}

bool takeFilledBatch(Batch **outBatch, uint32_t timeoutMs) {
  return xQueueReceive(g_filledQ, outBatch, pdMS_TO_TICKS(timeoutMs)) == pdTRUE;
}

void releaseBatch(Batch *b) {
  // The pool has exactly RING_BUFFER_SLOTS batches and every batch is
  // always owned by exactly one of {freeQ, filledQ, producer, consumer},
  // so there is always room and this never actually blocks.
  xQueueSend(g_freeQ, &b, portMAX_DELAY);
}

void setDiagAveraging(uint16_t n) {
  if (n < 1) n = 1;
  if (n > DIAG_AVG_N_MAX) n = DIAG_AVG_N_MAX;
  g_diagAvgN = n;
}

uint16_t getDiagAveraging() { return g_diagAvgN; }

void setDiagDcRemove(bool enabled) { g_diagDcRemove = enabled; }
bool getDiagDcRemove() { return g_diagDcRemove; }

float getDiagReadingMv() { return g_diagLastReading; }
uint16_t getLatestRaw() { return g_latestRaw; }

} // namespace acquisition
