# PolicyBridge: Questions and Results

This folder contains the questions we asked PolicyBridge about Seattle-area regulations, the answers every system produced, and how each answer was judged. It is published so anyone can read the actual questions and check the answers for themselves.

Each round is a separate file. Every entry shows the question, the verified reference answer, and each system's answer with its verdict.

## The systems compared

- **PolicyBridge**: the retrieval-augmented system (hybrid search over the regulatory corpus plus a citation graph). Later rounds run it with two answer models, GPT-5.1 and GPT-5.5.
- **Vanilla vector RAG**: a plain vector-search RAG over the same documents, no graph (early rounds).
- **ChatGPT**: the public ChatGPT answering from its own knowledge, no access to the document corpus.

## Rounds

| Round | Questions | What it looks at | File |
|---|---|---|---|
| 1 | 71 | First three-way run, LLM-judged 1-5 | [round_1.md](round_1.md) |
| 2 | 120 | Expanded three-way run, LLM-judged 1-5 | [round_2.md](round_2.md) |
| 3 | 35 | Cross-agency questions, six difficulty levels, four arms | [round_3.md](round_3.md) |
| 4 | 45 | Single-fact questions, deterministic scoring | [round_4.md](round_4.md) |

## Headline numbers

**Round 1** (mean correctness, 1-5 scale)

| System | Correctness | Faithfulness |
|---|---|---|
| PolicyBridge | 3.46 | 3.83 |
| Vanilla vector RAG | 2.99 | 3.38 |
| ChatGPT | 2.30 | 1.65 |

**Round 2** (mean correctness, 1-5 scale)

| System | Correctness | Faithfulness |
|---|---|---|
| PolicyBridge | 4.39 | 4.19 |
| Vanilla vector RAG | 3.96 | 4.00 |
| ChatGPT | 2.72 | 3.01 |

**Round 3** (numeric answer correct, out of 33)

| System | Correct |
|---|---|
| PolicyBridge (GPT-5.1) | 23 |
| PolicyBridge (GPT-5.5) | 25 |
| ChatGPT (no system prompt) | 24 |
| ChatGPT (with system prompt) | 26 |

Round 3 is the hardest set (cross-agency, multi-level), and on the pure numeric-correctness measure the public ChatGPT was competitive. The full round_3 file also flags fabricated citations, where the grounded systems differ from a model answering from memory.

**Round 4** (single-fact, deterministic scoring, out of 45)

| System | Correct |
|---|---|
| PolicyBridge (GPT-5.1) | 39 |
| PolicyBridge (GPT-5.5) | 39 |
| ChatGPT (standalone) | 31 |

## How to read a verdict

- Rounds 1-2 use an LLM judge that scores each answer 1-5 on correctness (does it match the verified answer) and faithfulness (is it grounded in the cited text).
- Rounds 3-4 score the numeric or factual value directly. Round 4 uses a deterministic check: the answer is correct only if it states the verified value.

The reference answers are traceable to specific sections and pages of the source regulations.
