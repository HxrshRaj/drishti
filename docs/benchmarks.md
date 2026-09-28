# Benchmarks

**Hardware this environment actually has:** CPU only. `nvidia-smi` is not
present. Every number below is a real measurement from a run in this
repo, with the exact command to reproduce it. Nothing is estimated or
invented. The GPU comparison table (fp16 / 4-bit / 8-bit / vLLM /
batch-size sweep) is shipped as a ready-to-run notebook,
`benchmarks/colab_bench.ipynb`, and marked **pending user run** — not
filled with guessed numbers.

## Perception model choice

`HuggingFaceTB/SmolVLM-256M-Instruct` (Apache-2.0). Picked specifically
for CPU feasibility: 256M parameters is small enough that a single
inference call completes in real time on a CPU-only machine (see below),
which a 7B+-class VLM would not.

## Two-stage pipeline latency (real, CPU)

Source: `benchmarks/results/perception_eval.json`, built from
`benchmarks/manual_check.py --n 20 --seed 3` (Phase 1's required
"check by hand for at least 20 images" run) via
`benchmarks/summarize_manual_check.py`.

```bash
python benchmarks/manual_check.py --n 20 --seed 3 --out benchmarks/results/manual_check_20.jsonl
python benchmarks/summarize_manual_check.py
```

| metric | value |
|---|---|
| images | 20 |
| device | cpu |
| JSON parse failure rate | **0.0%** (0/20) — see "what changed" below for why this wasn't always true |
| latency p50 | 32.1 s |
| latency p95 | 50.8 s |
| latency mean | 33.1 s |
| latency min / max | 27.9 s / 50.8 s |

This is per-image, end-to-end (VLM caption + local-LLM structuring). It is
slow — see `docs/limitations.md` on why `MissionGraphDeps.max_waypoints`
defaults to 3, not a full site sweep, for one real end-to-end mission run
to stay tractable.

## What changed, and why (the actual debugging story)

The first design was a single VLM call: show the image, ask for the exact
JSON schema in one prompt. Measured on real images:

- **Parse failure / groundedness problem, not a formatting problem.** The
  model returned syntactically-plausible JSON, but its *content* was
  copied verbatim from the prompt's few-shot example regardless of which
  image it was shown — confirmed by feeding it 4 different images and
  getting the identical `"a white car is parked near the right edge of
  the frame"` string back every time.
- **Control test:** the same model, given only `"Describe what is visible
  in this image in one or two sentences."` with no JSON constraint,
  produced different, plausible, grounded captions per image (e.g. "In
  this image we can see buildings, trees, vehicles, roads, poles..." vs.
  "In this image, we can see vehicles on the road. There are some
  lights..."). This isolated the failure to combining vision grounding
  with strict structured output, not vision grounding itself.
- **Fix:** two stages. Stage 1 = free-text caption (grounded, per the
  control test above). Stage 2 = the local text LLM
  (`Qwen/Qwen2.5-0.5B-Instruct`) structures that caption into the JSON
  schema — a text-only task, no vision grounding required of it. Parse
  failure rate: 0/20 in the tracked run above.
- **Remaining, honest caveat:** on this 20-image sample, the structuring
  stage chose `finding_type: "vehicle_presence"` for 18/20 images and
  `"people_presence"` for 2/20 — every one of the 20 sampled images'
  ground truth includes at least one vehicle class, so a model that always
  guesses "vehicle" would score highly here too. This is called out
  explicitly in `perception_eval.json`'s `accuracy_note` field and in
  `docs/bias-report.md` — a coarse-accuracy number of 100% on this sample
  is a real, reproducible result, and it is *not* strong evidence of fine-
  grained discrimination. See `docs/limitations.md`.
- Confidence scores were also observed to cluster very tightly around
  0.90 across all 20 images — the local structuring LLM is not well
  calibrated; treat `confidence` as a rough signal, not a probability.

## Resolution sweep (real, CPU)

```bash
python benchmarks/run_bench.py --n 2
```

| config | resize | latency p50 | throughput |
|---|---|---|---|
| fp32, native resolution | 1400×788 (native) | 32.06 s | 0.032 img/s |
| fp32, half resolution | 700×394 | 30.19 s | 0.033 img/s |

**Real, slightly counterintuitive finding:** halving the input resolution
barely moved latency (~6% faster). SmolVLM's image processor resamples
input images to a fixed internal patch grid regardless of the source
resolution, so shrinking the source image before inference does not
proportionally shrink the model's actual compute — the bottleneck here is
the fixed-size vision encoder + the two full model forward passes (caption
+ structuring), not input pixel count. This is exactly the kind of
tradeoff the brief asks to be documented, not oversold: resizing input
images is not a meaningful CPU optimization lever for this model.

## Batch size, fp16, 4-bit/8-bit quantization, vLLM — pending GPU run

Not run here, for stated reasons, not omitted silently:

- **fp16/bfloat16 on CPU** is not meaningfully faster than fp32 for this
  architecture on CPU (no hardware fp16 acceleration path without a GPU);
  `VLMPerceptionService` already selects `bfloat16` automatically when
  `torch.cuda.is_available()` — see `app/perception/vlm.py`.
- **4-bit / 8-bit quantization** via `bitsandbytes` is CUDA-accelerated;
  its CPU kernels are not a real-world speedup path for this project's
  hardware.
- **vLLM** targets GPU-served inference and is not the right tool for a
  CPU-only single-request demo service.
- **Batch-size sweep** needs a GPU (or a batching-aware CPU server) to show
  a meaningful throughput curve; a batch-size-2 CPU run of a HF
  `generate()` call does not parallelize the way a batched GPU kernel
  does.

Run `benchmarks/colab_bench.ipynb` on a free Colab/Kaggle T4 GPU to fill
in: fp16 baseline, 4-bit/8-bit quantized, a batch-size sweep, and — if the
model supports it — a vLLM comparison, each measured against accuracy on
the same held-out labeled subset, per the brief's requirement that speed
is always reported next to accuracy.

## Retrieval quality (real)

```bash
python benchmarks/eval_retrieval.py
```

Source: `benchmarks/results/retrieval_eval.json`, against the 28-query
hand-labeled set in `data/eval/retrieval_queries.jsonl` (2 queries per SOP
document, 14 SOPs).

| k | recall@k |
|---|---|
| 1 | 92.9% (26/28) |
| 3 | 96.4% (27/28) |
| 5 | 100.0% (28/28) |

63 chunks ingested from 14 SOP documents (`app/rag/chunking.py`, section-
aware splitting on `## ` headings). The 2 queries that miss at k=1 are
logged in the JSON output's `per_query` field for inspection.

## Parity report

See `docs/bias-report.md` — built from the same 20-image manual-check run
via `benchmarks/build_parity_report.py`, so the expensive model run only
happens once.

## Reproducing everything above from a fresh clone

```bash
cd backend && pip install -r requirements-dev.txt && pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cpu
cd ../benchmarks
python manual_check.py --n 20 --seed 3 --out results/manual_check_20.jsonl
python summarize_manual_check.py
python eval_retrieval.py
python build_parity_report.py
python run_bench.py --n 2
```
