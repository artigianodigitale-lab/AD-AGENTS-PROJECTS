# Piano — Un solo motore di scrittura (DSH) e Cursor in sola lettura

**Stato: APPROVED WITH CONSTRAINTS** (il CEO, 2026-10-10), aggiornato da `DEC-0039`
(2026-10-11): il gancio su Cursor **non si costruisce**.

Blueprint di riferimento: `studio/2026-10-10-blueprint-motore-dsh-cursor-readonly.md`
(analizzato e verificato voce per voce; vedi `DECISIONI/DEC-0038-un-solo-motore-di-scrittura.md`).

## 1. Cosa ha chiesto il CEO

`APPROVED WITH CONSTRAINTS`, con un ordine vincolante per il primo sprint e sette vincoli.

## 2. Cosa e' stato verificato, e cosa corretto

- **Le cinque fonti esistono tutte**, verificate una per una il 2026-10-10.
  - errata: il paper `2608.16891` non si chiama «Aegis» (Aegis e' `2603.12621`)
  - manca il link di «CapNET / capability grants»
- **`MODEL-ROUTING.md` e' falso**: dichiara Cursor «non in uso» mentre Cursor e' in esecuzione
- **`P0.4` e' falsa**: `test_ad_org.py` **passa** (248 controlli) e il test di `security_scan` usa
  una cartella temporanea. Sostituita dal **filtro dei falsi allarmi**
- il difetto vero: `security_scan.py` esce **1 su 15 progetti su 17**, tutti per `generic-api-key`,
  su campioni che sono fixture. In mezzo al rumore, **3 vulnerabilita' vere** restano invisibili

## 3. Ordine vincolato dello Sprint 1

```text
1  i falsi allarmi di security_scan     exit 1 solo sui segnali plausibili
2  fail-closed selettivo                deny su .brain/, tools/, cartelle numerate
3  suite e documentazione allineate     nessun FAIL inventato
4  MODEL-ROUTING vero                   Cursor e' uno strumento di lettura, e si dice
```

## 4. Cosa serve dal CEO

- **`GOV-001`**: il permesso che copre `.brain/`, `tools/`, `MODEL-ROUTING.md`, `TASK-CONTRACTS.md`,
  `RUNTIME.md`, `contratti/_TEMPLATE.yaml`, `drift/README.md`, `piani/`, `orchestrazione/`,
  `evals/`, `evidenze/`. **Un agente non lo scrive da solo** (invariante 7)
- **`GOV-000`** scade il **2026-11-08** e non si auto-rinnova
- il marcatore in `approvazioni/societa/GOV-001.yaml`, che cita il verdetto

## 5. Ambito di scrittura

`contratti/societa/GOV-001.yaml` e i percorsi sopra. **Nessun progetto numerato.**

## 6. Passi

| # | Passo | Esito atteso |
|---|---|---|
| 1 | Filtro falsi allarmi in `security_scan.py` | 0 falsi allarmi; 1 solo sui plausibili |
| 2 | Fail-closed selettivo nel plugin | checker assente → deny su governance e progetti |
| 3 | Suite e `tools/README.md` allineati | `PASS`, nessun FAIL inventato |
| 4 | `MODEL-ROUTING` vero | la dichiarazione corrisponde: Cursor legge, DSH esegue |
| 5 | Fast-path L1 (K=5) | cerimonia ridotta per i micro-task |

## 7. Fuori ambito, dichiarato

Capability token (rimandati), P2, i 17 progetti nel merito, e la sostituzione di DSH.
