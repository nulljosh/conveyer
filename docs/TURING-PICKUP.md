# Turing picker pickup (2026-10-02, 17:35)

Goal: Turing's own small model picks Conveyer's next skill, so we can run on ours instead of Claude. Honest scope: the model owns the opening and crash recovery. Late-game builds stay scripted in scripts/planner.py.

## Done
- Eval: `scripts/eval_picker.py` scores skill name, then params, on `data/valid.jsonl`. Every run appends to `eval/history.jsonl`; `scripts/bench_graph.py` redraws `eval/benchmarks.svg`.
- Split is by run file (`scripts/export_training.py`), so the score is honest. Plain Qwen2.5-0.5B: 1% skill, 0% params. LoRA 600 iters: 49% skill, 28% params, 100% valid JSON.
- Gate: `scripts/gate.sh [adapter]` fails if skill or params drop below `eval/baseline.json`.
- Train: `cd ~/Documents/Code/turing && DATA=$HOME/Documents/Code/conveyer/data LORA_ARGS="--batch-size 4" training/train_resilient.sh mlx-community/Qwen2.5-0.5B-Instruct-4bit conveyer-adapter2 600`. Eval needs Turing's venv python.
- Logging: `scripts/planner.py step` writes each decision (tile, stock, result) to `runs/planner/*.jsonl`. Not exported yet, on purpose.
- Live test passed on a copy of the world: `agent.py --picker --picker-url http://127.0.0.1:8081 --model <fused dir>` ran 6 steps, valid skills, a drill got placed. Serve with `cd ~/Documents/Code/turing && ./.venv/bin/python -m mlx_lm server --model /private/tmp/claude-loop/fused-conveyer --port 8081`. The copy ran as a second container on ports 27001 and 34198 with `FACTORIO_SERVER_PORT=27001`, never the real server.

## GGUF (fixed 2026-10-02 18:00)
Junk came from fusing into the dequantized 4-bit base, and Q8_0 also breaks this model. What works: fuse onto the full-precision base (`mlx_lm fuse --model Qwen/Qwen2.5-0.5B-Instruct --adapter-path ...`, no --dequantize), convert with `--outtype f16`, `ollama create conveyer-picker -f models/Modelfile`. Valid JSON in llama.cpp and Ollama.
Catch: an adapter trained on the 4-bit base scores worse on the fp base (25% skill, 9% params vs 49% and 34%). Train LoRA on `Qwen/Qwen2.5-0.5B-Instruct` itself so train and serve match.

## Status (2026-10-02 19:10, grade B)
Honest run-split eval, 79 held-out examples, plain base is 1% skill and 0% params. All rows below train on the full-precision base `Qwen/Qwen2.5-0.5B-Instruct` (500 iters, `--num-layers 8`) so the F16 Ollama export matches what was trained.
| prompt | skill | params |
|---|---|---|
| last result only | 38% | 25% |
| + last three skill names | 59% | 28% |
| + known entity positions, one position format | 59% | 43% |
`conveyer-picker` in Ollama is the last row (adapter7). Gate baseline: `eval/baseline.json`.
Remaining skill misses: half are gold `inspect` predicted `peek` (inspect follows craft and feed most of the time, but the valid set is only 79 rows, so each point is noise of about 5). Ceiling is data and ambiguous next-skill choices; `step.sh` logs every Claude skill call to runs/, so retrain as runs grow. The prompt format lives in `scripts/export_training.py` and `agent.py`, keep them identical.
Live test on a world copy through Ollama (adapter5): it ran, then looped on `inspect`; the repeat guard now retries once warm (temperature 0.8) before stopping. Not re-run since adapter7.

## Next
1. Train on the fp base, eval, export F16, then `agent.py --picker --model conveyer-picker` on Ollama (the picker prompt now carries the last skill call).
2. Raise accuracy: look at which skills it misses, add templates, add `runs/planner/` rows once we decide the model picks tiles, retrain, run gate.
3. Longer live test on a copy, then decide what the model owns.

Never join the server with a real Factorio client. Leave the loop and its background tasks alone.
