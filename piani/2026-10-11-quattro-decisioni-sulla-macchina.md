# Piano — Cinque decisioni sulla macchina, emerse dal kickoff di Marketing Factory

```yaml
id: PIANO-2026-10-11-macchina
stato: parzialmente approvato  # decisione 1 approvata; 2-5 in attesa
data: 2026-10-11
progetto: societa          # non e' un progetto: sono regole della macchina
dominio: technical
richiesta: >
  Decidere cinque cose emerse mentre si lavorava alla milestone 3 di Marketing
  Factory: dove finiscono i documenti di un progetto, se il registro delle
  autorizzazioni entra in git, come si registra l'autorizzazione, dove vive il
  Blueprint, e chi puo' scrivere le viste.
esito_ricerca: da completare — nessuna delle cinque e' stata cercata fuori
decision_record: ""        # da aprire per ciascuna decisione presa
```

## 1. Cosa hai chiesto

Niente di tutto questo, direttamente. Sono **cinque cose che il lavoro ha fatto
emergere** mentre eseguivo il kickoff di Marketing Factory: quattro le hai gia'
incontrate (il commit dei documenti, la regola di congelamento, il varco del
Blueprint, la registrazione dell'autorizzazione); la quinta — chi puo' scrivere le
viste — e' venuta fuori **riparando** la quarta, ed e' la stessa famiglia.

Non sono lavoro di Marketing Factory. Sono **regole della macchina**, e per
questo stanno in un piano a parte invece che dentro il progetto.

## 2. Cosa ho trovato

Tutte e cinque hanno la stessa forma: **una cosa che si faceva a mano, o che
nessuno faceva, e che il sistema non sa dichiarare.** Nessuna e' un guasto: sono
lacune del disegno, e si vedono solo adesso che i controlli funzionano.

Le fonti sono interne e verificabili — non c'e' ricerca esterna da fare su
nessuna delle cinque. E' una decisione di governo, non una scelta di metodo.

## 3. Cosa consiglio

| # | Decisione | Consiglio |
|---|---|---|
| 1 | Dove finiscono i documenti di un progetto | Versionarli nel repository del progetto |
| 2 | Il registro delle autorizzazioni entra in git | **Si', e subito**: e' la cosa piu' urgente delle cinque |
| 3 | Come si registra l'autorizzazione | Il marcatore dichiara il momento della **registrazione** |
| 4 | Dove vive il Blueprint | Renderlo un **documento della macchina**, fuori dal progetto |
| 5 | Chi puo' scrivere le viste | Un permesso unico per le viste, **piu' un controllo che lo pretende** |

## 4. Cosa serve da te

Cinque risposte secche. La (2) e' quella con il costo piu' alto se si aspetta.

---

## Decisione 1 — I documenti di un progetto entrano in un archivio

**Gia' decisa da te l'11 ottobre** («Si': versionare i documenti nel progetto»).
La registro qui perche' manca la parte operativa, e perche' ha una conseguenza
che allora non era visibile.

**Il fatto.** I 19 documenti di Marketing Factory (poi 20) — report, Blueprint,
analisi, evidenze, 1.028 righe — **non stanno in nessun repository**: non in
quello del progetto (`git ls-files Analisi-Prompt-Report/` esce **0**), non in
quello della radice (che esclude i 17 progetti per scelta deliberata,
`DEC-0042`, `.gitignore` riga 20). Vivono su un solo disco.

**Opzioni.**

- **(a) Versionarli nel repository del progetto** — un `git add`, nessuna regola
  da cambiare, la cartella **non** e' ignorata (`git check-ignore` esce 1). Costo:
  un comando e una convenzione per i messaggi (il progetto usa `AMF-nnn: …`).
  Rischio basso. **Non e' un backup**: i 161 commit del progetto non sono mai
  usciti dalla macchina.
- **(b) Un archivio separato, fuori dalla macchina** — l'unica che risponde a «e
  se il disco muore?». Costo alto: una destinazione, una cadenza, un modo di
  sapere se l'ultima copia e' recente. Decisione di **Livello 3** (cosa esce).
- **(c) Non fare nulla** — costo zero oggi, **tutto** il giorno in cui serve: si
  perdono 1.028 righe di storia e le prove dei gate.

**Consiglio:** (a) come primo atto — e' l'unica fattibile oggi a costo quasi zero
— e (b) come risposta vera, da prendere una volta per **tutti** i progetti.

**Cosa manca per farlo:** una card. **Nessuna delle 42 card copre «committare le
carte di un progetto»**: `implementation` non trova match, e la regola dice che
in quel caso non si assegna alla card piu' vicina. C'e' il precedente di
`REL-001` (8 ottobre, card `technical-writer`, task type `documentation`), ma il
precedente non e' una copertura.

---

## Decisione 2 — Il registro delle autorizzazioni entra in git

**Trovata adesso, non era nel piano. E' la piu' urgente delle cinque.**

**Il fatto.** Il registro che il controllore legge **a ogni scrittura** —
`contratti/` e `approvazioni/` — ha in questo momento **12 file non versionati**:

```
contratti/3-ad-marketing-factory/ADMF-001.yaml     approvazioni/3-ad-marketing-factory/ADMF-001.yaml
contratti/3-ad-marketing-factory/ADMF-002.yaml     approvazioni/3-ad-marketing-factory/ADMF-002.yaml
contratti/3-ad-marketing-factory/ADMF-003.yaml     approvazioni/3-ad-marketing-factory/ADMF-003.yaml
contratti/societa/ADMF-004.yaml                    approvazioni/societa/ADMF-004.yaml
errori/ERR-0026-blueprint-senza-guardia.yaml       errori/ERR-0027-evidenza-scelta-senza-filtro.yaml
errori/ERR-0028-prodotto-modificato-durante-il-gate.yaml
piani/2026-10-11-ad-marketing-factory-milestone-3.md
```

I file **presenti** sono 49, quelli **tracciati** 43. E la radice **non ha
nessun remoto** (`git remote -v` non stampa niente): quei 43 sono versionati, ma
non sono copiati da nessuna parte.

**Perche' conta piu' delle altre tre.** I documenti di un progetto sono la
memoria di **quel** progetto. Questo registro e' **la memoria delle
autorizzazioni di tutti**: se sparisce, si perde la prova di chi ha autorizzato
cosa — e il controllore, al riavvio, non saprebbe piu' chi puo' scrivere dove.
E' il file che rende eseguibile la regola «senza contract non si scrive».

**Opzioni.**

- **(a) Un commit subito** — `git add` dei 12 file nella radice. Costo: un
  comando. **Attenzione, e l'ho verificato**: `git add` **cambia l'mtime** del
  file, e il controllore pretende che il contract sia **piu' recente** della sua
  approvazione. Un `add` sui contract appena creati puo' quindi renderli
  invalidi finche' il marcatore non viene riscritto — la stessa trappola che mi
  ha respinto due volte stanotte. Va fatto **con l'ordine giusto**: prima i
  marcatori, poi i contract.
- **(b) Un commit e un remoto** — come (a), piu' una destinazione fuori dalla
  macchina. E' l'unica che sopravvive alla perdita del disco. Decisione di
  **Livello 3**.
- **(c) Non fare nulla** — il registro resta com'e': la sua parte piu' recente
  (tutto il lavoro di oggi) vive solo su disco, e un `rm -rf` la cancella. La
  stessa sorte che `ERR-0024` ha sfiorato per una cartella di progetto.

**Consiglio:** (a) **oggi**, con l'ordine giusto marcatori-poi-contract, e (b) —
il remoto — insieme alla decisione 1(b), perche' e' la stessa domanda: *se questa
macchina muore, cosa resta?*

**Cosa manca per farlo:** un permesso. `contratti/` e `approvazioni/` sono liberi
**apposta** (sono l'input dell'autorizzazione), ma `errori/` e `piani/` no: vanno
coperti, e il commit nella radice e' una scrittura di governance.

---

## Decisione 3 — Come si registra l'autorizzazione

**Il fatto, raccontato come e' andata.** Aprendo i permessi dello sprint 2 ho
scritto i marcatori con `data: 17:00` — l'ora della nostra conversazione — mentre
i contract li ho scritti alle **17:54**. Il controllore ha rifiutato tutti e tre:
*«Il contract e' stato scritto PRIMA dell'approvazione. L'ordine e' ricerca →
risposta → consenso → contract: un contract retrodatato non copre»*. Ho corretto
con un'altra data sbagliata, e ha rifiutato di nuovo. Alla terza ho capito: il
campo `data` non e' **quando ne abbiamo parlato**, e' **quando il sistema registra
l'autorizzazione**.

**Perche' non e' un dettaglio.** Il cancello confronta due cose: la data
**dichiarata** nel marcatore e l'mtime **reale** del contract. Sono due orologi
diversi — uno lo scrive una persona, l'altro lo mette il filesystem — e la regola
funziona solo se si sa quale dei due comanda. Oggi lo dice il messaggio d'errore;
non lo dice nessun documento.

**Opzioni.**

- **(a) Scriverlo nel modello** — una riga in `contratti/_TEMPLATE.yaml` e in
  `approvazioni/`: «`data` e' il momento della registrazione, non del consenso; il
  consenso va in `fonte`». Costo: due righe. E' quello che ho fatto a mano sui
  marcatori di oggi, e ha funzionato.
- **(b) Far controllare il sistema** — un controllo che avverta quando la data
  dichiarata e' **precedente** all'mtime del file che dovrebbe autorizzare.
  Rende impossibile l'errore invece di sconsigliarlo.
- **(c) Non fare nulla** — ogni sessione che apre un permesso sbaglia almeno una
  volta, lo scopre dal rifiuto, e corregge. E' quello che e' successo: tre
  tentativi per due permessi. Funziona, costa tempo, e non lascia niente scritto.

**Consiglio:** (b), con (a) come documentazione. E' la differenza fra una regola
scritta e una regola eseguita — la stessa lezione di `ERR-0026`.

**Nota.** La difesa esiste gia' ed e' buona: il cancello **mi ha preso**. Il
punto e' che mi ha preso **due volte su tre**, e ognuna e' costata un giro.

---

## Decisione 4 — Dove vive il Blueprint

**Il fatto.** Il Blueprint e' «una fotografia dei registri, scattata alla chiusura
di ogni tappa», e la sequenza di chiusura (passo 12) prescrive di rigenerarlo. Ma
vive **dentro il progetto** (`Analisi-Prompt-Report/BLUEPRINT.md`), e nessun
permesso lo copre fra una tappa e l'altra. Adesso che la guardia funziona — la
stessa che ho appena riparato — **quella scrittura e' impossibile**:

```console
$ python3 tools/contract_scope.py check "3. AD-Marketing-Factory/Analisi-Prompt-Report/BLUEPRINT.md"
exit 1 — Nessun task contract copre
$ python3 tools/blueprint.py render "3. AD-Marketing-Factory"
exit 2 — rifiutato
```

Prima passava **perche' il controllo non c'era**: e' la stessa storia di
`ERR-0026`, vista dall'altro lato. Il Blueprint di Marketing Factory e' quindi
rimasto **indietro** (autentico, non manomesso) — e non c'e' modo di aggiornarlo.

**Opzioni.**

- **(a) Renderlo un documento della macchina** — il Blueprint si genera in
  `orchestrazione/`, fuori dai progetti, come `stato.md`; nei progetti resta un
  rimando. Diventa scrivibile sempre, perche' i percorsi di governance non sono
  protetti come i prodotti. Costo: cambia dove si trova la fotografia — una
  scelta per il CEO, non un dettaglio tecnico.
- **(b) Dare a ogni sprint il permesso di rigenerarlo** — si aggiunge la riga
  `3. AD-Marketing-Factory/Analisi-Prompt-Report/BLUEPRINT.md` al `write_scope`
  degli sprint. Costo: una riga per contract, e il Blueprint torna scrivibile
  **solo** mentre lo sprint e' aperto — che e' esattamente quando serve.
- **(c) Un permesso dedicato alla chiusura** — un contract per ogni chiusura di
  tappa. E' il piu' corretto sulla carta e il piu' pesante: un documento di
  governo per una rigenerazione meccanica.
- **(d) Non fare nulla** — il Blueprint resta indietro finche' qualcuno non apre
  un permesso apposta. Il file e' autentico, quindi non mente: e' solo vecchio, e
  il controllo lo dice.

**Consiglio:** (b). Il Blueprint e' una vista del progetto e li' deve restare:
spostarlo nella macchina risolve il problema cambiando la cosa che descrive. (b)
costa una riga e lega la fotografia al momento in cui si scatta.

**Nota del 2026-10-11, dopo la riparazione della guardia.** Questa decisione ha
smesso di essere teorica: il Blueprint del progetto **non e' piu' rigenerabile**.
L'ultima fotografia e' delle **18:15:48.088**; la guardia e' entrata in
`blueprint.py` alle **18:15:50.303** — due secondi e mezzo dopo. Da quel momento il
passo 12 della sequenza di chiusura fallisce, correttamente, perche' nessun
permesso copre il percorso. Prima funzionava **perche' il controllo non c'era**:
e' la stessa storia di `ERR-0026`, vista dall'altro lato.

---

## Decisione 5 — Chi puo' scrivere le viste

**Trovata mentre si riparava la (4): e' la stessa famiglia, e va decisa insieme.**

**Il fatto.** La sequenza di chiusura di ogni tappa impone tre scritture che
**nessun permesso copre**:

| Vista | Percorso | Stato |
|---|---|---|
| La fotografia del progetto (passo 12) | `<progetto>/Analisi-Prompt-Report/BLUEPRINT.md` | **BLOCCATO** |
| La vista operativa | `orchestrazione/stato.md` | scrivibile |
| La baseline comportamentale | `evals/baseline.yaml` | scrivibile |

Le ultime due sono scrivibili **solo perche' stanno fuori dalle cartelle
prodotto**: non e' una decisione, e' un effetto della regola sulle cartelle. E il
gate `Code Review` di `ADMF-004` ha infatti contestato che `orchestrazione/stato.md`
fosse stato rigenerato **fuori dal `write_scope`** del contract (`tools/`). Ha
ragione sulla lettera: il file e' stato scritto da fuori l'ambito. Ma la procedura
**impone** di rigenerarlo, e il permesso non lo prevede.

**Perche' conta.** E' la terza volta in una giornata che si incontra la stessa
forma: **una procedura prescrive una scrittura, e il permesso non la copre.** La
prima e' `ERR-0026` (lo strumento scriveva senza controllo). La seconda e' il
Blueprint (il passo 12 non e' eseguibile). La terza e' questa. Non sono tre
incidenti: e' **un buco nel modo in cui i permessi si scrivono** — si scrive il
`write_scope` di cio' che il lavoro *produce*, e ci si dimentica di cio' che la
*chiusura* pretende.

**Opzioni.**

- **(a) Le viste dichiarate nei permessi** — ogni contract il cui sprint si chiude
  aggiunge al `write_scope` i percorsi delle viste che rigenera. Costo: due-tre
  righe per contract. Rischio: si dimenticano, ed e' esattamente cosa succede oggi.
- **(b) Un permesso unico per le viste** — un contract di governance che copre
  `orchestrazione/`, `evals/` e i Blueprint di tutti i progetti, e che si apre
  quando si chiude. Costo: un permesso da tenere, ma **una volta sola**.
- **(c) Un controllo che le pretende** — come (a), ma con un controllo che alla
  chiusura di uno sprint **verifica** che il permesso copra le viste che la
  procedura impone, e fallisce se non e' cosi'. Rende l'omissione impossibile
  invece di sconsigliarla.
- **(d) Non fare nulla** — ogni chiusura si scontra con la guardia e qualcuno
  scrive "fuori ambito" come e' appena successo, oppure rinuncia a rigenerare e le
  viste restano vecchie. E' lo stato di adesso.

**Consiglio:** (c) sopra (b). La (b) toglie il problema oggi; la (c) e' l'unica
che impedisce alla quarta volta di succedere. Ed e' la stessa lezione di
`ERR-0026`: **un principio non meccanizzato torna a mancare.**

---

## Rischi e dipendenze

- La (2) ha una **trappola d'ordine** verificata: `git add` cambia l'mtime dei
  contract e puo' invalidarli. Va fatto marcatori-prima, contract-dopo.
- La (1) e la (2) condividono la stessa domanda di fondo. Deciderle insieme costa
  una volta sola.
- La (3) e la (4) sono piccole, e nessuna delle due blocca le altre. La (5) e' la
  stessa famiglia della (4): deciderle separate significa riparare due volte lo
  stesso buco.
- Nessuna delle cinque tocca un documento normativo. La regola di congelamento
  (`ERR-0028`, `QUALITY-GATES.md`) e' **fuori da questo piano**: e' una decisione
  a parte, con il suo Decision Record.

## Costo previsto

Fascia deterministica: nessuna ricerca esterna, nessuna spesa. Le decisioni (1) e
(2) richiedono lavoro di esecuzione (commit, permessi); (3) e (4) richiedono
poche righe e i loro controlli.

## Fuori scope

- la regola di congelamento (`ERR-0028`) e la modifica di `QUALITY-GATES.md`;
- qualsiasi lavoro dentro Marketing Factory: la milestone 3 va avanti per conto suo;
- il remoto dei repository, se non come parte della (1b) e (2b).

## Approvazione

```yaml
approvato_da: CEO
data_approvazione: "2026-10-11"
note: >
  Approvata la decisione 1 (versionare i documenti nel progetto) — eseguita sotto
  il contract ADMF-006. Le decisioni 2, 3, 4 e 5 restano in attesa: la 2 e' la piu'
  urgente (il registro delle autorizzazioni ha 5 file non versionati e la radice
  non ha remoto), la 5 chiude il buco che rende il passo 12 di chiusura non
  eseguibile.
```
