# agent-authority/1 — profilo leggero

**Non è uno standard. È un profilo sopra ciò che esiste già.**

Definisce come descrivere **chi ha il diritto di agire** su un lavoro vero, in modo che
**un altro programma** possa verificarlo — e aggiunge le quattro cose che nessuno degli
standard esistenti copre.

> **La tesi, in una riga.**
> Gli standard in corso ([ricevute di autorizzazione firmate][ietf]) costruiscono la
> **prova**. Nessuno costruisce la **serratura**. Questo profilo descrive **entrambe**:
> la prova, riusando la loro, e la serratura, che è la parte nostra.

[ietf]: https://datatracker.ietf.org/doc/draft-izmaylov-agent-permission-receipts/

**Stato: v1, 2026-10-13.** Scritto perché sia **implementabile in un pomeriggio** da chi
non ci conosce. Se serve un pomeriggio in più, è troppo lungo e va tagliato.

---

## 1 · Cosa riusa, e cosa aggiunge

**Riusa senza ridefinire.** I formati delle ricevute firmate sono specificati meglio di
quanto sapremmo fare noi, e uno è **già implementato** (`provared`, Apache-2.0). Non li
tocchiamo.

| Questo profilo dice | Lo standard dice | Come si collega |
|---|---|---|
| `slip` — il permesso | `slip` | **lo stesso record**, campi nostri mappati sui loro |
| `approval` — il consenso | `approval` | idem |
| `seal` — il sigillo | `seal` | idem: `sha256` del contenuto |
| — | `stub` — ricevuta d'azione | **non implementato qui** (§7) |
| — | `pass` — delega | **non implementato qui** (§7) |

**Aggiunge quattro cose.** Sono la ragione per cui questo profilo esiste:

| Cosa | Perché nessuno ce l'ha |
|---|---|
| **Il punto in cui si blocca** | gli standard registrano **dopo**. Qui c'è un punto, **prima** dell'azione, che può dire **no** |
| **La cicatrice che diventa controllo** | un record per un errore, con l'obbligo di dichiarare **cosa lo avrebbe preso**. Se si meccanizza, il record **si accorcia**: vedi §6 |
| **La metrica della maturità** | un numero riproducibile: **quante cicatrici sono diventate codice, su quante ne sono nate** |
| **Il legame col lavoro** | il permesso nomina **una cartella numerata**, non un ruolo astratto. Il diritto vive **con** la cosa su cui si esercita |

---

## 2 · I tre record

Tutti e tre sono **file di testo**, uno per record, con nomi **derivati dall'identificatore**
— così un altro programma li trova senza un indice.

### 2.1 · `slip` — il permesso

```yaml
# contratti/<gruppo>/<id>.yaml
id: GOV-008                    # un identificatore, PRENOTATO e non scelto (§5)
slip_version: 1
agent: platform                # chi agisce: una card, non una persona
granted_by: CEO                # chi ha concesso: un RUOLO, mai un nome proprio
objective: "il cancello che blocca le scritture non permesse"
write_scope:                   # DOVE puo' scrivere. File, non cartelle (regola 3)
  - "tools/ad_scope.py"
  - "tools/tests/test_ad_org.py"
status: active                 # active | chiuso
opened: "2026-10-13"           # la data DICHIARATA, non l'mtime (§5)
expires: "2026-11-08T00:00:00+01:00"
```

**Tre regole che non sono negoziabili:**

1. **`write_scope` dichiara file, non cartelle.** Un permesso su una cartella intera copre
   anche i file che qualcun altro aggiungerà domani — cioè copre ciò che non si è deciso.
2. **Un solo titolare per percorso.** Due permessi attivi che nominano lo stesso percorso
   sono una **violazione**, non un avviso: la responsabilità deve avere un nome.
3. **`opened` è una data scritta nel documento.** Gli orari dei file si azzerano con una
   copia, e un controllo che accusa un documento innocente insegna a ignorarlo.

### 2.2 · `approval` — il consenso

```yaml
# approvazioni/<gruppo>/<id>.yaml
id: GOV-008
approval_version: 1
task_id: GOV-008
approved_by: CEO               # un RUOLO (§4)
approved_at: "2026-10-13T10:12:54+02:00"
```

**Un permesso senza il suo consenso copre `nulla`.** E l'ordine si legge dalle date
**dichiarate**: il consenso precede il permesso, e il permesso precede il **lavoro**.

> L'ordine è **consenso → permesso → lavoro**. Un permesso dichiarato **prima** del consenso
> è **retrodatato** e non copre. Il 2026-10-13 questo confronto era **invertito** nel
> codice di riferimento, e bloccava il caso giusto: la dimostrazione l'ha trovato (§8).

### 2.3 · `scar` — la cicatrice

```yaml
# errori/<id>.yaml
id: ERR-0052
scar_version: 1
date: "2026-10-13"
what_failed: "la condizione dell'ordine era invertita in due posti"
what_fixed_it: "le due condizioni corrette, e le date della prova raddrizzate"
what_would_have_caught_it: "la dimostrazione del cancello, costruita dalla regola"
becomes: check                 # check | note | record
where: "tools/tests/test_ad_org.py"    # obbligatorio se becomes: check, e DEVE esistere
found_by: review               # check | review | another-agent | me
state: closed                  # closed | open
```

**La terza domanda è quella che conta.** Non *cosa è fallito* e *cosa l'ha risolto*, ma
**cosa lo avrebbe preso**. Senza quella non è apprendimento: è un diario.

**E `becomes: check` è una promessa verificabile:** il file in `where` **deve esistere**.
Una voce che dichiara un controllo inesistente è **peggio** di una voce assente, perché
**sembra una difesa**.

### 2.4 · `seal` — il sigillo

Qualunque documento generato si sigilla così:

```text
impronta = sha256(corpo_del_blocco_generato)[:12]
```

**Un sigillo sul contenuto, non un puntatore ai registri.** La differenza è tutta qui: un
puntatore **non si può verificare** dopo che i registri sono cambiati — un sigillo **sì,
sempre**. È ciò che permette di distinguere **vecchio** da **falso**, che senza sigillo si
assomigliano.

E il sigillo dice **integrità, non correttezza**: dice che nessuno ci ha scritto sopra,
non che il contenuto sia giusto.

---

## 3 · Come si verifica, in quattro domande

Un verificatore risponde a **quattro** domande, e le tiene **separate** — perché
confonderle è il modo in cui un controllo comincia a mentire:

```text
1. ESISTE il consenso per questo permesso?          no -> il permesso non copre
2. L'ORDINE e' giusto?  consenso <= permesso?       no -> retrodatato, non copre
3. Il permesso e' ATTIVO e non scaduto?             no -> non copre
4. Il PERCORSO e' dentro write_scope?               no -> non copre
```

**E una quinta, che riguarda il documento invece dell'azione:**

```text
5. Il SIGILLO corrisponde al contenuto?             no -> manomesso
```

**Solo la quinta è un errore di manomissione.** Le prime quattro dicono *«non copre»*, che
è una cosa diversa: un permesso che non copre è un permesso **da fare**, non un documento
falso. Distinguerle serve a non gridare al tradimento quando manca un timbro.

---

## 4 · Nessun nome proprio

**In un record verificabile non entra il nome di una persona.** Entra il **ruolo**:

```yaml
approved_by: CEO        # non "Mario Rossi"
```

Il nome è un dato, sta **una volta sola**, nella configurazione locale del motore — e
**non si versiona**. Un formato che si pubblica non spedisce l'anagrafica di chi lo usa.

---

## 5 · Gli identificatori si prenotano, non si scelgono

Un identificatore (`GOV-`, `ERR-`, `DEC-`) **non si sceglie leggendo il massimo e
aggiungendo uno**: due sessioni che lavorano insieme scelgono **lo stesso numero**, e
succede ogni volta.

**Si prenota**: il file nasce **vuoto** e il numero è suo, assegnato dal filesystem in modo
**atomico** (`O_CREAT | O_EXCL`). *Rileggere il massimo e aggiungere uno non è prenotare: è
scommettere.*

E **gli id non si rinumerano**: una voce tolta **lascia il suo numero**, perché ogni
citazione a un id diventerebbe falsa. Per questo le sequenze si pretendono **crescenti**, non
contigue.

---

## 6 · La metrica della maturità

Questa è la parte che nessun altro pubblica, e si calcola da due numeri che il registro
delle cicatrici contiene già:

```text
maturita = cicatrici diventate CONTROLLO / cicatrici totali
```

**Perché è un buon numero:**

- **non si può gonfiare** senza scrivere i controlli, perché ogni `becomes: check` dichiara
  **il file che lo attua**, e quel file deve esistere;
- **sale da sola** quando il sistema impara, e **scende** quando si sbaglia di nuovo —
  cioè si comporta come una misura, non come un trofeo;
- **non è copiabile con un prompt**, perché richiede di **avere** le cicatrici.

**E c'è un numero più onesto ancora**, che il registro permette di calcolare e che vale la
pena pubblicare: **quante cicatrici ha trovato un controllo e quante una persona per
fortuna.** Nel motore di riferimento, il 2026-10-13:

```text
20 cicatrici · 5 trovate da un controllo · 9 trovate per fortuna · 4 ancora aperte
16 diventate CONTROLLO su 20  ->  maturita' 80%
giudizio vero: «equilibrio: meta' controlli, meta' fortuna»
```

**Un formato che permette di dire questo di sé stesso è un formato di cui ci si può fidare.**
Il numero si pubblica **anche quando è brutto**.

---

## 7 · Cosa NON è implementato qui, e lo dice

Un formato che promette più di quanto fa è un formato che mente. Quindi:

| Cosa | Stato |
|---|---|
| I record `slip`, `approval`, `scar`, `seal` | **implementati** e usati ogni giorno |
| Il **punto di blocco** prima dell'azione | **implementato dove il programma ha un gancio**. Dove non ce l'ha, il motore **lo dichiara** invece di fingere |
| La ricevuta d'azione firmata (`stub`) | **non implementata**. Va ripresa dalla [bozza IETF][ietf], non reinventata |
| La delega che restringe (`pass`) | **non implementata** |
| Il log Merkle e la verifica offline | **non implementati** |
| La firma crittografica dei record | **non implementata**: oggi i record sono **in chiaro**, e il sigillo è un digest, **non una firma**. Non autentica: rileva le modifiche |
| La metrica | **implementata** (`tools/comportamento.py`, `tools/errori.py stats`) |

**Il passo successivo ovvio**, per chi vuole il profilo completo: **firmare** i record con lo
schema della bozza e **produrre gli `stub`**. Le due parti sono complementari — loro la
prova, noi la serratura — e insieme coprono quello che nessuna delle due copre da sola.

---

## 8 · Perché ci si può fidare di questo documento

Perché ogni affermazione **si rifà**, e le sue cicatrici sono pubbliche.

Il giorno in cui questo profilo è stato scritto, la **dimostrazione del cancello** — la
quarta prova, *«e se il permesso viene prima del consenso?»* — ha risposto **OK** dove
doveva rispondere **NO**:

```text
permesso 2026-10-08 · consenso 2026-10-07  ->  PASSA     (giusto)
permesso 2026-10-07 · consenso 2026-10-08  ->  RIFIUTA   (giusto, dopo la correzione)
permesso 2026-10-07 · consenso 2026-10-07  ->  PASSA     (stesso giorno: l'ordine sta nella giornata)
```

**La condizione era invertita in due posti**, e nella macchina da cui viene questo profilo
non si vedeva: i permessi veri hanno consenso e apertura **lo stesso giorno**, e `13 > 13` è
falso. **Il difetto era invisibile da dentro.**

E c'era una prova che lo difendeva, scritta **guardando il codice** invece della regola:

> **Una prova che passa non dimostra che la regola sia giusta: dimostra che il codice fa
> quello che il codice fa.**

È la **terza volta in un giorno** che la stessa forma si è presentata — una prova che
dipende dal mondo, una firma che dipende dal mondo, una prova che dipende dal codice — e le
tre sono nel registro delle cicatrici, con nome e numero.

**Questo è il motivo per cui il formato vale la pena di essere pubblicato:** non perché è
giusto, ma perché **si può controllare**.
