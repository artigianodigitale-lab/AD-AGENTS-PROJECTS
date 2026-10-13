# DEC-0039 — Cursor non è una superficie da mettere sotto cancello

```yaml
id: DEC-0039
stato: approvato
livello: 3
data: 2026-10-11
approver: CEO
supera: DEC-0038 nel punto 2 e nella parte Cursor
```

## Problema

`DEC-0038` (2026-10-10) approvava di mettere **Cursor in sola lettura** con un gancio di blocco
`.cursor/`, sulla base di un fatto verificato: Cursor era in esecuzione e non passava dal cancello.

Il CEO ha chiarito il 2026-10-11:

> *«riguardo a Cursor è ovvio che se lo lancio io riesce a entrare ovunque bypassandoti, quindi non
> è un problema. Se lo lancio è solo per un analisi comparativa, non lo farò lavorare a nessun
> progetto, a meno che non mi serva»*

## L'analisi era sbagliata di framing, non di fatto

Il fatto è vero: Cursor **può** scrivere, e non passa dal cancello. Ma non è una **falla**: è **il CEO
che lo lancia**. Un controllo che deve difendere il sistema **dal suo proprietario** non è un
controllo: è teatro.

La distinzione che mancava:

| | |
|---|---|
| **Superficie di esecuzione** | un agente che lavora **da solo**, e che va autorizzato — è DSH |
| **Strumento di lettura** | un programma che il CEO apre **per guardare** — è Cursor |

Mettere un cancello sulla seconda significa **costruire una difesa contro chi ha già le chiavi**, e
il costo è un gancio da mantenere per sempre.

## Opzioni

1. **Costruire il gancio `.cursor/`** — come da `DEC-0038`. Conseguenza: Cursor non può mutare.
   Costo: un file di configurazione, e la manutenzione di un blocco su una superficie che **non si
   usa per scrivere**. Rischio: **un falso senso di sicurezza** — il gancio è aggirabile da chi
   lancia Cursor, cioè dal CEO, cioè da chi il gancio vorrebbe fermare. Fonte: [Microsoft
   agent-governance-toolkit](https://github.com/microsoft/agent-governance-toolkit), che mette i
   verdetti nel **runtime che esegue**, non nello strumento che legge.
2. **Non costruirlo, e dire la verità nei documenti** — `MODEL-ROUTING.md` smette di dire «Cursor
   non in uso» (falso) e dichiara cosa è: **uno strumento di analisi comparativa che il CEO apre, in
   sola lettura per scelta, fuori dal perimetro dell'enforcement — deliberatamente**. Costo: una
   riga. Rischio: nessuno, perché **non promette niente**. Fonte: [arXiv 2608.16891, *Runtime
   Governance for Agentic AI*](https://arxiv.org/abs/2608.16891), dove il runtime che governa è
   quello che **esegue**, non ogni superficie che tocca i file.
3. **Non fare nulla** — `MODEL-ROUTING.md` continua a dire «Cursor — non in uso» mentre Cursor gira.
   Conseguenza: un documento normativo **afferma il falso**, e chi lo legge per orientarsi sbaglia.
   Il costo non è di sicurezza: è che **la mappa non corrisponde al territorio**, ed è la cosa che
   questo sistema combatte da quando esiste `drift/`.
4. **Estendere il cancello a Cursor** — respinta per la ragione dell'opzione 1, e perché `DEC-0038`
   l'aveva già scartata: due host da mantenere allineati.

## Evidenze

- Due processi Cursor in esecuzione (PID 61925, 61931) — **verificato**, e non è un problema
- `MODEL-ROUTING.md` riga 30: *«Cursor (IDE) — **non in uso**»* — **falso**
- `.cursor/` assente nel progetto; `~/.cursor/` presente con `plugins/` e `skills-cursor/`
- `DEC-0038` punto 2 e punto 6: la parte Cursor, ora superata

## Scelta

**Opzione 2 — non costruirlo, e dire la verità.** Approvata dal CEO il 2026-10-11.

- **`.cursor/` non si crea.** Non c'è nessun gancio da mantenere
- **`GOV-001` perde `.cursor/` dal `write_scope`**: non c'è niente da scrivere lì
- **`MODEL-ROUTING.md`** dichiara Cursor per quello che è: strumento di analisi del CEO, in
  lettura, **fuori dal perimetro dell'enforcement per scelta** — non per dimenticanza
- **Il resto di `DEC-0038` resta**: fail-closed selettivo, falsi allarmi, ordine di P0, `GOV-001`
- **Una cosa di `DEC-0038` si conferma**: il fatto che quella proposta sia stata **scritta da
  Cursor** resta la prova che uno strumento di lettura può produrre lavoro utile. Non serve
  bloccarlo: serve **dichiararlo**

## Conseguenze

- **P0 perde una voce** e si accorcia: `1` falsi allarmi (fatto) → `2` fail-closed selettivo →
  `3` suite e documentazione → **la parte Cursor si riduce a `MODEL-ROUTING` vero**
- **`GOV-001`** aggiornato: via `.cursor/`
- Il piano in `piani/` aggiornato
- **Nessun gancio su Cursor**, e nessuna promessa: chi legge `MODEL-ROUTING` sa che l'enforcement
  vale su DSH

## Metrica

`MODEL-ROUTING.md`: **zero affermazioni false** sulla superficie. Ganci da mantenere su Cursor:
**zero**.

## Data di revisione

2026-11-09

## Esito misurato

<Da compilare il 2026-11-09: se qualcuno ha provato a lavorare da Cursor, e se `MODEL-ROUTING`
descrive ancora la realtà.>
