#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <numeric>
#include <vector>
#include "edge-impulse-sdk/classifier/ei_run_classifier.h"

static std::vector<int16_t> pcm;
static uint16_t le16(const uint8_t *p) { return uint16_t(p[0]) | (uint16_t(p[1]) << 8); }
static uint32_t le32(const uint8_t *p) { return uint32_t(p[0]) | (uint32_t(p[1]) << 8) | (uint32_t(p[2]) << 16) | (uint32_t(p[3]) << 24); }
static bool load_wav(const char *path) {
    FILE *f = fopen(path, "rb"); if (!f) return false;
    uint8_t riff[12];
    if (fread(riff, 1, 12, f) != 12 || memcmp(riff, "RIFF", 4) || memcmp(riff + 8, "WAVE", 4)) { fclose(f); return false; }
    bool fmt_ok = false, data_ok = false;
    while (!data_ok) {
        uint8_t chunk[8]; if (fread(chunk, 1, 8, f) != 8) break;
        uint32_t size = le32(chunk + 4);
        if (!memcmp(chunk, "fmt ", 4)) {
            std::vector<uint8_t> fmt(size); if (fread(fmt.data(), 1, size, f) != size || size < 16) break;
            fmt_ok = le16(fmt.data()) == 1 && le16(fmt.data()+2) == 1 && le32(fmt.data()+4) == 16000 && le16(fmt.data()+14) == 16;
        } else if (!memcmp(chunk, "data", 4)) {
            if (!fmt_ok || size != EI_CLASSIFIER_RAW_SAMPLE_COUNT * 2) break;
            pcm.resize(EI_CLASSIFIER_RAW_SAMPLE_COUNT); data_ok = fread(pcm.data(), 1, size, f) == size;
        } else fseek(f, size + (size & 1U), SEEK_CUR);
    }
    fclose(f); return data_ok;
}
static int get_data(size_t offset, size_t length, float *out) {
    if (offset + length > pcm.size()) return -1;
    for (size_t i = 0; i < length; ++i) out[i] = pcm[offset + i];
    return EIDSP_OK;
}
static float percentile(std::vector<float> v, double q) {
    std::sort(v.begin(), v.end()); return v[static_cast<size_t>(q * (v.size() - 1))];
}
int main(int argc, char **argv) {
    if (argc < 4) { fprintf(stderr, "Usage: mfe_dump SUMMARY.csv VECTORS.csv WAV...\n"); return 2; }
    FILE *summary = fopen(argv[1], "wb"), *vectors = fopen(argv[2], "wb");
    if (!summary || !vectors) return 3;
    fprintf(summary, "file,rms,mfe_mean,mfe_std,mfe_min,mfe_p05,mfe_p50,mfe_p95,mfe_max,band_00_09,band_10_19,band_20_29,band_30_39,time_first,time_middle,time_last\n");
    fprintf(vectors, "file,index,frame,filter,value\n");
    for (int arg = 3; arg < argc; ++arg) {
        if (!load_wav(argv[arg])) { fprintf(stderr, "Invalid WAV %s\n", argv[arg]); return 4; }
        double sum = 0, sq = 0; for (int16_t v : pcm) { sum += v; sq += double(v)*v; }
        double mean_pcm = sum / pcm.size(); double rms = sqrt(std::max(0.0, sq/pcm.size()-mean_pcm*mean_pcm));
        signal_t signal = {}; signal.total_length = pcm.size(); signal.get_data = get_data;
        ei::matrix_t matrix(1, EI_CLASSIFIER_NN_INPUT_FRAME_SIZE);
        ei_model_dsp_t block = ei_dsp_blocks[0];
        int err = block.extract_fn(&signal, &matrix, block.config, EI_CLASSIFIER_FREQUENCY);
        if (err != EIDSP_OK) { fprintf(stderr, "MFE error %d\n", err); return 5; }
        std::vector<float> values(matrix.buffer, matrix.buffer + matrix.cols);
        double mfe_mean = std::accumulate(values.begin(), values.end(), 0.0) / values.size(), variance = 0;
        for (float v : values) variance += (v-mfe_mean)*(v-mfe_mean);
        double bands[4] = {}, times[3] = {}; size_t band_n[4] = {}, time_n[3] = {};
        for (size_t i = 0; i < values.size(); ++i) {
            size_t frame = i / 40, filter = i % 40, b = filter / 10;
            size_t t = frame < 49 ? 0 : (frame < 100 ? 1 : 2);
            bands[b] += values[i]; ++band_n[b]; times[t] += values[i]; ++time_n[t];
            fprintf(vectors, "\"%s\",%zu,%zu,%zu,%.9f\n", argv[arg], i, frame, filter, values[i]);
        }
        fprintf(summary, "\"%s\",%.6f,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f", argv[arg], rms,
                mfe_mean, sqrt(variance/values.size()), *std::min_element(values.begin(),values.end()),
                percentile(values,.05), percentile(values,.50), percentile(values,.95), *std::max_element(values.begin(),values.end()));
        for (int i=0;i<4;++i) fprintf(summary, ",%.9f", bands[i]/band_n[i]);
        for (int i=0;i<3;++i) fprintf(summary, ",%.9f", times[i]/time_n[i]);
        fprintf(summary, "\n");
    }
    fclose(summary); fclose(vectors); return 0;
}
