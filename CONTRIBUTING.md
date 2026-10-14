# Contribuire / Contributing

**Questo progetto è aperto al mondo, e la porta è un documento che il sistema ti dà.**

*This project is open to the world, and the door is a document the system gives you.*

---

**Una parola che non capisci?** [GLOSSARY.md](GLOSSARY.md) — 25 termini, italiano e inglese, tre righe l'uno.

## Italiano

### Come si contribuisce, in quattro passi

```bash
# 1. Il sistema ti dà il documento, con le domande dentro
python3 tools/contributo.py nuovo

# 2. Rispondi alle 6 domande. Non serve essere ordinati: serve essere precisi.
#    Se una domanda non ha risposta per te, scrivi "non lo so".
#    «Non lo so» è un'informazione. Una risposta inventata per riempire lo spazio no.
#    La sesta domanda chiede se vuoi essere RINGRAZIATO COL TUO NOME: decidi tu.
#    Se scrivi «anonimo», resti anonimo, e non te lo chiediamo due volte.

# 3. Controlla che non manchi niente
python3 tools/contributo.py check contributi/CONTRIBUTO-001-*.md

# 4. Mandalo per email
#    a:  artigianodigitale.me@gmail.com
#    oggetto: [CONTRIBUTO 001] due o tre parole
```

**Non serve sapere niente di questo sistema per contribuire.** Non serve conoscere il codice,
non serve un account, non serve aprire una pull request. **Il documento te lo scrive il
sistema**, tu lo riempi, e lo mandi.

### Cosa cerchiamo

**Un problema vero, raccontato bene.** Vale più di cento raccontati male. E ci interessa
soprattutto quando il sistema **ti ha fermato e non avrebbe dovuto**, o **non ti ha fermato
e avrebbe dovuto** — perché quelle sono le due cose che questo motore esiste per fare.

**E ci interessa quando una regola ti ha dato fastidio senza motivo.** Se il cancello ti ha
bloccato su qualcosa che era legittimo, quello è un difetto **del cancello**, non tuo.

### Cosa succede dopo

**Una persona legge il tuo documento.** Non un modulo automatico: una persona. E ti risponde.

**E una cosa la vogliamo dire con precisione, perché è il motivo per cui questo progetto
esiste:** se dal tuo contributo nasce un **controllo** — una cosa che il sistema non ti
lascia più sbagliare — **il tuo nome resta scritto lì**. Nel registro delle cicatrici, con
il numero e la data. È il modo in cui questo sistema ricorda, e non dimentica chi l'ha
aiutato.

### E se invece vuoi LAVORARCI, non solo segnalare

Il documento serve a **raccontare un problema**. Se quello che vuoi è **partecipare a un
progetto aperto**, la strada è un'altra:

1. **Vai sulla pagina**: [community.artigianodigitale.me](https://community.artigianodigitale.me)
2. **Scegli un progetto** fra quelli aperti
3. **Entra da lì** — dentro la pagina di quel progetto trovi Discord, e la stanza di quel progetto

**Si entra dai progetti che si scelgono:** non c'è un invito unico, ogni progetto ha la sua
stanza. *Scegli una cosa, e quella cosa ha un posto dove parlarne.*

### Cosa succede da questa parte

Il documento che hai mandato **non finisce in una casella**. Diventa una ** voce del registro
delle cicatrici** — la scheda che questo sistema tiene per ogni problema che ha incontrato:

```bash
python3 tools/contributo.py importa contributi/CONTRIBUTO-001-*.md
# -> crea errori/ERR-0053-da-contributo.yaml, con dentro il tuo racconto
# -> e con il tuo nome, se l'hai voluto
```

**E il sistema prepara la scheda, ma non la completa.** Due campi restano scritti
`DA COMPLETARE`, e li riempie **una persona**, perché quelle due cose non si possono dedurre
da un racconto:

- **cosa l'ha risolto** — lo sa chi risolve;
- **cosa lo avrebbe preso** — è la domanda che rende utile tutto il resto.

**Quando quella difesa diventa un controllo, la voce si chiude — e il tuo nome resta.**
Nel registro, col numero e la data. È il modo in cui questo sistema ricorda.

### Le tre regole di un buon contributo

1. **Riproducibile.** I passi esatti, e i comandi che hai dato. «Non funziona» non è
   riproducibile; «ho dato questo comando, e ha risposto questo» sì.
2. **Onesto sui limiti.** Se non sei sicuro, dillo. Se non hai provato, dillo. **Non
   dichiarare ciò che non è** è la regola che questo sistema pretende da sé stesso, e la
   pretende da chi lo usa.
3. **Corto.** Cinque risposte, non un romanzo. Se serve un romanzo, il problema è più grande
   e lo scopriremo insieme.

### Il credito

**Ideato e creato da Luca / Artigiano Digitale.**
Costruito **con** il [DeepSeek Harness](https://github.com/deepseek-ai) (DSH, licenza MIT):
il merito di quella parte resta ai suoi autori, ed è scritto nel `NOTICE`.

---

## English

### How to contribute, in four steps

```bash
# 1. The system gives you the document, with the questions inside
python3 tools/contributo.py nuovo

# 2. Answer the 6 questions. You do not need to be tidy: you need to be precise.
#    If a question has no answer for you, write "I don't know".
#    "I don't know" is information. An answer invented to fill the space is not.

# 3. Check that nothing is missing
python3 tools/contributo.py check contributi/CONTRIBUTO-001-*.md

# 4. Send it by email
#    to:      artigianodigitale.me@gmail.com
#    subject: [CONTRIBUTO 001] two or three words
```

**You do not need to know anything about this system to contribute.** You do not need to
read the code, you do not need an account, you do not need to open a pull request. **The
system writes the document**, you fill it in, and you send it.

### What we are looking for

**A real problem, well told.** Worth more than a hundred told badly. And we are especially
interested when the system **stopped you and it should not have** — or **did not stop you
and it should have** — because those are the two things this engine exists to do.

**And we are interested when a rule got in your way for no reason.** If the gate blocked
something legitimate, that is a defect **of the gate**, not of you.

### What happens next

**A person reads your document.** Not an automated form: a person. And they answer you.

**And one thing we want to state precisely, because it is why this project exists:** if your
contribution becomes a **check** — something the system no longer lets anyone get wrong —
**your name stays written there**. In the scar register, with its number and its date. That
is how this system remembers, and it does not forget who helped it.

### And if you want to WORK on it, not just report

The document is for **telling us about a problem**. If what you want is to **take part in an
open project**, the way in is different:

1. **Go to the page**: [community.artigianodigitale.me](https://community.artigianodigitale.me)
2. **Choose a project** among the open ones
3. **Enter from there** — inside that project's page you find Discord, and that project's room

**You enter through the projects you choose:** there is no single invite, every project has its
own room. *Choose a thing, and that thing has a place to talk about it.*

### What happens on our side

The document you sent **does not end up in an inbox**. It becomes an entry in the **scar
register** — the record this system keeps for every problem it has met:

```bash
python3 tools/contributo.py importa contributi/CONTRIBUTO-001-*.md
# -> creates errori/ERR-0053-da-contributo.yaml, with your account inside
# -> and with your name, if you wanted it
```

**And the system prepares the record, but does not complete it.** Two fields stay marked
`DA COMPLETARE` *(to be completed)*, and **a person** fills them, because those two things
cannot be deduced from an account:

- **what fixed it** — the one who fixes it knows;
- **what would have caught it** — the question that makes all the rest useful.

**When that defence becomes a check, the entry is closed — and your name stays.** In the
register, with its number and its date. That is how this system remembers.

### The three rules of a good contribution

1. **Reproducible.** The exact steps, and the commands you ran. "It does not work" is not
   reproducible; "I ran this command and it answered this" is.
2. **Honest about limits.** If you are unsure, say so. If you did not test it, say so.
   **Do not declare what is not** is the rule this system demands of itself, and it demands
   it of whoever uses it.
3. **Short.** Five answers, not a novel. If it needs a novel, the problem is bigger and we
   will find out together.

### Credit

**Conceived and created by Luca / Artigiano Digitale.**
Built **with** the [DeepSeek Harness](https://github.com/deepseek-ai) (DSH, MIT licence):
the credit for that part stays with its authors, and it is written in the `NOTICE` file.

---

## Perché la porta è un documento, e non un modulo

*Why the door is a document, and not a form*

**Perché un problema raccontato bene vale più di cento raccontati male.**

E perché il documento **resta**. Si allega, si cita, e un giorno si può rileggere per capire
se quel problema è stato davvero risolto. Un modulo che sparisce in una coda non lo puoi
rileggere; un file con la data e un numero, sì.

**Because a problem well told is worth more than a hundred told badly.**

And because the document **stays**. You can attach it, cite it, and one day read it again to
see whether that problem was really solved. A form that disappears into a queue cannot be
read again; a file with a date and a number can.
