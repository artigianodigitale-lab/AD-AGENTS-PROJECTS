# AD-AGENTS-PROJECTS

**Un motore che dà a un agente AI le regole di una casa — e la forza di rispettarle.**

Colleghi questa cartella al tuo programma, scrivi `AGENTS.md`, e da quel momento l'agente
lavora con permessi, consenso, prove e memoria: non con la buona volontà.

Non è un prompt più lungo. È un sistema che **si installa**, e dove può **blocca**.

> **Questa è la versione vergine**: nessun progetto, nessuna carta di progetto. Si collega a un
> programma che sa leggere le regole, e da lì si comincia.

---


> **English?** [Read this document in English](README.md).

## Il lavoro per cui ti assume

Non «un agente che scrive codice». Il lavoro è questo:

> **Far lavorare un agente su cose che contano — soldi, clienti, dati di altre persone — senza
> doverti fidare della sua buona educazione.**

È un lavoro di **fiducia**. Ed è l'unico lavoro in cui un prompt non basta: un prompt è una
richiesta, non un confine. Un agente che *dovrebbe* non scrivere in produzione è un agente che
ci scriverà, il giorno in cui gli sembrerà una buona idea.

**Qui la differenza è una parola:** altrove è **sconsigliato**, qui — dove esiste un gancio — è
**impossibile**. E dove non è impossibile, **è scritto che non lo è**.

---

## Cosa riesce a fare

**Chiudere le porte.** Una scrittura in una cartella di progetto senza un permesso attivo
**viene rifiutata**, e il rifiuto dice **cosa manca e come rimediare**. Il permesso è un file:
dichiara chi scrive, dove, e per quale tappa.

**Far decidere una persona prima che si cominci.** Nessun lavoro parte senza il consenso
scritto di chi ha l'autorità — e l'ordine conta: **prima il consenso, poi il permesso**. Un
permesso retrodatato non copre niente, e il sistema se ne accorge **leggendo le date dichiarate
nei documenti**, non gli orari dei file: una copia li azzera, e un controllo che accusa
innocenti insegna a ignorarlo.

**Ricordare.** Ogni decisione è un verbale con le opzioni, **le fonti** e — obbligatoriamente —
la voce *«non fare nulla»*. Ogni errore è una cicatrice con tre domande: cosa è fallito, cosa
l'ha risolto, e **cosa lo avrebbe preso**.

**Accorgersi di essere peggiorato.** Sette prove comportamentali girano contro una baseline
salvata e rispondono a una domanda sola: **è peggiorato qualcosa?** Aggiornarla è una firma,
non un tasto.

**Fotografare, e non poter mentire.** Il documento d'ingresso di un progetto è metà scritto a
mano e metà **generato dai registri**, sigillato con un'impronta. Il controllo distingue
**vecchio** da **falso** — due cose che, senza sigillo, si assomigliano.

**Controllare sé stesso.** Un comando confronta le regole scritte con ciò che il sistema è
davvero: skill, comandi, passi, cartelle, documenti. Se la descrizione diverge, **lo dice** —
perché un agente che legge una descrizione sbagliata **segue quella**.

**Fare i conti senza spendere.** Diciannove comandi eseguono la governance **senza consumare
token**: validano, verificano, fotografano, misurano. L'intelligenza si usa dove serve.

---

## La prova, non la promessa

I numeri di oggi, e si possono rifare — sono nel repository:

| | |
|---|---|
| **464** controlli deterministici | girano in pochi secondi, senza rete |
| **36** controlli del cancello | modalità, classi di percorso, esiti di guasto |
| **19** comandi · **9** procedure · **12** passi | la banda deterministica e il processo |
| **0** permessi in conflitto | due contratti sullo stesso percorso: nessuno |
| **47 → 17** cicatrici | **un registro che si accorcia sta diventando codice** |

E la cosa che vale più di tutte, perché è la più facile da gonfiare e la più difficile da fare:

> **I controlli si verificano iniettando il difetto.** Non «il controllo esiste»: il controllo
> **si rompe** quando qualcuno sbaglia. Un controllo che non può fallire non è un controllo — e
> qui è scritto anche questo.

---

## Per chi è

**Queste sono ipotesi, non ricerca.** È la prima cosa che questo sistema insegna sul dire le
cose: una persona che non è stata intervistata è una **persona inventata**, e va dichiarata
come tale.

```yaml
- ipotesi: "Chi mette un agente su un lavoro vero ha gia' provato, e si e' spaventato almeno una volta"
  conferma_se: "su 8 persone, 5 raccontano un episodio preciso di scrittura indesiderata"
  smentita_se: "3 su 8 dicono di non aver mai avuto il problema"
  dati: nessuno          # <- nessuna intervista fatta: e' un'ipotesi, e lo dice
  validata: no
```

**Chi lo sta cercando adesso:** chi ha già un agente che lavora su più progetti e non sa più
cosa ha toccato; chi deve far entrare un collaboratore — o un agente — in un lavoro con dei
confini; chi ha bisogno di raccontare a qualcun altro **perché** una cosa è stata decisa.

**Chi non lo sta cercando:** chi vuole un agente che faccia tutto da solo. Questo motore fa
l'opposto: **rallenta dove una decisione non è stata presa**, ed è progettato per quello.

---

## In che spazio si muove

Non è solo. Accanto ci sono cose serie, e più mature:

- **I sistemi di permessi degli assistenti di codice** — chiedono il consenso al momento. Sono
  ottimi dove sono, ma quel consenso vale **per una volta sola**: non c'è memoria di ciò che è
  stato autorizzato ieri.
- **I framework per agenti** — orchestrano passi e strumenti. Il confine, però, di solito è
  **convenzione**: gli agenti *dovrebbero* rispettarlo.
- **Le piattaforme di valutazione** — misurano se l'agente fa bene un compito. Non se **ha il
  diritto** di farlo.
- **I sistemi di governance aziendale** — esistono, sono seri, e non parlano con un agente.

**Il posto vuoto è l'incrocio**: un permesso che **vive con il progetto**, un controllo che
**impedisce** invece di consigliare, e una memoria che sopravvive alla sessione.

---

## Il posizionamento

> **Per chi mette un agente AI su un lavoro che conta, AD-AGENTS-PROJECTS è il motore che
> trasforma le regole in confini — perché dove un controllo è possibile, la disciplina non
> serve più.**

**E la prova dal lato di chi lo usa.** Questa è la parte che conta, e l'unico modo onesto di
dirla è lasciarla leggere: guarda cosa risponde il motore a chi prova a scrivere dove non può.
Non dice *«attenzione, non dovresti»*. Dice:

```text
"IlMioProgetto" non e' una cartella di macchina, e non e' numerata.
**I progetti si numerano**: il numero e' cio' che dice al sistema che quella
cartella e' un prodotto — e quindi che va protetta con un permesso e
un'approvazione.
Rimedio: rinominala in **1. IlMioProgetto**. Il prossimo numero libero e' 1.
```

**Un divieto senza il rimedio è un vicolo cieco.** E quello che un sistema dice quando ti ferma
è tutto ciò che devi sapere su come è stato pensato.

---

## Come si usa

```text
1.  Copia la cartella dove vuoi che viva il motore.
2.  Collegalo al tuo programma (DSH, Claude Code, Codex, Cursor...).
3.  Scrivi:  AGENTS.md
4.  Il motore dichiara come si comportera', e ti chiede:
        un progetto NUOVO      -> crea una cartella numerata col nome del progetto
        un progetto ESISTENTE  -> ne importa uno che hai gia', e lo sposta solo se glielo dici
5.  Lavora. Il motore si occupa dei permessi, delle prove e della memoria.
```

**Se il programma ha un gancio** (DSH, Claude Code, Codex, Antigravity), una volta sola:

```sh
python3 tools/setup.py            # collega il cancello, la costituzione e le skill
python3 tools/setup.py --check    # e dimmi se e' a posto, senza scrivere niente
```

**Se non ce l'ha** (Cursor, o un'applicazione qualsiasi): `AGENTS.md` **è la porta**, e basta
dirgli di leggerlo. **Le regole viaggiano; il cancello no** — vedi sotto.

**La prima volta** chiede due cose: **come ti chiami** (diventa il CEO, cioè chi approva) e il
**permesso di installare** ciò che serve. Poi **prova** che il cancello blocca: crea una
cartella di progetto, verifica che la scrittura venga **rifiutata**, e la cancella anche se
qualcosa va storto.

**Non si dichiara installato: si prova che rifiuta.**

---

## Cosa c'è dentro

| | |
|---|---|
| `AGENTS.md` | **la porta**: è la costituzione, ed è il file che il programma legge da solo quando colleghi la cartella |
| `.brain/` | il cervello: costituzione, 9 procedure, il plugin che blocca le scritture |
| `tools/` | **19 comandi**, che lavorano senza consumare token |
| `sede.yaml` | **chi è il CEO** e **dove sono i progetti** (non si versiona: è tuo) |
| `contratti/`, `approvazioni/` | il registro delle autorizzazioni |
| `DECISIONI/`, `errori/`, `drift/`, `piani/` | la memoria |
| `milestone/`, `orchestrazione/` | i modelli e la vista operativa |

## Cosa è portabile, e cosa no

Verificato il 2026-10-13, **spostando davvero il motore** e facendo girare tutto da lì.

| | Portabile? |
|---|---|
| Le **regole** | **sì, sempre** — sono un documento che il programma legge |
| I **comandi** | **sì, sempre** — li esegue chiunque abbia Python |
| I **registri** | **sì** — sono file |
| La **ricerca web** | con SearXNG: è un servizio, non un file |
| Il **cancello che blocca** | **solo se il programma lo chiama.** È un plugin, e vive nel profilo del programma |

> **La differenza fra «sconsigliato» e «impossibile» è tutto quello che questo sistema ha
> imparato. Non si cancella per far contenta una tabella.**

## Vedere il cancello in azione

I permessi in questa cartella sono **tutti chiusi**, ed è voluto: *un permesso aperto in una
copia non è un esempio, è un permesso* — darebbe autorità sulla sede da cui la copia viene.
Il cancello si dimostra **creando il permesso al momento**. Due file, dieci righe, e si vede.

```text
# 1. senza permesso: rifiutato
$ python3 tools/contract_scope.py check ".brain/COSTITUZIONE.md"
".brain/COSTITUZIONE.md" e' un artefatto di GOVERNANCE (.brain/), non una cartella prodotto.
Rimedio: un contract con write_scope che includa ".brain/" e il marcatore
approvazioni/<task_id>.yaml approvato dal CEO
[exit 1]

# 2. il CEO approva, e si scrive il permesso
$ cat > approvazioni/societa/DEMO-001.yaml <<'FINE'
task_id: DEMO-001
approvato_da: CEO
data: "2026-10-13"
FINE
$ cat > contratti/societa/DEMO-001.yaml <<'FINE'
task_id: DEMO-001
status: active
aperto: "2026-10-13"
write_scope:
  - ".brain/"
FINE

# 3. e adesso passa
$ python3 tools/contract_scope.py check ".brain/COSTITUZIONE.md"
OK   .brain/COSTITUZIONE.md — coperto dal contract DEMO-001 (DEMO-001.yaml),
     approvato da CEO il 2026-10-13

# 4. ma se il permesso e' RETRODATATO, non copre
$ sed -i 's/2026-10-13/2026-10-11/' contratti/societa/DEMO-001.yaml
$ python3 tools/contract_scope.py check ".brain/COSTITUZIONE.md"
Il contract DEMO-001 e' stato scritto PRIMA dell'approvazione (2026-10-13).
L'ordine e' ricerca -> risposta -> consenso -> contract: un contract retrodatato non copre.
```

**Il quarto passo è il motivo per cui questa dimostrazione esiste.** Scrivendola, il 2026-10-13,
ha risposto **OK** dove doveva rispondere **NO** — perché la condizione dell'ordine era
**invertita**. Nella macchina da cui viene questa copia non si vedeva: i permessi veri hanno
consenso e apertura **lo stesso giorno**, e il difetto restava nascosto. Vedi `ERR-0052`.

> **Una prova che passa non dimostra che la regola sia giusta: dimostra che il codice fa quello
> che il codice fa.** Se la prova è scritta guardando il codice, il difetto è invisibile.

## Cosa manca — da leggere prima di fidarsi

Il motore **dichiara i propri limiti**, e questa sezione non è una formalità: un sistema che
nasconde cosa non sa fare è un sistema di cui non puoi fidarti su nient'altro.

1. **Il cancello non si acquisisce: si installa.** Collegare la cartella dà **le regole**; per
   il cancello che **blocca** serve `setup.py`, una volta. Dove il programma non ha un gancio,
   **si dice** che non c'è.
2. **Gli adattatori per gli altri programmi sono dichiarati, non provati.** Claude Code, Codex
   e Antigravity non sono su questa macchina, e **non si dice che funzionino**.
3. **Il consenso è imposto solo se qualcuno esegue il validatore.** Il cancello blocca le
   *scritture*, non l'assenza di consenso: è una divergenza **dichiarata**, non nascosta.
4. **L'analisi dei comandi di shell è un'euristica.** Un comando che cambia cartella e poi
   scrive in modo relativo può sfuggirgli. Il confine affidabile resta il permesso scritto.
5. **La ricerca web vuole SearxNG**, che è un servizio locale: senza, il motore legge solo gli
   indirizzi che gli dai.
6. **La suite si ferma su un motore appena scaricato.** Alcune prove presuppongono che il mondo
   esista. È un difetto **dichiarato** con la sua correzione (`errori/ERR-0049`).
7. **Il registro delle cicatrici è curato, non completo.** E lo dichiara.

**In una riga**: il motore funziona da solo, e le due cose che non fa da solo sono
**installarsi** e **funzionare su un programma senza gancio**.

---

## Perché è fatto così

È nato in **cinque giorni**, e la forma della curva non è casuale:

| Giorno | Verbali | Cicatrici | |
|---|---|---|---|
| 08/10 | 27 | 6 | la governance |
| 10/10 | 11 | 10 | il cervello |
| **11/10** | 14 | **25** | **il giorno peggiore** |
| 12/10 | 0 | 3 | i progetti |
| 13/10 | 4 | 4 | la portabilità |

**Venticinque cicatrici in un giorno**, quasi tutte della stessa famiglia: *qualcosa scritto a
mano che poteva essere controllato*. E il modello dei verbali seguito **3 volte su 36**, perché
nessuno lo verificava.

Da lì nasce la regola che governa ogni pezzo nuovo:

> **Se puoi meccanizzarlo, fallo adesso. Altrimenti scrivi perché non puoi.**

**E la regola si applica anche a sé stessa**: il registro delle cicatrici **si è accorciato**
quando le sue voci sono diventate controlli. **Un registro che si allunga è un registro che non
sta diventando codice.**

---

## La documentazione

| File | Cosa contiene |
|---|---|
| **[GRAFO.md](GRAFO.md)** | **sette diagrammi** che spiegano il funzionamento; GitHub li disegna da solo. Comincia da qui |
| **[DOCUMENTAZIONE-TECNICA.md](DOCUMENTAZIONE-TECNICA.md)** | **per developer**: architettura, modello di autorizzazione, il cancello, i 19 comandi coi codici di uscita, il modello dati, la strategia di prova — **e le divergenze trovate** |
| **`AGENTS.md`** | la porta: è la costituzione |
| **`.brain/`** | la costituzione, le 9 procedure, il plugin |
| **`tools/README.md`** | il **registro**: l'unico posto dove i comandi sono dichiarati |

**Tre cose che questo sistema pretende da chi lo legge, e le mantiene su di sé:** ogni
affermazione ha una verifica; ogni limite è dichiarato; ogni numero si può rifare.

---

## Credito

**Ideato e creato da Luca / Artigiano Digitale.**
Costruito **con** il [DeepSeek Harness](https://github.com/deepseek-ai) (DSH, MIT): il merito di quella parte resta ai suoi autori, ed e' scritto nel file `NOTICE`.

Il progetto e' aperto al mondo: **[CONTRIBUTING.md](CONTRIBUTING.md)** e' la porta. Non serve conoscere il codice — il documento te lo da' il sistema.

## Licenza

**Apache-2.0.** Il motore nasce dentro il *DeepSeek Harness* (DSH), che è **MIT**: il merito di
quella parte resta suo, ed è scritto qui.

---

> **Una regola scritta non cambia il comportamento. Un controllo che fallisce sì.**
>
> Tutto il resto di questo repository è la conseguenza di quella frase.
