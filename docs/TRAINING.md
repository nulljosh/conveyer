# Training a model on Conveyer

Same recipe as Turing's hands-adapter. A small base model, LoRA, one job: pick the next skill.

## What it learns

Not code. Small models fail at writing raw Factorio code, so the model never writes any. It reads the last observation and answers with one skill and its parameters as JSON. `skills.py` does the rest.

## The data

`runs/*.jsonl` holds every skill call the agent has made: observation, skill, params, result. `scripts/export_training.py` turns the successful calls into chat examples and writes `data/train.jsonl` and `data/valid.jsonl`. Failed calls are dropped. Right now that is 819 train and 90 valid.

The planner's decisions (which tile to build, when to feed a chest) are not in `runs/`. They are deterministic Python in `scripts/planner.py`, so there is nothing to learn there. The next data to log is the planner's chosen tile and the stock that led to it.

## Train

```bash
python3 scripts/export_training.py
mlx_lm.lora --model Qwen/Qwen2.5-0.5B-Instruct --train --data data --iters 600 --batch-size 4 --adapter-path conveyer-adapter
```

Any LLM that takes chat JSONL works the same way: Llama 3.2 1B, Qwen3 0.6B, Gemma. Swap `--model`.

## Check it

Hold out `data/valid.jsonl`. Score the exact skill name first, then the parameters. Beat the plain base model before trusting it, and run it against the live server before it plays on the real save.

## First result (2026-10-05)

Qwen2.5-0.5B-Instruct, LoRA, 600 iterations, batch 4, 681 train and 77 valid examples. `python3 eval/score_adapter.py` (run it from the repo root, not `scripts/`, which has a `queue.py` that shadows the stdlib):

| | skill name | name and params |
|---|---|---|
| base model | 1/77 (1%) | 0/77 |
| LoRA adapter | 59/77 (77%) | 56/77 (73%) |

It beats the base model by a wide margin. Not yet run against the live server, so it does not play the real save. Next: look at the 18 misses, then more runs for data.

## Export

`mlx_lm.fuse --dequantize`, then llama.cpp's `convert_hf_to_gguf.py` to Q8_0, as in Turing's `training/export_gguf.py`. That gives a GGUF that runs anywhere.

## Limits

About 900 examples is thin. The mix skews to early game (find, mine, craft). Late-game builds are scripted, so the model would only help with the opening and with recovery after a crash. More runs mean more data.
