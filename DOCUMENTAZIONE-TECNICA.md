# AD-AGENTS-PROJECTS — documentazione tecnica

**Per sviluppatori.** Descrive cosa fa il motore, come è costruito e perché ogni pezzo è
fatto così. Non è una guida per l'utente: quella è il [README](README.md), e la mappa
visiva è il [GRAFO](GRAFO.md).

> **Come leggerla.** Ogni affermazione qui dentro viene da codice che è stato letto o da un
> comando che è stato eseguito, con il risultato riportato. Dove non c'è una verifica, c'è
> scritto che non c'è. È una regola di questo progetto: **un documento che afferma senza
> verificare è un documento che invecchia in silenzio**, ed è esattamente il difetto che il
> motore esiste per impedire.

---

## 1 · Il problema

Un agente AI che lavora su un progetto reale ha tre difetti strutturali:

1. **Scrive dove non dovrebbe.** Nessuna capacità gli manca; quello che manca è un confine.
2. **Dimentica.** Tra una sessione e l'altra non sa cosa è stato deciso, da chi, e perché.
3. **Non sa di aver sbagliato.** Un errore non registrato si ripete; una regola scritta non
   cambia il comportamento.

Le soluzioni consuete sono tutte **discipline**: un `AGENTS.md` più lungo, un prompt di
sistema più severo, una convenzione di squadra. Una disciplina **non fallisce mai in modo
visibile**: non c'è niente che si rompa quando viene ignorata.

Questo motore prende una strada diversa: **dove un controllo è possibile, la disciplina è
sostituita da un controllo che fallisce.**

## 2 · La tesi, e i suoi tre corollari

> **Una regola scritta non cambia il comportamento. Un controllo che fallisce sì.**

Da qui discendono le tre scelte che attraversano tutto il codice:

**a · Il numero è la protezione.** Una cartella di progetto si chiama `18. Nome`. Il numero
davanti non è estetica: è ciò che dice al sistema che quella cartella è un prodotto, e da lì
discendono il permesso, l'approvazione e il cancello. Verificato: senza numero, una cartella
passa il cancello — nessun permesso, nessuna approvazione, e nessuno se ne accorge.

**b · Un errore corretto diventa un controllo.** Se si può meccanizzare, diventa codice che
si rompe. Se non si può, resta una nota. **La terza domanda è quella che conta**: non solo
*cosa è fallito* e *cosa l'ha risolto*, ma **cosa lo avrebbe preso**.

**c · Un fallimento si dichiara, non si nasconde.** Il plugin non può disfare una scrittura:
lo **dice**. Un programma senza gancio riceve le regole e nessuno lo ferma: lo **dice**. Il
registro delle cicatrici è curato e non completo: lo **dice**.

## 3 · Come è stata costruita

Questa sezione esiste perché **il modo in cui il motore è nato è la sua documentazione più
onesta**. Cinque giorni, e la forma della curva non è casuale.

| Giorno | Verbali | Cicatrici | Cosa succedeva |
|---|---|---|---|
| 2026-10-08 | 27 | 6 | la governance: livelli, contratti, card, il primo cancello |
| 2026-10-10 | 11 | 10 | il cervello: skill, plugin, il Blueprint |
| 2026-10-11 | 14 | 25 | **il giorno peggiore**: due sessioni, id duplicati, registri scritti a mano |
| 2026-10-12 | 0 | 3 | il lavoro sui progetti, non sulla macchina |
| 2026-10-13 | 4 | 4 | la portabilità, l'ingresso, i numeri come regola |

**Il picco del 2026-10-11 è il punto di svolta.** Venticinque cicatrici in un giorno, quasi
tutte della stessa famiglia: **qualcosa scritto a mano che poteva essere controllato**.
Ventisei verbali in tre giorni, e il modello seguito solo in tre casi su trentasei.

Da lì nasce il criterio che oggi governa ogni pezzo nuovo:

> **Se puoi meccanizzarlo, fallo adesso. Altrimenti scrivi perché non puoi.**

**E il criterio si applica anche a sé stesso**, con una conseguenza che vale la pena dire:
il registro delle cicatrici **si è accorciato** quando le sue voci sono diventate controlli.
Da 47 a 17 file. Un registro che si allunga è un registro che non sta diventando codice.

### 3.1 · Le cicatrici che sono diventate controlli

| Era una cicatrice | Adesso è | Dove |
|---|---|---|
| due sessioni scelsero lo **stesso id** | `ad_docs.prenota_id()`, atomico con `O_CREAT\|O_EXCL` | `ad_docs.py` |
| un verbale senza opzioni e senza «non fare nulla» | `verbali.py check` | `verbali.py` |
| rapporti di passo senza le sei sezioni | il controllo in `milestone.py check` | `milestone.py` |
| un CAPTCHA scambiato per una pagina da leggere | il muro in `leggo`/`e_un_muro` | `ricerca.py` |
| un 403 letto come «link morto» | `verifica` distingue 404 da 403 | `ricerca.py` |
| un progetto senza numero passava il cancello | il blocco in `evaluate()` | `ad_scope.py` |
| **due permessi sullo stesso percorso** | `conflitti_di_raggio()` + l'esenzione dichiarata | `ad_contract.py` |
| l'**ordine letto dagli mtime** | confronto fra **date dichiarate** | `ad_scope.py`, `comportamento.py` |

### 3.2 · I tre criteri che si sono corretti eseguendoli

Un dato che vale più di una descrizione: **tre criteri di selezione sono stati sbagliati, e
tutti e tre si sono visti solo eseguendoli.**

1. **«Tengo le cicatrici che il sistema cita»** — cercando le citazioni **dentro i registri**,
   ogni cicatrice ne cita un'altra, e non si toglieva niente. Le fonti devono essere **il
   sistema** (regole, controlli, prove, drift, contratti), non i registri filtrati.
2. **Lo stesso criterio, corretto** — una cicatrice **nuova** non è ancora citata da nessuno,
   quindi veniva cancellata subito, e **il registro non poteva crescere**.
3. **«I documenti di root sono tutti normativi»** — ma un `README` è una porta e un `GRAFO`
   è una spiegazione. Il problema cresceva **a ogni documento aggiunto**, che è il segno che
   la domanda era sbagliata.

## 4 · L'architettura in una schermata

```text
AD-AGENTS-PROJECTS/
├── AGENTS.md              symlink → .brain/COSTITUZIONE.md   la porta
├── sede.yaml              chi e' il CEO, dove sono i progetti (NON versionato)
├── .brain/
│   ├── COSTITUZIONE.md    15 invarianti, la sequenza, i limiti dichiarati
│   ├── skills/            9 procedure (SKILL.md con frontmatter)
│   └── plugin/            il cancello: due hook Cordis
├── tools/                 18 comandi + 9 librerie ad_*.py
│   └── tests/             la suite deterministica
├── contratti/  approvazioni/     il registro delle autorizzazioni
├── DECISIONI/  errori/  drift/   la memoria
├── milestone/  orchestrazione/   modelli e vista generata
├── evals/                 la baseline comportamentale
└── strategic_memory/      retrieval selettivo
```

**Tre confini, e ognuno è una decisione:**

- **`.brain/` e `tools/` sono governance.** Una scrittura lì cambia il comportamento di
  **tutti** gli agenti, in ogni sessione. Sono protetti come le cartelle prodotto, ma il
  raggio d'azione è più ampio — e per questo il cancello li tratta a parte.
- **`contratti/` e `approvazioni/` sono liberi.** Sono l'**input** dell'autorizzazione:
  proteggerli impedirebbe di creare il primo contratto. È un bootstrap, ed è deliberato.
- **La radice contiene la macchina, non le carte dei progetti.** Quelle vivono in
  `<progetto>/Analisi-Prompt-Report/`. La regola è l'invariante 15, e ha un motivo
  meccanico: se le carte dei progetti stanno nella radice, il numero di file non
  governabili cresce con il numero di progetti.

## 5 · La portabilità: cosa viaggia e cosa no

Verificato il 2026-10-13 spostando la macchina e facendo girare tutto da lì.

| Livello | Portabile | Perché |
|---|---|---|
| Le regole | **sì** | sono un documento che il programma legge |
| I comandi | **sì** | sono processi Python: li esegue chiunque abbia Python |
| I registri | **sì** | sono file |
| La ricerca web | con SearxNG | è un servizio locale, non un file |
| **Il cancello che blocca** | **no** | è un plugin, e vive nel profilo del programma |

**Due cose sono state rimosse per renderlo vero:**

1. **Un percorso assoluto nella costituzione.** La prima riga diceva *«questo blocco vale
   solo per lavori dentro `/home/luka/...`»* — e un altro utente veniva istruito a
   **ignorare le regole**.
2. **La dipendenza dagli mtime.** Il controllo che verifica «prima il consenso, poi il
   permesso» leggeva `st_mtime`. Una copia — o un `git clone` — li azzera: il controllo
   **accusava un contratto di essere retrodatato quando era solo copiato**. Una falsa accusa
   è peggio di un controllo mancante, perché insegna a ignorarlo. Ora si confrontano le
   **date dichiarate nei documenti**, che viaggiano con i documenti.

**E una distinzione che il codice fa esplicitamente**: il motore e i progetti possono essere
**due cartelle diverse** (`ad_docs.DOCS_ROOT` e `ad_docs.PROGETTI_ROOT`). Gli scope dei
contratti sono scritti **relativi ai progetti**, e il controllo lo sa. Quando la cornice è il
motore, i permessi si risolvono rispetto ai progetti; quando chi chiama passa una radice sua
— una cartella di prova — **quella** è la cornice, e non si scavalca.

## 6 · I limiti dichiarati

Questa sezione è deliberata, e non è una formalità. Il motore si rifiuta di dichiarare un
controllo che non c'è stato; per coerenza, dichiara anche i propri.

| Limite | Conseguenza | Dichiarato in |
|---|---|---|
| **Il cancello non si acquisisce, si installa** | collegare la cartella dà le regole, non il blocco | `README.md`, `COSTITUZIONE.md` |
| **Gli adattatori per altri IDE sono dichiarati, non provati** | Claude Code, Codex, Antigravity: mai eseguiti su questa macchina | `setup.py`, `AMBIENTI` |
| **Cursor non ha un gancio** | riceve regole, non un cancello | decisione `DEC-0039` |
| **I permessi per-card non sono imposti** | il plugin verifica il `write_scope`, non che la card sia autorizzata a quel task | `COSTITUZIONE.md` |
| **L'analisi della shell è un'euristica** | un comando che fa `cd` e poi scrive in modo relativo può sfuggirgli | `COSTITUZIONE.md` |
| **Il plugin non disfa la scrittura** | la metà `post-execute` **avvisa** dopo | `index.mjs` |
| **`verifica` non dice se una fonte dice quello che le attribuiamo** | dice che **esiste**. Un link vivo che non contiene la frase citata resta un problema | `DEC-0053` |
| **Il registro delle cicatrici è curato, non completo** | e lo dichiara | `errori/README.md` |
| **La ricerca web non copre il web aperto** | senza Brave, la categoria `general` non ha motori: **0 risultati**, misurato | `DEC-0053` |

## 7 · Glossario per chi legge il codice

| Termine nel codice | Cosa significa |
|---|---|
| **contract** | un permesso: dichiara *chi* può scrivere *dove*, per quale tappa e quale passo |
| **marcatore** | l'approvazione del CEO. Senza, il contract non copre nulla |
| **write_scope** | l'elenco dei percorsi che il contract copre. **Relativi ai progetti.** |
| **governance** | `.brain/` e `tools/`: ciò che cambia il comportamento di tutti |
| **cartella prodotto** | un percorso che inizia con un numero |
| **cartella macchina** | un elenco **dichiarato** (`CARTELLE_MACCHINA`): non sono progetti |
| **raggio** | nel lessico degli errori, il `write_scope` di un contract |
| **sigillo / impronta** | l'`sha256` del blocco generato di un Blueprint |
| **drift** | una divergenza fra ciò che i documenti dicono e ciò che il sistema fa |
| **cicatrice** | una voce di `errori/`: cosa è fallito, cosa l'ha risolto, **cosa lo avrebbe preso** |
| **banda deterministica** | i comandi che eseguono la governance **senza consumare token** |

---
## 8 · Il modello di autorizzazione

*(Questa sezione e' stata estratta leggendo `tools/ad_scope.py`, `tools/ad_contract.py`,
`tools/contract_scope.py` e `.brain/plugin/enforce-contract/index.mjs`. I riferimenti
`file:riga` sono verificabili.)*

Il motore ha **un solo posto** in cui la domanda «posso scrivere qui?» riceve risposta:
`tools/ad_scope.py`. Il layer di runtime **non reimplementa** la regola: la interroga, via
`tools/contract_scope.py`.

### 8.1 · Le tre serrature

Un percorso protetto e' coperto solo quando valgono **tutte** queste condizioni, e
`coverage()` (`ad_scope.py:287`) le verifica in quest'ordine:

1. **Il contract copre** — esiste un contract attivo, non scaduto, con un `write_scope` che
   include il percorso (`load_write_scopes()` + `WriteScope.covers()`).
2. **Il marcatore del CEO** — esiste `approvazioni/<task_id>.yaml` con `task_id`,
   `approvato_da` e `data` non vuoti (`load_approvals()`).
3. **L'ordine consenso -> permesso** — la data che il permesso *dichiara* non e' successiva
   a quella dell'approvazione.

La serratura 1 e' doppia: il contract deve essere anche nello **stato** giusto.
`ACTIVE_STATES = ("active", "attivo", "approvato")` (`ad_scope.py:45`) e `_expired()`
scarta chi ha `expires` nel passato (`ad_scope.py:113`):

```python
# tools/ad_scope.py:150
        raw = data.get("write_scope")
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list) or not raw:
            continue
        status = str(data.get("status", "active")).strip().lower()
        if status not in ACTIVE_STATES or _expired(data.get("expires")):
            continue
```

La serratura 2, senza la quale il contract copre «nulla» (`ad_scope.py:309`):

```python
        approval = approvals.get(scope.task_id)
        if approval is None:
            return None, (
                f'Il contract {scope.task_id} copre "{relative}" ma manca '
                "l'approvazione del CEO.\nSenza consenso non si lavora: serve "
                f"{approvals_dir(root_path)}/{scope.task_id}.yaml con task_id, "
                "approvato_da e data (GOVERNANCE-AZIENDALE.md)."
            )
```

Un marcatore **incompleto** viene ignorato in lettura: senza `task_id`, `approvato_da` o
`data` il file non entra nel dizionario (`ad_scope.py:275`).

**L'ordine si legge dalle date dichiarate, non dagli mtime.** Il motivo e' nel commento
stesso del codice (`ad_scope.py:318-342`): una copia della macchina — o un `git clone` —
azzera gli mtime, quindi un controllo basato sugli orari dei file **accusa di retrodazione
un permesso che e' solo stato copiato**. *«Un controllo che sbaglia cosi' insegna a
ignorarlo, che e' peggio di non averlo.»* Se la data dichiarata manca, non si accusa e non
si tace: si lascia passare, e il permesso resta **non verificabile**, elencabile con
`contract_scope.py titolari`.

```python
# tools/ad_scope.py:343
            if scope.aperto and str(scope.aperto)[:10] > str(approval.data)[:10]:
                return None, (
                    f'Il contract {scope.task_id} e\' stato scritto PRIMA '
                    f"dell'approvazione ({approval.data}).\nL'ordine e' "
                    "ricerca -> risposta -> consenso -> contract: un contract "
                    "retrodatato non copre."
                )
```

Il campo che porta la data viaggia col documento (`ad_scope.py:75`) e viene troncato a 10
caratteri, cioe' al **giorno** (`ad_scope.py:173`): l'ordine sta nella giornata, non nel
secondo.

### 8.2 · La quarta serratura, condizionata alla tappa

Se il contract dichiara `milestone` e `sprint`, il permesso copre **solo** le carte di quella
tappa **finche' il passo non e' aperto**. Il motivo e' un cane che si morde la coda: per
aprire il passo serve il permesso, e per avere il permesso servirebbe il passo aperto.

```python
# tools/ad_scope.py:364
        if scope.milestone is not None and scope.sprint is not None:
            radice_progetto = (Path(root_path) / _primo_progetto(scope.scopes)
                               if _primo_progetto(scope.scopes) else None)
            if radice_progetto is not None:
                prompt = ad_milestone.sprint_prompt(
                    radice_progetto, scope.milestone, scope.sprint)
                if not prompt.is_file():
                    ...
```

`sprint_prompt()` (`ad_milestone.py:206`) risolve
`Analisi-Prompt-Report/Milestone N/Sprint M/PROMPT.md`. La deroga copre l'**intera cartella
della tappa** (`Milestone N/`), non solo il passo, perche' per aprire un passo bisogna prima
creare la tappa, e il rapporto della tappa sta li'.

### 8.3 · Come si risolve un percorso

```python
# tools/ad_scope.py:188
def relative_to_root(target: Path | str, root: Path | str) -> str | None:
    try:
        return Path(target).resolve().relative_to(Path(root).resolve()).as_posix()
    except (ValueError, OSError):
        return None
```

`resolve()` **segue i symlink**: fuori dall'albero restituisce `None`, e `guard()` tratta
quel `None` come **rifiuto**, non come permesso (`ad_scope.py:625`).

Le tre classificazioni guardano tutte il **primo** segmento del percorso relativo, quindi si
escludono a vicenda:

```python
# tools/ad_scope.py:42
PROTECTED_DIR = re.compile(r"^\d+\.")
```

```python
# tools/ad_scope.py:196  ·  ad_scope.py:204
def protected_segment(relative):
    if not relative: return None
    head = relative.split("/", 1)[0]
    return head if PROTECTED_DIR.match(head) else None

def governance_segment(relative):
    if not relative: return None
    head = relative.split("/", 1)[0]
    return head if head in GOVERNANCE_PATHS else None
```

con `GOVERNANCE_PATHS = (".brain", "tools")` (`ad_scope.py:38`).

«Tutto il resto» **non e' una funzione**: e' il caso in cui entrambe restituiscono `None` — e
allora o e' una cartella macchina dichiarata, o e' una cartella **non numerata** (che viene
bloccata), o e' fuori dalle classi protette e passa.

L'elenco delle cartelle macchina e' **dichiarato**, non dedotto (`ad_scope.py:408`):

```python
CARTELLE_MACCHINA = frozenset({
    ".brain", ".git", "tools", "tests", "DECISIONI", "approvazioni",
    "comunicazioni", "contratti", "drift", "errori", "evals", "evidenze",
    "milestone", "orchestrazione", "piani", "REQUISITI", "strategic_memory",
    "studio", "AD-AGENTS-PROJECTS",
})
```

Il commento che lo precede dice perche' non si deduce: *«dedurlo da cosa esiste vorrebbe dire
accettare come "macchina" qualunque cartella qualcuno crei — che e' il buco da chiudere»*
(`ad_scope.py:405-407`).

**Da notare**: `GOVERNANCE_PATHS` e' un **sottoinsieme** di questo elenco. `DECISIONI`,
`piani`, `errori` ecc. sono **macchina ma non governance**, e infatti restano scrivibili
senza contract — ed e' voluto: sono i registri che gli strumenti scrivono.

### 8.4 · La risoluzione doppia: motore e progetti, due cartelle

`evaluate()` risolve il percorso **due volte**. La cornice normale e' la root del motore
(`ad_docs.DOCS_ROOT`, il genitore di `tools/`); ma se il percorso sta sotto
`ad_docs.PROGETTI_ROOT` — dichiarato in `sede.yaml` come `macchina.progetti`, altrimenti
«accanto a me» — allora la relativizzazione si fa **rispetto ai progetti**.

```python
# tools/ad_scope.py:481
    progetti = ad_docs.PROGETTI_ROOT
    relative = relative_to_root(target, root_path)
    if root_path == ad_docs.DOCS_ROOT and progetti != root_path:
        fuori = relative_to_root(target, progetti)
        if fuori and not str(fuori).startswith(".."):
            relative = fuori
```

Il commento sopra il blocco (`ad_scope.py:465-480`) dice cosa succedeva senza: il raggio di
un contract e' scritto **relativo ai progetti** (`11. Modelbel/...`), ma veniva risolto
**rispetto al motore**. Finche' i due stanno nella stessa cartella **non si vede**; appena si
separano **il permesso non copre piu' niente** e le scritture nei progetti passano.

La clausola `root_path == ad_docs.DOCS_ROOT` e' **deliberata**: solo quando la cornice e' il
motore si scavalca al ramo progetti. Se chi chiama passa una radice sua — una cartella di
prova, un progetto singolo — **quella** e' la cornice, e non si scavalca. (Questa clausola
e' nata da una regressione: la prima versione scavalcava sempre, e le prove dei test — che
girano dentro la cartella dei progetti — smettevano di essere coperte.)

L'altro lato della doppia risoluzione e' in `primo_numero_libero()`, che conta i numeri usati
**fra i progetti**, non nella cartella del motore (`ad_scope.py:433-437`).

I **registri**, invece, restano sempre nella cartella del motore: `contracts_dir()` e
`approvals_dir()` compongono `root / "contratti"` e `root / "approvazioni"`
(`ad_scope.py:108`, `ad_scope.py:242`). Ed e' li' che il controllore li legge a ogni
scrittura.

### 8.5 · Le altre uscite di `evaluate()`

L'ordine delle decisioni conta:

| Caso | Esito | Riga |
|---|---|---|
| Cartella non in `CARTELLE_MACCHINA`, non numerata, **esistente** | rifiuto, col numero da usare | `ad_scope.py:501-527` |
| Ne' prodotto ne' governance | passa (`protected=False`) | `ad_scope.py:529` |
| Prodotto o governance **coperti** | passa | `ad_scope.py:533` |
| Prodotto o governance con **motivo** di rifiuto | rifiuto | `ad_scope.py:535` |
| Governance non coperta | rifiuto, col rimedio | `ad_scope.py:538-550` |
| Prodotto non coperto | rifiuto, con l'elenco dei contract attivi | `ad_scope.py:552-584` |

`allowed` e' la sintesi: `covered or not protected` (`ad_scope.py:103`).

Il blocco sulle cartelle non numerate e' esplicito sul perche' (`ad_scope.py:517`):

```python
                    f'"{testa}" non e\' una cartella di macchina, e non e\' numerata.\n'
                    "**I progetti si numerano**: il numero e' cio' che dice al sistema "
                    "che quella cartella e' un prodotto — e quindi che va protetta con "
                    "un permesso e un'approvazione.\n"
                    ...
                    f"Rimedio: rinominala in **{num}. {testa}**. "
                    f"Il prossimo numero libero e' {num}."
```

Da notare la condizione `(root_path / testa).is_dir()`: il blocco scatta su una cartella che
**esiste**. Creare una cartella non numerata non e' bloccato — e' il mestiere di
`progetto.py`, che propone il numero.

### 8.6 · La shell: un'euristica dichiarata

`bash_target()` **e' dichiarata euristica**, non confine (`ad_scope.py:674-682`). Prima cerca
il nome di una cartella protetta seguita da `/` dentro il comando, cosi' i nomi con spazi
vengono riconosciuti; poi i token con `/`; se non c'e' nessun percorso esplicito, vale la
`cwd`. La mutazione deve prima somigliare a una delle `MUTATION_PATTERNS` (`ad_scope.py:50`).

`guard()` e' la porta per gli **strumenti Python**, che il plugin non vede (`ad_scope.py:624`):

```python
    root_path = Path(root) if root is not None else ad_docs.DOCS_ROOT
    if relative_to_root(target, root_path) is None:
        raise PermissionError(
            f'"{Path(target)}" non sta sotto la root di autorita\' ({root_path}).\n'
        )
    verdict = evaluate(target, root_path)
    if not verdict.allowed:
        raise PermissionError(verdict.reason)
```

Il `root` di `guard()` e' **l'autorita'**, non la cartella su cui lo strumento lavora: il
parametro esiste per i test, gli strumenti chiamano `guard(percorso)` e basta. Fuori
dall'albero non si concede un'eccezione, si rifiuta — *«la richiesta e' un errore di chi
invoca»*.

---

## 9 · Il layer di enforcement

File unico: `.brain/plugin/enforce-contract/index.mjs`. Il modulo si dichiara
*«adattatore sottile, l'autorita' e' il codice Python gia' testato»* (`index.mjs:2-7`) e
dichiara subito la sua politica in caso di guasto: **fail-open**.

```javascript
// .brain/plugin/enforce-contract/index.mjs:18
 * Fail-open: qualunque errore inatteso di questo plugin lascia passare la
 * chiamata. Un difetto dell'enforcement non deve bloccare il lavoro.
```

### 9.1 · I due hook

```javascript
// .brain/plugin/enforce-contract/index.mjs:401
  ctx.on('tools/pre-execute', async (exec, next) => {
// .brain/plugin/enforce-contract/index.mjs:504
  ctx.on('tools/post-execute', async (exec, result, next) => {
```

- **`pre-execute`** intercetta i tool che portano un percorso di file scrivibile —
  `PATH_TOOLS = new Set(['write', 'edit', 'str_replace_editor'])` (`index.mjs:52`) — e il
  tool `bash` quando `bashGuard` e' attivo. Tutto il resto passa subito con `next()`.
- **`post-execute`** rilegge il file appena scritto e, se trova problemi, risponde
  `{ kind: 'block', feedback: [...] }`. **Non disfa la scrittura**: *«il `block` ferma il
  risultato»*, il file resta com'e' e il modello deve correggerlo (`index.mjs:179-182`).

Il `targetOf()` di post-execute accetta **solo** `PATH_TOOLS`: una mutazione fatta via shell
**non** viene riletta dopo l'esecuzione.

La decisione di pre-execute ha tre modi, e sotto `ask` **non esiste un percorso che si
approvi da solo** (`index.mjs:9`):

```javascript
 *   mode: ask   -> { kind: 'ask',  reason }   il default
 *   mode: deny  -> { kind: 'deny', reason }
 *   mode: allow -> passa sempre
 *
 * Con `kind: 'ask'`, dsh-tools interroga il servizio di approvazione: se il
 * servizio manca o l'utente rifiuta, la decisione diventa `deny`.
```

In modalita' `auto` la scelta fra `ask` e `deny` dipende da se l'approvazione puo' davvero
arrivare a un umano (`index.mjs:486`). Il motivo e' in `approvalPossible()`
(`index.mjs:141-147`): con la policy `never` il servizio risponde `rejected` senza mostrare
nulla, e il registro sostituisce il motivo con un messaggio generico — quindi conviene
`deny`, che **porta il motivo al modello**.

### 9.2 · Come scopre la propria radice

```javascript
// .brain/plugin/enforce-contract/index.mjs:35
const HERE = dirname(fileURLToPath(import.meta.url))

// .brain/plugin/enforce-contract/index.mjs:49
const RADICE_SCOPERTA = resolve(HERE, '..', '..', '..')
```

Il commento che lo precede e' la storia di perche' e' cosi' (`index.mjs:37-48`): la radice
era **scritta dentro il codice**, e spostando la macchina *«il cancello non bloccava piu'
niente»* — credeva di essere ancora nella vecchia sede. E quel file e' **symlinkato in ogni
sessione**, quindi avrebbe mentito a tutti.

La configurazione si compone **in cascata** — default, poi `settings.json` accanto al plugin,
poi il `config` di chi monta il plugin (`index.mjs:379`):

```javascript
  const settings = {
    ...DEFAULTS,
    ...loadSettings(),
    ...(config && typeof config === 'object' ? config : {}),
  }
```

`loadSettings()` legge `join(HERE, 'settings.json')` e in caso di errore restituisce `{}`
(`index.mjs:95-102`). **`settings.json` non esiste in questo checkout**: l'unico file
presente e' `settings.example.json`. Quindi allo stato attuale valgono i soli `DEFAULTS` — e
`root` vale `RADICE_SCOPERTA`.

### 9.3 · I quattro punti in cui puo' fermare una scrittura, in ordine

**1 · Modalita' `allow` — non ferma nulla** (`index.mjs:403`). E' il primo `return`, e spegne
l'enforcement.

**2 · `.md` nuovo nella radice — l'unico punto in cui si *impedisce*** (`index.mjs:421`).
Il file non esiste ancora, quindi e' l'unico momento in cui il divieto e' **possibile**
invece che un avviso a cose fatte:

```javascript
        const docRadiceNuovo =
          exec.name === 'write' &&
          dirname(target) === settings.root &&
          target.endsWith('.md') &&
          !existsSync(target) &&
          !settings.rootDocs.includes(basename(target))
```

Il commento motiva l'eccezione alla logica prevalente (`index.mjs:414-420`): *«una regola si
dimentica, un blocco no»*. Qui la decisione e' **sempre `deny`**: `mode` non viene consultato.

**3 · Il verdetto dell'autorita' Python sui tool a percorso** (`index.mjs:443`):

```javascript
        const verdict = runChecker(checker, ['check', target], settings)
        if (!verdict) {
          warnOnce(`verifica non disponibile per "${target}": la scrittura procede`)
          return next()
        }
        if (verdict.allowed !== false) return next()
```

**4 · Il verdetto dell'autorita' sul comando shell** (`index.mjs:452`), con la `cwd` presa
dalla sessione dell'agente, dal `workdir` dell'argomento, o dalla radice — in quest'ordine.

Il checker e' **sempre lo stesso processo**, invocato con `--json --root <settings.root>`
(`index.mjs:120-129`). Se il processo non parte, non produce stdout o produce JSON non
valido, `runChecker` restituisce `null` e la chiamata **procede**: fail-open in entrambi i
rami 3 e 4.

Il verdetto finale e' comune (`index.mjs:478`), e il `try/catch` che avvolge tutto il gestore
chiude il cerchio: qualunque eccezione inattesa fa `next()` con un `warnOnce`
(`index.mjs:490-493`).

**Un quinto confine esiste prima di tutti, ma non e' un blocco**: `targetOf()` restituisce
`null` per un tool che non e' in `PATH_TOOLS`, per argomenti non oggetto, per `file_path` non
stringa o vuoto; e `insideRoot()` scarta i percorsi fuori dalla radice (`index.mjs:412`). In
quei casi la scrittura passa.

### 9.4 · `rootDocs`: la whitelist del controllo 2

```javascript
// .brain/plugin/enforce-contract/index.mjs:62
  // I documenti che possono stare nella radice della super cartella. Un .md
  // nuovo qui fuori e' quasi sempre un errore: la radice tiene la macchina, non
  // le carte. Elenco configurabile: per aggiungerne uno legittimo basta
  // scriverlo in settings.json, senza toccare il codice.
  rootDocs: [
    'GOVERNANCE-AZIENDALE.md', 'AGENTI-V2.md', 'AGENT-CARDS-V2.md',
    'AGENT-CARDS-BUSINESS.md', 'TASK-CONTRACTS.md', 'RUNTIME.md',
    'QUALITY-GATES.md', 'SPECIALIZATION.md', 'COMMUNICATION.md',
    'STRATEGIC-MEMORY.md', 'MODEL-ROUTING.md', 'AGENT-PROMPT-TEMPLATE.md',
    'README.md',
  ],
```

E' la whitelist del controllo 2: un `.md` **che non esiste ancora** e il cui nome non e' in
questa lista viene **rifiutato**. Serve a distinguere un documento normativo legittimo da una
carta lasciata nella radice.

**Una nota utile**: la whitelist contiene `README.md`, che `ad_coherence.DOCUMENTI_NON_NORMATIVI`
classifica invece come **non normativo**. Le due liste rispondono a domande **diverse** —
*«puo' stare nella root?»* contro *«la costituzione deve nominarlo?»* — e `README.md` e' si'
nella root, ma **non e' una regola**. (Nel codice di `index.mjs` `AGENTS.md` e' in `rootDocs`:
e' la porta, e senza di lei il file verrebbe rifiutato alla creazione.)

### 9.5 · I tre controlli della meta' che avvisa

`controllaScritto()` (`index.mjs:251`) restituisce una lista di problemi; lista vuota =
nessun blocco. Il commento di testa dichiara **il criterio con cui i controlli sono stati
scelti** (`index.mjs:241`):

```javascript
 * Tre controlli, e sono i tre errori che hanno gia' sbagliato una volta:
 *   1. un orario dichiarato nel futuro;
 *   2. un marcatore di approvazione piu' recente del suo permesso;
 *   3. un permesso chiuso mentre il passo che autorizzava non ha il suo rapporto.
 *
 * Non inventiamo altri casi. Un controllo che non ha mai visto fallire il
 * proprio bersaglio non e' un controllo: e' una speranza.
```

**Controllo 1 — orari dichiarati nel futuro.** Vale per **qualunque** file scritto, non solo
per i registri:

```javascript
// .brain/plugin/enforce-contract/index.mjs:186
const ORARIO_RE =
  /(?:^|\n)[ \t]*(data|timestamp|aperta|chiusa|chiuso):[ \t]*"?(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:?\d{2})?)/g
```

Lo scarto e' `clockSkewMs: 60000` (`index.mjs:82`). I campi riconosciuti sono `data`,
`timestamp`, `aperta`, `chiusa`, `chiuso` — **`expires` non c'e', ed e' voluto**: una
scadenza **deve** essere nel futuro. Il test lo prova esplicitamente (`test.mjs:289-294`).

**Controllo 2 — il marcatore piu' recente del suo permesso.** Scatta solo se il percorso e'
sotto `approvazioni/` e finisce in `.yaml`; cerca il contract omonimo con `trovaFile()` sotto
`contratti/`, fino a 4 livelli di profondita', saltando le voci che iniziano con un punto
(`index.mjs:201-219`, `index.mjs:272-274`). Le **date dichiarate vincono sempre**; l'mtime
subentra solo se mancano entrambe, ed e' dichiarato come **ripiego fragile**:

```javascript
// .brain/plugin/enforce-contract/index.mjs:314
        } else if (statSync(contratto).mtimeMs < statSync(percorso).mtimeMs) {
          problemi.push([
              `L'ordine e' rotto: il permesso "${task}" risulta scritto PRIMA della sua approvazione.`,
              "Nessuno dei due documenti dichiara una data, quindi si legge dagli mtime —",
              "che una copia azzera. Rimedio durevole: dichiara `aperto:` nel permesso.",
```

**Controllo 3 — chiudere un permesso non chiude il passo.** Scatta solo se il percorso e'
sotto `contratti/`, finisce in `.yaml` e dichiara `status: chiuso` o `status: closed`
(`index.mjs:336`). Se `python3 tools/milestone.py check <progetto>` esce con codice diverso
da zero, allega le prime sei righe dell'output e blocca con *«Chiudere il permesso non chiude
il passo: la tappa ha ragione lei»* (`index.mjs:362`). Il progetto si ricava **senza un
parser YAML**, prendendo la prima voce di `write_scope` e tenendone il primo segmento se e'
una cartella numerata — *«Basta per quello che serve»* (`index.mjs:227-237`).

**Il limite dichiarato del controllo 3 e' la sua stessa dipendenza**: se `tools/milestone.py`
non c'e' o lo stat fallisce, **non si blocca niente** (`index.mjs:324-326`, `index.mjs:341`).
E il commento lo dice: *«Un controllo che accusa perche' non riesce a controllare e' peggio
di nessun controllo»*.

### 9.6 · I limiti dichiarati nel file

Il plugin dichiara i propri limiti **in testa, prima di qualunque codice** (`index.mjs:18`):
fail-open; *«le scritture via shell sono coperte solo in parte: un comando che cambia
directory con `cd` e poi scrive in modo relativo puo' sfuggirgli»*; solo import builtin.

E il limite della meta' che avvisa e' dichiarato dove vive (`index.mjs:179`):

```javascript
// Limite dichiarato: **non disfa la scrittura**. Il file resta com'e'. Il
// `block` ferma il *risultato*: il modello vede che quella scrittura non e'
// accettabile e deve correggerla. Prevenire e avvisare sono due mestieri
// diversi, e questo fa il secondo.
```

---

## 10 · Come si estende senza rompere niente

### 10.1 · Il registro dei comandi

`tools/README.md` e' il registro: la tabella
`| Comando | Cosa fa, in parole comprensibili | Come si usa |` e' *«l'unico posto in cui un
comando e' **dichiarato**»* (`ad_coherence.py:45-52`). La pretesa e' stata **girata qui**
dalla costituzione, perche' la costituzione e' il livello che **ogni agente legge a ogni
avvio**, e un elenco che cresce a ogni strumento e' il candidato peggiore per quel posto.

`tools/coherence.py` e' un entry point **sottile**: chiama `ad_coherence.problemi()` e
traduce la lista in codice di uscita 0/1 (`coherence.py:33-52`). Tutta la logica sta in
`tools/ad_coherence.py`.

Le quattro divergenze del registro, *«ognuna un modo in cui un elenco puo' mentire»*
(`ad_coherence.py:185-229`):

```python
# tools/ad_coherence.py:211
    for comando in sorted(comandi_nel_progetto(base) - set(dichiarati)):
        fuori.append(
            f"il comando tools/{comando} esiste ma non e' dichiarato in {REGISTRO}: "
            "per chi legge il registro non esiste"
        )
    for comando in sorted(comandi_nominati(registro)):
        if not (base / TOOLS_DIR / comando).is_file():
            fuori.append(f"il registro {REGISTRO} nomina tools/{comando}, che non esiste")
    for comando, (descrizione, uso) in sorted(dichiarati.items()):
        if len(descrizione) < DESCRIZIONE_MINIMA or len(descrizione.split()) < 3:
            fuori.append(...)
        if f"{TOOLS_DIR}/{comando}" not in uso:
            fuori.append(f"{REGISTRO}: la forma d'uso di {comando} non lo nomina: «{uso}»")
```

**Cosa conta come «comando che esiste»** e' una definizione precisa, non un `glob`:

```python
# tools/ad_coherence.py:154
def comandi_nel_progetto(root=None) -> set[str]:
    """Return the command-line tools that exist, ignoring the libraries.

    Le librerie (`ad_*.py`) non vanno documentate: sono moduli che altri
    importano. I comandi (`*_*.py` con un `if __name__`) si'.
    """
```

Cioe': qualunque `tools/*.py` che contenga `if __name__ == "__main__":` (`MAIN_RE`,
`ad_coherence.py:104`). Percio' `drift.py` e' un comando e `ad_drift.py` una libreria; e
`tools/tests/test_ad_org.py` non entra perche' la glob e' **piatta** (`*.py`).

Un comando e' «dichiarato» solo se ha una **riga** di tabella che comincia col suo nome fra
backtick (`ad_coherence.py:106`):

```python
#: Si legge la **riga** e non la sottostringa. Un comando e' dichiarato quando ha
#: una riga di tabella che comincia col suo nome fra backtick; cercare il nome
#: ovunque nel file farebbe passare per dichiarazione una semplice citazione — ed e'
#: il modo in cui un elenco si riempie di voci che nessuno mantiene.
REGISTRO_RIGA_RE = re.compile(r"^\|\s*`([a-z0-9_]+\.py)`\s*\|([^|]*)\|([^|]*)\|\s*$", re.M)
```

E **nessun altro documento del cervello** puo' tenere una copia dell'elenco:
`elenchi_duplicati()` (`ad_coherence.py:232`). Il difetto da prendere e' l'elenco in **due**
posti, non la forma della tabella — per questo `DICHIARAZIONE_RE` (`ad_coherence.py:121`) e'
piu' larga di `REGISTRO_RIGA_RE`. **Citare** un comando dentro una frase resta permesso: la
costituzione **deve** poter nominare i comandi che sono un passo della sequenza.

Il limite e' dichiarato (`ad_coherence.py:202`):

```python
    Il limite, dichiarato: **la chiarezza di una descrizione non si misura.** Qui si
    controlla che ci sia e che non sia un segnaposto; che sia in parole
    comprensibili lo giudica chi legge, non questo modulo. Un controllo che
    pretendesse di giudicare la chiarezza sarebbe un controllo che non puo'
    fallire — e quindi nessun controllo.
```

### 10.2 · Cosa verifica `ad_coherence.problemi()`

`problemi(root)` (`ad_coherence.py:474`) raccoglie tutto in una lista; lista vuota = livello
coerente. I blocchi, nell'ordine:

**Skill** (`ad_coherence.py:490-499`) — ogni directory `ad-*` in `.brain/skills/` deve essere
nominata nella costituzione, e ogni nome nominato deve esistere. Il commento dice perche'
conta: `ad-milestone` non era nominata, *«quindi per un agente nuovo non esisteva»*.

**Comandi** (`ad_coherence.py:514-526`) — la costituzione deve citare `tools/README.md`; ogni
`tools/<nome>.py` citato deve esistere; poi si delega a `problemi_del_registro()` ed
`elenchi_duplicati()`. Prima si pretendeva che **ogni** comando fosse nominato nella
costituzione, ma cosi' l'elenco *«non era verificato, era ricopiato»*.

**Cartelle** (`ad_coherence.py:533`) — solo quelle dentro la sezione `## Dove sta cosa`,
delimitata a `\n## `. Il commento spiega la restrizione: altrove la costituzione nomina
cartelle che vivono **dentro** i progetti (`Analisi-Prompt-Report/`), e pretenderle nella root
sarebbe un falso allarme.

**Documenti di root** (`ad_coherence.py:541`):

```python
    documenti = documenti_nella_root(base)
    elencati = documenti_nominati(testo)
    for documento in sorted(documenti - elencati - DOCUMENTI_NON_NORMATIVI):
        fuori.append(f"il documento di root '{documento}' non e' nominato nella costituzione")
```

L'elenco **non e' scritto a mano**: `documenti_nella_root()` e' `base.glob("*.md")`
(`ad_coherence.py:265-268`), quindi il controllo **non invecchia**. I documenti nominati si
riconoscono con `` `([A-Z][A-Z0-9-]*\.md)` `` (`DOC_RE`, `ad_coherence.py:98`).

**Sequenza** (`ad_coherence.py:550`) — la costituzione e
`.brain/skills/ad-kickoff/SKILL.md` devono avere lo **stesso numero di passi**, contigui, con
le **stesse etichette**. `sequenza()` legge i passi solo dal **primo blocco ` ```text `**
(`ad_coherence.py:276-284`), e `PASSO_RE` e' stato allentato perche' pretendere sempre due
spazi faceva **sparire** il passo `6 ANALISI DI AVVIO`, che ne ha uno solo
(`ad_coherence.py:87-94`).

**Cortesia — il glossario** (`ad_coherence.py:573-595`) — le cartelle nominate nella
costituzione devono comparire nel glossario, altrimenti non c'e' modo di spiegarle al CEO
(invariante 14). I comandi non si controllano piu' qui: la loro descrizione vive nel registro.

**Gergo — i conteggi delle card** (`ad_coherence.py:409`):

```python
CONTEGGI_RE = (
    (re.compile(r"(\d+)\s+card tecniche"), "tecniche"),
    (re.compile(r"(\d+)\s+card business"), "business"),
    (re.compile(r"Business\s*\((\d+)\)"), "business"),
    (re.compile(r"(\d+)\s+specialisti"), "specialisti"),
    (re.compile(r"Tutte le \*\*(\d+) card"), "totale"),
)
```

I numeri dichiarati nei `.md` del cervello si confrontano col registry, **con le stesse
funzioni che usa `cards.py check`**: *«il conteggio dev'essere UNO solo, altrimenti il
documento e lo strumento possono dire due numeri diversi»* (`ad_coherence.py:434`). E se il
registry **non si legge**, l'errore si **dichiara**: un `except: return []` faceva un
controllo che non controllava niente **in silenzio**, ed e' la prima lezione scritta nel
codice (`ad_coherence.py:422-433`).

**Registri raggruppati** (`ad_coherence.py:341-359`) — `contratti/` e `approvazioni/` devono
essere organizzati per progetto: il gruppo atteso si ricava dal primo segmento numerato del
`write_scope` (`_gruppo_atteso`, `ad_coherence.py:311`), altrimenti `societa`. Un file
**sciolto** direttamente nella cartella del registro e' una divergenza.

**Orari nel futuro** — sui record che dichiarano un orario: `RECORD_ORARIO = ("approvazioni",
"contratti", "evidenze")` (`ad_coherence.py:60`), coi campi `CAMPI_ORARIO = ("data",
"timestamp", "aperta", "chiusa", "chiuso")`. **`expires` e' escluso di proposito**: *«una
scadenza **deve** essere nel futuro. La prima versione di questo controllo non lo escludeva e
segnalava tutti i permessi attivi come se fossero falsi»* (`ad_coherence.py:62-66`).

**Ganci e plugin** (`ad_coherence.py:287-303`, `ad_coherence.py:606-613`) — `~/.dsh/AGENTS.md`
deve esistere e risolversi su `COSTITUZIONE`; le skill globali in `~/.agents/skills/` non
devono essere symlink rotti; il plugin deve esistere e risultare **montato** in
`~/.dsh/profiles/web/cordis.patch.yml`.

### 10.3 · `DOCUMENTI_NON_NORMATIVI`

```python
# tools/ad_coherence.py:464
#: I documenti di root che **non sono normativi**: porte e spiegazioni.
#:
#: Il 2026-10-13 la versione vergine ha aggiunto `README.md` (una distribuzione
#: senza README non si sa usare) e `GRAFO.md` (come funziona il motore).
#: Il controllo li trattava come documenti normativi e pretendeva che la costituzione li
#: nominasse — ma **non sono regole**. Il problema cresceva a ogni documento nuovo,
#: il che e' il segno che la domanda era sbagliata.
#:
#: **Elenco dichiarato**, non dedotto: dedurlo («quelli che non sembrano regole»)
#: vorrebbe dire accettare come non-normativo qualunque cosa qualcuno aggiunga.
DOCUMENTI_NON_NORMATIVI = frozenset({"README.md", "GRAFO.md"})
```

Il criterio e' lo stesso di `CARTELLE_MACCHINA`: **elenco dichiarato, non dedotto**, perche'
dedurre vorrebbe dire accettare come eccezione qualunque cosa qualcuno aggiunga. Un documento
nuovo nella root che non sia ne' normativo ne' in questa lista fa fallire `coherence.py`
finche' non entra in uno dei due insiemi.

> **E ci sono TRE liste con la stessa forma e lo stesso scopo**, che rispondono a tre
> domande diverse: `rootDocs` (plugin, «puo' stare nella root?»), `DOCUMENTI_NON_NORMATIVI`
> (coherence, «la costituzione deve nominarlo?»), `CARTELLE_MACCHINA` (scope, «e' un
> progetto?»). Un file nuovo puo' dover entrare in piu' di una — e questo e' un punto di
> attrito noto, non un difetto nascosto.

---

*(Seguono: la banda deterministica comando per comando, il modello dati, la sequenza,
le skill e la strategia di prova.)*
## 11 · La banda deterministica: i 18 comandi

Sono la fascia che esegue la governance **senza consumare token**. Le misure di questa sezione
sono state prese **eseguendo** i comandi (2026-10-13), non leggendoli.

**Nota di perimetro.** I comandi sono **18**, non 17: `tools/README.md` dichiara **18 righe** e
`ad_coherence.comandi_nel_progetto()` ne rileva **18**. La differenza sta in
`camoufox_ponte.py`, che è un comando a tutti gli effetti (ha `if __name__ == "__main__":`), è
dichiarato nel registro ed è chiamato da `ricerca.py`. Il README **non è un comando**: è il
registro.

> **Cosa distingue un comando da una libreria**: un `tools/*.py` che contiene
> `if __name__ == "__main__":` è un comando; `ad_*.py` no, sono moduli che altri importano
> (`ad_coherence.py:154`). Confondere le due categorie produce un conteggio che **sembra** un
> problema e non lo è.

### 11.1 · I comandi che aprono e chiudono il lavoro

| Comando | Cosa fa | Uscita 0 | Uscita 1 | Uscita 2 |
|---|---|---|---|---|
| **`cards.py`** | il registry delle Agent Card: elenca, mostra, cerca il match per `task_type` | elenco/mostra/trovato | `show` non trovata; **`match` senza esito (STOP)**; `check --strict` con problemi bloccanti | — |
| **`validate_contract.py`** | valida un contract contro i documenti normativi | nessuna violazione | almeno una **VIOLATION** (o WARNING con `--strict`) | contract **illeggibile** |
| **`contract_scope.py`** | **l'autorità del cancello**: un percorso è coperto? | ammesso | protetto e **non** coperto; comando shell rifiutato; `titolari` con conflitti | *(dichiarato nella docstring, ma nessun `return 2` esiste nel file)* |
| **`verdict.py`** | ACCEPT/REJECT su un contract e le sue evidenze | ACCEPT | REJECT | contract o evidenze illeggibili |
| **`milestone.py`** | apre milestone e sprint, e verifica la storia | completo / scritto | manca un report, un prompt, o la numerazione ha un buco | errore di lettura, `PermissionError`, milestone inesistente |
| **`progetto.py`** | crea un progetto numerato o ne collega uno | elenco/creato/spostato | `nuovo` senza `--si`; `collega` su cartella **non numerata** | nome vuoto, già numerato, destinazione esistente |

`cards.py match` che esce **1** è il caso più importante della tabella: è l'invariante 5 reso
eseguibile — *nessun match significa STOP*, e **non** «assegno all'agente più vicino».

`progetto.py collega` che esce **1** su una cartella non numerata porta **il rimedio**: *«rinominala in "N · Nome"»*. Un divieto senza il rimedio è un vicolo cieco.

### 11.2 · I comandi dei registri e della memoria

| Comando | Cosa fa | Uscita 0 | Uscita 1 | Uscita 2 |
|---|---|---|---|---|
| **`drift.py`** | verifica e consulta il registro delle divergenze | coerente / elenco | voce incompleta, id non contiguo, o chiusura **senza Decision Record** | — |
| **`errori.py`** | valida le cicatrici e verifica che **la difesa dichiarata esista** | a posto / id prenotato | voce incompleta o difesa inesistente | scrittura rifiutata; PyYAML assente |
| **`verbali.py`** | la struttura che il modello chiede, e l'esito che nessuno scrive | conforme / elenco | verbale fuori modello; id non trovato | scrittura rifiutata |
| **`comportamento.py`** | le prove comportamentali: **è peggiorato qualcosa?** | nessuna regressione | regressione rispetto a `evals/baseline.yaml`; `show` con una prova fallita | `--update` rifiutato |

`errori.py check` verifica una cosa che vale più di tutte le altre: **che `dove` esista sul
disco** se la voce dichiara `diventa: controllo`. *«Una voce che promette un controllo
inesistente è peggio di una voce assente, perché sembra una difesa.»*

### 11.3 · I comandi della fotografia e della coerenza

| Comando | Cosa fa | Uscita 0 | Uscita 1 | Uscita 2 |
|---|---|---|---|---|
| **`blueprint.py`** | `render`/`check`/`show` la fotografia di un progetto | senza manomissioni | `manomesso`, `senza-marcatori`, `senza-impronta` | manca il progetto; scrittura rifiutata |
| **`stato.py`** | la vista operativa, generata dai registri | `aggiornato` o `indietro` | `manomesso`, `senza-impronta`, `senza-marcatori` | scrittura rifiutata |
| **`coherence.py`** | confronta il livello sempre caricato con ciò che il sistema è | coerente | almeno una divergenza | — |
| **`security_scan.py`** | segreti, dipendenze, SBOM, e **file che un agente legge come istruzioni** | nessun segreto tracciabile, nessuna vulnerabilità con fix | segreto tracciabile o vulnerabilità con fix | scanner assente, percorso assente, errore |
| **`misure.py`** | esegue le misure dichiarate e genera l'allegato | esito atteso | misura inattesa (**l'allegato c'è lo stesso, ed è il punto**) | elenco rifiutato, area non valida, allegato non scrivibile |

**`blueprint.py check` distingue sei verdetti**, e solo tre sono errori — la costituzione ne
cita tre, il codice ne ha sei (`blueprint.py:263-270`): `aggiornato` (fotografia dei registri
di adesso), `indietro` (**autentica** ma di registri più vecchi: normale fra due tappe),
`manomesso`, `senza-impronta`, `senza-marcatori`, `assente`.

**`security_scan.py` ha un quarto esito che non ha niente a che vedere con la sicurezza e
conta quanto gli altri**: `istruzioni-mascherate` — file che un agente legge **come propri
ordini**. Su questo checkout ne trova **1**: `AGENTS.md`. È **voluto** (è la porta), ma il
primo materiale di studio importato il 2026-10-11 ne conteneva uno che **non** era voluto, ed
è arrivato nel contesto come istruzione.

### 11.4 · L'installazione, il web, il progetto

| Comando | Cosa fa | Uscita 0 | Uscita 1 | Uscita 2 |
|---|---|---|---|---|
| **`setup.py`** | collega plugin, costituzione e skill; `--check` non scrive | ogni prova passata | **almeno una prova fallita** | — |
| **`ricerca.py`** | ricerca: prima la via leggera, il browser solo se serve | lettura/ricerca riuscita | non riuscito; `verifica` con un morto | argomento mancante |
| **`camoufox_ponte.py`** | il ponte verso il browser vero | **sempre 0** | — | — |

**`camoufox_ponte.py` esce sempre 0, ed è deliberato**: il successo e l'errore escono
entrambi `0`, e il chiamante distingue i due casi **dal campo `ok` del JSON**. Un exit code di
errore romperebbe il contratto col chiamante.

**Le 6 prove di `setup.py`**, e la quinta è quella che conta:

| # | Prova | Cosa significa |
|---|---|---|
| 1 | il plugin esiste | senza il file non c'è nessun cancello da montare |
| 2 | il montaggio dichiara il plugin | il profilo sa che il plugin esiste |
| 3 | **e il percorso è quello di ADESSO** | distingue «montato» da **«montato bene»** |
| 4 | la costituzione è **collegata** alla macchina | una fonte sola, non una copia che invecchia |
| 5 | **il cancello RIFIUTA una scrittura in un progetto** | crea `99. Prova Del Cancello`, pretende uscita ≠ 0, e la **cancella** anche se qualcosa va storto. **Non si dichiara «installato»: si prova che rifiuta** |
| 6 | le prove del plugin passano | il cancello supera i propri test |

### 11.5 · Le librerie `ad_*.py`

Le librerie **non sono comandi** e non vanno dichiarate nel registro. Sono i moduli che i
comandi importano. Il grafo delle dipendenze ha un centro netto:

| Libreria | Cosa espone | Chi la chiama |
|---|---|---|
| **`ad_scope.py`** | `evaluate`, `guard`, `coverage`, `load_write_scopes`, `primo_numero_libero`, `bash_target`, `policy` | **11 moduli** — è la libreria più usata |
| `ad_docs.py` | `read`, `sede`, `ceo`, `progetti_root`, **`prenota_id`** (atomico) | 11 moduli |
| `ad_contract.py` | `load`, `validate`, `conflitti_di_raggio`, `classe_della_scrittura` | `validate_contract.py`, `verdict.py`, `ad_evidence.py` |
| `ad_registry.py` | `load`, `by_domain`, `task_type_index`, la classe `Card` | `cards.py`, `validate_contract.py`, `ad_contract.py` |
| `ad_milestone.py` | `scan`, `problems`, `scaffold_*`, `sprint_prompt` | `milestone.py`, `blueprint.py`, `stato.py`, `comportamento.py` |
| `ad_coherence.py` | `problemi`, `problemi_del_registro`, `elenchi_duplicati`, `sequenza`, `conteggi_delle_card` | `coherence.py`, `comportamento.py`, `stato.py` |
| `ad_drift.py` | `load`, `problems`, la classe `Drift` | `drift.py`, `blueprint.py`, `stato.py` |
| `ad_evidence.py` / `ad_gates.py` | `collect`, `evaluate` / il catalogo dei 15 gate | `verdict.py` / `cards.py`, `ad_contract.py` |

**Il punto architetturale**: `ad_scope.py` è **l'unica sorgente** della risposta «posso
scrivere qui?». Il plugin non reimplementa la regola: la interroga. E il plugin è un
**adattatore sottile** che si dichiara tale (`index.mjs:2-7`).

---

## 12 · La sequenza in 12 passi e i controlli che la impongono

Questa è **la tabella più importante del documento**, perché dice dove il sistema è forte e
dove è ancora disciplina.

| Passo | Cosa impone | Controllo che lo impone |
|---|---|---|
| **1 RICHIESTA** | la richiesta è una proposta da verificare, non un ordine | **NESSUNO** |
| **2 COMPRENSIONE** | cosa vuole ottenere davvero | **NESSUNO** |
| **3 RICERCA** | esiste un modo migliore? anche online | **Nessun controllo che la imponga.** Esistono `ricerca.py` e la skill `ad-evolution`, ma nulla collega un kickoff a una ricerca fatta. L'unico controllo che pretende fonti è `verbali.py:162`, per i Decision Record |
| **4 CARD** | `cards.py match`; nessun match → STOP | **Sì, forte**: `cards.py:112-129` + `ad_contract.py:556-637` (7 codici) eseguiti da `validate_contract.py:42` |
| **5 RISPOSTA** | si risponde **prima** di fare | **NESSUNO.** Solo l'**ordine** consenso→permesso: `ad_scope.py:343-349`; B1 in `comportamento.py:60-104` |
| **6 ANALISI + BLUEPRINT** | inventario completo + Blueprint | **Parziale**: `blueprint.py:596-623`, `:544-593`, B6 `comportamento.py:159-176`. **L'inventario non ha un controllo di completezza** |
| **7 CONSENSO** | il CEO approva le milestone | **Sì**: `load_approvals:247-284`, `coverage:309-316`, ordine `:343-349`, `index.mjs:272-328`. **Ma `validate_contract.py` non verifica il marcatore** (solo `approval.human`) |
| **8 PERMESSO** | contract con `write_scope`, `milestone`, `sprint`, **prima** della tappa | **Sì**: `validate_contract.py` + `ad_contract` (campi, priorità/impatto, milestone/sprint, un titolare); `load_write_scopes:127-176`; DRIFT-010 gestito |
| **9 MILESTONE** | `milestone.py new-milestone` | **Sì**: `milestone.py:175-183` → `scaffold_milestone` con `guard` |
| **10 SPRINT** | `milestone.py new-sprint` | **Sì**: `scaffold_sprint` (rifiuto se la milestone non esiste); B3; **chiusura del permesso con storia incompleta bloccata** da `index.mjs:336-373` |
| **11 ESECUZIONE** | un solo esecutore → evidenze → gate → report | **Parziale**: report e gate imposti. **«Un solo esecutore» non è imposto da nulla**, e **nulla pretende che le evidenze vengano prodotte** |
| **12 CHIUSURA** | ACCEPT/REJECT, errori registrati, fotografia | **Parziale**: `verdict.py`, `errori.py`, `verbali.py`, `blueprint.py render/check`, `stato.py`. **Nulla obbliga a registrare un errore né a rigenerare la fotografia** (`DEC-0030:74-77`) |

**I passi senza controllo sono 1, 2, 3 e 5** — cioè **l'intera metà del pensiero**: capire,
cercare, rispondere. Sono anche i passi dove un controllo è **difficile senza fingere**: non
si meccanizza «hai capito davvero», e un controllo che pretendesse di farlo sarebbe un
controllo che non può fallire.

**Ed è un'informazione, non una vergogna.** Questo documento esiste anche per dire dove la
disciplina **non** è ancora diventata codice — perché è lì che il motore si fida di chi lo usa.

---

## 13 · Le 9 skill

| Skill | `whenToUse` | Cosa contiene |
|---|---|---|
| `ad-avvio` | all'avvio, quando si dice `AGENTS.md` | le tre parti della risposta; engine non avviato; i due percorsi |
| `ad-kickoff` | all'apertura di una richiesta su un progetto | la sequenza; classificazione; card; consenso; contract |
| `ad-milestone` | dopo il consenso, a ogni apertura/chiusura di sprint | struttura su disco; ciclo in 5 fasi; la guardia |
| `ad-task-contract` | quando nasce un lavoro o un contract va controllato | regole; schema; tabella VIOLATION/WARNING |
| `ad-quality-gate` | quando servono le evidenze o si deve capire un REJECT | evidenza valida; la regola del verdetto; owner dei 15 gate |
| `ad-agent-cards` | per sapere quale card copre un task | i comandi; i campi per l'assegnazione; quando nessuna copre |
| `ad-agent-org` | prima di iniziare o assegnare un lavoro | il ciclo obbligatorio; escalation; limiti dichiarati |
| `ad-evolution` | prima di un piano, e alle revisioni periodiche | il dovere; come si cerca; cosa si produce |
| `ad-brand-team` | **solo su chiamata del CEO** | 8 passi; metodi con fonti (Kapferer/Aaker, Mark & Pearson, Keller) |

**Due cose che il controllo ha trovato qui:**

- **`ad-brand-team` non ha `whenToUse`** nel frontmatter: è l'unica delle nove.
- **7 skill contengono il percorso assoluto `/home/luka/Scrivania/AD Projects/`**, contro
  l'invariante *«Nessun percorso assoluto»*. È lo stesso difetto della costituzione, in sette
  posti invece che in uno.

---

## 14 · Il modello dati: i formati su disco

### `contratti/<gruppo>/<ID>.yaml` — il permesso

Un solo gruppo reale in questa versione: `contratti/societa/`. Esempio `GOV-008.yaml`:
`task_id`, `title`, `domain`, `agent`, `task_type`, `product`, `decision_record`,
`objective`, `inputs`, `acceptance_criteria`, `constraints`, `outputs`, `required_gates`,
`approval.human`, `budget.max_retries`, `priority`, `impact_forecast` (6 aree),
**`status`**, **`aperto`**, **`write_scope`** (file **espliciti**), `expires`.

**I campi del layer di enforcement sono gli ultimi quattro**, e stanno in un blocco
riconoscibile: `status`, `write_scope`, `expires`, `aperto` (`contratti/_TEMPLATE.yaml:66-76`).
Lo schema normativo è in `TASK-CONTRACTS.md:15-71`.

### `approvazioni/<gruppo>/<ID>.yaml` — il consenso

`task_id`, `piano`, `approvato_da`, `data`, `fonte`, `consenso`. **Obbligatori `task_id`,
`approvato_da` e `data`**: senza uno dei tre il file viene **ignorato in lettura**
(`ad_scope.py:272-283`) — non è un errore rumoroso, è un permesso che semplicemente non copre.

### `errori/ERR-*.yaml` — la cicatrice

`diventa` ∈ {`controllo`, `nota`, `verbale`}; `trovato_da` ∈ {`controllo`, `revisore`,
`altro-agente`, `io`}; `stato` ∈ {`chiuso`, `aperto`}. Con `diventa: controllo` il file in
`dove` **deve esistere** (`errori.py:118-124`). Le tre domande obbligatorie: cosa è fallito,
cosa l'ha risolto, **cosa lo avrebbe preso**.

### `DECISIONI/DEC-*.md` — il verbale

Frontmatter `id`, `stato`, `livello`, `data`, `approver`, `supera`. Le **8 sezioni** pretese
da `verbali.py:57-66` per i verbali **dal n. 37**: Problema, Opzioni (con URL **e** la voce
numerata `**Non fare nulla**`), Evidenze, Scelta, Conseguenze, Metrica, Data di revisione,
Esito misurato. I verbali **< 37** sono esenti perché immutabili — ma se dichiarano una
revisione passata senza esito finiscono in `da_rivedere`: non è un errore, è **una cosa da
fare**.

**Il controllo cerca la voce numerata, non la frase**: *«un controllo che pretende una
punteggiatura sbagliata obbliga a sbagliare»*.

### Il sigillo del Blueprint

`impronta = sha256(corpo)[:12]` (`blueprint.py:466-468`). **È un sigillo sul contenuto, non un
puntatore ai registri** — e la differenza è tutta lì: *un puntatore non si può verificare
dopo che i registri sono cambiati; un sigillo sì, sempre.* È ciò che permette di distinguere
**vecchio** da **falso**, che senza sigillo si assomigliano.

**Ma garantisce l'integrità, non la correttezza** (`blueprint.py:449-454`): dice che la
fotografia non è stata toccata, non che la fotografia sia giusta.

---

## 15 · La strategia di prova

Tre livelli, e ognuno prova **una cosa diversa**:

| Livello | Cosa prova | Come si esegue |
|---|---|---|
| **La suite deterministica** | che i **programmi** funzionino | `python3 tools/tests/test_ad_org.py` |
| **Il plugin** | che il **cancello** funzioni | `node .brain/plugin/enforce-contract/test.mjs` → **36 controlli, PASS** |
| **Le prove comportamentali** | che **l'agente** si comporti bene | `python3 tools/comportamento.py show` |

**L'iniezione dei difetti è il cuore della suite.** I test **costruiscono** il caso sbagliato
in root temporanee invece di sperarlo — `test_ad_org.py:2099` lo dice: *«IL CONTROLLO DEVE
SAPER FALLIRE. Ogni difetto iniettato, uno per uno.»* Le funzioni si chiamano `rompi()`. Ed è
la lezione di `ERR-0011`: *un controllo che non può fallire non è un controllo.*

**Le 7 prove comportamentali**, ognuna nata da un errore vero: **B1** ordine firma→permesso
(`ERR-0004`); **B2** nessun orario futuro (`ERR-0001`); **B3** ogni permesso chiuso ha la
storia completa (`ERR-0003`); **B4** ogni errore dichiara una difesa **che esiste**; **B5** la
radice tiene solo i documenti normativi (invariante 15); **B6** nessun Blueprint mente
(`ERR-0009`); **B7** registro raggruppato per progetto.

**E una cosa che va detta sulla suite, perché è un difetto vero:** le prove si fermano al
**primo** `AssertionError` (non c'è pytest), e **alcune dipendono dallo stato esistente** —
una pretende che esistano cartelle di progetto, un'altra che i verbali superino una soglia.
In un motore **vergine** quelle premesse non valgono, e la suite si ferma. *Una prova che ha
bisogno di dati esistenti non prova un motore nuovo: prova questo computer.* È la stessa
famiglia di `ERR-0047` — la prova di `setup.py` che cercava un progetto esistente — e la
stessa lezione: **una prova si costruisce il proprio caso.**

---

## 16 · Le divergenze trovate scrivendo questo documento

Elencarle è il punto: sono **divergenze reali**, ciascuna con la sua conseguenza. Non sono
state corrette qui — una correzione richiede un Decision Record — ma **registrarle è il
mestiere**.

| # | Divergenza | Conseguenza |
|---|---|---|
| 1 | **`ad-kickoff:47` dice che l'analisi si scrive «in `piani/`»**, la costituzione (`:96-97`) dice «**NEL PROGETTO**» | due istruzioni opposte sulla stessa cosa, e l'invariante 15 perde |
| 2 | **7 skill contengono `/home/luka/Scrivania/AD Projects/`** | l'invariante «nessun percorso assoluto» è violato in 7 posti: le skill si rompono se la cartella si sposta |
| 3 | **`contratti/README.md:11-17` dice che `tools/` è scrivibile senza contract**, ma `GOVERNANCE_PATHS` include `tools` | un documento di governance descrive il contrario di ciò che il codice fa |
| 4 | **`--json` accettato ma ignorato** in `cards.py check`, `drift.py list`, `comportamento.py check` | chi automatizza legge testo dove si aspetta JSON |
| 5 | **`contract_scope.py` dichiara l'uscita 2 nella docstring, ma nessun `return 2` esiste** | l'uscita non è raggiungibile: chi la gestisce scrive codice morto |
| 6 | **`ad-brand-team` non ha `whenToUse`** nel frontmatter | è l'unica delle nove, e il suo innesco non è dichiarato |
| 7 | **`DOCUMENTI_NON_NORMATIVI`, `rootDocs` e `CARTELLE_MACCHINA` sono tre liste** con la stessa forma, che rispondono a tre domande diverse | un file nuovo può dover entrare in più di una, e la dimenticanza si vede solo quando il controllo protesta |
| 8 | **`validate_contract.py` non verifica il marcatore del CEO** (solo `approval.human`) | un contract può passare la validazione **senza consenso**: a fermarlo è solo il cancello a runtime |
| 9 | **`validate_contract.py` non è verificato dal plugin** | è un controllo che **va eseguito**: chi non lo esegue non ha il controllo |

**La 8 e la 9 sono le più serie**, e vanno lette insieme: il consenso e il match con una card
sono imposti **solo** se qualcuno esegue il validatore. Il cancello blocca le **scritture**,
non l'assenza di consenso. Sono **divergenze fra ciò che il sistema dice di fare e ciò che
impedisce**, ed è esattamente il tipo di cosa che questo motore esiste per trovare.
