// oracle_harness.cpp - reference inference harness against llama.cpp libllama
// Usage:
//   oracle_harness --model MODEL.gguf --prompt "text"           # tokenize, print ids
//   oracle_harness --model MODEL.gguf --tokens "1,2,3" --n 16   # greedy decode
//   oracle_harness ... --dump-layers FILE                       # dump per-layer f32 [pos][layer][hidden]
//   oracle_harness ... --dump-logits FILE                       # dump top-2 (id, logit) per step f32 [step][2]
//
// Never detokenizes / retokenizes: --tokens is a comma-separated list of ids.
// Layer dump filters the "l_out-<il>" tensors produced by llama.cpp's graph
// naming callback (src/llama-context.cpp graph_get_cb).

#include "llama.h"
#include "ggml.h"
#include "ggml-backend.h"

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

struct DumpState {
    bool collect_layers = false;
    int n_embd_expected = 0;
    int n_layer_expected = 0;

    // Per-decode layer captures: layer index -> f32 data [pos][hidden]
    std::map<int, std::vector<float>> layer_data;
    std::vector<int> layer_order;
    int last_n_tokens = 0;

    // Logits: top-2 (id, logit) for each generation step.
    std::vector<std::pair<int, float>> top2_per_step;
    std::vector<llama_token> generated;

    void clear_layers() {
        layer_data.clear();
        layer_order.clear();
        last_n_tokens = 0;
    }
};

static bool starts_with(const char * s, const char * prefix) {
    return std::strncmp(s, prefix, std::strlen(prefix)) == 0;
}

static bool eval_callback(struct ggml_tensor * t, bool ask, void * user_data) {
    DumpState * s = reinterpret_cast<DumpState *>(user_data);
    if (ask) {
        return s->collect_layers && starts_with(t->name, "l_out-");
    }
    if (!s->collect_layers || !starts_with(t->name, "l_out-")) {
        return true;
    }
    const int il = std::atoi(t->name + 6);
    if (il < 0) return true;

    const int n_embd = static_cast<int>(t->ne[0]);
    const int n_tokens = static_cast<int>(t->ne[1]);
    if (s->n_embd_expected > 0 && n_embd != s->n_embd_expected) {
        std::fprintf(stderr, "warn: l_out-%d has n_embd=%d, expected %d\n", il, n_embd, s->n_embd_expected);
    }
    if (t->type != GGML_TYPE_F32) {
        std::fprintf(stderr, "warn: l_out-%d type is %s, expected f32\n", il, ggml_type_name(t->type));
    }

    const size_t n_bytes = ggml_nbytes(t);
    std::vector<uint8_t> tmp;
    const uint8_t * src = nullptr;
    const bool host = ggml_backend_buffer_is_host(t->buffer);
    if (host) {
        src = reinterpret_cast<const uint8_t *>(t->data);
    } else {
        tmp.resize(n_bytes);
        ggml_backend_tensor_get(t, tmp.data(), 0, n_bytes);
        src = tmp.data();
    }

    std::vector<float> flat(static_cast<size_t>(n_embd) * n_tokens);
    for (int p = 0; p < n_tokens; ++p) {
        for (int h = 0; h < n_embd; ++h) {
            const size_t off = static_cast<size_t>(p) * t->nb[1] + static_cast<size_t>(h) * t->nb[0];
            flat[static_cast<size_t>(p) * n_embd + h] = *reinterpret_cast<const float *>(src + off);
        }
    }
    s->layer_data[il] = std::move(flat);
    if (std::find(s->layer_order.begin(), s->layer_order.end(), il) == s->layer_order.end()) {
        s->layer_order.push_back(il);
    }
    s->last_n_tokens = n_tokens;
    return true;
}

static void print_usage(const char * argv0) {
    std::printf("Usage:\n"
                "  %s --model MODEL.gguf --prompt \"text\"\n"
                "  %s --model MODEL.gguf --tokens \"1,2,3\" --n N [--dump-layers FILE] [--dump-logits FILE]\n",
                argv0, argv0);
}

static std::vector<llama_token> parse_tokens(const std::string & s) {
    std::vector<llama_token> out;
    std::stringstream ss(s);
    std::string item;
    while (std::getline(ss, item, ',')) {
        // Trim whitespace.
        size_t a = 0, b = item.size();
        while (a < b && std::isspace(static_cast<unsigned char>(item[a]))) ++a;
        while (b > a && std::isspace(static_cast<unsigned char>(item[b - 1]))) --b;
        if (a >= b) continue;
        out.push_back(static_cast<llama_token>(std::stol(item.substr(a, b - a))));
    }
    return out;
}

static std::string ids_to_string(const std::vector<llama_token> & ids) {
    std::string s;
    for (size_t i = 0; i < ids.size(); ++i) {
        if (i) s += ' ';
        s += std::to_string(ids[i]);
    }
    return s;
}

static std::pair<int, int> top2_from_logits(const float * logits, int n_vocab) {
    int best_id = 0, second_id = 1;
    float best = logits[0], second = logits[1];
    if (second > best) {
        std::swap(best, second);
        std::swap(best_id, second_id);
    }
    for (int i = 2; i < n_vocab; ++i) {
        const float v = logits[i];
        if (v > best) {
            second = best; second_id = best_id;
            best = v; best_id = i;
        } else if (v > second) {
            second = v; second_id = i;
        }
    }
    return {best_id, second_id};
}

int main(int argc, char ** argv) {
    std::string model_path;
    std::string prompt_text;
    std::string tokens_arg;
    std::string dump_layers_path;
    std::string dump_logits_path;
    int n_gen = 0;

    for (int i = 1; i < argc; ++i) {
        std::string a(argv[i]);
        if (a == "--model" && i + 1 < argc) model_path = argv[++i];
        else if (a == "--prompt" && i + 1 < argc) prompt_text = argv[++i];
        else if (a == "--tokens" && i + 1 < argc) tokens_arg = argv[++i];
        else if (a == "--n" && i + 1 < argc) n_gen = std::atoi(argv[++i]);
        else if (a == "--dump-layers" && i + 1 < argc) dump_layers_path = argv[++i];
        else if (a == "--dump-logits" && i + 1 < argc) dump_logits_path = argv[++i];
        else if (a == "-h" || a == "--help") { print_usage(argv[0]); return 0; }
        else { std::fprintf(stderr, "unknown arg: %s\n", a.c_str()); print_usage(argv[0]); return 1; }
    }

    if (model_path.empty() || (prompt_text.empty() && tokens_arg.empty())) {
        std::fprintf(stderr, "error: need --model and either --prompt or --tokens\n");
        print_usage(argv[0]);
        return 1;
    }

    llama_backend_init();
    llama_numa_init(GGML_NUMA_STRATEGY_DISABLED);

    llama_model_params mparams = llama_model_default_params();
    mparams.n_gpu_layers = 0; // CPU-only oracle

    llama_model * model = llama_model_load_from_file(model_path.c_str(), mparams);
    if (!model) {
        std::fprintf(stderr, "error: failed to load model %s\n", model_path.c_str());
        return 1;
    }
    const llama_vocab * vocab = llama_model_get_vocab(model);
    const int n_vocab = llama_vocab_n_tokens(vocab);

    // Tokenizer mode.
    if (!prompt_text.empty()) {
        std::vector<llama_token> ids(n_vocab);
        const int n = llama_tokenize(vocab, prompt_text.c_str(), static_cast<int32_t>(prompt_text.size()),
                                     ids.data(), static_cast<int32_t>(ids.size()), false, true);
        if (n < 0) {
            std::fprintf(stderr, "error: llama_tokenize failed (needed %d)\n", -n);
            llama_model_free(model);
            llama_backend_free();
            return 1;
        }
        ids.resize(n);
        std::vector<char> buf(8192);
        int32_t nd = llama_detokenize(vocab, ids.data(), static_cast<int32_t>(ids.size()),
                                      buf.data(), static_cast<int32_t>(buf.size()), false, true);
        if (nd < 0) {
            buf.resize(-nd + 1);
            nd = llama_detokenize(vocab, ids.data(), static_cast<int32_t>(ids.size()),
                                  buf.data(), static_cast<int32_t>(buf.size()), false, true);
        }
        std::string decoded(buf.data(), nd > 0 ? nd : 0);
        std::printf("ids: %s\n", ids_to_string(ids).c_str());
        std::printf("decode: %s\n", decoded.c_str());
        llama_model_free(model);
        llama_backend_free();
        return 0;
    }

    // Decode mode.
    std::vector<llama_token> prompt_ids = parse_tokens(tokens_arg);
    if (prompt_ids.empty()) {
        std::fprintf(stderr, "error: empty token list\n");
        llama_model_free(model);
        llama_backend_free();
        return 1;
    }

    DumpState state;
    state.collect_layers = !dump_layers_path.empty();
    state.n_embd_expected = llama_model_n_embd(model);
    state.n_layer_expected = llama_model_n_layer(model);

    llama_context_params cparams = llama_context_default_params();
    cparams.n_ctx = 4096;
    cparams.n_batch = 4096;
    cparams.n_ubatch = 4096;
    cparams.cb_eval = eval_callback;
    cparams.cb_eval_user_data = &state;

    llama_context * ctx = llama_init_from_model(model, cparams);
    if (!ctx) {
        std::fprintf(stderr, "error: failed to create context\n");
        llama_model_free(model);
        llama_backend_free();
        return 1;
    }

    auto t0 = std::chrono::steady_clock::now();

    llama_batch batch = llama_batch_init(static_cast<int32_t>(prompt_ids.size()), 0, 1);
    for (size_t i = 0; i < prompt_ids.size(); ++i) {
        batch.token[static_cast<int32_t>(i)] = prompt_ids[i];
        batch.pos[static_cast<int32_t>(i)] = static_cast<llama_pos>(i);
        batch.n_seq_id[static_cast<int32_t>(i)] = 1;
        batch.seq_id[static_cast<int32_t>(i)][0] = 0;
        batch.logits[static_cast<int32_t>(i)] = 0;
    }
    batch.logits[static_cast<int32_t>(prompt_ids.size()) - 1] = 1;
    batch.n_tokens = static_cast<int32_t>(prompt_ids.size());

    if (llama_decode(ctx, batch) != 0) {
        std::fprintf(stderr, "error: llama_decode failed on prompt\n");
        llama_batch_free(batch);
        llama_free(ctx);
        llama_model_free(model);
        llama_backend_free();
        return 1;
    }

    // Save layer dump for the prompt positions if requested.
    if (state.collect_layers && !state.layer_data.empty()) {
        std::sort(state.layer_order.begin(), state.layer_order.end());
        const int n_layer = static_cast<int>(state.layer_order.size());
        const int n_pos = state.last_n_tokens;
        const int n_embd = state.n_embd_expected;
        std::ofstream f(dump_layers_path, std::ios::binary);
        if (!f) {
            std::fprintf(stderr, "error: cannot open %s\n", dump_layers_path.c_str());
        } else {
            for (int p = 0; p < n_pos; ++p) {
                for (int il : state.layer_order) {
                    const auto & layer = state.layer_data[il];
                    const float * row = layer.data() + static_cast<size_t>(p) * n_embd;
                    f.write(reinterpret_cast<const char *>(row), static_cast<std::streamsize>(n_embd * sizeof(float)));
                }
            }
            std::printf("layers shape: [%d][%d][%d]  file: %s\n", n_pos, n_layer, n_embd, dump_layers_path.c_str());
        }
        state.clear_layers();
    }

    int n_past = static_cast<int>(prompt_ids.size());
    state.generated.reserve(n_gen);

    for (int step = 0; step < n_gen; ++step) {
        const float * logits = llama_get_logits_ith(ctx, batch.n_tokens - 1);
        if (!logits) {
            std::fprintf(stderr, "error: no logits at step %d\n", step);
            break;
        }
        auto [best_id, second_id] = top2_from_logits(logits, n_vocab);
        state.top2_per_step.push_back({best_id, logits[best_id]});
        state.top2_per_step.push_back({second_id, logits[second_id]});

        llama_token next_id = static_cast<llama_token>(best_id);
        state.generated.push_back(next_id);

        batch.token[0] = next_id;
        batch.pos[0] = static_cast<llama_pos>(n_past);
        batch.n_seq_id[0] = 1;
        batch.seq_id[0][0] = 0;
        batch.logits[0] = 1;
        batch.n_tokens = 1;
        ++n_past;

        if (llama_decode(ctx, batch) != 0) {
            std::fprintf(stderr, "error: llama_decode failed at generation step %d\n", step);
            break;
        }
    }

    auto t1 = std::chrono::steady_clock::now();
    double elapsed = std::chrono::duration<double>(t1 - t0).count();

    std::printf("gen: %s\n", ids_to_string(state.generated).c_str());
    std::printf("wall_s: %.3f\n", elapsed);

    if (!dump_logits_path.empty() && !state.top2_per_step.empty()) {
        std::ofstream f(dump_logits_path, std::ios::binary);
        if (!f) {
            std::fprintf(stderr, "error: cannot open %s\n", dump_logits_path.c_str());
        } else {
            for (const auto & p : state.top2_per_step) {
                float idf = static_cast<float>(p.first);
                f.write(reinterpret_cast<const char *>(&idf), sizeof(float));
                f.write(reinterpret_cast<const char *>(&p.second), sizeof(float));
            }
            std::printf("logits shape: [%zu][2]  file: %s\n", state.top2_per_step.size() / 2, dump_logits_path.c_str());
        }
    }

    llama_batch_free(batch);
    llama_free(ctx);
    llama_model_free(model);
    llama_backend_free();
    return 0;
}
