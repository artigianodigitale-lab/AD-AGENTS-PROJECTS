# DEC-0038 — Un solo motore di scrittura

```yaml
id: DEC-0038
stato: approvato
livello: 3
data: 2026-10-10
approver: CEO
supera:
```

## Problema

Il sistema ha **due superfici** e **un solo cancello**.

`MODEL-ROUTING.md` dichiara Cursor «non in uso». **È falso, ed è falso adesso**: al momento della
verifica risultano in esecuzione due processi Cursor (PID 61925 e 61931, avviati alle 20:26), e
`~/.cursor/` contiene `plugins/` e `skills-cursor/`.

Le skill `ad-*` sono symlinkate in `~/.agents/skills/`, quindi **Cursor le carica** — ma il plugin
`enforce-contract` è montato **solo su DSH**. In Cursor un agente legge le regole e **può
scriverci sopra**: le skill guidano, il cancello non c'è.

E la prova che il buco non è teorico è che **questa proposta è stata scritta da un agente su
Cursor**. L'analisi che l'ha prodotta è arrivata da lì.

## Opzioni

1. **Allineare Cursor al cancello** — un hook PreToolUse che chiama lo stesso Python di DSH.
   Conseguenza: Cursor resta capace di scrivere, ma sotto controllo. Costo: **due host da
   mantenere allineati**, due superfici che possono divergere, e ogni buco si apre due volte.
   Rischio: il sistema ha già sofferto la divergenza fra documenti e realtà — `DRIFT-016` è di
   oggi. Fonte: [arXiv 2608.16891, *Runtime Governance for Agentic AI: Action-Boundary Control
   with Trusted Provenance and Fail-Closed Execution*](https://arxiv.org/abs/2608.16891).
2. **Una superficie scrive, una legge** — DSH esegue, Cursor legge. In Cursor un deny-hook
   **blocca ogni mutazione** dentro `AD Projects`, senza reimplementare lo scope: non serve
   capire cosa è permesso, serve solo dire no. Costo: **un hook, non un secondo cervello**, e la
   frizione di dover cambiare finestra. Rischio: un hook eludibile — ma DSH resta autoritativo, e
   una scrittura avvenuta di nascosto si vede in `drift/`. Fonte: [Microsoft
   agent-governance-toolkit](https://github.com/microsoft/agent-governance-toolkit), che adotta
   verdetti espliciti con **errore → deny**.
3. **Non fare nulla** — Cursor resta un buco di scrittura. Conseguenza: la governance vale solo
   dove si è deciso di lavorare, e **basta aprire l'altra finestra per non averla**. Il costo non
   è immediato: è che ogni artefatto prodotto in Cursor è **fuori dal registro delle
   autorizzazioni**, e la sua provenienza non è verificabile. Le regole già esistono e dicono
   Cursor «non in uso»: **sono false, e nessuno se ne accorgeva.**

## Evidenze

- **Le cinque fonti verificate una per una** il 2026-10-10: `2608.16891` esiste e il titolo
  contiene *«Fail-Closed Execution»*; `2609.24446` è ActGov, titolo conforme; il toolkit Microsoft
  esiste; `agent-tooltrust` esiste. **Una errata**: il paper `2608.16891` è chiamato «Aegis» nel
  blueprint, ma **Aegis è `2603.12621`**, un altro lavoro. L'ID e il principio sono giusti,
  l'etichetta no. **Una senza link**: «CapNET / capability grants».
- **Cursor in esecuzione**: `ps aux` → due processi, `~/.cursor/` presente.
- **`MODEL-ROUTING.md` riga 30**: *«Cursor (IDE) — **non in uso**»*. Falso.
- **Il difetto che il blueprint aveva visto male**: `P0.4` dichiara che `test_ad_org.py` fallisce
  su `security_scan`. **Falso**: la suite passa **248 controlli**, e il test lavora su una cartella
  temporanea. Ma guardando lì ho trovato un difetto **peggiore**: `security_scan.py` esce **1 su 15
  progetti su 17**, tutti e 15 per la sola regola `generic-api-key`, su campioni che sono
  **fixture** (`openrouter_api_key="sk-or-test-key-12345"`, `dedupeKey: "sbx21-warm-neutrals"`).
  Un allarme che suona sempre **spegne il controllo**, e in mezzo al rumore restano invisibili
  **3 vulnerabilità vere** nel `package-lock.json` di `3. AD-Marketing-Factory`.
- **Stato del motore**: plugin montato su DSH e non su Cursor; fail-open; shell euristica;
  permessi per-card non a runtime. Tutti e tre **già dichiarati** come limiti.

## Scelta

**Opzione 2 — una superficie scrive, una legge.** Con i vincoli del CEO
(`APPROVED WITH CONSTRAINTS`, 2026-10-10):

| # | Decisione | Vincolo |
|---|---|---|
| 1 | Cursor sola lettura | una superficie scrive (DSH), una legge (Cursor) |
| 2 | `.cursor/` solo deny-write | DEC obbligatorio: **gancio di blocco sì, secondo cervello no** |
| 3 | Fail-closed se `tools/` è rotto | **selettivo**: deny su `.brain/`, `tools/`, cartelle numerate; altrove resta fail-open |
| 4 | Capability token | **rimandati** fuori da P0, solo dopo metriche P0 e DEC dedicato |
| 5 | Fast-path Livello 1, K=5 | **anticipato in P0** |
| 6 | Sequenza P0 → P1 → stop → P2 | con P0 riordinato |
| 7 | Sostituire `P0.4` | **filtro falsi allarmi**, non «aggiustare la suite» |

**Ordine di P0, vincolato dal CEO:**

```text
1  i falsi allarmi di security_scan      (exit 1 solo sui plausibili)
2  fail-closed selettivo                 (deny dove conta, fail-open altrove)
3  suite e documentazione allineate      (nessun FAIL inventato)
4  deny-write Cursor + MODEL-ROUTING vero
```

**Il riordino è la sostanza, non la forma**: il fail-closed *aggiunge* un cancello, e oggi il
cancello che esiste **grida su 15 progetti su 17**. Aggiungere controlli prima di aggiustare
quello rumoroso ripete l'errore registrato due volte in un giorno — `ERR-0011` (un controllo che
non poteva fallire) e il suo specchio (un controllo che fallisce sempre).

**I capability token sono rimandati, e dico perché**: la minaccia dichiarata è *«con accesso shell
si può falsificare»*, ma chi ha accesso shell **può anche cancellare il plugin**. La crittografia
difende da un avversario che ha già vinto. Il paper che la sostiene parla di enforcement
verificabile **fra più parti**; noi siamo un CEO e una macchina. Serve a rendere **visibile** la
manomissione — e questo il marcatore già lo fa.

## Conseguenze

- **`MODEL-ROUTING.md` cambia**: Cursor è in uso, **in sola lettura**. Era falso.
- **`.cursor/` nasce**, con **un solo** gancio di blocco. `DRIFT-001` (chiusa: «niente
  `.cursor/rules`») non si riapre: quel divieto era contro un **secondo cervello**, non contro un
  cancello.
- **Il plugin diventa fail-closed selettivo**: se non sa rispondere, **blocca** su governance e
  cartelle numerate, e lascia passare altrove.
- **`security_scan.py` cambia verdetto**: separa i segnali plausibili dalle forme da fixture.
- **Nuovo permesso `GOV-001`**, firmato dal CEO. **`GOV-000` non si rinnova da solo** e scade il
  **2026-11-08**: un agente non modifica i propri permessi (invariante 7).
- **Le carte vivono in `societa/`**: `piani/`, `DECISIONI/`, `contratti/societa/`,
  `approvazioni/societa/`. **Nessun progetto numerato si apre**: è la macchina, non un prodotto.
- **Fuori ambito**: capability token, P2, e i 17 progetti nel merito — salvo ciò che serve al
  filtro dello scanner e alle evidenze.

## Metrica

`security_scan.py` su 17 progetti: oggi **15 escono 1 per falsi allarmi**; atteso **0** per i
falsi allarmi, e **1** ogniqualvolta c'è un segnale plausibile. Plugin: fail-closed **verificato
con un difetto iniettato**, non dichiarato. `MODEL-ROUTING.md`: **zero affermazioni false** sulla
superficie.

## Data di revisione

2026-11-09

## Esito misurato

<Da compilare il 2026-11-09: quanti falsi allarmi restano, se il fail-closed ha mai bloccato un
lavoro legittimo, e se una scrittura è mai arrivata da Cursor.>
