# DEC-0012 — Registro drift e i tre pezzi del protocollo

```yaml
id: DEC-0012
stato: approvato
livello: 2
data: 2026-10-08
approver: CEO
supera:
```

## Problema

Due vuoti, distinti.

**1. Nessun posto dove mettere una divergenza.** Il gate di hash sui documenti normativi impedisce le modifiche silenziose, ma non offre un posto per una divergenza **trovata e non ancora sanata**. Le opzioni erano due, entrambe sbagliate: ignorarla, oppure aprire un Decision Record — un atto di governance per una nota. `ad_gates.py` copriva gia' **un solo caso** di drift (il catalogo dei gate fra due documenti), ed e' la prova che il meccanismo serve.

**2. Tre doveri mancanti.** La scala di priorita' con la regola «vale il massimo»; il dovere di **previsione** dell'impatto prima del diff; un vocabolario di risposta che non ammetta interpretazioni.

## Evidenze

- Nessun registro accessibile: l'unico drift tracciato era dentro `ad_gates.py`, cablato nel codice.
- Il Continuity Pack documenta il proprio fallimento in `DRIFT-102`: `middleware.ts` citato da **18 documenti** e mai corretto. Un registro senza lettore e senza controllo e' un'illusione di controllo.
- `RISK-003` di quel registro cita «single-tenant auth RISK-006», ma RISK-006 e' «Migrations shallow»: l'auth e' RISK-008. Un refuso che nessun controllo intercetta.
- Il consenso non aveva un vocabolario: `approvazioni/*.yaml` accettava qualunque testo nel campo `consenso`.
- Nessun contract dichiarava cosa poteva rompersi: l'impatto si scopriva dopo.

## Scelta

### C2 — Registro drift

In `drift/README.md`: una voce per divergenza, con `Severita'`, `Documento dice`, `Realta' dice`, `Rischio`, `Stato`, `Evidenza`. Severita' `CRITICAL | HIGH | MEDIUM | LOW | INFORMATIONAL`; stato `OPEN | FIXED | CLOSED | ACCEPTED`.

Regola: **si registra, non si corregge in silenzio.** La correzione richiede un Decision Record, la registrazione no.

**Una chiusura senza Decision Record esistente non e' una chiusura**: e' una modifica silenziosa con un'etichetta. Il validatore lo impone, e controlla anche la forma della data.

**Non sta nella root, sta in una cartella.** `tests/test_strategic_memory.py` usa il glob `*.md`: ogni file markdown nella root diventa un documento canonico sotto snapshot. Un registro che cambia a ogni voce chiusa avrebbe richiesto una rigenerazione dello snapshot ogni volta — attrito che l'avrebbe ucciso. E' la stessa ragione per cui `DECISIONI/`, `piani/` ed `EVOLUZIONE/` sono cartelle.

Il registro nasce con **6 voci reali**, tutte verificate prima di essere scritte. Una e' `CRITICAL` ed e' chiusa: `.brain/` non protetto (DEC-0009).

**Una voce che il revisore aveva riportato non e' stata registrata**: il presunto «elenco a 8 gate in `AGENTI-V2.md`». Verificato, quel elenco non esiste. Non l'ho scritto — sarebbe stato un drift inventato dentro il registro che serve a non inventare.

### Il pezzo 1 — Scala P0-P4

`priority` e' obbligatorio nel contract, con la regola: **se la modifica tocca piu' livelli vale il massimo**. Un criterio sostanziale che importo perche' e' giusto: una UI che forza un KPI a `0` invece di `N/A` e' `P0`, non una rifinitura.

### Il pezzo 2 — Previsione di impatto

`impact_forecast` e' obbligatorio su sei aree — `data`, `schema`, `auth`, `security`, `shared_platform`, `product` — con livelli `NONE | LOW | MED | HIGH | UNKNOWN`. E' il **dovere di previsione prima del diff**, che non avevamo affatto: stimavamo l'impatto dopo, o mai.

`UNKNOWN` e' ammesso e onesto. Il validatore impone la coerenza: **un impatto `HIGH` impone `P0`,** verificato.

### Il pezzo 3 — Vocabolario di risposta

`APPROVED` / `APPROVED WITH CONSTRAINTS` / `REJECTED`, in `GOVERNANCE-AZIENDALE.md`. Serve a coprire il caso che oggi non sapevamo rappresentare: un consenso **con condizioni**. E a dire esplicitamente che il silenzio non e' un'approvazione.

## Conseguenze

- Una divergenza ha un posto, e smette di essere una scelta fra ignorarla e aprire un Decision Record.
- Una chiusura e' verificabile: senza Decision Record esistente, `drift.py check` esce 1.
- L'impatto si dichiara **prima**, e un impatto alto obbliga la priorita' massima.
- Il consenso ha tre valori, e le condizioni non si perdono.
- 9 fixture di contract aggiornate; la suite passa da 131 a **142 controlli**.
- Tre documenti di root cambiati (`GOVERNANCE-AZIENDALE.md`, `TASK-CONTRACTS.md`, `QUALITY-GATES.md`): snapshot rigenerato.
- **Limite dichiarato, ed e' il piu' importante di questo record**: il registro ha bisogno di un **lettore**. Se non viene riletto nella revisione dei 30 giorni e nella review strategia del primo lunedi' del mese, invecchia esattamente come il loro `DRIFT-102`. E' scritto nella prima pagina del registro, insieme alla conseguenza: un registro morto va cancellato, perche' e' peggio di nessun registro.
- **Secondo limite**: `impact_forecast` e' una dichiarazione, non una misura. Nessun controllo verifica che un `NONE` sia davvero tale. La disciplina resta umana; il valore sta nel fatto che ora e' scritta prima del lavoro, quindi contestabile dopo.

## Metrica

Voci drift aperte piu' vecchie di 30 giorni (atteso: zero — o chiuse, o `ACCEPTED` con motivo). E percentuale di contract con `impact_forecast` compilato senza `UNKNOWN` su aree poi rivelatesi toccate: misura se la previsione sta diventando reale.

## Data di revisione

2026-11-07
