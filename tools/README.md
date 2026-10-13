# tools — fascia deterministica

Codice che esegue la governance di AD Projects **senza consumare token**: e' la
fascia 1 di [MODEL-ROUTING.md](../MODEL-ROUTING.md). Non aggiunge agenti, non
modifica permessi e non scrive nei documenti normativi: li legge.

## Il registro dei comandi

I comandi che vivono in questa cartella sono dichiarati **qui**, e in nessun altro
posto. Ogni riga dice tre cose: il **nome** (il file), **cosa fa in parole
comprensibili** — al CEO non si parla in gergo (invariante 14) — e la **forma
d'uso**. `tools/coherence.py` confronta questa tabella con i file che esistono
davvero: un comando non dichiarato, una riga che nomina un comando che non c'e'
piu', una descrizione vuota e una forma d'uso copiata dalla riga sbagliata fanno
fallire il controllo.

**Aggiungere uno strumento si fa qui**, in una riga. Non si scrive nella
costituzione: quella e' il livello che ogni agente legge a ogni avvio, e ogni riga
in piu' li' la pagano tutti.

### Elenco e procedura sono due cose diverse

L'**elenco** e' questa tabella: tutti i comandi che esistono, anche quelli che si
chiamano di rado. Cresce a ogni strumento nuovo, e per questo vive accanto al
codice che descrive.

La **procedura** e' la sequenza dei passi per aprire un lavoro, e sta in
`.brain/COSTITUZIONE.md` e nella skill `ad-kickoff`. Li' restano i pochi comandi
che sono un passo obbligato — `cards.py match` (passo 4), `blueprint.py render`
(passi 6 e 12), `milestone.py new-milestone` e `new-sprint` (passi 9 e 10),
`stato.py render` (passo 12) — perche' chi apre un lavoro deve trovarli **nella
sequenza**, non in un file che deve sapere di aprire.

Un comando nuovo entra nell'**elenco**. Entra nella **procedura** solo se diventa un
passo che nessuno puo' saltare: non e' la stessa decisione, e non si prendono
insieme.

| Comando | Cosa fa, in parole comprensibili | Come si usa |
|---|---|---|
| `blueprint.py` | **la carta d'identita' di un progetto**: dice cos'e' e a che punto e', e non puo' mentire perche' e' sigillato con un'impronta | `python3 tools/blueprint.py render "<progetto>"` (o `check`) |
| `camoufox_ponte.py` | **il ponte verso il browser vero**: si usa quando una pagina non si lascia leggere, e non si chiama da solo — lo chiama `ricerca.py` | `python3 tools/camoufox_ponte.py "<url>"` |
| `cards.py` | **chi sa fare cosa**: cerca il mestiere giusto per un lavoro, e tiene in ordine l'elenco dei mestieri | `python3 tools/cards.py match <task-type>` (o `list`, `show`, `check`) |
| `coherence.py` | **il controllo di coerenza**: verifica che il regolamento descriva il sistema vero, e non una versione vecchia | `python3 tools/coherence.py` |
| `comportamento.py` | **le prove sull'agente**: dice se un cambiamento ci ha reso peggiori, confrontando l'esito con la misura di partenza | `python3 tools/comportamento.py check` |
| `contributo.py` | Il documento per raccontare un problema: lo **genera** il sistema, con le domande dentro, in italiano e inglese. Chi arriva non deve sapere niente di questo motore per contribuire. | `python3 tools/contributo.py nuovo` · `importa <file>` |
| `contract_scope.py` | **il controllo del perimetro**: dice se un posto si puo' scrivere, e il controllore lo interroga prima di ogni scrittura | `python3 tools/contract_scope.py check <path>` |
| `drift.py` | **le discrepanze**: tiene l'elenco dei punti in cui i documenti dicono una cosa e la realta' un'altra | `python3 tools/drift.py check` |
| `errori.py` | **le cicatrici**: ogni sbaglio con scritto accanto cosa lo avrebbe fermato, e se stiamo imparando o avendo fortuna | `python3 tools/errori.py check` (o `stats`, `nuovo`) |
| `milestone.py` | **le tappe e i passi di un progetto**: apre la tappa, apre il passo, e verifica che i rapporti ci siano tutti | `python3 tools/milestone.py check "<progetto>"` (o `new-milestone`, `new-sprint`) |
| `misure.py` | **la macchina delle misure**: esegue le misure di una verifica e scrive la prova con il comando, l'esito e il momento | `python3 tools/misure.py run <elenco.yaml> --out <allegato.md>` |
| `progetto.py` | **i progetti**: crea un progetto nuovo col numero giusto, collega una cartella esistente, ed elenca quelli che ci sono | `python3 tools/progetto.py elenca` (o `nuovo "<nome>"`, `collega "<percorso>"`) |
| `ricerca.py` | **la lettura del web**: prova prima la via leggera e chiama il browser solo quando la pagina non si lascia leggere | `python3 tools/ricerca.py leggi "<url>"` |
| `security_scan.py` | **i controlli di sicurezza**: cerca password in chiaro, dipendenze con falle note e istruzioni mascherate nel materiale di studio | `python3 tools/security_scan.py "<progetto>"` |
| `setup.py` | **l'installazione**: collega la macchina al programma che la usa — il cancello, la costituzione, le skill — **ovunque la macchina sia**. E lo prova con una scrittura che deve essere rifiutata | `python3 tools/setup.py` (o `--check`, `--uninstall`, `--ide <nome>`) |
| `stato.py` | **la vista operativa**: cosa e' aperto, come si comporta l'agente e cosa aspetta una decisione del CEO | `python3 tools/stato.py render` (o `check`) |
| `validate_contract.py` | **il controllo del permesso**: dice se un lavoro puo' partire, prima che parta | `python3 tools/validate_contract.py <contract.yaml>` |
| `verbali.py` | **i verbali seguiti davvero**: le opzioni scartate, cosa succede se non si fa niente, e l'esito misurato | `python3 tools/verbali.py check` |
| `verdict.py` | **il verdetto**: passa o non passa leggendo le prove, e non accetta che a validare sia chi ha fatto il lavoro | `python3 tools/verdict.py --contract <contract.yaml> --evidence <path>` |

### Note: quello che una riga non contiene

Le righe qui sopra dicono **cosa fa** ogni comando. Queste note dicono il resto:
i dettagli, i codici di uscita, e perche' un comportamento e' fatto cosi'. Non sono
una seconda dichiarazione dell'elenco: se un comando non e' nella tabella, per il
controllo non esiste, qualunque cosa dicano queste righe.

I test dei validatori stanno in `tools/tests/test_ad_org.py` — si eseguono con
`python3 tools/tests/test_ad_org.py`, e si fermano al primo controllo fallito. Sono
loro a provare che il registro sappia **fallire**: un comando non dichiarato, un
nome che non esiste piu', una descrizione segnaposto.

`misure.py` esegue le misure di una verifica e **genera** l'allegato delle prove:
per ogni misura il comando, l'esito, il codice di uscita e il momento. Le misure
stanno in un **elenco dichiarato** (`tools/misure-liste/`), non nel codice, e
nessuna misura e' scritta a mano: un numero vecchio non si legge come attuale e un
comando che fallisce viene riportato col suo codice invece di sparire (`DEC-0044`,
il rimedio ai tre `FAIL` sulla forma del report del 10-11 ottobre).

Esegue comandi **di sola lettura**, e li rifiuta per **famiglia**: scrittura sul
filesystem, strumenti che scrivono file, storia di git, esecuzione annidata,
interpreti con codice inline, linguaggi che eseguono comandi, testo che diventa
codice, redirezioni, scaricamenti, processi, pacchetti. Il rifiuto e' **spiegato**
— dice la famiglia e come riformulare. La validazione dell'intero elenco viene
prima dell'esecuzione: se una voce e' vietata non parte niente e non si scrive
niente. La guardia di ambito (`ad_scope.guard`) e' chiamata prima di eseguire **e**
dentro `scrivi`, l'unico punto in cui lo strumento tocca il disco.

Ma il rifiuto **non e' un sandbox**, e va detto qui e non solo nel codice: un
comando che scrive senza somigliare a nessuna di quelle forme **non viene visto** —
il caso dichiarato e' `python3 tools/<programma>.py`, dove quello che succede lo
decide il programma. La prima versione dello strumento prometteva la sola lettura;
un gate ha dimostrato che era falso eseguendo dieci forme che passavano, fra cui
`git -C . commit`, che ha creato un commit vero. Quelle forme ora si rifiutano, la
promessa no: il testo del limite vive in `misure.LIMITE_RIFIUTO`, e finisce
**dentro l'allegato**, che e' l'artefatto che si cita come prova.

La **riproducibilita'** non e' una promessa: l'allegato porta in testa l'impronta
stabile — lo `sha256` del documento con i momenti sostituiti — e `confronta`
verifica due file veri. Le uniche righe che cambiano sono quelle dichiarate in
`PREFISSI_VARIABILI`, e sono tutte un momento. **A parita' di mondo**: se un
registro o un file si muove, l'impronta cambia, ed e' il punto.

Resta un caso che nessuna maschera toglie, ed e' dichiarato invece che nascosto:
**un comando puo' stampare un valore che dipende dal tempo** — `coherence.py`
scrive l'ora corrente nei suoi messaggi, e un gate l'ha trovato contando tre
impronte diverse a mondo fermo. Quelle righe contano nell'impronta, perche'
mascherarle nasconderebbe anche una differenza vera che capita nello stesso output.
La misura lo dichiara con `tempo_nell_output: true`, e `misure.py confronta`
**separa** le differenze dichiarate da quelle vere mostrandole entrambe: non si
sceglie quale delle due far vedere.

Codici di uscita: `run` esce 0 quando ogni misura ha l'esito dichiarato, 1 quando
una e' andata diversamente (l'allegato c'e' lo stesso, ed e' il punto), 2 quando
l'elenco e' rifiutato o l'allegato non e' scrivibile.

`contract_scope.py` e' l'**autorita' dell'enforcement di runtime**: il plugin
`.brain/plugin/enforce-contract` lo interroga prima di ogni scrittura e non
reimplementa la regola. Esce 0 quando il percorso e' ammesso, 1 quando e'
bloccato.

Un percorso e' ammesso solo se valgono **tutte** queste condizioni: il contract e'
attivo, il suo `write_scope` include il percorso, esiste il marcatore di
approvazione del CEO in `approvazioni/<task_id>.yaml`, e il contract **non** e'
stato scritto prima del marcatore. Senza consenso depositato, nessuna scrittura.

Due classi di percorso sono protette: le **cartelle prodotto** (i percorsi che
iniziano con un numero) e gli **artefatti di governance** (`.brain/`, `tools/`).
La seconda ha un raggio d'azione piu' ampio: `.brain/` e' symlinkato in
`~/.dsh/AGENTS.md` e nelle skill globali, e `tools/` e' l'autorita' che il plugin
interroga. `contratti/` e `approvazioni/` restano liberi perche' sono l'input
dell'autorizzazione.

`milestone.py` verifica che la storia di un progetto sia completa — ogni sprint con
`PROMPT.md` e `REPORT.md`, ogni milestone con `REPORT.md`, numerazione contigua — e
apre milestone e sprint dai modelli in `milestone/`. **Si rifiuta di scrivere** in
una cartella prodotto non coperta: le scritture fatte da uno script non passano
dall'euristica della shell del plugin, quindi la guardia sta dentro lo strumento.

Codici di uscita: `cards.py check --strict` esce 1 se trova problemi di
integrita'; `validate_contract.py` esce 1 con almeno una violazione (o con una
WARNING se `--strict`); `verdict.py` esce 0 su `ACCEPT` e 1 su `REJECT`. Sono
utilizzabili come gate di pipeline.

## Cosa verifica il validatore di contract

| Regola | Documento |
|---|---|
| Campi obbligatori presenti e non vuoti | TASK-CONTRACTS.md, Schema |
| `domain` coerente con il dominio della card | GOVERNANCE-AZIENDALE.md |
| Il contract non si assegna a una card dell'altro dominio | GOVERNANCE-AZIENDALE.md |
| La card esiste ed e' `inactive` | RUNTIME.md, Avvio |
| Match esplicito con `authorized_task_types`, nessun `excluded_task_types` | SPECIALIZATION.md, RUNTIME.md |
| Il contract toglie permessi, non ne aggiunge | RUNTIME.md, Permessi |
| Ogni gate e' nel catalogo e almeno uno e' richiesto | QUALITY-GATES.md |
| Chi esegue non e' l'owner di default del gate che deve validarlo | GOVERNANCE-AZIENDALE.md |
| Il Decision Record citato esiste ed e' approvato | GOVERNANCE-AZIENDALE.md |

Due livelli di esito:

- **VIOLATION** — la regola e' violata, il task **non parte**.
- **WARNING** — il documento non permette di verificare la condizione. Il caso
  tipico: il contract non dichiara `task_type`, quindi il match resta una
  dichiarazione e non un controllo. Con `--strict` anche gli avvisi falliscono.

## Formato dell'evidenza

[QUALITY-GATES.md](../QUALITY-GATES.md) dice **cosa** deve dichiarare
un'evidenza ma non in quale contenitore. Il contenitore minimo e':

```yaml
task_id: BIO-142
gate: QA
outcome: PASS          # PASS | FAIL
producer: qa           # card che ha prodotto l'evidenza
artifact_producer: backend    # opzionale
timestamp: 2026-10-08T07:20:00+02:00   # opzionale, decide nel rework
references:
  - artefatti/report.txt
```

Un'evidenza che non dichiara `task_id`, `gate`, esito e produttore **non
conta**. Se il produttore e' l'esecutore del contract, l'evidenza e' invalida:
chi produce un artefatto non ne valida il gate.

## Limiti dichiarati

Il validatore controlla cio' che i documenti permettono di controllare. Non
verifica la veridicita' di un'evidenza, non esegue test e non applica i permessi
a runtime: questo e' un gate di coerenza documentale, non un sandbox. Il
`Card.assignable` vale `False` per le card business perche' il catalogo non
dichiara `authorized_task_types`: e' una lacuna dei documenti, non del codice, e
il validatore si ferma invece di indovinare.

Lo stesso vale per il registro dei comandi, e va detto invece di lasciarlo
credere: il controllo pretende che ogni comando abbia una **descrizione**, non che
la descrizione sia **chiara**. La chiarezza non si misura — un controllo che
pretendesse di misurarla sarebbe un controllo che non puo' fallire, e quindi
nessun controllo. Che le parole siano comprensibili lo giudica chi legge
(invariante 14).
