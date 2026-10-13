# STATO OPERATIVO

Vista umana dello stato. Non viene caricata automaticamente nel contesto del modello.

**La parte sopra il marcatore la scrive una persona. La parte sotto la genera
`tools/stato.py` leggendo i registri**, e il controllo la rigenera e confronta: dice
**aggiornato**, **indietro** (autentica ma di registri piu' vecchi) o **manomesso**.

<!-- generato:inizio -->
> **Vista generata dai registri.** impronta: `618660873ef8`
> Il controllo la rigenera e confronta. **Autentica non vuol dire giusta**: il sigillo protegge dall'alterazione, non dall'errore.

## Permessi attivi

**Nessuno.** Nessun lavoro e' aperto: ogni scrittura su un progetto e' bloccata.

## L'agente si comporta come deve?

| | |
|---|---|
| Prove comportamentali | **7/7** |
| Errori registrati | 20 |
| Trovati da un **controllo** | 5 |
| Trovati per **fortuna** | 9 |

*equilibrio: meta' controlli, meta' fortuna*

## Cosa aspetta una decisione

- Discrepanza aperta **DRIFT-002** (MEDIUM) — Il campo `product` elenca 3 prodotti, le cartelle numerate sono 17
- Discrepanza aperta **DRIFT-005** (LOW) — I contatori del pack sono superati
- Discrepanza aperta **DRIFT-009** (LOW) — I contract del 2026-10-08 non soddisfano l'invariante 13
- Discrepanza aperta **DRIFT-018** (HIGH) — Cinque permessi sullo stesso percorso: un percorso senza titolare
- Discrepanza aperta **DRIFT-019** (LOW) — Un permesso scaduto resta scritto come attivo
- Errore aperto **ERR-0018** — Al revisore indipendente del gate QA ho passato come «fonte» la trascrizione delle risposte di Michele, e dentro quella 
- Errore aperto **ERR-0019** — Ho aperto un passo con `milestone.py new-sprint ... 2`, indicando la tappa 2 — ma la tappa 2 era stata **aperta e chiusa
- Errore aperto **ERR-0028** — Mentre i due gate verificavano il report dello sprint 1 di Marketing Factory, **io ho modificato quel report**: ho aggiu
- Errore aperto **ERR-0029** — `tools/ricerca.py`, riga 256: `print(esito.get("testo", "")[:4000])`. La via a riga di comando **tronca in silenzio il t

## Gli ultimi lavori chiusi

Nessun passo chiuso in nessun progetto.

## I numeri

| Cosa | Quanti |
|---|---|
| Verbali (Decision Record) | 34 |
| Discrepanze registrate | 10 |
| Errori registrati | 20 |
| Skill del cervello | 9 |
| Comandi nella fascia deterministica | 18 |
| Progetti | 0 |

Generato da `tools/stato.py`. **Non si modifica a mano**: il controllo rigenera e confronta, e un testo che non corrisponde al proprio sigillo e' **manomesso**.
<!-- generato:fine -->
