# DEC-0030 — Il Blueprint

```yaml
id: DEC-0030
stato: approvato
livello: 2
data: 2026-10-10
approver: CEO
supera:
```

## Problema

Per capire a che punto e' un progetto servivano cinque o sei file: l'indice, l'analisi, i
requisiti, i rapporti delle tappe, i permessi, le discrepanze. E quando una sessione riparte da
zero — succede sempre — quel lavoro si rifa' ogni volta.

Ma un riassunto **scritto a mano** sarebbe stato peggio del problema: la **seconda verita'** del
progetto, la cosa che si allontana piu' in fretta perche' nessuno la rilegge. E la prova che
questo rischio e' reale l'abbiamo in casa: `comunicazioni/` e `REQUISITI/` sono **due registri
progettati, mai usati, oggi vuoti**.

## Scelta

Il Blueprint ha **due parti**:

| Parte | Chi la scrive | Quando |
|---|---|---|
| **Cos'e' il progetto, per chi** | una persona | una volta sola, e non si rigenera |
| **Tutto il resto** — a che punto e', la storia, chi puo' scrivere, le prove, cosa non torna, i verbali, dove sta cosa | `tools/blueprint.py` leggendo i registri | a ogni cambiamento |

E il pezzo che rende la cosa seria: **`blueprint.py check` rigenera la parte generata e
confronta.** Se qualcuno la modifica a mano, o se non e' aggiornata dopo un cambiamento,
**e' un errore**.

**Il Blueprint non puo' mentire.** Non per disciplina: perche' e' impossibile.

## Evidenze

- `tools/blueprint.py` — 3 comandi (`render`, `check`, `show`); il generatore e'
  **deterministico** (nessuna data, nessun ordine casuale: altrimenti il controllo griderebbe a
  ogni esecuzione, e un controllo che grida sempre non lo guarda piu' nessuno).
- Test della suite: da **183 a 193 controlli**. Fra questi, la prova che il Blueprint **mente
  davvero**: gli si inserisce una riga falsa e il controllo la trova.
- **Primo Blueprint vero** generato su `3. AD-Marketing-Factory` (tappa 2, passo 1, `ORD-004`),
  gate **ACCEPT** prodotto da `review`.
- **Il Blueprint ha preso se stesso mentre diventava vecchio**, due volte: quando ho scritto il
  rapporto del passo, e quando ho chiuso il permesso. Entrambe le volte `check` ha detto
  DIVERGENTE, e rigenerando e' tornato aggiornato.

## Il difetto che il Blueprint ha rivelato su di se'

Al primo tentativo la tabella della storia dichiarava **«chiusa»** una tappa appena aperta.
Causa: il generatore decideva lo stato guardando se il rapporto **esisteva** — ma
`new-milestone` lo crea come **modello**, con `stato: aperta`.

Corretto: lo stato si legge dal campo **dichiarato** dentro il record.

Registrato come `ERR-0009`, e il difetto **l'ho trovato leggendo l'output**, non eseguendo un
test: il generatore passava tutte le prove che avevo scritto.

E la lezione e' piu' grande del difetto: **`ERR-0009`, `ERR-0003` e `ERR-0005` sono lo stesso
errore tre volte** — confondere l'**esistenza** con lo **stato**. «Il file esiste» invece di
«dichiara di essere chiuso»; «il permesso e' chiuso» invece di «il passo e' chiuso»; «assente»
invece di «non ho guardato». Ora e' scritto, e c'e' una prova per ciascuno.

## Conseguenze

- Il passo **6** della sequenza ora include la generazione del Blueprint.
- `blueprint.py check` entra nella fascia deterministica del cervello.
- **Limite dichiarato**: il controllo **non** considera un errore l'**assenza** di Blueprint.
  Un progetto senza e' una cosa da fare; un Blueprint divergente e' una bugia. Le due vanno
  distinte, altrimenti la suite diventa rossa su 16 progetti e nessuno la guarda piu'.
- **Limite dichiarato**: **niente obbliga a rigenerarlo.** Il controllo lo trova quando
  qualcuno lo esegue. E' la stessa lacuna di `DRIFT-013`: la regola c'e', il blocco no. Quando
  questo mordra', diventera' una voce in `errori/` e poi un controllo — **ed e' esattamente il
  meccanismo che abbiamo appena costruito.**
- **Limite dichiarato**: la parte scritta a mano **puo' mentire**, e nessun controllo la
  verifica. E' narrativa, non stato. La differenza e' scritta nel file stesso.
- **Gli altri 16 progetti**: il Blueprint si genera quando il progetto viene toccato. Non e' un
  lavoro da fare in blocco.
- **Limite dichiarato, ed e' una tensione vera**: il Blueprint e' una **fotografia dei
  registri**. Se i registri cambiano — per esempio perche' si scrive un verbale che nomina il
  progetto — la fotografia diventa **vecchia**. Il controllo la segnala, ma **non distingue una
  fotografia vecchia da una manomissione**: dal file, le due cose sono identiche. L'ho visto su
  di me: scrivendo questo stesso verbale, il Blueprint del Marketing Factory e' diventato
  divergente. E rigenerarlo **richiede un permesso sul progetto**: un verbale della societa' puo'
  quindi lasciare vecchi i Blueprint di piu' progetti, e aggiornarli non e' gratis. **Non ho una
  soluzione pulita**, e preferisco dirlo che nasconderlo dietro una regola che non regge.
- **Cosa farebbe la differenza**: distinguere le due cose. Un modo ci sarebbe — far dichiarare al
  Blueprint **da quale fotografia dei registri viene** — ma servirebbe un'impronta stabile dei
  registri, che e' un lavoro a se'. **Non ora.**

## Metrica

Progetti con Blueprint divergente: atteso **zero** — ed e' un errore, non un avviso.
Progetti senza Blueprint: **16**, da ridurre toccando i progetti. Un progetto senza non mente:
semplicemente non ha ancora la carta d'identita'.

## Data di revisione

2026-11-09
