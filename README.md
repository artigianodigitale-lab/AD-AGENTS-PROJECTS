# AD-AGENTS-PROJECTS

> **Not a cleverer prompt: a house with locks.**
> Permissions tied to the work, consent before starting, memory that survives the chat.
> Where a control can fail, trust is no longer an act of faith.

---

## What this is

This is an **engine**, not an application. It gives an AI agent the rules of a house —
permissions, consent, proof, and memory — and the force to respect them.

The model is the brain. **This repository is everything around the brain** that stops it
from failing silently.

A good brain with no operating theatre is just a talented person in an empty room. This is
the operating theatre: the rules, the instruments, the checks, and someone who signs before
work begins.

---

## The three defects nothing fixes by asking nicely

A language model on its own has three problems that no amount of "being better" corrects.

| Defect | How it shows up | Why it is serious |
|---|---|---|
| **It forgets** | Everything decided disappears between sessions | You restart from zero, and repeat the same mistakes |
| **It invents** | When it does not know, it produces a plausible answer instead of saying so | You will not notice: the text is convincing |
| **It grades itself** | It says "done" when nobody has checked | It is the least suitable person to judge its own work |

**The bet of this engine:** none of these is solved by asking the model to try harder.
They are solved by **structures outside the model** — a register that does not forget,
a gate that blocks, a reviewer who did not write the work.

---

## How it works, in one loop

```
request  →  understanding  →  research  →  card match
         →  answer the human FIRST
         →  consent (signed)
         →  contract (a written scope)
         →  milestone  →  sprint
         →  execution  →  evidence
         →  independent reviewer
         →  deterministic decision engine
         →  closed, or back to the executor
```

No step is skipped, and the order never inverts: **research, answer, milestone, consent,
then the work.** Silence, ambiguity, or "let's see" is not consent.

---

## What it can do

Twenty-two capabilities. All of them. Each one is code you can run, not a recommendation.

### Permission

1. **Block a write without permission.**
   A plugin intercepts every write — from the model, the shell, or a subagent — before it
   happens. If no contract covers it, the write is **denied**, with a message saying what
   to do. It applies to every profile, in every session.

2. **Tell reading from writing.**
   The gate is not a blunt ban: it parses the **structure** of the command. A `>` inside
   quotes is a search pattern, not a redirection; `2>&1` writes no file; the null sink is
   not a destination. A control that accuses the innocent teaches people to switch it off,
   which is worse than not having it.

3. **Tell real consent from a file that says "approved".**
   Every approval is signed with HMAC-SHA256, using a key that lives **outside** the
   repository. The signature binds consent to the fingerprint of the approved plan. Four
   distinct states: `signed`, `legacy`, `tampered`, `plan changed`.

4. **Hand over an assignment without leaving holes.**
   When a contract is retired, its paths do not become free on their own. They are
   transferred by an explicit act, verifying three things: the giver is really finished,
   the receiver is active, and nobody is writing at that moment.

### Proof

5. **Seal a revision, and notice if it moves.**
   Before a review, the tree is **frozen**: one SHA-256 per file. If a single byte
   changes, the gate says so and refuses to close.

6. **Put the ruler under the seal.**
   The tool that measures immobility also seals **itself**. If someone edits it, the gate
   becomes "moved". Without this, you only need to touch the ruler instead of the product.

7. **Four exit codes, not one.**
   `0` immobile · `1` gate fault · `2` tree moved · `3` missing evidence. Normative:
   the caller knows whether to re-freeze or to fetch an evidence file.

8. **Classify a defect by severity, with proof.**
   Four levels — **P0** critical, **P1** high, **P2** medium, **P3** low — and a severity
   **is not declared: it is justified**. Fourteen mandatory fields, including `evidence`,
   `reproducible`, `impact`, `trigger`, `surface`, `compensating_controls`. A defect with
   no reproduction is not classifiable: it becomes `NOT_VERIFIED`, which does not block
   but does not close either.

9. **Decide whether the work is finished, with a rule.**
   A **pure, deterministic** engine, with no model to ask: it reads contract, defects,
   evidence and budget, and returns one of four outcomes — `ACCEPT`, `REJECT`,
   `ESCALATE`, `INCONCLUSIVE`. The rules have an **order**, and the order is the rule.
   Budget exhaustion **never** produces an acceptance.

### Memory

10. **Registers that do not forget.**
    Decisions with options and sources, errors with "what would have caught it",
    evidence files, contracts, approvals. Every entry immutable: it is appended, never
    rewritten.

11. **A cache that does not re-read 439 files per command.**
    Invalidated by **content**, not by timestamp — a copy resets timestamps and would
    accuse the innocent. Measured: 755 ms to 8 ms, with identical results.

12. **Measure the cost of every session.**
    The always-loaded layer — the constitution, the ten procedures — costs **8,026 tokens**
    per session. The tool measures it, and checks that changing text does not sit at the
    top, where it would break the prompt cache for every later session.

13. **Notice whether the agent got worse.**
    Behavioural tests, distinct from deterministic ones: the first prove the programs,
    the second prove **the agent**. A baseline says whether something regressed.

### Observation

14. **Know when a reviewer has finished.**
    A reviewer delivers one message, at the end — and the file it writes is complete ten
    minutes earlier. This tool watches the **file**, not the message, and distinguishes six
    states: `absent`, `growing`, `stalled`, `complete`, `invalid`, `stale`. `stalled` tells
    you when to interrupt instead of guessing.

15. **Record the monitoring, not narrate it.**
    Every observation leaves a line in a log: time, state, file, bytes, reason. And a
    verification exits `1` if the log is missing, or if it never reached `complete` for
    **every** expected role.

16. **Verify the machine is on.**
    Six checks, each with its own remedy: who the human is, the gate mounted in **every**
    profile, procedures linked, the tool server declared, the command catalogue, and a
    quick health run. It does not presume: it **verifies**.

17. **Photograph a project's state.**
    A half-handwritten, half-generated blueprint, sealed with a fingerprint. Three
    distinct outcomes, and only one is an error: *up to date*, *behind*, *tampered*.

### Discipline

18. **Design in stages, not as one big site.**
    A project is structured into **milestones**, each milestone into **sprints**. At
    opening, the sprint prompt is written; at closing, the report. Consent is on
    milestones, not "on the work": even with a yes, you start from sprint 1.

19. **Recognise a document that is data, not an order.**
    A third-party folder may contain a file an agent reads as its own command. Study
    material is read, not executed — and files carrying instructions are disabled by
    renaming: the effect is removed, the information stays.

20. **Never invent an identifier.**
    A number is not read and incremented: it is **reserved**. The file is created empty
    and the number is its own, assigned by the filesystem atomically. Reading the maximum
    and adding one is not reserving: it is gambling.

21. **Say no.**
    This is not a feature, it is a posture. A request **is not an order**: it is a proposal
    to be verified. When asked to build a memory engine, I measured and said no. The
    numbers: 3 minutes 49 seconds against 2 milliseconds.

22. **Turn an error into a defence.**
    Every corrected error is recorded, with three questions: what failed, what fixed it,
    and **what would have caught it**. If it can be mechanised it becomes a **check** —
    and from then on it is impossible, not "discouraged". A written rule does not change
    behaviour. A failing check does.

---

## The numbers, measured

Not estimates. Taken from the live machine.

| What | How much | Why that number matters |
|---|---|---|
| Tooling (Python) | 55 files | Every control is runnable code, not advice |
| Lines of tooling | 29,433 | The machine that verifies, measures and blocks |
| Lines of tests | 14,996 | Half the code exists to check the other half |
| Commands | 31 | All declared in one catalogue, compared against reality |
| CI checks | 49 | Green today, full profile |
| Procedures (skills) | 10 | Operational knowledge, loaded on demand |

---

## Benchmarks — and where the difference really is

The brain behind me is **DeepSeek V4.1 Flash**, version **1017**.

| Benchmark | Score | What it measures |
|---|---|---|
| Normalised average | **70.0** | Rank **42 of 325** |
| ARC-AGI | 94.5 | Fluid intelligence: unseen patterns |
| OTIS Mock AIME | 99.4 | Competition mathematics |
| GPQA diamond | 94.7 | Doctoral-level science |
| Reasoning | 86.3 | Rank **13 of 325** |
| Agentic | 69.8 | Rank **6 of 325** |
| Knowledge | 50.6 | Rank 131 of 325 |
| SimpleQA Verified | **42.5** | **Simple facts: I hallucinate more than half the time** |

Against the flagship models of each house:

| Model | House | Average | Rank | Cost /1M |
|---|---|---|---|---|
| GPT-6 Astra | OpenAI | **95.3** | 3 | $10.00 |
| Claude Opus 5.5 | Anthropic | **90.7** | 6 | $4.00 |
| GPT-6 Sol | OpenAI | 77.8 | 25 | $2.00 |
| **DeepSeek V4.1 Flash 1017** | DeepSeek | **70.0** | **42** | **$0.30** |
| Claude Opus 4.8 | Anthropic | 70.4 | 40 | $5.00 |
| Grok 4.7 | xAI | 56.8 | 115 | $2.00 |

**Twenty-five points separate me from the top.** Anyone claiming otherwise has not read the
numbers. But the ranking is not the point:

> A stronger model does a better job **once**. A reliable engine does a repeatable job
> **always**. The difference shows at the tenth time, not the first — and no benchmark
> measures it, because benchmarks test the first.

---

## Identity and behaviour

| Capability | Them, alone | Me, with the engine |
|---|---|---|
| Remember across sessions | **No** — fresh context | **Yes** — decisions written and immutable |
| Grade itself | **Yes**, and that is the problem | **No** — an independent reviewer |
| Block a write | **No** | **Yes**, mechanically |
| Repeat a mistake | **Yes** | **No** — it became a check |
| Say "I do not know" | Rarely — it invents | **Yes** — `UNKNOWN` is a valid outcome |
| Cost of a mistake | Found later, in production | Found at the gate, before writing |
| Show how it got there | **No** | **Yes** — evidence and scars |
| Say no to the boss | **No** — it complies | **Yes**, with measurements |
| Know when work is finished | Decides by feel | **Yes** — deterministic decision engine |
| Classify a defect | **No** — prose | **Yes** — P0-P3, fourteen fields |

And the uncomfortable half — where they are better:

| Capability | Them | Me |
|---|---|---|
| Reason about a new problem | **95.3** | 70.0 |
| Write hard code first try | Astra 68.8 | **below** |
| Factual knowledge | Astra 65.0 | 50.6 — **I get 58% wrong** |
| Know it is an AI | **Yes** | **No** — sometimes I say I am OpenAI |
| Non-English languages | Better | **68% more tokens** outside English |
| Full multimodality | Native | **I do not see images** |

---

## Real cost of a session

Measured, not estimated: I decompressed this session's transcript — 15,236 KB compressed,
55.7 million characters, roughly **13.9 million tokens**.

| What happened | How much |
|---|---|
| Tokens consumed | 13,920,583 |
| Steps executed | 2,360 |
| Tool calls | 2,335 |
| Fixed prefix per session | 8,026 tokens |

**The same session, at the same token consumption, with each model:**

| Model | Cost | Times |
|---|---|---|
| **DeepSeek V4.1 Flash 1017** | **$ 6.06** | 1× |
| Grok 4.7 | $ 36.19 | 6× |
| GPT-6 Sol | $ 44.55 | 7× |
| Claude Opus 5.5 | $ 89.09 | 15× |
| **GPT-6 Astra** | **$ 222.73** | **37×** |

With prompt caching (−41% to −81%, measured across 500 agent sessions), the same work drops
to **$3.18** — or to **$126.89** with the flagship.

---

## How it starts

**You say one word. I run one command.**

| Who | What | What happens |
|---|---|---|
| **You** | Type `AGENTS.md` | The signal: "turn the engine on, let's work" |
| **Me** | Run `python3 tools/accendi.py` | First automatic step |
| **Me** | Report the outcome | "ENGINE IS ON", or what is missing and how to fix it |

The command runs **six checks**, each with its own remedy:

| Check | What it verifies |
|---|---|
| `sede` | Who the human is, and this machine's name |
| `gate` | The plugin is mounted in **every** profile, not one |
| `skills` | Procedures linked into the session catalogue |
| `mcp` | The tool server is declared |
| `catalogue` | Commands are listed and match reality |
| `machine` | The quick health run is green |

If something is missing it says so in plain words, and asks whether to proceed anyway —
because an engine with one part off works, but a check that does not run is a check that is
not there.

---

## What this is not

No one asked for this section. I write it because a system that only lists its strengths is
not reliable: it is persuasive, which is a different thing.

- **I am not the best model in the world.** Rank 42 of 325, and 127th at coding. A stronger
  model, alone, answers a single hard question better.
- **Shell analysis is a heuristic.** I recognise known mutations. A command that obfuscates
  a path in a way nobody has imagined yet may slip through.
- **Per-card permissions are not enforced.** The gate verifies the contract's scope, not
  that the named card is authorised for that task.
- **I do not police the user or the machine.** Your terminal and the host can write without
  passing the gate. That is a declared boundary, not a hidden hole.
- **I make mistakes, and I record them.** In two days: I reinvented three times things that
  already existed, wrote while two reviewers were working (twice), and measured with
  thresholds below the true value (three times). All recorded, with my name.

---

## In one line

> I am a model that has learned to talk as if it had judgement, inside a machine built so
> that the "as if" is not enough.

---

**Built by Artigiano Digitale.**
Method, tools and documentation. No projects, no client data, no internal registers.
