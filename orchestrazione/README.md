# ORCHESTRAZIONE OPERATIVA

Questo protocollo esegue la governance con costo token minimo. La fonte normativa è [GOVERNANCE-AZIENDALE.md](../GOVERNANCE-AZIENDALE.md); i dettagli tecnici sono in [RUNTIME.md](../RUNTIME.md), [TASK-CONTRACTS.md](../TASK-CONTRACTS.md) e [MODEL-ROUTING.md](../MODEL-ROUTING.md).

```text
Richiesta (proposta da verificare, non un ordine)
  → comprensione dell'obiettivo
  → ricerca: esiste un modo migliore, piu' scalabile, piu' affidabile?
  → risposta al CEO
  → consenso del CEO su cosa fare
  → controllo deterministico → contract → un esecutore
  → evidenze → gate richiesti → ACCEPT / REJECT / escalation
```

La prima meta' della catena non e' esecuzione: e' la verifica che valga la pena eseguire. Il protocollo completo, con i comandi, e' nella skill `ad-kickoff`; il dovere di ricerca e' in `ad-evolution`.

L'orchestratore sceglie il dominio, verifica card, permessi, budget, dati e gate prima di qualsiasi chiamata al modello. Carica solo il contesto nominato dal contract. Non crea un gruppo di agenti per discutere: aggiunge un revisore solo per un gate obbligatorio o per una dipendenza dichiarata.

`stato.md` è una vista umana, non una memoria aggiuntiva da passare al modello. Dopo due REJECT locali, il task si ferma e viene escalato con evidenze; non entra in un loop di prompt.

## Versionamento e verifica automatica (ENG-006, DEC-0060)

La macchina e' un **repository git locale**: c'e' un primo commit come fotografia
dello stato, e ogni modifica successiva ha un diff e un ritorno indietro. Non c'e'
un remoto, di proposito: nessuna credenziale, nessun segreto nel repository, e il
lavoro funziona anche offline.

```text
python3 tests/ci.py          # profilo veloce: prima di ogni commit
python3 tests/ci.py --full   # profilo completo: prima di un push (e nel workflow)
python3 tests/ci.py --json   # esito strutturato, per i ganci e per un remoto
```

I ganci sono in `.githooks/` (attivati con `git config core.hooksPath .githooks`):
un commit con la verifica rossa **non parte**.

**Cosa misura.** I registri (coerenza, drift, verbali, errori), i contract attivi,
le suite deterministiche (evidenza, server MCP, generatore configurazioni, e nel
profilo completo la suite storica e il test della CI stessa).

**Cosa NON misura.** Non e' un Quality Gate: prova i programmi, non giudica il
lavoro — il giudizio resta a un revisore indipendente, con la sua evidenza. E non e'
una prova del comportamento dell'agente: quella e' `tools/comportamento.py`.

**Un'eccezione dichiarata, non silenziosa.** `DRIFT-023` (la suite storica si ferma
sui progetti assenti) e' riconosciuta e riportata come «noto» con una firma stretta:
qualunque altro guasto resta un fallimento. Il controllo delle impronte normative
**non** ha eccezioni: dopo `DEC-0061` (2026-10-19) lo snapshot e' riallineato, e una
modifica a un documento normativo senza Decision Record fa fallire la verifica.

| Eccezione | Perche' | Dove si chiude |
|---|---|---|
| `DRIFT-023` · la suite storica si ferma su `13. Commercialista Digitale` | la copia distributiva non ha i progetti numerati | quando la macchina avra' i progetti veri |

Il controllo dell'**albero** e' informativo: il testimone e' una fotografia e
invecchia per progetto fra un gate e l'altro, quindi non blocca un commit.

## Il revisore e' uno strumento (ENG-008, DEC-0062)

Il giudizio resta a un revisore indipendente, ma il **congelamento** e il **brief** li
fa il codice, non la memoria di chi scrive:

```sh
python3 tests/gate_kit.py preflight ENG-XXX   # il gate si apre solo se la batteria e' verde
python3 tests/gate_kit.py freeze    ENG-XXX   # apre il gate: impronte di tutto il write_scope
python3 tests/gate_kit.py brief     ENG-XXX --role qa       # brief per la scatola nera
python3 tests/gate_kit.py brief     ENG-XXX --role review   # brief per chi legge il codice
python3 tests/gate_kit.py check     ENG-XXX   # exit 1 se qualcosa si e' mosso
python3 tests/gate_kit.py close     ENG-XXX   # chiude il gate, solo a revisione immobile
```

**Due revisori, due contesti.** Il verdetto non e' di un agente solo:

| Ruolo | Metodo | Cosa cerca |
|---|---|---|
| **QA** | scatola nera: esegue, non legge il codice | fatti: cosa fa il programma, non cosa dice |
| **Code Review** | legge il codice, non si fida dei test | regole scritte e non applicate, rami morti, default, confini |

I due non si vedono: il brief di ciascuno **esclude l'evidenza dell'altro ruolo**, e
nessuno dei due deve sapere cosa ha concluso l'altro prima di scrivere la propria
evidenza. Il Lead raccoglie i due giudizi e li legge con `tools/verdict.py`; la
chiusura del contract la impedisce il codice (`validate_contract.py` e `ci.py`) finche'
il gate non e' chiuso.

**Il perimetro e' dichiarato (DEC-0064).** Un controllo senza minaccia dichiarata e'
un confine illimitato: sette gate REJECT di fila lo hanno dimostrato. Il kit copre
**dentro il perimetro**: aprire un gate senza preflight, chiudere con un revisore in
corso o con evidenze mancanti, chiudere con il prodotto mosso, bloccare una chiusura
onesta, crashare su input malformato, dichiarare piu' di quanto il codice faccia.
**Fuori perimetro**: riscrivere deliberatamente revisione o registro, ricalcolare i
sigilli (le formule sono pubbliche, non c'e' chiave), cancellare il registro, e in
generale qualunque difesa contro chi ha accesso in scrittura alla macchina. Un difetto
**dentro** il perimetro fa fallire il gate; uno **fuori** e' una nota da backlog, non
un FAIL. Il brief del revisore porta il perimetro.

**Cosa il kit promette, e cosa no.** (DEC-0063) Il kit protegge dalla
**dimenticanza**, che e' il fallimento reale osservato: aprire un gate senza batteria
verde, chiudere un gate mentre un revisore lavora, chiudere con il prodotto mosso. Un
file locale non firmato **non** protegge dal dolo: chi ha accesso in scrittura puo'
riscrivere la revisione. Contro il dolo valgono le altre difese: la storia di git (un
file forgiato si vede), il revisore indipendente (che verifica dall'esterno) e i
bundle sigillati. Il kit lo dice, non lo nasconde.

**A gate aperto non si fanno ATTI AMMINISTRATIVI**: non si chiude il contract, non si
estende il budget, non si ri-registra il testimone, non si modifica il prodotto.
Sono tutti cambiamenti del perimetro giudicato, e ognuno ha un costo (ERR-0057,
quattro ricorrenze). E «evidenza scritta» non significa «gate chiuso»: il revisore
scrive le evidenze prima del messaggio finale, poi verifica ancora.

**Il lucchetto e' nel codice.** `tools/ad_contract.py` rifiuta un contract chiuso
mentre il gate e' ancora aperto (`gate-aperto`), e `tests/ci.py` lo controlla a ogni
verifica (`gate-aperto`): non serve ricordarsi di aspettare il verdetto — la chiusura
prematura e' un errore, non una distrazione. Il gate si apre **solo** con un preflight
verde e fresco (`freeze` lo pretende: il preflight lasciato in `evidenze/.preflight-<task>.json`
vale un'ora), e le impronte coprono **tutto** il `write_scope`: file esistenti, file
dichiarati e non ancora creati («atteso assente»: se compara e' un movimento) e il
contenuto delle directory, file e sottodirectory (aggiunte comprese). La revisione e'
**sigillata** con un digest che copre anche il marcatore di formato: una modifica
ingenua si vede; una riscrittura deliberata del file, no — quello lo mostra git.

**Il registro delle revisioni** (`evidenze/.gate-ledger.yaml`) impedisce che cancellare
una revisione faccia ripartire il contatore da R1, e un registro incoerente fa rifiutare
la chiusura. Ma il registro e' un file: cancellarlo fa ripartire il contatore **in
silenzio** — e' il dolo, fuori dal perimetro di un file non firmato (DEC-0063).

**Limite dichiarato:** un contract **storico**, chiuso prima che esistesse il kit e
senza file di revisione, produce un **avviso** (`gate-non-verificabile`), non una
violazione: la sua chiusura non e' verificabile a posteriori. I contract nuovi hanno
sempre la revisione, quindi per loro vale il blocco. Se un file di revisione viene
cancellato, si torna all'avviso: cancellarlo e' un atto deliberato, e resta visibile
nel messaggio.

**Le classi d'attacco** sono in `tests/gate_kit.py` (`attacks`): percorsi derivati,
caratteri invisibili, forme malformate, stati di default, fail-open sul parametro
assente, promozione di cio' che non funziona, deriva documentale, risorse e
protocollo, confine e autorita', identita' e manomissione, dipendenza dallo stato,
copertura incompleta (12 classi: `python3 tests/gate_kit.py attacks`).
Ogni difetto nuovo che non era in quella lista aggiunge una classe.

## Registrare il server in un client (portatile)

Il server MCP (`tools/ad_mcp/server.py`) espone i dieci strumenti della macchina.
Perche' un client li veda, la sua configurazione deve contenere una voce che lo
avvia. La registrazione **non si copia da un'altra macchina**: ogni macchina la
rigenera, perche' contiene il percorso del server di *quella* macchina.

```sh
python3 tools/ad_mcp/install.py --list                 # i cinque client e dove vivono
python3 tools/ad_mcp/install.py --status auto          # stato su QUESTA macchina
python3 tools/ad_mcp/install.py --apply cursor         # scrive la voce (con backup)
python3 tools/ad_mcp/install.py --apply auto           # registra i client installati
python3 tools/ad_mcp/install.py --apply dsh --dry-run  # mostra, non scrive
python3 tools/ad_mcp/install.py --rollback cursor      # riporta il file com'era
```

`--status` distingue **aggiornata** (voce di questa macchina), **assente** (client non
registrato), **non registrata** (file presente, voce mancante) e **stale** (la voce
punta a un altro percorso, ha plugin/transport/serverName sbagliati o e'
disabilitata): in quel caso si esegue `--apply`, che la riabilita e la corregge. Il comando usa
`python3` dal PATH, quindi un solo campo dipende dalla macchina e si rigenera. Senza
`DSH_PROFILE` il profilo DSH viene rilevato (prima quello che contiene gia' la voce);
se ce ne sono piu' d'uno e nessuno la contiene, il comando **rifiuta** chiedendo
`DSH_PROFILE` invece di inventare un profilo; i permessi del file si conservano (600 resta 600).

**Cosa l'agente puo' verificare**: che la voce sia nella forma giusta, che il server
risponda ai dieci strumenti, che il file di configurazione resti valido e che il
rollback riporti il file **byte-identico**. **Cosa non puo' verificare**: l'interfaccia
del client — dopo il riavvio, che gli strumenti siano visibili lo guarda l'umano.

**Prudenza**: ogni scrittura fa un backup (il primo, e non lo sovrascrive) e
`--rollback` lo ripristina. Nessun client viene riavviato dall'agente: la
configurazione si scrive, non si forza.

## La prompt del revisore si genera, non si scrive

**La cartella si decide al lancio.** La sessione nasce nella cartella della macchina,
e ogni strumento trova la radice da `Path(__file__)`: nessuno deve dire a un agente
dove sta la macchina. Per questo al revisore non si dice la cartella, e **un percorso
assoluto in una prompt e' un errore** (`ERR-0064`): funzionerebbe su quella copia e
sbaglierebbe su ogni altra.

La prompt la scrive il codice:

```sh
python3 tests/gate_kit.py prompt ENG-XXX --role qa       # prompt per la scatola nera
python3 tests/gate_kit.py prompt ENG-XXX --role review   # prompt per chi legge il codice
```

Il comando stampa ruolo, metodo, comando per leggere il brief, perimetro, divieto di
chiudere il gate, file dell'evidenza e comando del verdetto — tutto con percorsi
**relativi**. Un test impone che ne' la prompt ne' il brief contengano la radice della
macchina: se qualcuno li rimette, la CI diventa rossa.
