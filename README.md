# AD-AGENTS-PROJECTS

> Non un prompt più furbo: una casa con le serrature. Permessi legati al lavoro, consenso
> prima di partire, memoria che resta dopo la chat. Dove un controllo può fallire, la
> fiducia non è più un atto di fede.

**Versione 1.8.2 — 2026-11-17.** Un motore che dà a un agente AI le regole di una casa — e la
forza di rispettarle. Colleghi questa cartella al tuo programma, scrivi `AGENTS.md`, e da quel
momento l'agente lavora con **permessi, consenso, prove e memoria**: non con la buona volontà.
Non è un prompt più lungo: è un sistema che **si installa**, e dove può **blocca**.

---

## Che cos'è

AAP è **due cose insieme**:

- **un motore**: la cartella che contiene `.brain/` — regole, strumenti, registri. È il
  cervello condiviso da tutte le sessioni.
- **i progetti**: cartelle **numerate** accanto al motore (`1. Nome`, `2. Nome`…). Ognuno ha
  la sua storia, il suo repository e il suo registro delle autorizzazioni.

Il motore non contiene i progetti: li ospita. E ogni scrittura passa da un permesso che
nomina esattamente i file toccati.

## Cosa sa fare oggi

| Area | Cosa c'è | Prova |
|---|---|---|
| **Governance** | task contract, approvazione del CEO, evidenze, Quality Gate, registri di errori/drift/decisioni, cancelli di enforcement | `python3 tests/ci.py` · `python3 tools/coherence.py` |
| **Progetti** | creazione/collegamento con numero, registro del progetto, blueprint e vista operativa generati | `python3 tools/progetto.py elenca` · `stato.py` · `blueprint.py` |
| **Sicurezza** | carta OWASP 2026, baseline a 12 controlli, sandbox bubblewrap, eval di iniezione, manifest MCP pinnato (15 tool) | `python3 tools/sicurezza.py` · `sandbox.py --autotest` · `redteam.py` |
| **Lettura del web** | crawler con robots, dedup, rate limit, guardia SSRF, snapshot + provenienza, browser headless quando serve; policy `CRAWLING.md` | `python3 tools/crawler.py avvia "<url>"` |
| **Code Mode (MCP)** | il server MCP espone **2 tool** (`ad_cerca`, `ad_esegui`) invece di 13: l'agente scrive JavaScript che compone i tool, eseguito in sandbox; −79,6% delle definizioni, composizione in un giro; `--classico` per i 13 | `python3 tools/codice.py metriche` |
| **Memoria e cache** | memoria lessicale **con provenienza** (`file:riga` + sha256, `verifica`, costo per query); cache verificabile con TTL e provenienza, fuori dal repository | `python3 tools/memoria.py cerca "<domanda>"` · `cache.py stato` |
| **Build** | build incrementale: salta le fasi i cui input non sono cambiati, dice il risparmio, `--forza` per il sospetto | `python3 tools/build.py` |
| **Apprendimento misurabile** | ogni errore diventa una cicatrice (`errori/`) con «cosa lo avrebbe preso»; se si può meccanizzare diventa un controllo. Il **flight recorder** ricompone le traiettorie e misura (fotografia al 2026-11-16): primo colpo **66,3%**, lezioni→controlli **55,8%**, terza domanda **100%**, errori per task chiuso **0,42**; una baseline (tolleranza **5 punti**) fa rosso se una metrica peggiora. Il comando `traiettorie.py analizza` mostra sempre i valori correnti | `python3 tools/traiettorie.py analizza` · `confronta` |
| **Metodo business** | **tela business verificabile** (`business.py`): 11 sezioni obbligate, ogni riga con cifre dichiara **fonte e data**, almeno 2 concorrenti, 2 rischi, 1 assunzione, prossimi passi. Non giudica la strategia e non verifica le fonti: rende l'analisi **controllabile**; il contenuto resta delle card business e del CEO | `python3 tools/business.py genera` · `check <file.md>` |

**Costo esterno: zero.** Tutto gira in locale: nessun servizio cloud, nessuna chiave API
richiesta per i controlli. (Il piano **M0-M10 è completo**; M6 misura il processo, M7 rende
l'analisi business tracciabile — nessuno dei due promette che la strategia sia giusta.)

## Come si usa AAP

### 1. Installazione (una volta)

```sh
git clone https://github.com/artigianodigitale-lab/AD-AGENTS-PROJECTS.git
cd AD-AGENTS-PROJECTS
python3 tools/setup.py --check     # cosa manca, senza scrivere niente
python3 tools/setup.py             # monta il cancello sui profili DSH
```

Il cancello ha effetto **al prossimo avvio** di DSH. Da quel momento ogni scrittura senza
permesso viene rifiutata, con il rimedio.

Su una **macchina nuova** (kit appena scaricato, senza progetti né client registrati)
`python3 tools/accendi.py` può riportare `profilo kit`: significa che i controlli che leggono
la macchina sono **dichiarati** e non eseguiti (`DEC-0127`); il motore è acceso lo stesso. Il
profilo si verifica a mano con `python3 tests/ci.py --kit`.

### 2. Accensione (a ogni sessione)

```sh
python3 tools/accendi.py
```

Controlla sei cose — chi è il CEO, il cancello montato, le skill collegate, il server MCP, il
catalogo dei comandi, la macchina verde — e dice `L'ENGINE È ACCESO` oppure **cosa fare**.

### 3. La prima risposta dell'agente

L'agente dichiara come si comporterà, dichiara che AAP è il suo comportamento da quel momento,
e chiede se vuoi **iniziare un progetto nuovo** o **collegarne uno esistente**. Poi aspetta:
non cerca progetti, non analizza niente.

### 4. Un progetto

```sh
python3 tools/progetto.py nuovo "Nome Del Progetto"   # crea la cartella numerata
python3 tools/progetto.py registro "<cartella>"      # collega il registro al cancello
```

Dentro il progetto: `governance/` (contratti e approvazioni), `Analisi-Prompt-Report/`
(analisi, tappe, sprint, rapporti). Il motore resta pulito.

### 5. Un lavoro

La sequenza è obbligatoria: **richiesta → analisi → consenso del CEO → contract → sprint →
esecuzione → evidenze → gate → chiusura**. Senza contract non si scrive; senza evidenze non è
fatto; senza gate indipendente non è accettato (chi produce non valida da solo).

```sh
python3 tools/cards.py match <tipo>                  # nessun match = STOP
python3 tools/validate_contract.py contratti/<c>.yaml
python3 tools/verdict.py --contract <c> --evidence <e1> --evidence <e2>
python3 tools/permessi.py check                      # i permessi non mentono
```

### 6. Verifica e build

```sh
python3 tests/ci.py            # verifica rapida (circa 60 controlli)
python3 tests/ci.py --full     # suite completa: verde tranne il debito dichiarato DRIFT-037
python3 tools/build.py         # incrementale: salta ciò che non è cambiato
python3 tools/coherence.py     # documenti e sistema dicono la stessa cosa
python3 tools/stato.py render  # la vista operativa (generata, non scritta a mano)
```

## I comandi principali

Il registro **completo** è in [`tools/README.md`](tools/README.md): ogni comando con cosa fa
in parole comprensibili e la forma d'uso. I più usati:

| Per | Comando |
|---|---|
| accendere e controllare | `accendi.py` · `setup.py --check` · `coherence.py` · `stato.py` |
| progetti | `progetto.py elenca` / `nuovo` / `collega` · `blueprint.py render "<p>"` · `milestone.py` |
| permessi e gate | `cards.py match` · `validate_contract.py` · `verdict.py` · `permessi.py` · `errori.py` |
| sicurezza | `sicurezza.py` · `sandbox.py --autotest` · `redteam.py` · `security_scan.py` |
| web | `ricerca.py leggi "<url>"` · `crawler.py avvia "<url>" [--cache]` |
| memoria, cache, build | `memoria.py cerca "<domanda>"` · `cache.py stato` · `build.py` · `traiettorie.py analizza` |
| MCP / Code Mode | `ad_mcp/server.py` (default 2 tool, `--classico` per 13) · `codice.py metriche` |

## Come è fatta la cartella

```text
AD-AGENTS-PROJECTS/          il motore (regole, strumenti, registri)
  .brain/                    costituzione, skill, plugin di enforcement
  tools/                     gli strumenti, con il registro in tools/README.md
  contratti/  approvazioni/  il registro delle autorizzazioni (collegamenti ai progetti)
  DECISIONI/  errori/  drift/  piani/  evidenze/  evals/  strategic_memory/
  SECURITY.md  CRAWLING.md   le carte: sicurezza e lettura del web
  README.md  VERSION  AGENTS.md
  ../Progetti/1. Nome Progetto/   i progetti, fuori dal motore (dove vuole il CEO)
```

**Niente percorsi assoluti:** la macchina si sposta e le regole viaggiano con lei. Tutti i
programmi trovano la radice da dove si trovano.

## Le regole che non si negoziano

1. Nessun agente parte senza **contract**, senza match con una card e senza contesto.
2. Senza **evidenze** non è DONE; senza **Quality Gate** non è ACCEPT.
3. ACCEPT non è rilascio, spesa o firma: quello decide il CEO.
4. Chi produce non valida il proprio gate: serve un revisore indipendente.
5. La capacità percepita non è autorizzazione: nessuna card, STOP.
6. La richiesta del CEO è una **proposta da verificare**, non un ordine.
7. Prima si risponde, poi si decide, poi si scrive.
8. Al CEO si parla in **parole comprensibili**.
9. La memoria è dei **registri**, non degli embedding: ogni risposta porta la fonte.
10. Ogni errore diventa una **difesa**: cosa è fallito, cosa l'ha risolto, cosa lo avrebbe preso.

## Stato attuale e limiti dichiarati

- **Tappe fatte:** M0 (pulizia) · M1 (progetti spostati e registri) · M2 (sicurezza) ·
  M3 (crawler) · M3b (Code Mode) · M4 (memoria e cache) · M5 (build e cache del crawler) ·
  M6 (flight recorder e metriche di apprendimento) · M7 (metodo business) · M8 (sei guardie
  per i debiti) · M9 (quattro guardie del motore) · **M10 (le ultime guardie)**.
- **Debiti:** il motore **non ne ha di aperti**; 8 voci dei progetti sono accettate con
  `DEC-0125`. `ci.py --full` è **verde**.
- **Limiti:** il retrieval è lessicale (sinonimi possono sfuggire); la sandbox non incapsula
  DSH e lascia leggibili i file leggibili dell'host (in Code Mode `~/.dsh` è nascosto); il
  browser non passa dalla guardia SSRF; la build può non accorgersi di una modifica che non
  tocca gli input dichiarati (`--forza` esiste per questo); M6 misura il **processo**, non il
  comportamento del modello; la tela di M7 verifica struttura e tracciabilità, **non la
  qualità della strategia** né la verità delle fonti.

## Requisiti

Python 3.10+ (solo libreria standard per i controlli), `bubblewrap` per la sandbox,
`node` 20+ per Code Mode, `git`. `gitleaks`/`osv-scanner`/`syft` sono opzionali: senza, la
baseline dichiara `skip` — mai un finto verde.

## Documenti

[`AGENTS.md`](AGENTS.md) (costituzione) · [`tools/README.md`](tools/README.md) (registro dei
comandi) · [`SECURITY.md`](SECURITY.md) · [`CRAWLING.md`](CRAWLING.md) ·
[`GOVERNANCE-AZIENDALE.md`](GOVERNANCE-AZIENDALE.md) · [`QUALITY-GATES.md`](QUALITY-GATES.md) ·
[`TASK-CONTRACTS.md`](TASK-CONTRACTS.md) · [`orchestrazione/`](orchestrazione/) ·
[`DECISIONI/`](DECISIONI/) · [`piani/`](piani/).

> **Il principio in una riga:** dove un controllo può fallire, la fiducia non è più un atto
> di fede — e un rifiuto porta sempre con sé il proprio rimedio.
