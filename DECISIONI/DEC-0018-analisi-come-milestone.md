# DEC-0018 — L'analisi di un progetto è una milestone, non un piano

```yaml
id: DEC-0018
stato: approvato
livello: 2
data: 2026-10-08
approver: CEO
supera:
```

## Problema

Il 2026-10-08, sul progetto `3. AD-Marketing-Factory`, l'analisi ha prodotto una risposta e poi — con il consenso del CEO — **lavoro diretto**. Sono nati tre contract scollegati (`SEC-001`, `FIX-001`, `SEC-002`) e nessuna milestone.

Non e' cio' che il sistema prevede. `milestone/`, la skill `ad-milestone` e i passi 8-9 di `ad-kickoff` esistono da ieri. Ma **non sono mai stati usati, e la causa non e' una dimenticanza**.

## Evidenze

Due sequenze, e non dicono la stessa cosa:

| Livello | Caricamento | Passi |
|---|---|---|
| `.brain/COSTITUZIONE.md` → `~/.dsh/AGENTS.md` | **sempre**, ogni sessione | 10 — **senza** milestone |
| `.brain/skills/ad-kickoff/SKILL.md` | a chiamata | 12 — **con** `ANALISI DI AVVIO` e `MILESTONE` |

Nella costituzione la parola «milestone» compare **due volte**, e in nessuno dei due casi come passo obbligatorio: `milestone/` in una tabella di cartelle, e `python3 tools/milestone.py check` fra gli strumenti. La sequenza che il cervello segue davvero e':

```text
6 CONSENSO → 7 PIANO → 8 CONTRACT → 9 ESECUZIONE
```

**Causa prima**: il sistema milestone e' stato collocato nel livello che si carica **a chiamata** invece che nel livello che si carica **sempre**. Il testo che decide e' quello gia' in memoria, non quello che bisognerebbe andare a leggere.

**Causa seconda, e piu' profonda**: il consenso e' stato interpretato come autorizzazione a **lavorare**. Anche con il consenso del CEO, il lavoro non doveva iniziare: il consenso doveva essere sulle **milestone**. L'oggetto del consenso era sbagliato.

## Scelta

Tre livelli, in ordine di forza crescente.

**1 · Costituzione** — la sequenza passa a 12 passi, con `ANALISI DI AVVIO`, `MILESTONE`, `SPRINT` nel livello che si carica sempre. Necessario, ma **debole**: questa giornata ha dimostrato che il testo da solo non vincola.

**2 · Invariante 13** — *«L'analisi di un progetto produce una milestone con i suoi sprint, non un piano di lavoro. Nessuna scrittura in un progetto prima che lo sprint sia aperto con il suo `PROMPT.md` e le milestone siano approvate dal CEO.»* Citabile dai contract, ma ancora testo.

**3 · Il meccanismo** — **l'unico che lega.** Un contract con `write_scope` su una cartella progetto **deve** dichiarare `milestone` e `sprint`, e il `PROMPT.md` di quello sprint **deve esistere**. Il validatore emette violazione altrimenti.

La conseguenza e' che il percorso **non si puo' imboccare al contrario**: non si apre un contract su un progetto senza aver scritto il prompt dello sprint, e non si scrive il prompt senza aver creato la milestone, perche' `milestone.py` rifiuta di aprire uno sprint in una milestone inesistente.

E' lo stesso principio che ha chiuso il buco in `.brain/`: la regola si sposta dalla prosa al validatore.

**4 · `ad-kickoff`** — il passo del consenso cambia oggetto: *«il CEO approva le milestone»*, non *«il CEO approva il lavoro»*.

## Conseguenze

- Una lavorazione su un progetto entra nella **storia del progetto** come sprint di una milestone, invece di restare un intervento isolato. I tre contract di oggi sarebbero stati tre sprint di una milestone «Igiene e sicurezza del prodotto», con un report che racconta come e' andata.
- Vale anche per le sanatorie di un solo file: non e' un peso, e' la documentazione che si vuole.
- Il validatore **rifiuta** un contract di progetto senza sprint aperto. Verificato con un test negativo.
- Documento normativo cambiato (`TASK-CONTRACTS.md`) e costituzione cambiata: snapshot rigenerato.
- **Limite dichiarato**: il controllo verifica che il prompt dello sprint **esista**, non che sia sensato. Uno sprint mal tagliato passa. La qualita' della pianificazione resta una responsabilita' umana, verificata dal CEO.
- **Limite dichiarato**: il meccanismo lega i contract, non i pensieri. Un agente puo' ancora leggere il codice di un progetto senza aprire una milestone — la lettura non richiede autorizzazione. Cio' che diventa impossibile e' **scriverci**.

## Metrica

Contract su progetti aperti senza milestone o sprint: atteso zero. E sprint chiusi con report, sul totale degli sprint aperti: atteso 100%, oggi 0 su 0.

## Data di revisione

2026-11-07
