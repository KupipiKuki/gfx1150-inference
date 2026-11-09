// Golden reference generator for Phase 7F-2 (Gate G6).
//
// Pinned llama.cpp build: see audit/evidence/G6/7F/golden/README.md (commit
// recorded there). Deterministic greedy generation on the raw logits of the
// last position: argmax, no sampling chain, mirroring the engine's
// temperature-0 path exactly (sample_next_token with temperature == 0.0).
//
// Emits:
//   <out-prefix>.tokens.txt   one token id per line: prompt tokens, then the
//                             generated ids (greedy chain)
//   <out-prefix>.logits.f32   raw float32 logits of the last position of every
//                             generation step, concatenated (steps * n_vocab)
//
// Usage: golden_ref --model M.gguf --prompt-file P.txt --steps N --out-prefix OUT
#include "llama.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>

static void die(const char *msg) {
    fprintf(stderr, "golden_ref: %s\n", msg);
    exit(1);
}

int main(int argc, char **argv) {
    const char *model_path = nullptr;
    const char *prompt_path = nullptr;
    const char *out_prefix = nullptr;
    int steps = 16;
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "--model") && i + 1 < argc) model_path = argv[++i];
        else if (!strcmp(argv[i], "--prompt-file") && i + 1 < argc) prompt_path = argv[++i];
        else if (!strcmp(argv[i], "--steps") && i + 1 < argc) steps = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--out-prefix") && i + 1 < argc) out_prefix = argv[++i];
    }
    if (!model_path || !prompt_path || !out_prefix) {
        die("usage: golden_ref --model M.gguf --prompt-file P.txt --steps N --out-prefix OUT");
    }
    std::ifstream pf(prompt_path);
    std::string prompt((std::istreambuf_iterator<char>(pf)), std::istreambuf_iterator<char>());

    llama_backend_init();

    llama_model_params mp = llama_model_default_params();
    mp.n_gpu_layers = 0;  // CPU reference build
    llama_model *model = llama_model_load_from_file(model_path, mp);
    if (!model) die("cannot load model");

    const llama_vocab *vocab = llama_model_get_vocab(model);

    const int n_prompt = -llama_tokenize(vocab, prompt.c_str(), (int32_t) prompt.size(),
                                         nullptr, 0, true, false);
    if (n_prompt <= 0) die("prompt tokenization failed");
    std::vector<llama_token> tokens(n_prompt);
    if (llama_tokenize(vocab, prompt.c_str(), (int32_t) prompt.size(),
                       tokens.data(), (int32_t) tokens.size(), true, false) < 0) {
        die("prompt tokenization failed (buffer)");
    }

    llama_context_params cp = llama_context_default_params();
    cp.n_ctx = (uint32_t)(n_prompt + steps + 1);
    cp.n_batch = (uint32_t)(n_prompt > 512 ? n_prompt : 512);
    llama_context *ctx = llama_init_from_model(model, cp);
    if (!ctx) die("cannot create context");

    const int n_vocab = llama_vocab_n_tokens(vocab);

    llama_batch_ext *batch = llama_batch_ext_init(ctx);
    llama_pos pos = 0;
    std::vector<llama_token> prompt_ids = tokens;  // copy: batch holds the pointer
    std::vector<llama_token> generated;

    std::ofstream logits_out(std::string(out_prefix) + ".logits.f32",
                              std::ios::binary);
    if (!logits_out.is_open()) die("cannot open the logits output for writing");

    // prefill: output logits only for the last prompt token
    {
        llama_batch_ext_clear(batch);
        for (int i = 0; i < n_prompt; ++i) {
            const int32_t idx = llama_batch_ext_add_token(batch, 0, prompt_ids[i]);
            llama_pos p = pos + i;
            llama_batch_ext_set_pos(batch, idx, &p);
        }
        llama_batch_ext_set_output_logits(batch, n_prompt - 1, true);
        if (llama_process(ctx, LLAMA_PROCESS_TYPE_DECODE, batch)) {
            die("prefill decode failed");
        }
        pos += n_prompt;
    }

    for (int step = 0; step < steps; ++step) {
        float *row = llama_get_logits_ith(ctx, -1);
        if (!row) die("no logits returned");
        logits_out.write((const char *) row, (std::streamsize) n_vocab * sizeof(float));
        llama_token next = 0;
        float best = row[0];
        for (int i = 1; i < n_vocab; ++i) {
            if (row[i] > best) {
                best = row[i];
                next = i;
            }
        }
        generated.push_back(next);

        llama_batch_ext_clear(batch);
        const int32_t idx = llama_batch_ext_add_token(batch, 0, next);
        llama_batch_ext_set_pos(batch, idx, &pos);
        llama_batch_ext_set_output_logits(batch, 0, true);
        if (llama_process(ctx, LLAMA_PROCESS_TYPE_DECODE, batch)) {
            die("decode step failed");
        }
        pos += 1;
    }
    logits_out.close();

    {
        std::ofstream out(std::string(out_prefix) + ".tokens.txt");
        if (!out.is_open()) die("cannot open the tokens output for writing");
        for (llama_token t : tokens) out << t << "\n";
        out << "---\n";
        for (llama_token t : generated) out << t << "\n";
        out.close();
    }

    llama_batch_ext_free(batch);
    llama_free(ctx);
    llama_model_free(model);
    llama_backend_free();

    printf("prompt tokens: %d; generated: %d steps; n_vocab: %d\n",
           n_prompt, (int) generated.size(), n_vocab);
    return 0;
}
