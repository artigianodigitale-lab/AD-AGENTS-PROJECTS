# Rilascio 1.8.2 — kit pubblico completo, e il ripiego non copre più i difetti veri

**Data:** 2026-11-17 · **Tag:** `v1.8.2`

Questa versione corregge un difetto trovato dalla revisione indipendente di ENG-062: il
ripiego che permette a `accendi.py` di accendersi su un kit nuovo copriva anche rossi veri.

## Il difetto

`tools/accendi.py`, quando la verifica rapida era rossa, riprovava con `tests/ci.py --kit`.
Il profilo kit salta i controlli elencati in `CONTROLLI_AMBIENTE`. Quell'elenco conteneva
anche `coerenza`, `test-sicurezza`, `drift`, `test-codice`, `test-memoria`: un loro
fallimento **vero** veniva quindi coperto dal secondo giro, e `accendi.py` diceva
«L'ENGINE È ACCESO» con un documento incoerente o una difesa rotta.

## La correzione

1. `CONTROLLI_AMBIENTE` contiene **solo** i controlli che leggono il mondo e non possono
   mascherare un difetto del codice o dei documenti: `test-mcp`, `test-100-aap`,
   `test-arti`, `test-sandbox`, `test-prodotti`.
2. `coerenza`, `drift`, `verbali`, `test-sicurezza`, `test-codice`, `test-memoria`,
   `test-traiettorie` **non sono più saltabili**: un loro rosso resta rosso.
3. I test che richiedono dati o strumenti assenti su un kit nuovo ora **dichiarano lo skip
   dentro di sé**, invece di essere saltati per nome:
   - `test-codice`: skip se la sandbox non è disponibile (niente `bubblewrap`/`node`);
   - `test-memoria`: skip dell'eval se i registri sono vuoti (kit nuovo);
   - `test-traiettorie`: skip del confronto se non ci sono task chiusi.
4. `init.py` crea anche `backup/`, `strategic_memory/`, `studio/`, la **chiave di firma**
   (`~/.dsh/ad-consenso.key`) e il **primo bundle** in `backup/` se la cartella è un
   repository git. Così la baseline di sicurezza è verde su un motore appena nato.
5. `drift.py` accetta un registro **esistente e vuoto**: «0 voci» è coerente, non un errore.
   Il kit include un `drift/README.md` iniziale.
6. `test_reversibilita` confronta il gancio con il nome della **propria** radice, non con una
   cartella chiamata per forza `AD-AGENTS-PROJECTS`.

## Verifica

Il caso che aveva fatto fallire il gate è ora un test: una `coerenza` rotta **non** è
coperta dal ripiego, e `accendi.py` dice «NO macchina». Sul kit nuovo i controlli che
richiedono il mondo restano dichiarati: il resto è verde o skip dichiarato, mai un finto ok.

## Limiti invariati

Vecchi commit del repository pubblico raggiungibili solo per hash noto (nessun ref li
espone), dichiarato nel §«Limite residuo della ricostruzione». La prova del flusso «PC
nuovo» è fatta su un host con DSH: il montaggio del cancello su un PC senza DSH passa da
`tools/setup.py --ide …`.
