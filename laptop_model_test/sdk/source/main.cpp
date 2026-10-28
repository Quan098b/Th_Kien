#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
#include "edge-impulse-sdk/classifier/ei_run_classifier.h"

static std::vector<int16_t> pcm;

static uint16_t le16(const uint8_t *p) { return uint16_t(p[0]) | (uint16_t(p[1]) << 8); }
static uint32_t le32(const uint8_t *p) { return uint32_t(p[0]) | (uint32_t(p[1]) << 8) | (uint32_t(p[2]) << 16) | (uint32_t(p[3]) << 24); }

static bool load_wav(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) { std::fprintf(stderr, "Cannot open %s\n", path); return false; }
    uint8_t riff[12];
    if (fread(riff, 1, 12, f) != 12 || std::memcmp(riff, "RIFF", 4) || std::memcmp(riff + 8, "WAVE", 4)) {
        std::fprintf(stderr, "Invalid RIFF/WAVE: %s\n", path); fclose(f); return false;
    }
    bool format_ok = false, data_ok = false;
    while (!data_ok) {
        uint8_t chunk[8];
        if (fread(chunk, 1, 8, f) != 8) break;
        const uint32_t size = le32(chunk + 4);
        if (!std::memcmp(chunk, "fmt ", 4)) {
            std::vector<uint8_t> fmt(size);
            if (fread(fmt.data(), 1, size, f) != size || size < 16) break;
            format_ok = le16(fmt.data()) == 1 && le16(fmt.data() + 2) == 1 &&
                        le32(fmt.data() + 4) == 16000 && le16(fmt.data() + 14) == 16;
        }
        else if (!std::memcmp(chunk, "data", 4)) {
            if (!format_ok || size != EI_CLASSIFIER_RAW_SAMPLE_COUNT * sizeof(int16_t)) break;
            pcm.resize(EI_CLASSIFIER_RAW_SAMPLE_COUNT);
            data_ok = fread(pcm.data(), 1, size, f) == size;
        }
        else { fseek(f, size + (size & 1U), SEEK_CUR); }
    }
    fclose(f);
    if (!data_ok) std::fprintf(stderr, "Expected PCM16 mono 16kHz, 24000 samples: %s\n", path);
    return data_ok;
}

static int get_signal_data(size_t offset, size_t length, float *out) {
    if (offset + length > pcm.size()) return -1;
    for (size_t i = 0; i < length; ++i) out[i] = static_cast<float>(pcm[offset + i]);
    return EIDSP_OK;
}

int main(int argc, char **argv) {
    if (argc < 2) { std::fprintf(stderr, "Usage: laptop_infer WAV...\n"); return 2; }
    run_classifier_init();
    std::printf("META\tproject_id=%d\tproject=%s\tdeploy=%d\tsamples=%d\tfrequency=%d\tlabels=%d\n",
        EI_CLASSIFIER_PROJECT_ID, EI_CLASSIFIER_PROJECT_NAME, EI_CLASSIFIER_PROJECT_DEPLOY_VERSION,
        EI_CLASSIFIER_RAW_SAMPLE_COUNT, EI_CLASSIFIER_FREQUENCY, EI_CLASSIFIER_LABEL_COUNT);
    for (int arg = 1; arg < argc; ++arg) {
        if (!load_wav(argv[arg])) return 3;
        double sum = 0.0, squares = 0.0;
        int16_t minimum = 32767, maximum = -32768;
        size_t clipped = 0;
        for (int16_t x : pcm) { sum += x; squares += double(x) * x; minimum = std::min(minimum, x); maximum = std::max(maximum, x); clipped += (x == -32768 || x == 32767); }
        const double mean = sum / pcm.size();
        const double rms = std::sqrt(std::max(0.0, squares / pcm.size() - mean * mean));
        signal_t signal = {}; signal.total_length = pcm.size(); signal.get_data = get_signal_data;
        ei_impulse_result_t result = {};
        EI_IMPULSE_ERROR err = run_classifier(&signal, &result, false);
        if (err != EI_IMPULSE_OK) { std::fprintf(stderr, "run_classifier error %d for %s\n", int(err), argv[arg]); return 4; }
        size_t best = 0;
        std::printf("FILE\t%s\trms=%.6f\tmin=%d\tmax=%d\tclipped=%zu", argv[arg], rms, minimum, maximum, clipped);
        for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; ++i) {
            std::printf("\t%s=%.9f", result.classification[i].label, result.classification[i].value);
            if (result.classification[i].value > result.classification[best].value) best = i;
        }
        std::printf("\tpredicted=%s\tdsp_ms=%u\tinference_ms=%u\n",
            result.classification[best].label, result.timing.dsp, result.timing.classification);
    }
    return 0;
}
