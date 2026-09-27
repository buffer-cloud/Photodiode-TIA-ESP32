#pragma once
// Rev A firmware configuration.
// See docs/design-contract.md for the electrical/protocol contract this
// implements. Keep these values in sync with that document.

#include <stdint.h>
#include "hal/adc_types.h"

// ---------------------------------------------------------------------------
// ADC front end
// ---------------------------------------------------------------------------
// GPIO34 is ADC1 channel 6 on the original ESP32 (fixed silicon mapping;
// changing the pin means changing the channel too).
#define ADC_INPUT_GPIO       34
#define ADC_INPUT_UNIT       ADC_UNIT_1
#define ADC_INPUT_CHANNEL    ADC_CHANNEL_6
#define ADC_INPUT_ATTEN      ADC_ATTEN_DB_12   // contract "11 dB": same setting, renamed DB_12 in IDF 4.4.5+; ~0.15-2.45 V usable window
#define ADC_INPUT_BITWIDTH   ADC_WIDTH_BIT_12   // 12-bit, 0-4095 counts

// ---------------------------------------------------------------------------
// Acquisition timing
// ---------------------------------------------------------------------------
#define SAMPLE_RATE_HZ_DEFAULT   4000u
#define SAMPLE_RATE_HZ_MIN       1000u
#define SAMPLE_RATE_HZ_MAX       8000u

// ---------------------------------------------------------------------------
// Batching / ring buffer
// ---------------------------------------------------------------------------
#define BATCH_SIZE             256u   // samples per emitted packet (64 ms @ 4 ksps)
#define RING_BUFFER_SLOTS      10u    // >=8 batches required by contract; extra margin absorbs Wi-Fi jitter

// ---------------------------------------------------------------------------
// Gain metadata (manual; must match the installed JP_G10K/JP_G100K/JP_G1M jumper)
// ---------------------------------------------------------------------------
#define GAIN_OHM_DEFAULT   100000u
// Allowed set is enforced in code: {10000, 100000, 1000000}

// ---------------------------------------------------------------------------
// FreeRTOS task configuration
// ---------------------------------------------------------------------------
#define ACQUISITION_TASK_PRIORITY   (configMAX_PRIORITIES - 2)
#define ACQUISITION_TASK_CORE       1
#define ACQUISITION_TASK_STACK      4096

#define TELEMETRY_TASK_PRIORITY     2
#define TELEMETRY_TASK_CORE         0
#define TELEMETRY_TASK_STACK        6144

// ---------------------------------------------------------------------------
// Networking
// ---------------------------------------------------------------------------
#define WEBSOCKET_PORT       81
#define JSON_BUFFER_BYTES    8192   // sized for BATCH_SIZE=256 worst-case raw+mv+dt_us digits

// ---------------------------------------------------------------------------
// Serial console
// ---------------------------------------------------------------------------
#define SERIAL_BAUD   115200

// ---------------------------------------------------------------------------
// Diagnostics (never applied to the streamed raw/mv arrays)
// ---------------------------------------------------------------------------
#define DIAG_AVG_N_MAX   64
