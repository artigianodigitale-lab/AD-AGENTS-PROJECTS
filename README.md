# AD-AGENTS-PROJECTS

**An engine that gives an AI agent the rules of a house — and the force to respect them.**

You link this folder to your program, type `AGENTS.md`, and from that moment the agent works
with permissions, consent, evidence and memory: not with good will.

It is not a longer prompt. It is a system that **installs itself**, and where it can, it
**blocks**.

> **This is the virgin version**: no projects, no project papers. It links to a program that
> knows how to read the rules, and from there you begin.

---


> **Italiano?** [Leggi questo documento in italiano](README.it.md).

## The job you hire it for

Not "an agent that writes code". The job is this:

> **Making an agent work on things that matter — money, clients, other people's data — without
> having to trust its good manners.**

It is a job of **trust**. And it is the only job where a prompt is not enough: a prompt is a
request, not a boundary. An agent that *should not* write to production is an agent that will
write to it, the day it seems like a good idea.

**Here the difference is one word:** elsewhere it is **advised against**, here — where a hook
exists — it is **impossible**. And where it is not impossible, **it is written that it is not**.

---

## What it can do

**Close the doors.** A write into a project folder without an active permission **is refused**,
and the refusal says **what is missing and how to fix it**. The permission is a file: it
declares who writes, where, and for which stage.

**Make a person decide before anything starts.** No work starts without the written consent of
whoever has the authority — and the order matters: **first the consent, then the permission**. A
backdated permission covers nothing, and the system notices by **reading the dates declared in
the documents**, not the file timestamps: a copy resets those, and a check that accuses
innocents teaches you to ignore it.

**Remember.** Every decision is a record with the options, **the sources** and — mandatory —
the entry *"do nothing"*. Every error is a scar with three questions: what failed, what fixed
it, and **what would have caught it**.

**Notice that it has got worse.** Seven behavioural tests run against a saved baseline and
answer one question only: **has anything got worse?** Updating it is a signature, not a button.

**Take a picture, and be unable to lie.** A project's entry document is half written by hand
and half **generated from the registers**, sealed with a fingerprint. The check tells **old**
apart from **fake** — two things that, without a seal, look alike.

**Check itself.** One command compares the written rules with what the system actually is:
skills, commands, steps, folders, documents. If the description diverges, **it says so** —
because an agent that reads a wrong description **follows that one**.

**Do the maths without spending.** Nineteen commands run the governance **without consuming
tokens**: they validate, verify, photograph, measure. Intelligence is used where it is needed.

---

## The proof, not the promise

Today's numbers, and they can be redone — they are in the repository:

| | |
|---|---|
| **464** deterministic checks | they run in a few seconds, without network |
| **36** gate checks | modes, path classes, failure outcomes |
| **19** commands · **9** procedures · **12** steps | the deterministic band and the process |
| **0** conflicting permissions | two contracts on the same path: none |
| **47 → 17** scars | **a register that gets shorter is becoming code** |

And the thing worth more than all of them, because it is the easiest to inflate and the hardest
to do:

> **Checks are verified by injecting the defect.** Not "the check exists": the check **breaks**
> when someone gets it wrong. A check that cannot fail is not a check — and here that is
> written down too.

---

## Who it is for

**These are hypotheses, not research.** It is the first thing this system teaches about saying
things: a person who has not been interviewed is an **invented person**, and must be declared
as such.

```yaml
- ipotesi: "Chi mette un agente su un lavoro vero ha gia' provato, e si e' spaventato almeno una volta"
  conferma_se: "su 8 persone, 5 raccontano un episodio preciso di scrittura indesiderata"
  smentita_se: "3 su 8 dicono di non aver mai avuto il problema"
  dati: nessuno          # <- nessuna intervista fatta: e' un'ipotesi, e lo dice
  validata: no
```

The comment inside the block is the whole point of this section: *no interview was done, so this is a hypothesis, and it says so.*

**Who is looking for it now:** whoever already has an agent working across several projects and
no longer knows what it has touched; whoever has to bring a collaborator — or an agent — into a
job with boundaries; whoever needs to tell someone else **why** something was decided.

**Who is not looking for it:** whoever wants an agent that does everything on its own. This
engine does the opposite: **it slows down where a decision has not been made**, and it is
designed for that.

---

## The space it moves in

It is not alone. Next to it there are serious things, and more mature ones:

- **Code assistants' permission systems** — they ask for consent at the moment. They are
  excellent where they are, but that consent holds **for one time only**: there is no memory of
  what was authorised yesterday.
- **Agent frameworks** — they orchestrate steps and tools. The boundary, though, is usually a
  **convention**: agents *should* respect it.
- **Evaluation platforms** — they measure whether the agent does a task well. Not whether it
  **has the right** to do it.
- **Corporate governance systems** — they exist, they are serious, and they do not talk to an
  agent.

**The empty place is the crossing**: a permission that **lives with the project**, a check that
**prevents** instead of advising, and a memory that survives the session.

---

## The positioning

> **For whoever puts an AI agent on a job that matters, AD-AGENTS-PROJECTS is the engine that
> turns rules into boundaries — because where a check is possible, discipline is no longer
> needed.**

**And the proof from the side of whoever uses it.** This is the part that matters, and the only
honest way to say it is to let it be read: look at what the engine answers to whoever tries to
write where they cannot. It does not say *"careful, you should not"*. It says:

```text
"IlMioProgetto" non e' una cartella di macchina, e non e' numerata.
**I progetti si numerano**: il numero e' cio' che dice al sistema che quella
cartella e' un prodotto — e quindi che va protetta con un permesso e
un'approvazione.
Rimedio: rinominala in **1. IlMioProgetto**. Il prossimo numero libero e' 1.
```

*(original in Italian)*

**A prohibition without the remedy is a dead end.** And what a system says when it stops you is
everything you need to know about how it was thought through.

---

## How it is used

```text
1.  Copia la cartella dove vuoi che viva il motore.
2.  Collegalo al tuo programma (DSH, Claude Code, Codex, Cursor...).
3.  Scrivi:  AGENTS.md
4.  Il motore dichiara come si comportera', e ti chiede:
        un progetto NUOVO      -> crea una cartella numerata col nome del progetto
        un progetto ESISTENTE  -> ne importa uno che hai gia', e lo sposta solo se glielo dici
5.  Lavora. Il motore si occupa dei permessi, delle prove e della memoria.
```

**If the program has a hook** (DSH, Claude Code, Codex, Antigravity), once only:

```sh
python3 tools/setup.py            # collega il cancello, la costituzione e le skill
python3 tools/setup.py --check    # e dimmi se e' a posto, senza scrivere niente
```

**If it does not have one** (Cursor, or any application): `AGENTS.md` **is the door**, and it is
enough to tell it to read it. **The rules travel; the gate does not** — see below.

**The first time** it asks two things: **what your name is** (it becomes the CEO, that is,
whoever approves) and the **permission to install** what is needed. Then it **proves** that the
gate blocks: it creates a project folder, verifies that the write **is refused**, and deletes it
even if something goes wrong.

**It does not declare itself installed: it proves that it refuses.**

---

## What is inside

| | |
|---|---|
| `AGENTS.md` | **the door**: it is the constitution, and it is the file the program reads by itself when you link the folder |
| `.brain/` | the brain: constitution, 9 procedures, the plugin that blocks writes |
| `tools/` | **19 commands**, which work without consuming tokens |
| `sede.yaml` | **who the CEO is** and **where the projects are** (not versioned: it is yours) |
| `contratti/`, `approvazioni/` | the register of authorisations |
| `DECISIONI/`, `errori/`, `drift/`, `piani/` | the memory |
| `milestone/`, `orchestrazione/` | the templates and the operational view |

## What is portable, and what is not

Verified on 2026-10-13, **actually moving the engine** and running everything from there.

| | Portable? |
|---|---|
| The **rules** | **yes, always** — they are a document the program reads |
| The **commands** | **yes, always** — anyone with Python can run them |
| The **registers** | **yes** — they are files |
| **Web research** | with SearXNG: it is a service, not a file |
| The **gate that blocks** | **only if the program calls it.** It is a plugin, and it lives in the program's profile |

> **The difference between "advised against" and "impossible" is everything this system has
> learned. It is not deleted to keep a table happy.**

## Seeing the gate in action

The permissions in this folder are **all closed**, and that is deliberate: *an open permission
in a copy is not an example, it is a permission* — it would give authority over the seat the
copy comes from. The gate is demonstrated **by creating the permission at the moment**. Two
files, ten lines, and you can see it.

```text
# 1. senza permesso: rifiutato
$ python3 tools/contract_scope.py check ".brain/COSTITUZIONE.md"
".brain/COSTITUZIONE.md" e' un artefatto di GOVERNANCE (.brain/), non una cartella prodotto.
Rimedio: un contract con write_scope che includa ".brain/" e il marcatore
approvazioni/<task_id>.yaml approvato dal CEO
[exit 1]

# 2. il CEO approva, e si scrive il permesso
$ cat > approvazioni/societa/DEMO-001.yaml <<'FINE'
task_id: DEMO-001
approvato_da: CEO
data: "2026-10-13"
FINE
$ cat > contratti/societa/DEMO-001.yaml <<'FINE'
task_id: DEMO-001
status: active
aperto: "2026-10-13"
write_scope:
  - ".brain/"
FINE

# 3. e adesso passa
$ python3 tools/contract_scope.py check ".brain/COSTITUZIONE.md"
OK   .brain/COSTITUZIONE.md — coperto dal contract DEMO-001 (DEMO-001.yaml),
     approvato da CEO il 2026-10-13

# 4. ma se il permesso e' RETRODATATO, non copre
$ sed -i 's/2026-10-13/2026-10-11/' contratti/societa/DEMO-001.yaml
$ python3 tools/contract_scope.py check ".brain/COSTITUZIONE.md"
Il contract DEMO-001 e' stato scritto PRIMA dell'approvazione (2026-10-13).
L'ordine e' ricerca -> risposta -> consenso -> contract: un contract retrodatato non copre.
```

**The fourth step is the reason this demonstration exists.** Writing it, on 2026-10-13, it
answered **OK** where it should have answered **NO** — because the condition of the order was
**inverted**. On the machine this copy comes from it was not visible: real permissions have
consent and opening **on the same day**, and the defect stayed hidden. See `ERR-0052`.

> **A test that passes does not prove that the rule is right: it proves that the code does what
> the code does.** If the test is written by looking at the code, the defect is invisible.

## What is missing — to be read before trusting it

The engine **declares its own limits**, and this section is not a formality: a system that hides
what it cannot do is a system you cannot trust on anything else.

1. **The gate is not acquired: it is installed.** Linking the folder gives you **the rules**;
   for the gate that **blocks** you need `setup.py`, once. Where the program has no hook, **it
   is said** that there is none.
2. **The adapters for other programs are declared, not tested.** Claude Code, Codex and
   Antigravity are not on this machine, and **it is not said that they work**.
3. **Consent is enforced only if someone runs the validator.** The gate blocks *writes*, not
   the absence of consent: it is a divergence that is **declared**, not hidden.
4. **The analysis of shell commands is a heuristic.** A command that changes folder and then
   writes with a relative path can slip past it. The reliable boundary remains the written
   permission.
5. **Web research wants SearxNG**, which is a local service: without it, the engine reads only
   the addresses you give it.
6. **The suite stops on a freshly downloaded engine.** Some tests presuppose that the world
   exists. It is a defect that is **declared** with its fix (`errori/ERR-0049`).
7. **The register of scars is curated, not complete.** And it says so.

**In one line**: the engine works on its own, and the two things it does not do on its own are
**installing itself** and **working on a program without a hook**.

---

## Why it is built this way

It was born in **five days**, and the shape of the curve is not random:

| Day | Records | Scars | |
|---|---|---|---|
| 08/10 | 27 | 6 | the governance |
| 10/10 | 11 | 10 | the brain |
| **11/10** | 14 | **25** | **the worst day** |
| 12/10 | 0 | 3 | the projects |
| 13/10 | 4 | 4 | portability |

**Twenty-five scars in one day**, almost all of the same family: *something written by hand that
could have been checked*. And the record template followed **3 times out of 36**, because nobody
verified it.

From there comes the rule that governs every new piece:

> **If you can mechanise it, do it now. Otherwise write why you cannot.**

**And the rule applies to itself too**: the register of scars **has got shorter** when its
entries became checks. **A register that gets longer is a register that is not becoming code.**

---

## The documentation

| File | What it contains |
|---|---|
| **[GRAFO.md](GRAFO.md)** | **seven diagrams** that explain how it works; GitHub draws them by itself. Start here |
| **[DOCUMENTAZIONE-TECNICA.md](DOCUMENTAZIONE-TECNICA.md)** | **for developers**: architecture, authorisation model, the gate, the 19 commands with their exit codes, the data model, the testing strategy — **and the divergences found** |
| **`AGENTS.md`** | the door: it is the constitution |
| **`.brain/`** | the constitution, the 9 procedures, the plugin |
| **`tools/README.md`** | the **register**: the only place where the commands are declared |

**Three things this system demands of whoever reads it, and keeps on itself:** every statement
has a verification; every limit is declared; every number can be redone.

---

## Credit

**Conceived and created by Luca / Artigiano Digitale.**
Built **with** the [DeepSeek Harness](https://github.com/deepseek-ai) (DSH, MIT): the credit for that part stays with its authors, and it is written in the `NOTICE` file.

The project is open to the world: **[CONTRIBUTING.md](CONTRIBUTING.md)** is the door. You do not need to know the code — the system gives you the document to fill in.

## Licence

**Apache-2.0.** The engine was born inside the *DeepSeek Harness* (DSH), which is **MIT**: the
credit for that part remains its own, and it is written here.

---

> **A written rule does not change behaviour. A check that fails does.**
>
> Everything else in this repository is the consequence of that sentence.
