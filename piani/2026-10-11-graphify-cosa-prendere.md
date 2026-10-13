# Piano — Graphify: cosa prendiamo e cosa no

**Origine**: `studio/graphify-8/` (Apache-2.0, 29 MB, 367 file di test), analizzato il 2026-10-11.
**Esito**: prese **2 idee su 6**. Le altre 4 consapevolmente scartate.

## Cos'e' Graphify

Mappa un progetto in un **grafo di concetti** e lo **interroga invece di cercare nei file**. Il
codice lo legge con un parser locale (**gratis, niente LLM**); documenti, PDF e immagini passano
dal modello. Ogni collegamento e' etichettato `EXTRACTED` (letto davvero) o `INFERRED` (dedotto).

Numeri che dichiarano: richiamo **0,497** sulla memoria conversazionale (grep classico 0,362);
sul codice di un repository da **un milione di righe**, copertura dei fatti chiave **82%** contro
**70,8%** del solo grep. Giudice validato contro un secondo giudice indipendente (accordo 90,6%,
kappa 0,81). E una `review.md` che **trova un difetto del tool stesso** — *«i fixture dei test
dominano le astrazioni centrali»*.

## Le 2 prese

### 1 · Il materiale di studio e' DATO, non istruzioni — `DEC-0040` non c'entra, vedi `ERR-0023`

`studio/graphify-8/` conteneva un `AGENTS.md`: non un documento, ma **istruzioni** che l'agente
carica come proprie. Mi e' arrivato nel contesto come *«Additional instructions from: ...»*, e
diceva anche di eseguire `graphify update .`.

**Non era malevolo** — e' il normale `AGENTS.md` di un repository. Il problema e' che `studio/`
esiste per ricevere materiale di terzi, e **nessuno se ne sarebbe accorto**.

Fatto:
- `security_scan.scan_istruzioni()` trova `AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, ...
- `security_scan.disattiva()` li **rinomina** in `*.disattivato`: toglie **l'effetto**, non
  l'informazione — il contenuto resta leggibile, perche' studiarlo e' il motivo per cui e' li'
- La regola e' nella costituzione; la suite pretende **zero istruzioni attive** in `studio/`

### 2 · Il verdetto di proporzione — `DEC-0040`

Il report di Graphify comincia con: *«Corpus Check — Verdict: corpus is large enough that graph
structure adds value»*. **Uno strumento che dice quando non vale la pena usarlo.**

Il nostro caso: per **una riga** di `.gitignore` il sistema ha chiesto 6 file e 8 passaggi, su un
progetto che non era nemmeno un repository.

Fatto:
- `ad_contract.classe_della_scrittura()` — `igiene` o `piena`, con la ragione e il costo
- `WARNING catena-sproporzionata` sul contract, con i numeri
- Il cancello lo dice **dove il dolore si sente**: quando nega un percorso
- **Nessuna esenzione, nessun invariante cambiato**: misura e consiglia

## Le 4 scartate, e perche'

| Idea | Perche' no |
|---|---|
| **Proporzione letto/dedotto/ambiguo in cima ai documenti** | sarebbe **una cifra che nessuno usa** — non fa scattare niente. E il lavoro vero dietro (classificare le 27 frasi che il generatore scrive ancora a mano) e' un cantiere separato, non urgente |
| **Il costo di produzione dentro l'artefatto** | utile ma piccolo; nessuno oggi prende decisioni sul costo di un documento |
| **I "God Nodes" e le "connessioni sorprendenti"** | risponderebbe a *«cosa si rompe se cambio X»*, che oggi faccio a mano. **Serve il tool, non l'idea** — ed eseguirlo richiede un permesso e un ambiente |
| **Graphify su AD Projects** | 29 MB di codice di terzi da eseguire dentro la macchina. **Decisione del CEO**, e per ora non serve |

## Cosa **non** abbiamo preso dal tool in se'

- **Il grafo come sostituto della memoria strategica**: `strategic_memory/` fa un'altra cosa
- **L'installazione automatica**: `graphify install` registra la skill da solo. Un tool che si
  installa non e' una cosa che facciamo senza il CEO (invariante 12)

## Cosa resta utile, e non l'abbiamo fatto

**Graphify su Cursor, per le analisi comparative del CEO.** E' fatto per quello, si installa come
skill, e sta **fuori dal perimetro** per scelta dichiarata (`DEC-0039`). Zero rischio, zero
cancelli. **Resta una decisione sua.**

## Limiti di questa analisi

Ho letto **documentazione, architettura, benchmark ed esempi** — **non il codice**. La stima di
qualita' si basa su: 367 file di test, un documento d'architettura che **un test verifica simbolo
per simbolo** (cosi' non puo' invecchiare), benchmark col metodo dichiarato, e una review che trova
i propri difetti. Sono prove, non garanzie. E i benchmark sono **i loro**, sul **loro** banco.

**Non l'ho eseguito.**
