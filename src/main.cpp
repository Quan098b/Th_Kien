#include <Arduino.h>
#include <VuDieuAnhSang_inferencing.h>
#include <driver/i2s.h>
#include <esp_heap_caps.h>
#include <math.h>
#include <edge-impulse-sdk/dsp/numpy.hpp>
#include <Network.h>  // Arduino core 3.x: lets the library finder pick up WiFi's dependency
#include <FS.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <WiFi.h>
#include "web_page.h"
#include "wifi_secrets.h"

#define DEBUG_VERBOSE 0

namespace {
constexpr i2s_port_t kI2sPort = I2S_NUM_0;
constexpr int kBclkPin = 4;
constexpr int kWsPin = 5;
constexpr int kDataPin = 6;
constexpr int kLedPin = 7;  // active high: GPIO7 -> 220-330 ohm -> LED -> GND
constexpr size_t kReadSamples = 512;
constexpr int16_t kClipLevel = 32760;
int16_t *g_audio = nullptr;
int32_t g_i2s_raw[kReadSamples];
bool g_i2s_ready = false;

struct AudioStats { float rms; int16_t minimum; int16_t maximum; uint32_t clipped; };
struct VoiceGateStats {
    float active_ratio;
    float spectral_flatness;
    float low_ratio;
    float zcr;
    bool pass;
};

constexpr float kGateMinRms = 20.0f;
constexpr float kGateMinActiveRatio = 0.02f;
constexpr float kGateMaxFlatness = 0.15f;
constexpr float kGateMaxLowRatio = 0.80f;
constexpr float kGateMinZcr = 0.01f;

AudioStats calculate_stats(const int16_t *samples, size_t count) {
    AudioStats stats = {0.0f, INT16_MAX, INT16_MIN, 0};
    double sum = 0.0, sum_squares = 0.0;
    for (size_t i = 0; i < count; ++i) {
        const int16_t pcm = samples[i];
        sum += pcm; sum_squares += static_cast<double>(pcm) * pcm;
        if (pcm < stats.minimum) stats.minimum = pcm;
        if (pcm > stats.maximum) stats.maximum = pcm;
        if (pcm >= kClipLevel || pcm <= -kClipLevel) ++stats.clipped;
    }
    const double mean = sum / count;
    double variance = sum_squares / count - mean * mean;
    if (variance < 0.0) variance = 0.0;
    stats.rms = static_cast<float>(sqrt(variance));
    return stats;
}

VoiceGateStats calculate_voice_gate(const int16_t *samples, size_t count,
                                    const AudioStats &audio) {
    constexpr size_t kEnergyFrame = 320;
    constexpr size_t kFftSize = 256;
    constexpr size_t kHop = 160;
    constexpr size_t kBins = kFftSize / 2 + 1;
    constexpr size_t kMaxFrames = (EI_CLASSIFIER_RAW_SAMPLE_COUNT - kEnergyFrame) / kHop + 1;
    float frame_rms[kMaxFrames];
    float sorted_rms[kMaxFrames];
    size_t energy_frames = 0;
    for (size_t start = 0; start + kEnergyFrame <= count; start += kHop) {
        double sum = 0.0, sum_sq = 0.0;
        for (size_t i = 0; i < kEnergyFrame; ++i) {
            const double v = samples[start + i]; sum += v; sum_sq += v * v;
        }
        const double mean = sum / kEnergyFrame;
        frame_rms[energy_frames++] = sqrt(max(0.0, sum_sq / kEnergyFrame - mean * mean));
    }
    memcpy(sorted_rms, frame_rms, energy_frames * sizeof(float));
    for (size_t i = 1; i < energy_frames; ++i) {
        const float value = sorted_rms[i]; size_t j = i;
        while (j && sorted_rms[j - 1] > value) { sorted_rms[j] = sorted_rms[j - 1]; --j; }
        sorted_rms[j] = value;
    }
    const float floor = sorted_rms[static_cast<size_t>(0.10f * (energy_frames - 1))];
    const float active_threshold = max(35.0f, floor * 3.0f);
    size_t active = 0;
    for (size_t i = 0; i < energy_frames; ++i) if (frame_rms[i] > active_threshold) ++active;

    float average_spectrum[kBins] = {};
    float frame[kFftSize], spectrum[kBins];
    size_t spectral_frames = 0;
    for (size_t start = 0; start + kFftSize <= count; start += kHop) {
        for (size_t i = 0; i < kFftSize; ++i) {
            const float window = 0.5f - 0.5f * cosf(2.0f * PI * i / (kFftSize - 1));
            frame[i] = static_cast<float>(samples[start + i]) * window;
        }
        if (ei::numpy::power_spectrum(frame, kFftSize, spectrum, kBins, kFftSize) != EIDSP_OK) {
            return {0.0f, 1.0f, 1.0f, 0.0f, false};
        }
        for (size_t i = 0; i < kBins; ++i) average_spectrum[i] += spectrum[i];
        ++spectral_frames;
    }
    for (float &value : average_spectrum) value /= spectral_frames;
    double total = 0.0, low = 0.0, log_sum = 0.0, arithmetic_sum = 0.0;
    size_t flat_bins = 0;
    for (size_t bin = 2; bin <= 121; ++bin) { // 125 Hz through 7562.5 Hz
        const double power = average_spectrum[bin] + 1e-12;
        total += power; arithmetic_sum += power; log_sum += log(power); ++flat_bins;
        if (bin < 4) low += power; // below 250 Hz
    }
    const float flatness = exp(log_sum / flat_bins) / (arithmetic_sum / flat_bins);
    size_t crossings = 0;
    for (size_t i = 1; i < count; ++i) if ((samples[i] < 0) != (samples[i - 1] < 0)) ++crossings;
    VoiceGateStats stats = {
        static_cast<float>(active) / energy_frames,
        flatness,
        total > 0.0 ? static_cast<float>(low / total) : 1.0f,
        static_cast<float>(crossings) / (count - 1),
        false
    };
    stats.pass = audio.rms >= kGateMinRms && stats.active_ratio >= kGateMinActiveRatio &&
                 stats.spectral_flatness <= kGateMaxFlatness &&
                 stats.low_ratio <= kGateMaxLowRatio && stats.zcr >= kGateMinZcr;
    return stats;
}

bool init_i2s() {
    i2s_config_t config = {};
    config.mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_RX);
    config.sample_rate = EI_CLASSIFIER_FREQUENCY;
    config.bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT;
    config.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
    config.communication_format = I2S_COMM_FORMAT_STAND_I2S;
    config.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
    config.dma_buf_count = 8;
    config.dma_buf_len = 256;
    config.use_apll = false;
    config.tx_desc_auto_clear = false;
    config.fixed_mclk = 0;
    i2s_pin_config_t pins = {};
    pins.bck_io_num = kBclkPin;
    pins.ws_io_num = kWsPin;
    pins.data_out_num = I2S_PIN_NO_CHANGE;
    pins.data_in_num = kDataPin;
    esp_err_t err = i2s_driver_install(kI2sPort, &config, 0, nullptr);
    if (err != ESP_OK) { Serial.printf("I2S_INIT_ERROR install=%d\n", static_cast<int>(err)); return false; }
    err = i2s_set_pin(kI2sPort, &pins);
    if (err != ESP_OK) {
        Serial.printf("I2S_INIT_ERROR pins=%d\n", static_cast<int>(err));
        i2s_driver_uninstall(kI2sPort);
        return false;
    }
    i2s_zero_dma_buffer(kI2sPort);
#if DEBUG_VERBOSE
    Serial.printf("I2S_OK rate=%d bclk=%d ws=%d data=%d format=32bit-left shift=16 gain=1\n",
                  EI_CLASSIFIER_FREQUENCY, kBclkPin, kWsPin, kDataPin);
#endif
    return true;
}

bool capture_window(AudioStats &stats) {
    size_t captured = 0;
    double sum = 0.0, sum_squares = 0.0;
    stats.minimum = INT16_MAX; stats.maximum = INT16_MIN; stats.clipped = 0;
    while (captured < EI_CLASSIFIER_RAW_SAMPLE_COUNT) {
        const size_t wanted = min(kReadSamples, EI_CLASSIFIER_RAW_SAMPLE_COUNT - captured);
        size_t bytes_read = 0;
        const esp_err_t err = i2s_read(kI2sPort, g_i2s_raw, wanted * sizeof(int32_t),
                                       &bytes_read, pdMS_TO_TICKS(1000));
        if (err != ESP_OK || bytes_read == 0) {
            Serial.printf("I2S_READ_ERROR code=%d bytes=%u captured=%u\n", static_cast<int>(err),
                          static_cast<unsigned>(bytes_read), static_cast<unsigned>(captured));
            return false;
        }
        const size_t count = bytes_read / sizeof(int32_t);
        for (size_t i = 0; i < count && captured < EI_CLASSIFIER_RAW_SAMPLE_COUNT; ++i) {
            // Match the original WAV firmware: 24-bit left-justified I2S to PCM16, unity gain.
            const int16_t pcm = static_cast<int16_t>(g_i2s_raw[i] >> 16);
            g_audio[captured++] = pcm;
            sum += pcm; sum_squares += static_cast<double>(pcm) * pcm;
            if (pcm < stats.minimum) stats.minimum = pcm;
            if (pcm > stats.maximum) stats.maximum = pcm;
            if (pcm >= kClipLevel || pcm <= -kClipLevel) ++stats.clipped;
        }
    }
    const double mean = sum / EI_CLASSIFIER_RAW_SAMPLE_COUNT;
    double variance = sum_squares / EI_CLASSIFIER_RAW_SAMPLE_COUNT - mean * mean;
    if (variance < 0.0) variance = 0.0;
    stats.rms = static_cast<float>(sqrt(variance));
    return true;
}

int signal_get_data(size_t offset, size_t length, float *out_ptr) {
    if (!g_audio || offset + length > EI_CLASSIFIER_RAW_SAMPLE_COUNT) return -1;
    for (size_t i = 0; i < length; ++i) out_ptr[i] = static_cast<float>(g_audio[offset + i]);
    return 0;
}

uint32_t crc32(const uint8_t *data, size_t length) {
    uint32_t crc = 0xffffffffU;
    for (size_t i = 0; i < length; ++i) {
        crc ^= data[i];
        for (uint8_t bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (0xedb88320U & (0U - (crc & 1U)));
    }
    return ~crc;
}

size_t g_last_serial_read = 0;

bool read_exact(uint8_t *destination, size_t length, uint32_t timeout_ms) {
    const uint32_t started = millis();
    size_t received = 0;
    while (received < length && millis() - started < timeout_ms) {
        const int available = Serial.available();
        if (available > 0) {
            const size_t chunk = min(static_cast<size_t>(available), length - received);
            received += Serial.readBytes(destination + received, chunk);
        }
        else delay(1);
    }
    g_last_serial_read = received;
    return received == length;
}

// ---- Web dashboard: inference (core 1) publishes, web task (core 0) reads ----
enum class Decision : uint8_t { BatDen, TatDen, Noise, Silence };
const char *decision_name(Decision d) {
    switch (d) {
        case Decision::BatDen: return "BAT_DEN";
        case Decision::TatDen: return "TAT_DEN";
        case Decision::Silence: return "SILENCE";
        default: return "NOISE";
    }
}

struct HistoryEntry { uint32_t ms; Decision decision; uint8_t label; float confidence; int rms; };
constexpr size_t kHistorySize = 20;
struct WebState {
    uint32_t seq;
    uint32_t ms;
    const char *source;
    Decision decision;
    uint8_t best;
    float probs[EI_CLASSIFIER_LABEL_COUNT];
    float rms;
    VoiceGateStats gate;
    int dsp_ms, nn_ms;
    bool lamp_on;
    uint32_t counts[4];
    HistoryEntry history[kHistorySize];
    size_t history_count, history_head;
};
WebState g_web = {};
portMUX_TYPE g_web_mux = portMUX_INITIALIZER_UNLOCKED;
WebServer g_server(80);
bool g_ip_announced = false;

void publish_result(const char *source, const AudioStats &stats, const VoiceGateStats &gate,
                    const ei_impulse_result_t &result, size_t best, Decision decision) {
    const uint32_t now = millis();
    portENTER_CRITICAL(&g_web_mux);
    ++g_web.seq;
    g_web.ms = now;
    g_web.source = source;
    g_web.decision = decision;
    g_web.best = static_cast<uint8_t>(best);
    for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; ++i) g_web.probs[i] = result.classification[i].value;
    g_web.rms = stats.rms;
    g_web.gate = gate;
    g_web.dsp_ms = result.timing.dsp;
    g_web.nn_ms = result.timing.classification;
    if (decision == Decision::BatDen) g_web.lamp_on = true;
    if (decision == Decision::TatDen) g_web.lamp_on = false;
    ++g_web.counts[static_cast<size_t>(decision)];
    g_web.history[g_web.history_head] = {now, decision, static_cast<uint8_t>(best),
                                         result.classification[best].value,
                                         static_cast<int>(lroundf(stats.rms))};
    g_web.history_head = (g_web.history_head + 1) % kHistorySize;
    if (g_web.history_count < kHistorySize) ++g_web.history_count;
    portEXIT_CRITICAL(&g_web_mux);
}

void handle_state() {
    static WebState s;
    static char json[4096];
    portENTER_CRITICAL(&g_web_mux);
    s = g_web;
    portEXIT_CRITICAL(&g_web_mux);
    const char *const *labels = ei_classifier_inferencing_categories;
    const bool accept = s.seq && (s.decision == Decision::BatDen || s.decision == Decision::TatDen);
    size_t n = snprintf(json, sizeof json,
        "{\"seq\":%u,\"uptime\":%u,\"ip\":\"%s\",\"source\":\"%s\",\"kind\":\"%s\",\"accept\":%s,"
        "\"label\":\"%s\",\"conf\":%.4f,\"labels\":[",
        s.seq, millis(), WiFi.localIP().toString().c_str(), s.source ? s.source : "-",
        decision_name(s.decision), accept ? "true" : "false", labels[s.best], s.probs[s.best]);
    for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; ++i)
        n += snprintf(json + n, sizeof json - n, "%s\"%s\"", i ? "," : "", labels[i]);
    n += snprintf(json + n, sizeof json - n, "],\"probs\":[");
    for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; ++i)
        n += snprintf(json + n, sizeof json - n, "%s%.4f", i ? "," : "", s.probs[i]);
    n += snprintf(json + n, sizeof json - n,
        "],\"rms\":%.1f,\"gate\":{\"active\":%.4f,\"flat\":%.4f,\"low\":%.4f,\"zcr\":%.4f,\"pass\":%s},"
        "\"th\":{\"rms\":%.0f,\"active\":%.2f,\"flat\":%.2f,\"low\":%.2f,\"zcr\":%.2f},"
        "\"dsp_ms\":%d,\"nn_ms\":%d,\"lamp\":%s,\"counts\":[%u,%u,%u,%u],\"history\":[",
        s.rms, s.gate.active_ratio, s.gate.spectral_flatness, s.gate.low_ratio, s.gate.zcr,
        s.gate.pass ? "true" : "false", kGateMinRms, kGateMinActiveRatio, kGateMaxFlatness,
        kGateMaxLowRatio, kGateMinZcr, s.dsp_ms, s.nn_ms, s.lamp_on ? "true" : "false",
        s.counts[0], s.counts[1], s.counts[2], s.counts[3]);
    for (size_t k = 0; k < s.history_count; ++k) {  // newest first
        const HistoryEntry &h = s.history[(s.history_head + kHistorySize - 1 - k) % kHistorySize];
        n += snprintf(json + n, sizeof json - n, "%s{\"ms\":%u,\"k\":\"%s\",\"l\":\"%s\",\"c\":%.3f,\"r\":%d}",
                      k ? "," : "", h.ms, decision_name(h.decision), labels[h.label], h.confidence, h.rms);
    }
    snprintf(json + n, sizeof json - n, "]}");
    g_server.sendHeader("Cache-Control", "no-store");
    g_server.send(200, "application/json", json);
}

void web_task(void *) {
    g_server.on("/", [] { g_server.send_P(200, "text/html; charset=utf-8", kWebPage); });
    g_server.on("/api/state", handle_state);
    g_server.onNotFound([] { g_server.send(404, "text/plain", "not found"); });
    bool mdns_started = false;
    bool server_started = false;
    for (;;) {
        if (WiFi.status() == WL_CONNECTED) {
            if (!server_started) { g_server.begin(); server_started = true; }
            if (!mdns_started) mdns_started = MDNS.begin(WEB_HOSTNAME);
            g_server.handleClient();
        }
        vTaskDelay(pdMS_TO_TICKS(2));
    }
}

void start_web() {
    WiFi.mode(WIFI_STA);
    WiFi.setHostname(WEB_HOSTNAME);
    WiFi.setAutoReconnect(true);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    xTaskCreatePinnedToCore(web_task, "web", 8192, nullptr, 1, nullptr, 0);
}

// Printed from loop() only, so it never lands inside a WAV or EIP1 transfer.
void announce_web() {
    if (g_ip_announced || WiFi.status() != WL_CONNECTED) return;
    g_ip_announced = true;
    Serial.printf("WEB | http://%s | http://%s.local\n", WiFi.localIP().toString().c_str(), WEB_HOSTNAME);
}

void classify_and_print(const char *source, const AudioStats &stats) {
#if DEBUG_VERBOSE
    Serial.printf("AUDIO source=%s rms=%.2f pcm_min=%d pcm_max=%d clipped=%u/%d\n", source,
                  stats.rms, stats.minimum, stats.maximum, stats.clipped,
                  EI_CLASSIFIER_RAW_SAMPLE_COUNT);
#endif
    const VoiceGateStats gate = calculate_voice_gate(g_audio, EI_CLASSIFIER_RAW_SAMPLE_COUNT, stats);
#if DEBUG_VERBOSE
    Serial.printf("FILTER source=%s pass=%s active_ratio=%.6f flatness=%.6f low_ratio=%.6f zcr=%.6f "
                  "thresholds=rms>=%.1f,active>=%.2f,flat<=%.2f,low<=%.2f,zcr>=%.2f\n",
                  source, gate.pass ? "yes" : "no", gate.active_ratio, gate.spectral_flatness,
                  gate.low_ratio, gate.zcr, kGateMinRms, kGateMinActiveRatio, kGateMaxFlatness,
                  kGateMaxLowRatio, kGateMinZcr);
#endif
    signal_t signal = {};
    signal.total_length = EI_CLASSIFIER_RAW_SAMPLE_COUNT;
    signal.get_data = signal_get_data;
    ei_impulse_result_t result = {};
    const EI_IMPULSE_ERROR error = run_classifier(&signal, &result, false);
    if (error != EI_IMPULSE_OK) {
        Serial.printf("INFERENCE_ERROR source=%s code=%d\n", source, static_cast<int>(error));
        return;
    }
    size_t best = 0, second = 0;
    for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; ++i) {
#if DEBUG_VERBOSE
        Serial.printf("PROB source=%s %s=%.6f\n", source, result.classification[i].label,
                      result.classification[i].value);
#endif
        if (result.classification[i].value > result.classification[best].value) {
            second = best; best = i;
        } else if (i != best && (second == best ||
                   result.classification[i].value > result.classification[second].value)) second = i;
    }
    const float margin = result.classification[best].value - result.classification[second].value;
    const char *model_label = result.classification[best].label;
    const bool is_bat = strcmp(model_label, "Bat_Den") == 0;
    const bool is_tat = strcmp(model_label, "Tat_Den") == 0;
    Decision decision = Decision::Noise;
    if (!gate.pass && stats.rms < kGateMinRms) decision = Decision::Silence;
    else if (gate.pass && is_bat) decision = Decision::BatDen;
    else if (gate.pass && is_tat) decision = Decision::TatDen;
    if (decision == Decision::BatDen) digitalWrite(kLedPin, HIGH);
    if (decision == Decision::TatDen) digitalWrite(kLedPin, LOW);
    publish_result(source, stats, gate, result, best, decision);
#if DEBUG_VERBOSE
    Serial.printf("RESULT source=%s best=%s probability=%.6f second=%s margin=%.6f "
                  "dsp_ms=%u inference_ms=%u anomaly_ms=%u\n", source,
                  result.classification[best].label, result.classification[best].value,
                  result.classification[second].label, margin, result.timing.dsp,
                  result.timing.classification, result.timing.anomaly);
    Serial.printf("DECISION source=%s final=%s model=%s reason=%s\n", source,
                  gate.pass && (strcmp(result.classification[best].label, "Bat_Den") == 0 ||
                                strcmp(result.classification[best].label, "Tat_Den") == 0)
                      ? result.classification[best].label : "REJECT",
                  result.classification[best].label,
                  gate.pass ? "voice_gate_pass" : "voice_gate_reject");
#else
    (void)margin;
    const int rms_rounded = static_cast<int>(lroundf(stats.rms));
    if (decision == Decision::Silence) {
        Serial.printf("SILENCE | RMS:%d | REJECT\n", rms_rounded);
    }
    else if (decision == Decision::BatDen || decision == Decision::TatDen) {
        Serial.printf("%-7s | %.1f%% | RMS:%d | ACCEPT\n",
                      is_bat ? "BAT DEN" : "TAT DEN",
                      result.classification[best].value * 100.0f, rms_rounded);
    }
    else {
        Serial.printf("NOISE   | %.1f%% | RMS:%d | REJECT\n",
                      result.classification[best].value * 100.0f, rms_rounded);
    }
#endif
}

void receive_serial_test() {
    constexpr size_t payload_bytes = EI_CLASSIFIER_RAW_SAMPLE_COUNT * sizeof(int16_t);
    uint8_t header[12];
    Serial.printf("TEST_READY protocol=EIP1 samples=%d bytes=%u\n",
                  EI_CLASSIFIER_RAW_SAMPLE_COUNT, static_cast<unsigned>(payload_bytes));
    if (!read_exact(header, sizeof(header), 5000)) {
        Serial.println("TEST_ERROR header_timeout"); return;
    }
    const uint32_t sample_count = uint32_t(header[4]) | (uint32_t(header[5]) << 8) |
        (uint32_t(header[6]) << 16) | (uint32_t(header[7]) << 24);
    const uint32_t expected_crc = uint32_t(header[8]) | (uint32_t(header[9]) << 8) |
        (uint32_t(header[10]) << 16) | (uint32_t(header[11]) << 24);
    if (memcmp(header, "EIP1", 4) != 0 || sample_count != EI_CLASSIFIER_RAW_SAMPLE_COUNT) {
        Serial.printf("TEST_ERROR invalid_header magic=%02x%02x%02x%02x samples=%u\n",
                      header[0], header[1], header[2], header[3], sample_count); return;
    }
    Serial.println("TEST_HEADER_READY");
    if (!read_exact(reinterpret_cast<uint8_t *>(g_audio), payload_bytes, 30000)) {
        Serial.printf("TEST_ERROR payload_timeout received=%u expected=%u\n",
                      static_cast<unsigned>(g_last_serial_read),
                      static_cast<unsigned>(payload_bytes)); return;
    }
    const uint32_t actual_crc = crc32(reinterpret_cast<const uint8_t *>(g_audio), payload_bytes);
    Serial.printf("TEST_HEADER protocol=EIP1 samples=%u bytes=%u expected_crc=%08x "
                  "actual_crc=%08x valid=%s\n", sample_count, static_cast<unsigned>(payload_bytes),
                  expected_crc, actual_crc, expected_crc == actual_crc ? "yes" : "no");
    if (expected_crc != actual_crc) { Serial.println("TEST_ERROR crc_mismatch"); return; }
    classify_and_print("SERIAL", calculate_stats(g_audio, EI_CLASSIFIER_RAW_SAMPLE_COUNT));
    Serial.println("TEST_END");
}

void write_u16(uint16_t v) { const uint8_t b[] = {uint8_t(v), uint8_t(v >> 8)}; Serial.write(b, 2); }
void write_u32(uint32_t v) {
    const uint8_t b[] = {uint8_t(v), uint8_t(v >> 8), uint8_t(v >> 16), uint8_t(v >> 24)};
    Serial.write(b, 4);
}
void stream_wav() {
    constexpr uint32_t data_bytes = EI_CLASSIFIER_RAW_SAMPLE_COUNT * sizeof(int16_t);
    Serial.printf("WAV_BEGIN %u\n", static_cast<unsigned>(44 + data_bytes));
    Serial.write(reinterpret_cast<const uint8_t *>("RIFF"), 4); write_u32(36 + data_bytes);
    Serial.write(reinterpret_cast<const uint8_t *>("WAVEfmt "), 8); write_u32(16);
    write_u16(1); write_u16(1); write_u32(EI_CLASSIFIER_FREQUENCY);
    write_u32(EI_CLASSIFIER_FREQUENCY * 2); write_u16(2); write_u16(16);
    Serial.write(reinterpret_cast<const uint8_t *>("data"), 4); write_u32(data_bytes);
    Serial.write(reinterpret_cast<const uint8_t *>(g_audio), data_bytes);
    Serial.print("\nWAV_END\n");
}
void print_memory() {
#if DEBUG_VERBOSE
    Serial.printf("MEM heap_free=%u heap_min=%u psram_total=%u psram_free=%u\n",
                  ESP.getFreeHeap(), ESP.getMinFreeHeap(), ESP.getPsramSize(), ESP.getFreePsram());
#endif
}
}  // namespace

void setup() {
    pinMode(kLedPin, OUTPUT);
    digitalWrite(kLedPin, LOW);
    Serial.begin(115200); delay(1500);
#if DEBUG_VERBOSE
    Serial.println("BOOT VuDieuAnhSang diagnostic inference");
    Serial.printf("MODEL project=%s deploy=%d rate=%d samples=%d interval_ms=%.4f labels=%d\n",
                  EI_CLASSIFIER_PROJECT_NAME, EI_CLASSIFIER_PROJECT_DEPLOY_VERSION,
                  EI_CLASSIFIER_FREQUENCY, EI_CLASSIFIER_RAW_SAMPLE_COUNT,
                  EI_CLASSIFIER_INTERVAL_MS, EI_CLASSIFIER_LABEL_COUNT);
    Serial.printf("PSRAM found=%s size=%u free=%u\n", psramFound() ? "yes" : "no",
                  ESP.getPsramSize(), ESP.getFreePsram());
#else
    Serial.println("READY | Voice recognition deployment 4");
#endif
    g_audio = static_cast<int16_t *>(heap_caps_malloc(EI_CLASSIFIER_RAW_SAMPLE_COUNT * sizeof(int16_t),
                                                       MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    if (!g_audio) { Serial.println("FATAL audio_buffer_psram_allocation_failed"); return; }
    g_i2s_ready = init_i2s();
    start_web();
    print_memory();
#if DEBUG_VERBOSE
    Serial.println("COMMAND 'w'=export I2S window, 't'=receive EIP1 PCM test window");
#endif
}

void loop() {
    if (!g_i2s_ready || !g_audio) { delay(1000); return; }
    AudioStats stats = {};
    if (!capture_window(stats)) return;
    classify_and_print("I2S", stats);
    announce_web();
    print_memory();
    bool dump = false, test = false;
    while (Serial.available()) {
        const char c = static_cast<char>(Serial.read());
        if (c == 'w' || c == 'W') dump = true;
        if (c == 't' || c == 'T') test = true;
    }
    if (dump) stream_wav();
    if (test) receive_serial_test();
}
