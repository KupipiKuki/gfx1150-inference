# Header dump provenance — 7C evidence

Real GGUF header slices recorded for tensor-name/shape authority. No model weights
are committed; only the header slice was fetched over an HTTP range request and
dumped to text with `dump_gguf_header.py` (in this directory).

## Slice fetch command

    curl -sL -r 0-<END> "<URL>" -o <slice>
    python dump_gguf_header.py <slice> > <dump>

The dump tool stops at `data_offset` (it records, rather than validates, tensor
extents, because the slice does not contain the data); each dump states
`data_offset` and confirms the slice covers the complete header. The slice file
itself is not committed.

## Phi-3

- Repo: `microsoft/Phi-3-mini-4k-instruct-gguf`
- URL: https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf
- Repo revision (main, X-Repo-Commit): `a64113399c2f6b8ad3e11c394733a2ddadaa7f33`
- Full file size (Content-Length): 2393231072 bytes
- Byte range fetched: `0-4194303` (4 MiB); header ends at `data_offset = 737504`
- sha256(slice bytes 0..4194303): `9905adb5856e99ecce77b4e4f75800e92eb36987c56028368d28a4b7d10af853`
- Dump: `phi3-mini-4k-instruct-q4.header.txt`

## Gemma

The upstream `google/gemma-2b-it-GGUF` repository is gated (HTTP 401 without
authentication), so a public mirror of the same original conversion is used.
The tensor names are `gemma`-architecture-defined and identical.

- Repo: `MaziyarPanahi/gemma-2b-it-GGUF` (mirror of `models--google--gemma-2b-it`,
  per its `general.name` metadata)
- URL: https://huggingface.co/MaziyarPanahi/gemma-2b-it-GGUF/resolve/main/gemma-2b-it.Q4_K_M.gguf
- Repo revision (main, X-Repo-Commit): `72164ae6fc4003cecf37bc07f3a825b8a20b8cbb`
- Full file size (Content-Length): 1630263040 bytes
- Byte range fetched: `0-16777215` (16 MiB); header ends at `data_offset = 6039296`
- sha256(slice bytes 0..16777215): `3dcba9e2b31eb86f1a944caf63af7a4c7513eb6c981e79dc90c3f4173fb58de7`
- Dump: `gemma-2b-it-q4_k_m.header.txt`

## Key facts recorded by the dumps (checked against the implementation)

- Phi-3-mini-4k-instruct (q4): fused `blk.N.attn_qkv.weight` (dims `(3072, 9216)`
  = q 3072 + 2*kv 3072 = 32 heads * 96 head_dim * 3), fused
  `blk.N.ffn_up.weight` (dims `(3072, 16384)` = 2 x feed_forward_length 8192),
  `head_count_kv = 32`, `rope.dimension_count = 96`; no attention/FFN biases, no
  `rope_factors_*`, tied output (no `output.weight`).
- gemma-2b-it (Q4_K_M): separate `attn_q/k/v.weight`, `key_length = value_length
  = 256` (explicit, plus `head_count = 8`, `head_count_kv = 1`, hidden 2048),
  separate `ffn_gate/up/down`, tied output (no `output.weight`), no
  `final_logit_softcapping`.
