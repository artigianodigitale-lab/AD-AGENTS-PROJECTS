# Contribuire
**Questo progetto è aperto al mondo, e la porta è un documento che il sistema ti dà.**

*This project is open to the world, and the door is a document the system gives you.*

---

**Una parola che non capisci?** [GLOSSARY.md](GLOSSARY.md) — 25 termini, italiano e inglese, tre righe l'uno.

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

**Ideato e creato da il CEO / Progetto Lambda.**
Costruito **con** il [DeepSeek Harness](https://github.com/deepseek-ai) (DSH, licenza MIT):
il merito di quella parte resta ai suoi autori, ed è scritto nel `NOTICE`.

---
