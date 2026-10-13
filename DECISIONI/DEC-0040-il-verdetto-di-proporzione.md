# DEC-0040 — Il verdetto di proporzione

```yaml
id: DEC-0040
stato: approvato
livello: 2
data: 2026-10-11
approver: CEO
supera:
```

## Problema

Il 2026-10-10, per **una riga** di `.gitignore` su un progetto — che non era nemmeno un repository
Git — il sistema ha chiesto: un permesso, un marcatore, una milestone aperta, un passo aperto, un
rapporto del passo. **Sei file e otto passaggi.**

Il CEO ha detto la cosa che conta:

> *«la priorità non sono i progetti [...] la priorità è essere lineari e funzionali per lavorare»*

**Il sistema sa dire «per questo serve una tappa». Non sa dire «per questo non serve».** E la
differenza è tutta lì: un sistema che tratta allo stesso modo una riga di `.gitignore` e un
refactor **insegna a bypassarlo** — e un bypass rende inutile qualunque cancello, compreso quello
che stiamo costruendo.

## Opzioni

1. **Non fare nulla** — il sistema continua a chiedere la catena piena per qualunque scrittura in
   un progetto. Conseguenza: il costo per una modifica minima resta **6 file**. Il danno non è il
   tempo: è che **la regola giusta diventa una regola che si aggira**, e chi la aggira smette di
   fidarsi anche di quella che serve.
2. **Cambiare l'invariante 13**: esentare le modifiche minime dalla milestone. Conseguenza: la
   catena si accorcia. Costo: si tocca un invariante che il CEO ha scelto di proposito, e il confine
   «minimo» diventa una cosa da interpretare ogni volta. Fonte: il caso di ieri **non è un
   invariante sbagliato** — è un invariante applicato a una cosa che non è un lavoro di prodotto.
3. **Il verdetto di proporzione**: il sistema **misura** cosa sta per cambiare e **lo dice**, con i
   numeri, senza esentare niente. La decisione resta del CEO, ma arriva **informata**. Fonte:
   [Graphify, `BENCHMARKS.md` e `GRAPH_REPORT.md`](https://github.com/Graphify-Labs/graphify) — il
   suo report comincia con un **verdetto di utilità**: *«corpus is large enough that graph
   structure adds value»*. Uno strumento che dice quando **non** vale la pena usarlo.

## Evidenze

- Il caso vero: `contratti/10-web-chiara-boggetti/CBG-001.yaml` — **una riga**, e la catena ha
  prodotto 6 file, di cui **4 dentro il progetto del cliente**
- La scoperta misurando: il permesso **deve** includere `Analisi-Prompt-Report/` per soddisfare
  l'invariante 13. Quindi, se il verdetto contasse quella cartella come «cosa tocca», direbbe
  **sempre** `piena` e **non direbbe mai niente**. Il verdetto misura **la modifica**, non il
  permesso: la cartella delle tappe è **cerimonia**, e viene dichiarata come tale
- `classe_della_scrittura()` distingue `igiene` da `piena` con criteri **misurabili**: percorsi
  dentro il progetto esclusa la cerimonia, lista dichiarata di file di igiene, soglia di 5 percorsi
- Sul contract di ieri il verdetto dice, **con i numeri**:
  > *«tocca solo igiene (`.gitignore`): 1 percorso, nessun file di prodotto. La catena completa
  > chiede 4 documenti dentro il progetto. È sproporzionata»*
- E il cancello lo dice **dove il dolore si sente** — quando nega un percorso:
  > *«`11. Modelbel/.gitignore` è igiene del repository, non prodotto [...] la catena completa
  > chiede 4 documenti DENTRO il progetto [...] è sproporzionata — e se il consenso debba stare
  > sulla tappa o sul permesso è una decisione del CEO»*

## Scelta

**Opzione 3.** Il verdetto **misura e consiglia**. **Nessuna esenzione, nessun invariante
cambiato.**

- `ad_contract.classe_della_scrittura()` — il verdetto, con la ragione e il costo
- `ad_contract`: **WARNING `catena-sproporzionata`** sul contract, quando la classe è `igiene`
- `ad_scope`: il cancello lo dice nel messaggio con cui nega un percorso
- La classe `piena` resta il default: **si deve guadagnare** quella `igiene`, e i criteri sono
  stretti

**Quello che il verdetto NON fa**: non toglie un obbligo, non salta un gate, non autorizza niente.
Dice una cosa che oggi nessuno diceva: **quanto costa, in proporzione a cosa cambia.**

## Conseguenze

- Il sistema ora **dice** quando la catena è sproporzionata, **con i numeri** — e la domanda
  «il consenso deve stare sulla tappa o sul permesso?» arriva al CEO **insieme** al costo, non dopo
- **L'invariante 13 resta intatto.** Nessuna scrittura è esentata: cambia solo che adesso il costo
  si vede prima di pagarlo
- `violazioni: 0`, `avvisi: 4` sul contract di ieri — **nessuna violazione**: il verdetto non
  accusa, informa
- Test: **da 254 a 263 controlli** (le prove del verdetto e delle istruzioni mascherate)

## Limiti dichiarati

- **Il verdetto non ha ancora una conseguenza operativa.** Dice «è sproporzionata» e poi la catena
  si fa lo stesso. **È deliberato** — la conseguenza è una decisione del CEO sull'invariante 13, e
  non me la prendo io. Ma va detto: **oggi il verdetto informa e non cambia niente.**
- **La lista dei file di igiene è mia**, ed è incompleta: `.gitignore`, `.gitattributes`,
  `.editorconfig`, licenze, `SECURITY.md`, `CONTRIBUTING.md`. Un file di igiene che non ho
  elencato fa dire `piena` — **falso negativo, non falso positivo**: sbaglia dalla parte sicura
- **La soglia di 5 percorsi è arbitraria**, come il `K=5` del blueprint. Non l'ho misurata
- **Il verdetto guarda i percorsi, non il contenuto.** Un `.gitignore` che cancella tutto non è
  distinguibile da uno che aggiunge una riga: il contenuto del permesso non lo dice

## Metrica

Scritture di sola igiene riconosciute come tali: **1** (il contract di ieri). Documenti risparmiati
finora: **zero** — il verdetto non esenta. La metrica vera è la prossima decisione del CEO: se
l'invariante 13 resta com'è, questa metrica resta a zero e il verdetto resta un'informazione.

## Data di revisione

2026-11-09

## Esito misurato

<Da compilare il 2026-11-09: quante volte il verdetto ha detto `igiene`, e se in quei casi il CEO
ha scelto la catena piena o ha chiesto di cambiare l'invariante 13.>
