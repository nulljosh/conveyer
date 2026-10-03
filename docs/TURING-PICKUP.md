# Turing picker pickup (2026-10-02, 17:35)

Goal: Turing's own small model picks Conveyer's next skill, so we can run on ours instead of Claude. Honest scope: the model owns the opening and crash recovery. Late-game builds stay scripted in scripts/planner.py.

## Done
- Eval: `scripts/eval_picker.py` scores skill name, then params, on `data/valid.jsonl`. Every run appends to `eval/history.jsonl`; `scripts/bench_graph.py` redraws `eval/benchmarks.svg`.
- Split is by run file (`scripts/export_training.py`), so the score is honest. Plain Qwen2.5-0.5B: 1% skill, 0% params. LoRA 600 iters: 49% skill, 28% params, 100% valid JSON.
- Gate: `scripts/gate.sh [adapter]` fails if skill or params drop below `eval/baseline.json`.
- Train: `cd ~/Documents/Code/turing && DATA=$HOME/Documents/Code/conveyer/data LORA_ARGS="--batch-size 4" training/train_resilient.sh mlx-community/Qwen2.5-0.5B-Instruct-4bit conveyer-adapter2 600`. Eval needs Turing's venv python.
- Logging: `scripts/planner.py step` writes each decision (tile, stock, result) to `runs/planner/*.jsonl`. Not exported yet, on purpose.
- Live test passed on a copy of the world: `agent.py --picker --picker-url http://127.0.0.1:8081 --model <fused dir>` ran 6 steps, valid skills, a drill got placed. Serve with `cd ~/Documents/Code/turing && ./.venv/bin/python -m mlx_lm server --model /private/tmp/claude-loop/fused-conveyer --port 8081`. The copy ran as a second container on ports 27001 and 34198 with `FACTORIO_SERVER_PORT=27001`, never the real server.

## Broken
- GGUF: `training/export_gguf.py` output (Q8_0, F16 and BF16 all tried) answers with junk or an instant end token in llama.cpp and Ollama, while the same fused folder answers correct JSON in MLX. Not found yet. Ollama model `conveyer-picker` exists but is not trustworthy. Ruled out (2026-10-02 17:50): quantization (F16 and BF16 fail the same way as Q8_0), Metal (`-ngl 0` same), BOS handling, config and tokenizer values (look normal). Still open: a bad weight mapping in the converter, or the 4-bit base's tensors. Next probe: compare logits MLX vs llama.cpp on one prompt, check the tokenizer and the tied embedding.

## Next
1. Fix GGUF (above), then `agent.py --picker --model conveyer-picker` on Ollama.
2. Raise accuracy: look at which skills it misses, add templates, add `runs/planner/` rows once we decide the model picks tiles, retrain, run gate.
3. Longer live test on a copy, then decide what the model owns.

Never join the server with a real Factorio client. Leave the loop and its background tasks alone.
