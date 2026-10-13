# Piano — Come si verifica un documento che cita numeri che cambiano

```yaml
id: PIANO-2026-10-11-documento-che-invecchia
stato: proposto            # proposto | approvato | corretto | respinto
data: 2026-10-11
progetto: "3. AD-Marketing-Factory"   # nasce da qui, ma la regola e' della macchina
dominio: technical
richiesta: >
  Decidere come si chiude il report della verifica del 10-11 ottobre, che ha preso
  FAIL tre volte sul criterio della forma mentre tutti i suoi fatti sono stati
  verificati due volte da chi non li ha scritti.
esito_ricerca: da completare — la regola riguarda il metodo, non il dominio
decision_record: ""        # da aprire se si adotta
```

## 1. Cosa hai chiesto

Di rifare il report "in forma pulita", dopo che `ADMF-001` era stato bocciato due volte. L'ho
fatto. Il report nuovo — `Milestone 3/Sprint 2/REPORT.md`, 1.593 righe, 47 blocchi console — ha
preso **`FAIL` su entrambi i gate**. È il **terzo** `FAIL` consecutivo sul **criterio 1**:
*«ogni affermazione porta la sua prova (comando eseguito ed esito), non un rinvio»*.

**Non chiedo di riprovarlo una quarta volta.** Chiedo di decidere il metodo, perché il problema non
è la cura del documento: è che stiamo usando lo strumento sbagliato per il compito.

## 2. Cosa ho trovato

### I fatti sono veri, e sono stati verificati due volte

La QA ha rieseguito **64 affermazioni** con comandi indipendenti: **tutte vere**. La Code Review ne
ha rieseguite una trentina: le stesse. Il difetto storico — l'elenco delle decisioni che nominano il
progetto, che aveva fatto fallire `ADMF-001` — è **riparato**: ora il report dichiara il **criterio**
accanto a ogni numero (11 col filtro `DEC-*.md`, 12 col comando ovvio che include l'indice, 13 con
la forma con lo spazio). Nessun gate ha trovato un fatto falso.

### I tre `FAIL`, e cosa hanno contestato

| Giro | Cosa hanno bocciato |
|---|---|
| `ADMF-001` 1° | un elenco falso (11 voci invece di 13) + dieci numeri senza il comando |
| `ADMF-001` 2° | lo stesso elenco, non toccato dal rework + sei numeri senza comando |
| `ADMF-002` | un numero falso + **tre citazioni attribuite al prompt che il prompt non contiene** + conteggi invecchiati (7 invece di 9, «quattro» invece di «cinque») + una promessa non mantenuta |

**Il pattern è chiaro, e non è negligenza: è strutturale.**

1. **Ogni correzione sposta le righe.** Il report cita sé stesso e altri documenti per numero di
   riga. Correggere un difetto a riga 120 sposta tutto ciò che sta sotto, e le citazioni puntano
   altrove. Il rework del giro 2 ha **riparato i difetti elencati e creato citazioni nuove sbagliate
   in tre "Scostamenti dal prompt"** — esattamente per questa ragione.
2. **La cartella si muove mentre si scrive.** Fra le 18:18 e le 18:45 sono cambiati: il report, due
   evidenze di gate, la vista operativa, il piano. Un conteggio scritto alle 18:21 era già vecchio
   alle 18:25, e il report stesso lo dichiara — ma dichiararlo non lo rende verificabile.
3. **La severità cresce a ogni giro.** Il criterio è giusto e va tenuto; ma applicato a un documento
   di 1.593 righe con centinaia di numeri, ogni passata trova difetti nuovi **perché li crea la
   passata stessa**.

### Il costo, misurato

Tre giri di contract e rework, **nove verificatori indipendenti** (due per giro su `ADMF-001`, due su
`ADMF-002`, due su `ADMF-004`, uno su `ADMF-003`, più il primo `ADMF-004`), e il risultato è un
documento che **non è accettato** mentre i suoi fatti sono doppiamente confermati. Il costo è alto e
il beneficio marginale del quarto giro è vicino a zero: i difetti residui sono **dieci**, tutti
elencati con prova, e nessuno tocca una conclusione.

## 3. Cosa consiglio

**Fermare il ciclo e cambiare la forma del documento, non la sua cura.** Tre opzioni, più il non
fare nulla.

### (a) Il report diventa un **rapporto breve** e le prove si spostano in un allegato generato

Il rapporto (10-15 pagine) dice i fatti e le conclusioni, e **per ogni numero rimanda a una riga
dell'allegato**. L'allegato è **generato da uno script**: una tabella `comando → esito → momento`,
prodotta eseguendo i comandi, non scritta a mano. Così:

- il rapporto non contiene numeri scritti a mano: li **cita** dall'allegato;
- l'allegato si **rigenera** quando serve, e non invecchia: porta il momento di ogni misura;
- un verificatore controlla l'allegato **rieseguendo lo script**, e il rapporto controllando che i
  rimandi esistano.

**Costo:** uno script (mezza giornata) e la riscrittura del rapporto in forma breve. **Rischio:**
basso. È l'unica opzione che **toglie** la causa invece di curarla.

### (b) Il report si scrive **a cartella ferma**, con il numero che si congela

Si congela il workspace (nessuna scrittura durante la stesura), si scrive il report **in una sola
passata** prendendo le misure una volta, e si verifica **senza toccare niente**. Le citazioni
interne non si usano: si cita il **file e l'impronta**, non la riga.

**Costo:** una finestra di congelamento (ore). **Rischio:** medio — il congelamento dipende dalla
disciplina, e oggi **non è una regola scritta** (è `ERR-0028`, ancora aperto).

### (c) Un quarto giro **chirurgico**, con i dieci difetti come lista di lavoro

I due gate hanno elencato i difetti con la prova e indicano un rework puntuale. Un quarto giro
potrebbe chiuderli tutti.

**Costo:** basso per difetto, ma **è esattamente ciò che è stato fatto due volte**, e ogni volta ha
prodotto difetti nuovi. **Rischio: alto di un quarto `FAIL`.** Non lo consiglio da solo.

### (d) Non fare nulla

Il report resta quello che è: **fatti verificati due volte, forma non accettata**, con i suoi difetti
dichiarati in chiaro. Il lavoro del CEO — decidere la regolarizzazione dei documenti — **si può fare
lo stesso**, perché i fatti sono quelli e sono confermati.

**Costo:** zero. **Costo differito:** il progetto ha un report che nessun gate ha accettato, e la
prossima volta che serve una verifica si riparte da zero — che è il lavoro che questo report
doveva evitare.

## 4. Cosa serve da te

Una risposta secca. Il mio consiglio: **(a)**, con **(d)** come ponte — cioè **usare subito i fatti
del report per la tua decisione** (sono verificati) e **rifare la forma con lo script** quando
riprenderemo il filo, senza un quarto tentativo sullo stesso documento.

---

## Obiettivo

Un modo di produrre i rapporti di verifica che **non invecchino** e che un gate possa accettare
senza inseguire citazioni: numeri **generati**, non scritti; rimandi per **file e impronta**, non per
riga.

## Ambito

```text
write_scope previsto:
  - tools/                                          (lo script dell'allegato)
  - 3. AD-Marketing-Factory/Analisi-Prompt-Report/Milestone 3/Sprint 2/
```

## Card coinvolte

| Card | Perche' | Task type |
|---|---|---|
| `technical-writer` | riscrive il rapporto in forma breve | `documentation` |
| `platform` | lo script che genera l'allegato | `shared_platform` |

## Gate e indipendenza

| Gate | Owner dell'evidenza |
|---|---|
| Code Review | `review` |
| QA | `qa` |

Chi verifica e' **diverso** da chi scrive, e — questa e' la parte nuova — **verifica l'allegato
rieseguendo lo script**, non leggendo i numeri.

## Decisioni richieste al CEO

- **quale opzione** (a, b, c, d). Se (c): si apre un quarto tentativo sapendo che due sono già
  falliti e il rischio è dichiarato.
- se il **congelamento** diventa una regola scritta (`ERR-0028`), che tocca `QUALITY-GATES.md` e
  richiede un Decision Record.

## Rischi e dipendenze

- `ADMF-004` è `ACCEPT` ma **aspetta la firma del CEO**: finché non firma, il contract resta attivo.
- Il report di `ADMF-002` è **congelato**: chi lo tocca rompe la verifica (è `ERR-0028`).
- Se si sceglie (a), il rapporto breve **sostituisce** quello attuale, che resta come allegato
  storico — non si cancella.

## Costo previsto

Fascia deterministica per lo script (nessuna ricerca esterna, nessuna spesa). La riscrittura breve è
una frazione del tempo già speso nei tre giri.

## Fuori scope

- un quarto tentativo "a mano" senza cambiare il metodo;
- la modifica di `QUALITY-GATES.md` senza Decision Record;
- qualsiasi lavoro di business: la milestone 3 aspetta questa decisione per lo sprint 3.

## Approvazione

```yaml
approvato_da:              # il CEO
data_approvazione:
note:
```
