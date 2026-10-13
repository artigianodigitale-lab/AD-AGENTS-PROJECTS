---
name: ad-avvio
description: >-
  L'avvio di AD-AGENTS-PROJECTS. Si usa quando l'utente dice `AGENTS.md` o collega la
  cartella del motore: l'AI dichiara di aver capito come si comportera', dichiara che
  AAP e' il suo comportamento da quel momento, e chiede subito se l'utente vuole
  iniziare un progetto NUOVO (cartella numerata) o collegarne uno ESISTENTE. Non cerca
  un progetto e non ne apre uno: dichiara, chiede, e aspetta.
whenToUse: >-
  All'avvio, quando l'utente dice `AGENTS.md` o collega la cartella. Sempre, anche se
  l'engine e' gia' avviato: `sede.yaml` che c'e' cambia i primi passi, non l'avvio.
---

# Avvio

**Non cercare un progetto. Non aprirne uno. Non analizzare niente.**

Il primo passo di AAP **non e' un lavoro: e' una risposta**. Tre parti, in quest'ordine.

## 1 · Di' di aver capito come ti comporterai

**Non riassumere il file.** Di' **cosa farai e cosa non farai**, in parole comprensibili
(invariante 14). Cinque righe, non cinquanta. Per esempio:

> Ho capito come mi comporto. Da qui in avanti:
> - **niente si scrive senza un permesso** — prima dico cosa faccio e dove, e finche' quel
>   permesso non c'e' la scrittura e' bloccata;
> - **i progetti si numerano**: il numero e' cio' che dice al sistema che quella cartella
>   va protetta;
> - **tu approvi**: le proposte arrivano a te, e senza il tuo si' non si parte;
> - la tua richiesta **non e' un ordine**: la verifico, e se trovo un modo migliore te lo
>   porto con fonti, costi e rischi;
> - **ogni passo lascia un rapporto**, che gli altri agenti possono leggere.

Adattala a chi hai davanti: se e' la prima volta, spiega un po' di piu'; se vi conoscete,
due righe bastano.

## 2 · Dichiara che AAP e' il tuo comportamento da quel momento

Una riga, esplicita. Non «posso usare queste regole», ma:

> **Da adesso lavoro cosi'.**

Non e' un'opzione fra tante e non si riattiva a ogni messaggio: **e' il modo in cui lavori
in questa cartella**, da qui in avanti.

## 3 · Chiedi subito cosa vuole fare

**Due strade, e sono le uniche due:**

> Vuoi **iniziare un progetto nuovo**, o **collegarne uno che hai gia'**?

E **aspetta la risposta.** Non scegliere per lui, non proporne una terza, non iniziare a
lavorare «intanto».

---

## Se l'engine non e' ancora avviato

`AGENTS.md` e' la costituzione: il blocco in cima ti dice di guardare se esiste `sede.yaml`
nella cartella che contiene `.brain/`.

**Se non c'e'**, l'engine non e' avviato. Prima delle due strade servono **tre cose**:

### a · Chiedi il nome

Chiedilo e **aspettalo**. Diventa il CEO: e' chi approva. Se l'utente non vuole dirlo, va
bene — il CEO resta «il CEO». **Non inventare un nome.**

### b · Chiedi il permesso, e di' cosa comporta

Di' **esattamente** cosa vuoi scaricare e **perche'**, e aspetta il si'.

| Cosa | A che serve | Costo |
|---|---|---|
| **SearxNG** (Docker) | il cervello cerca da solo sul web — scienza e tecnica | ~200 MB, un servizio da aggiornare |
| **Python 3** | i comandi della macchina | di solito c'e' gia' |
| **Node** | il cancello che blocca le scritture | di solito c'e' gia' |

**Se l'utente dice no al web, va bene**: l'engine legge gli indirizzi che gli dai. **Dillo**,
invece di lasciare che scopra da solo che non cerca.

### c · Installa, e **prova**

```sh
python3 tools/setup.py
```

Collega il cancello, la costituzione e le skill — e **prova** di averlo fatto: l'ultima
prova e' **una scrittura vera che deve essere rifiutata**. Se quella prova non passa,
**l'installazione non e' riuscita**, e va detto.

Poi scrivi `sede.yaml` col nome vero, **rileggilo**, e mostralo all'utente: se ha sbagliato
a dirti il nome, e' il momento di correggerlo.

**Solo allora** si torna al passo 3: nuovo, o esistente.

---

## I due percorsi

### Nuovo progetto — si crea una cartella numerata

1. **Chiedi il nome del progetto.** Solo il nome: `Modelbel`, `Stock Tracker`.
2. **Trova il numero libero** — il numero e' **la protezione**, non un'etichetta:
   ```sh
   python3 -c "import sys;sys.path.insert(0,'tools');import ad_scope;print(ad_scope.primo_numero_libero())"
   ```
3. **Di' il nome completo prima di crearlo**, e fallo approvare: *«lo chiamo
   `18. Modelbel`»*. Il numero non si sceglie a caso e non si riusa.
4. **Crealo dentro la cartella dei progetti**, che sta in `sede.yaml` → `macchina.progetti`
   (se il campo e' vuoto, accanto al motore).
5. **Da qui si apre il lavoro vero**: si passa a **`ad-kickoff`** — analisi di avvio,
   milestone, e il consenso del CEO **sulle milestone**, non «sul lavoro».

### Progetto esistente — si importa una cartella numerata

**La cartella deve essere numerata col nome del progetto.** E' quello che il sistema chiede
per proteggerla, e non e' una formalita': una cartella non numerata **passa il cancello** —
nessun permesso, nessuna approvazione, e nessuno se ne accorge.

1. **Chiedi dove sta la cartella**, e guarda cosa contiene. **Guardare non e' toccare.**
2. **Se e' gia' dentro la cartella dei progetti**, e' gia' collegata: si passa a `ad-kickoff`.
3. **Se e' altrove**, va **portata dentro** con il numero giusto:
   - **gia' numerata** → si sposta com'e', e si **chiede conferma prima di muovere**
     qualunque cosa;
   - **non numerata** → il cancello la rifiuta, e il rifiuto dice **quale numero usare**.
     Proponilo: *«la chiamo `18. Nome`»*, e fallo approvare.
4. **Spostare la cartella di un progetto e' un'azione irreversibile**: si dice cosa si sta
   per fare, **dove**, e si aspetta un si' esplicito. `ERR-0024` esiste perche' ho spostato
   una cartella senza guardare dove finiva.
5. **Poi** si legge cosa c'e' dentro — non prima — e si passa a `ad-kickoff`.

---

## Cosa non fare, all'avvio

- **Non cercare un progetto** fra quelli esistenti per proporne uno.
- **Non aprire un progetto** di tua iniziativa.
- **Non iniziare a lavorare** «intanto che l'utente risponde».
- **Non spostare, rinominare o creare cartelle** senza un si' esplicito.
- **Non dichiarare fatto** quello che non hai provato: se `setup.py` non passa le sue
  prove, **l'installazione non e' riuscita**.
