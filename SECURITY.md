# SECURITY — modello di sicurezza del motore

> **Cosa e' questo documento.** La carta di sicurezza di AD-AGENTS-PROJECTS: cosa proteggiamo,
> da cosa, con quali controlli, e **cosa non e' coperto**. E' un documento normativo: e' sotto
> snapshot e si cambia con un Decision Record, non con una modifica silenziosa.
>
> Riferimento: **OWASP GenAI — LLM Top 10, edizione 2026** (la 2025 ha un ordine diverso;
> citare l'edizione e' parte della garanzia), consultata il 2026-11-15
> (<https://raw.githubusercontent.com/GenAI-Security-Project/GenAI-LLM-Top10/main/README.md>),
> e **MCP Security Best Practices** (consultata il 2026-11-15,
> <https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices.md>).
> Decisione: `DECISIONI/DEC-0112-m2-sicurezza.md`.

## 1 · Cosa proteggiamo

| Bene | Perche' conta | Dove vive |
|---|---|---|
| **I permessi** (`write_scope`) | sono cio' che tiene un agente dentro un confine | `contratti/` (collegamenti ai registri dei progetti) |
| **Il consenso firmato** | distingue un «si'» del CEO da un file che lo afferma | `approvazioni/`, chiave `~/.dsh/ad-consenso.key` (0600) |
| **I registri** (decisioni, errori, evidenze) | sono la memoria che rende il sistema verificabile | `DECISIONI/`, `errori/`, `evidenze/`, `drift/` |
| **I progetti** | dati di clienti e lavoro di mesi | `~/Scrivania/Progetti` (dichiarata in `sede.yaml`) |
| **Le credenziali** | una chiave in git e' una chiave persa | fuori dal repository: `.env`, chiave HMAC |
| **Il contesto del modello** | un'iniezione che entra nel contesto e' un ordine | prompt, tool output, materiale letto dal web |

## 2 · Da cosa — mappa OWASP 2026

| Rischio (OWASP 2026) | Come si presenta qui | Cosa lo prende |
|---|---|---|
| **LLM01 · Prompt Injection** | un testo letto dal web o da un file prova a farsi eseguire | contenuto esterno = **dato** (regola in costituzione + `ricerca.py regole`); documenti che portano ordini si **disattivano** rinominandoli; `security_scan.py` li elenca; eval in `tools/redteam.py` |
| **LLM02 · Sensitive Information Disclosure** | una chiave finisce in un prompt, in un log, in un commit | `gitleaks` sui file tracciabili (`security_scan.py`); chiave fuori dal repository; `.env` fuori da git |
| **LLM03 · Excessive Agency** | l'agente scrive fuori dal perimetro o agisce senza consenso | cancello `write_scope` (plugin DSH + `contract_scope.py`); consenso firmato; un solo esecutore per contract |
| **LLM04 · Supply Chain** | una dipendenza o un server MCP compromesso | manifest MCP **pinnato** (`tools/ad_mcp/manifest.json`); `osv-scanner` + `syft`; revisione delle dipendenze prima dell'installazione |
| **LLM05 · Data and Model Poisoning** | un documento avvelenato entra nella memoria | i registri sono verificabili e firmati; le evidenze hanno identita' (`ad_evidence.py`); il materiale di studio e' dato |
| **LLM06 · Unbounded Consumption** | un loop che brucia token o API | `budget.max_retries` per contract; fasce di costo in `MODEL-ROUTING.md`; la baseline controlla il budget dei contract attivi |
| **LLM07 · Misinformation** | un'affermazione plausibile e falsa | evidenze con comando ed esito; gate indipendente; «autentico non vuol dire corretto» (Blueprint) |
| **LLM08 · Hidden Context Exposure** | il contesto nascosto (prompt di sistema) finisce all'esterno | la costituzione e' pubblica per scelta; i segreti non entrano nel contesto; il limite e' dichiarato |
| **LLM09 · Vector and Embedding Weaknesses** | recupero da una memoria non verificata | la memoria sono i registri strutturati (grep, non embedding); RAG locale in M4, con eval |
| **LLM10 · Improper Output Handling** | un output viene eseguito come codice o comando | la sandbox (`tools/sandbox.py`) e' l'unico posto dove si esegue codice non fidato; egress allowlist dichiarato |

**MCP (superficie specifica).** Il server locale e' `tools/ad_mcp/server.py`: in modalita'
classica 13 tool, tutti `ad_*`, in sola lettura tranne `ad_shell_*` (apre il sito in locale e
scrive solo lo stato); in modalita' classica nessun tool di esecuzione arbitraria. Con
`--codice` (M3b, `DEC-0114`) il server espone **due** tool: `ad_cerca` (definizioni a
richiesta) e `ad_esegui`, che esegue JavaScript **solo** dentro la sandbox di M2 (rete
spenta, filesystem in sola lettura, ambiente azzerato, timeout, tetto di output) e chiama i
tool classici con le stesse validazioni. Il dispatch e' filtrato per modalita': il catalogo
non e' una facciata. Il nome e la descrizione di ogni tool sono **pinnati**
in un manifest: una descrizione che cambia senza aggiornare il manifest fa andare **rossa**
la baseline — e' la difesa contro il *tool poisoning*. Il manifest pinna i **13 tool
classici**; `ad_cerca` e `ad_esegui` (M3b) non sono ancora pinnati: limite dichiarato,
si chiude quando la modalita' codice esce dal pilota. Il server risolve i percorsi e rifiuta
tutto cio' che sta fuori dalle due cartelle di autorita' (motore e progetti); sessioni e
token non sono autenticazione: il confine e' di **autorita'**, non di identita'.

## 3 · I controlli, e dove vivono

| Controllo | Dove | Cosa prova | Cosa **non** prova |
|---|---|---|---|
| Cancello sui `write_scope` | `.brain/plugin/enforce-contract`, `tools/ad_scope.py` | una scrittura fuori dal contract e' bloccata (nei tool e nelle shell riconoscibili) | il terminale dell'utente, e i comandi che offuscano il percorso |
| Consenso firmato | `tools/ad_consenso.py`, chiave 0600 | un marcatore manomesso si vede; il consenso e' legato al piano | che il CEO abbia letto il piano |
| Evidenze con identita' | `tools/ad_evidence.py`, `tools/verdict.py` | il gate non passa senza prove; chi produce non valida | la qualita' dell'artefatto oltre i criteri |
| Segreti e dipendenze | `tools/security_scan.py` | credenziali nei file tracciabili, falle con fix, SBOM | che una credenziale non sia gia' nei log del fornitore |
| Manifest MCP | `tools/ad_mcp/manifest.json` + `tools/sicurezza.py` | tool e descrizioni non cambiano sotto | che il server non abbia bug |
| Sandbox | `tools/sandbox.py` (bubblewrap) | rete spenta, filesystem in sola lettura, ambiente non ereditato | DSH e il modello (non sono un file che scriviamo) |
| Baseline | `tools/sicurezza.py` | dodici difese controllate in un comando | cio' che e' `skip` (dichiarato, mai verde) |
| Eval di iniezione | `tools/redteam.py` | i controlli mordono su 8 casi | il comportamento del modello |

**La regola che rende utile la baseline:** un controllo che non si puo' eseguire e' `skip`,
mai `pass`. Un finto verde e' peggio di una lacuna dichiarata.

## 4 · Limiti dichiarati (non nascosti)

1. **La sandbox non incapsula DSH.** Il motore gira come programma sul sistema operativo:
   non puo' incapsulare se stesso. Chi vuole quel confine lo mette a livello di sistema
   (utente separato, container, macchina dedicata). `tools/sandbox.py` protegge cio' che il
   motore esegue **come comando**, non il processo che lo ospita.
1-bis. **La sandbox non nasconde i file leggibili dell'host.** Il filesystem e' montato in
   **sola lettura** (`--ro-bind / /`): chi esegue codice dentro la sandbox puo' **leggere**
   i file che l'utente puo' leggere. Blocca scrittura, rete e ambiente — non la lettura.
   **Eccezione decisa (`DEC-0115`):** la modalita' codice monta un `tmpfs` sopra `~/.dsh`,
   cosi' la chiave di firma non e' leggibile dal codice generato (provato da
   `test_codice.py` e dall'autotest della sandbox). Restano leggibili gli altri file
   dell'host (`~/.ssh`, ecc.): per quel confine in piu' si toglie il percorso dal bind o si
   usa un utente separato. (Rilievo della revisione di M2, 2026-11-15; eccezione di
   ENG-047.)
1-ter. **Il codice di Code Mode gira nello stesso processo node, non in un isolate.** Puo'
   importare i moduli di node (`fs`, `child_process`) e puo' chiamare `server.py --tool` per
   conto suo: l'allowlist di sola lettura del ponte e' una **comodita'**, non un confine. La
   difesa e' la sandbox (rete, scrittura, ambiente, timeout, tetto di output) e le
   validazioni del server; il limite di lettura e' quello di 1-bis. (Rilievo della
   revisione di ENG-046, 2026-11-15.)
2. **La prova che il modello non obbedisca a un'iniezione non e' deterministica.** Un test
   puo' provare che i controlli attorno al modello sono in piedi; il comportamento del
   modello si misura con le traiettorie (M6, flight recorder). Fino ad allora, questo e' un
   limite dichiarato — non una garanzia.
3. **L'analisi della shell e' un'euristica.** `cd`, le scritture dentro stringhe e i percorsi
   offuscati in modi non immaginati possono sfuggire; il confine affidabile resta il
   `write_scope` e, per il codice, la sandbox.
4. **Nessun vault dei segreti.** La chiave HMAC e la regola `.env` restano la verita'. Un
   secondo contenitore di segreti senza un caso d'uso reale sarebbe la quarta reinvenzione
   (`DEC-0102`). Si aggiunge quando nasce un bisogno (integrazioni, scraping con chiavi).
5. **Chi ha accesso root ha vinto.** La firma del consenso difende dal repository, non dalla
   macchina: la chiave sta sulla stessa macchina (`ad_consenso.py`, limite dichiarato).
6. **La rete del processo DSH non e' filtrata.** Il motore non ha un proxy di egress: la
   regola «pagine pubbliche, no paywall, no dati personali» e' scritta e verificata come
   dichiarazione (`ricerca.py regole`), non imposta a livello di rete. Un proxy di egress
   e' lavoro di M3.

## 5 · Risposta a un incidente

1. **Fermare.** Nessuna azione irreversibile; il dubbio sale di livello (invariante 9).
2. **Contenere.** Se la chiave e' sospetta: `python3 tools/chiave.py --check` e, se serve,
   `--rigenera` (le firme vecchie non tornano: e' voluto). Se un segreto e' in git: si
   revoca dal servizio **prima** di riscrivere la storia.
3. **Registrare** in `errori/` con le tre domande: cosa e' fallito, cosa l'ha risolto,
   **cosa lo avrebbe preso**. Un incidente senza la terza e' un racconto.
4. **Provare** con `python3 tools/sicurezza.py` e, se tocca i controlli,
   `python3 tools/redteam.py`. Se il difetto e' meccanizzabile diventa un controllo.
5. **Riportare al CEO** in parole comprensibili, con l'impatto e la via di ritorno.
6. **Rivedere** la carta: se un limite dichiarato si e' rivelato falso, si corregge qui.

## 6 · Revisione

- **Ogni milestone** (M2→M7): la baseline deve essere verde e il manifest coerente.
- **Ogni 30 giorni**: revisione del modello e delle fonti (OWASP cambia edizione).
- **A ogni incidente**: la carta si aggiorna **insieme** al registro errori.

Esecuzione: `python3 tools/sicurezza.py` (dodici controlli), `python3 tools/redteam.py`
(otto casi), `python3 tools/sandbox.py --autotest` (le promesse della sandbox).
