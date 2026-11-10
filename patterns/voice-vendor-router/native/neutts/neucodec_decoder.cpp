// neucodec_decoder: NeuCodec speech codes to 24 kHz audio with ONNX Runtime.
//
// NeuTTS generates speech as NeuCodec codes (<|speech_N|> tokens, 50 per
// second). This program turns them into audio with Neuphonic's int8 ONNX
// decoder, in C++, so the Rasa process needs neither torch nor numpy.
//
//   neucodec_decoder <model.onnx> --codes <codes.txt> --wav <out.wav>
//       One shot: whitespace-separated codes in, 16-bit 24 kHz mono WAV out.
//
//   neucodec_decoder <model.onnx> --serve
//       Keeps the model loaded and answers requests on stdin/stdout, so a
//       caller pays the model load once instead of once per sentence.
//       All integers little-endian.
//         request:  "NCDQ" u32 n_codes u32 sample_start u32 sample_end
//                   i32[n_codes]            (sample_end 0xFFFFFFFF = to the end)
//         response: "NCDA" u32 status u32 n, then float32[n] samples in
//                   [-1, 1] (status 0) or n bytes of UTF-8 error text.
//       sample_start/sample_end slice the decoded audio before it is sent,
//       which is how a streaming caller keeps only the new part of a chunk
//       decoded with look-back context.
//
// Options: --threads N (intra-op threads, default 4).
// SPDX-License-Identifier: Apache-2.0

#include <onnxruntime_cxx_api.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

constexpr uint32_t kSampleRate = 24000;
constexpr int64_t kMaxCodes = 1 << 16;

struct Decoder {
    Ort::Env env{ORT_LOGGING_LEVEL_WARNING, "neucodec"};
    std::unique_ptr<Ort::Session> session;
    std::string output_name;

    Decoder(const std::string &model, int threads) {
        Ort::SessionOptions options;
        options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
        options.SetIntraOpNumThreads(threads);
        options.SetInterOpNumThreads(1);
        session = std::make_unique<Ort::Session>(env, model.c_str(), options);
        Ort::AllocatorWithDefaultOptions allocator;
        output_name = session->GetOutputNameAllocated(0, allocator).get();
    }

    std::vector<float> decode(std::vector<int32_t> &codes) {
        if (codes.empty()) throw std::runtime_error("no speech codes supplied");
        const std::array<int64_t, 3> shape{1, 1, static_cast<int64_t>(codes.size())};
        auto memory = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
        auto input = Ort::Value::CreateTensor<int32_t>(
            memory, codes.data(), codes.size(), shape.data(), shape.size());
        const char *input_names[] = {"codes"};
        const char *output_names[] = {output_name.c_str()};
        auto outputs = session->Run(Ort::RunOptions{nullptr}, input_names, &input, 1,
                                    output_names, 1);
        const size_t count = outputs[0].GetTensorTypeAndShapeInfo().GetElementCount();
        if (count == 0) throw std::runtime_error("decoder returned no audio");
        const float *data = outputs[0].GetTensorData<float>();
        return std::vector<float>(data, data + count);
    }
};

void put_u16(std::ostream &out, uint16_t v) {
    out.put(static_cast<char>(v & 0xff));
    out.put(static_cast<char>(v >> 8));
}

void put_u32(std::ostream &out, uint32_t v) {
    put_u16(out, static_cast<uint16_t>(v & 0xffff));
    put_u16(out, static_cast<uint16_t>(v >> 16));
}

int16_t to_pcm16(float sample) {
    const float bounded = std::clamp(sample, -1.0f, 1.0f);
    return static_cast<int16_t>(std::lrint(bounded * 32767.0f));
}

void write_wav(const std::string &path, const std::vector<float> &samples) {
    std::ofstream out(path, std::ios::binary);
    if (!out) throw std::runtime_error("cannot create " + path);
    const uint32_t data_size = static_cast<uint32_t>(samples.size() * 2);
    out.write("RIFF", 4); put_u32(out, 36 + data_size); out.write("WAVE", 4);
    out.write("fmt ", 4); put_u32(out, 16); put_u16(out, 1); put_u16(out, 1);
    put_u32(out, kSampleRate); put_u32(out, kSampleRate * 2); put_u16(out, 2); put_u16(out, 16);
    out.write("data", 4); put_u32(out, data_size);
    for (float s : samples) put_u16(out, static_cast<uint16_t>(to_pcm16(s)));
    if (!out) throw std::runtime_error("failed writing " + path);
}

std::vector<int32_t> read_codes_file(const std::string &path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("cannot open " + path);
    std::vector<int32_t> codes;
    int64_t value;
    while (in >> value) {
        if (value < 0 || value > INT32_MAX) throw std::runtime_error("speech code out of range");
        codes.push_back(static_cast<int32_t>(value));
    }
    return codes;
}

bool read_exact(void *buffer, size_t size) {
    return std::fread(buffer, 1, size, stdin) == size;
}

uint32_t le32(const unsigned char *p) {
    return static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8) |
           (static_cast<uint32_t>(p[2]) << 16) | (static_cast<uint32_t>(p[3]) << 24);
}

void write_le32(uint32_t v) {
    const unsigned char b[4] = {static_cast<unsigned char>(v), static_cast<unsigned char>(v >> 8),
                                static_cast<unsigned char>(v >> 16), static_cast<unsigned char>(v >> 24)};
    std::fwrite(b, 1, 4, stdout);
}

void respond_error(const std::string &message) {
    std::fwrite("NCDA", 1, 4, stdout);
    write_le32(1);
    write_le32(static_cast<uint32_t>(message.size()));
    std::fwrite(message.data(), 1, message.size(), stdout);
    std::fflush(stdout);
}

int serve(Decoder &decoder) {
    std::fprintf(stderr, "neucodec_decoder ready sample_rate=%u\n", kSampleRate);
    std::fflush(stderr);
    unsigned char header[16];
    while (read_exact(header, sizeof header)) {
        if (std::memcmp(header, "NCDQ", 4) != 0) {
            respond_error("bad request magic");
            return 65;
        }
        const uint32_t n = le32(header + 4);
        uint32_t start = le32(header + 8);
        uint32_t end = le32(header + 12);
        if (n == 0 || n > kMaxCodes) {
            respond_error("code count out of range");
            return 65;
        }
        std::vector<int32_t> codes(n);
        if (!read_exact(codes.data(), n * sizeof(int32_t))) return 65;
        try {
            for (int32_t c : codes)
                if (c < 0) throw std::runtime_error("negative speech code");
            std::vector<float> audio = decoder.decode(codes);
            const uint32_t total = static_cast<uint32_t>(audio.size());
            end = std::min(end, total);
            start = std::min(start, end);
            std::fwrite("NCDA", 1, 4, stdout);
            write_le32(0);
            write_le32(end - start);
            std::fwrite(audio.data() + start, sizeof(float), end - start, stdout);
            std::fflush(stdout);
        } catch (const std::exception &error) {
            respond_error(error.what());
        }
    }
    return 0;
}

}  // namespace

int main(int argc, char **argv) {
    if (argc >= 2 && std::string(argv[1]) == "--version") {
        std::cout << "neucodec_decoder onnxruntime=" << Ort::GetVersionString() << "\n";
        return 0;
    }
    if (argc < 3) {
        std::cerr << "usage: neucodec_decoder <model.onnx> --serve [--threads N]\n"
                     "       neucodec_decoder <model.onnx> --codes <codes.txt> --wav <out.wav> [--threads N]\n";
        return 64;
    }
    const std::string model = argv[1];
    std::string codes_path, wav_path;
    bool serving = false;
    int threads = 4;
    for (int i = 2; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--serve") serving = true;
        else if (arg == "--codes" && i + 1 < argc) codes_path = argv[++i];
        else if (arg == "--wav" && i + 1 < argc) wav_path = argv[++i];
        else if (arg == "--threads" && i + 1 < argc) threads = std::max(1, std::atoi(argv[++i]));
        else {
            std::cerr << "unknown argument: " << arg << "\n";
            return 64;
        }
    }
    try {
        Decoder decoder(model, threads);
        if (serving) return serve(decoder);
        if (codes_path.empty() || wav_path.empty()) {
            std::cerr << "one-shot mode needs --codes and --wav\n";
            return 64;
        }
        auto codes = read_codes_file(codes_path);
        auto audio = decoder.decode(codes);
        write_wav(wav_path, audio);
        std::cout << "decoded_codes=" << codes.size() << " samples=" << audio.size() << "\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "neucodec_decoder: " << error.what() << "\n";
        return 1;
    }
}
