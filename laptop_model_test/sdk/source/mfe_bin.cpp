// Extract deployment MFE features for many WAVs into one float32 matrix.
// Usage: mfe_bin LIST.txt OUT.f32   (LIST: one WAV path per line)
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
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
int main(int argc, char **argv) {
    if (argc != 3) { fprintf(stderr, "Usage: mfe_bin LIST.txt OUT.f32\n"); return 2; }
    FILE *list = fopen(argv[1], "rb"), *out = fopen(argv[2], "wb");
    if (!list || !out) return 3;
    char line[4096]; size_t n = 0;
    while (fgets(line, sizeof line, list)) {
        std::string path(line);
        while (!path.empty() && (path.back() == '\n' || path.back() == '\r')) path.pop_back();
        if (path.empty()) continue;
        if (!load_wav(path.c_str())) { fprintf(stderr, "Invalid WAV %s\n", path.c_str()); return 4; }
        signal_t signal = {}; signal.total_length = pcm.size(); signal.get_data = get_data;
        ei::matrix_t matrix(1, EI_CLASSIFIER_NN_INPUT_FRAME_SIZE);
        ei_model_dsp_t block = ei_dsp_blocks[0];
        int err = block.extract_fn(&signal, &matrix, block.config, EI_CLASSIFIER_FREQUENCY);
        if (err != EIDSP_OK) { fprintf(stderr, "MFE error %d for %s\n", err, path.c_str()); return 5; }
        fwrite(matrix.buffer, sizeof(float), matrix.cols, out); ++n;
    }
    fclose(list); fclose(out);
    printf("rows=%zu cols=%d\n", n, EI_CLASSIFIER_NN_INPUT_FRAME_SIZE);
    return 0;
}
