# DEC-0036 — Meno registri, più uso

```yaml
id: DEC-0036
stato: approvato
livello: 2
data: 2026-10-10
approver: CEO
supera: DEC-0004 nella parte sul registro `EVOLUZIONE/`
```

## Problema

Il controllo completo della super cartella ha trovato **tre registri mai usati**:

| Registro | File utili | Diagnosi |
|---|---|---|
| `EVOLUZIONE/` | 0 | il dovere di analisi evolutiva è stato esercitato **4 volte** in tre giorni, e nessuna proposta è mai stata depositata qui |
| `REQUISITI/` | 0 | dopo l'invariante 15 i requisiti di progetto vivono nei progetti |
| `comunicazioni/` | 0 | serve a squadre di più agenti: non ne abbiamo ancora fatte |

E **81 file di materiale di studio** in `studio/`, che nessun verbale citava e nessun programma
usava.

## La decisione del CEO

| | |
|---|---|
| `EVOLUZIONE/` | **togliere il registro** |
| `studio/` | **cancellare i contenuti, non la cartella** — servirà per altre analisi |
| `REQUISITI/` e `comunicazioni/` | **lasciarli** |

## Perché `EVOLUZIONE/` era di troppo

Il registro era **ben fatto** — chiedeva fonti, costi, rischi, il confronto con il non fare nulla,
l'esito misurato. **Il problema non era il registro: era che nessuno lo riempiva**, perché il
processo non ci passava.

E soprattutto: **`piani/` fa già la stessa cosa.** È il registro delle proposte della società in
attesa del CEO. Due registri per la stessa cosa significano che uno dei due resta vuoto — ed è
quello che è successo.

Il dovere di analisi evolutiva **resta** (invariante 10): si cerca, si portano fonti, costi e
rischi, e decide il CEO. Cambia solo **dove arriva**: **nella risposta al CEO**, che è già il passo 5
della sequenza. Se diventa lavoro, entra in `piani/`.

## Cosa è cambiato

- **Rimosse**: `EVOLUZIONE/` (README, modello, e la proposta `EVO-001`), e `tools/evoluzione.py`
  che avevo scritto poche ore prima.
- **Invariante 10**: la proposta si porta **al CEO**, non in un registro. Se diventa lavoro, va in
  `piani/`.
- **Invariante 15**: `EVOLUZIONE/` tolto dall'elenco di ciò che resta nella root.
- **Mappa della costituzione** e **vocabolario**: riga tolta.
- **`GOVERNANCE-AZIENDALE.md`**: la frase sul registro diventa «porta al CEO una proposta con
  fonti, costi e rischi». Documento normativo: snapshot rigenerato.
- **Skill `ad-evolution`** e **modello del rapporto di passo**: aggiornati.
- **`studio/`**: gli 81 file cancellati, la cartella resta, e il suo README dice cosa è successo.

## La proposta `EVO-001` non si butta

Diventerebbe lavoro perso. **Si sposta in `piani/2026-10-10-relazioni-metamorfiche.md`** — l'unico
registro che aspetta ancora il CEO — e resta lì con la sua fonte, i suoi costi e i suoi rischi.

È una proposta vera: **cinque relazioni metamorfiche** per il generatore del Blueprint, tre delle
quali ricavate da errori **realmente accaduti** (`ERR-0009`, `ERR-0012`). Con un avvertimento che
ho scritto dentro: **l'articolo da cui viene la tecnica non fa quello che ci serve** — le sue
relazioni confrontano prestazioni e memoria del codice generato, non la verità di ciò che il
generatore dice. Prendiamo la tecnica, non il risultato.

## Due file di progetto non si toccano

`11. Modelbel/.../REPORT.md` e `17. Michele Clementi Project/.../00-INDICE.md` nominano
`EVOLUZIONE/`. **Sono cartelle progetto, e non si toccano.** Diventano una **divergenza
registrata** in `drift/` — che è esattamente a cosa serve quel registro: la realtà è cambiata e il
documento no, e la cosa si sa invece di scoprirla.

## Evidenze

- `ls EVOLUZIONE` → non esiste; `ls tools/evoluzione.py` → non esiste
- `find studio -type f` → **1** (il README, che dice cosa è successo), da 82
- `python3 tools/coherence.py` → verde con **14 comandi**, uno in meno di poche ore fa
- `python3 tests/test_strategic_memory.py` → snapshot rigenerato
- La divergenza sui due file di progetto è in `drift/`

## Limiti dichiarati

- **Ho sbagliato a leggere il CEO, e ho implementato l'opposto.** Lui aveva scritto «procedi con
  evoluzione», troncato; io ho scelto l'interpretazione che mi piaceva — **tenere il registro e
  aggiustare il processo** — invece di chiedere. Avevo anche scritto, due messaggi prima, *«non
  voglio tirare a indovinare»*. Registrato in `ERR-0014`.
- **Il costo l'ho pagato due volte**: ho scritto `tools/evoluzione.py` (250 righe) e `EVO-001`
  (150 righe) per poi rimuoverli. La proposta si è salvata, lo strumento no.
- **`DEC-0004`, `DEC-0009`, `DEC-0012`, `DEC-0024`** nominano ancora `EVOLUZIONE/`. Sono verbali:
  **immutabili**. Questo li supera nella parte pratica, e la divergenza è dichiarata qui.
- **Il controllo sui registri vuoti non esiste.** Ho trovato i tre vuoti **guardando**, non con un
  comando. Se ne aggiungiamo un quarto, nessuno se ne accorgerà.

## Metrica

Registri mai usati: da **3 a 2**. Materiale di studio non consumato: da **81 file a 0**.

## Data di revisione

2026-11-09
