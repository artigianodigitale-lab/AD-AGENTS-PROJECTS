# Il grafo di AAP — come funziona, esattamente

Sette viste, una per aspetto. **GitHub le disegna da solo.**

Se ne leggi una sola, leggi **la 3** (i dodici passi) e **la 5** (il cancello): sono
le due cose che distinguono questo motore da un insieme di regole scritte.

---

## 1 · La mappa — dove sta cosa

```mermaid
flowchart TB
    subgraph RADICE["la cartella del motore"]
        AG["AGENTS.md<br/>la porta"]
        SEDE["sede.yaml<br/>chi e' il CEO<br/>dove sono i progetti"]
        subgraph CERVELLO[".brain/"]
            COST["COSTITUZIONE.md<br/>le regole"]
            SKILL["9 skill<br/>le procedure"]
            PLUG["plugin<br/>il cancello"]
        end
        TOOLS["tools/<br/>18 comandi"]
        REG["contratti/ + approvazioni/<br/>chi puo' scrivere dove"]
        MEM["DECISIONI/ errori/ drift/ piani/<br/>la memoria"]
        VISTA["orchestrazione/stato.md<br/>la vista, generata"]
    end

    PROG["i PROGETTI<br/>cartelle numerate<br/>anche altrove"]
    IDE["il programma<br/>DSH, Cursor, un'app"]
    CEO(["il CEO<br/>approva"])

    AG -->|"e' un collegamento"| COST
    IDE -->|"legge da solo"| AG
    IDE -->|"monta"| PLUG
    SEDE -->|"dice dove"| PROG
    CEO -->|"marcatore"| REG
    REG --> PLUG
    TOOLS --> REG
    MEM --> VISTA
```

**Tre cose da notare:**

- `AGENTS.md` **è un collegamento** alla costituzione: **una fonte sola**. Se fosse una
  copia, le due divergerebbero in silenzio.
- Il **plugin** è l'unica cosa che non vive nella cartella: vive nel **profilo del
  programma**, e per questo va **installato** (`setup.py`).
- I **progetti possono stare altrove**. Il motore li trova perché `sede.yaml` lo dice.

---

## 2 · L'ingresso — cosa succede quando dici `AGENTS.md`

```mermaid
flowchart TD
    IN(["l'utente collega la cartella<br/>e dice AGENTS.md"]) --> LEGGE["il programma legge AGENTS.md<br/>= la costituzione"]
    LEGGE --> AVVIATO{"esiste sede.yaml?"}

    AVVIATO -->|no| NOME["1. chiede il NOME<br/>diventa il CEO"]
    NOME --> PERM["2. chiede il PERMESSO<br/>di scaricare cio' che serve"]
    PERM --> INST["3. installa e PROVA<br/>una scrittura deve essere RIFIUTATA"]
    INST --> SCRIVE["scrive sede.yaml"]
    AVVIATO -->|si| DICHIARA

    SCRIVE --> DICHIARA
    DICHIARA["DICHIARA:<br/>ho capito come mi comportero'<br/>e da adesso AAP e' il mio comportamento"] --> CHIEDE{"chiede"}

    CHIEDE -->|nuovo| NUOVO["crea una cartella NUMERATA<br/>e dice il nome prima di crearla"]
    CHIEDE -->|esistente| COLLEGA["importa una cartella numerata<br/>e la SPOSTA solo con un si' esplicito"]

    NUOVO --> KICK["ad-kickoff"]
    COLLEGA --> KICK

    classDef no fill:#ffe0e0,stroke:#c00
    classDef si fill:#e0ffe0,stroke:#0a0
    class AVVIATO no
    class CHIEDE si
```

**E cosa NON fa:** non cerca un progetto, non ne apre uno, non comincia a lavorare
«intanto». **Dichiara, chiede, e aspetta.**

---

## 3 · I dodici passi — la sequenza obbligatoria

```mermaid
flowchart TD
    P1["1 RICHIESTA<br/>non e' un ordine: e' una proposta"] --> P2["2 COMPRENSIONE<br/>cosa vuole davvero"]
    P2 --> P3["3 RICERCA<br/>esiste un modo migliore? anche online"]
    P3 --> P4["4 CARD<br/>nessun match, STOP"]
    P4 --> P5["5 RISPOSTA<br/>si risponde PRIMA di fare"]
    P5 --> P6["6 ANALISI DI AVVIO<br/>diventa la MILESTONE"]
    P6 --> P7["7 CONSENSO<br/>il CEO approva la MILESTONE"]
    P7 --> P8["8 PERMESSO<br/>contratto con write_scope"]
    P8 --> P9["9 MILESTONE"]
    P9 --> P10["10 SPRINT<br/>si apre il passo, col suo PROMPT"]
    P10 --> P11["11 ESECUZIONE<br/>un esecutore, evidenze, gate, RAPPORTO"]
    P11 --> P12["12 CHIUSURA<br/>ACCEPT o REJECT, errori, fotografia"]
    P12 -->|"il passo dopo riparte dal 10"| P10

    classDef blu fill:#e0ecff,stroke:#06c
    classDef verde fill:#e0ffe0,stroke:#0a0
    class P7,P8 verde
    class P5 blu
```

**Il passo 7 e l'8 non si invertono**: prima il consenso, poi il permesso. L'8 si scrive
**prima** della tappa, perché il permesso è quello che rende possibile aprirla.

---

## 4 · L'autorizzazione — tre serrature, non una

```mermaid
flowchart LR
    LAV["un lavoro da fare"] --> C{"esiste un CONTRACT<br/>che copre il percorso?"}
    C -->|no| STOP1["BLOCCATO<br/>nessun permesso"]
    C -->|si| A{"esiste il MARCATORE<br/>del CEO?"}
    A -->|no| STOP2["BLOCCATO<br/>senza consenso non si lavora"]
    A -->|si| O{"l'ordine e' giusto?<br/>consenso prima del permesso"}
    O -->|no| STOP3["BLOCCATO<br/>un permesso retrodatato non copre"]
    O -->|si| S{"e' una cartella PRODOTTO?<br/>inizia con un numero"}
    S -->|si, e ha un passo aperto| OK(["si puo' scrivere"])
    S -->|no, e non e' macchina| STOP4["BLOCCATO<br/>i progetti si numerano"]

    classDef stop fill:#ffe0e0,stroke:#c00
    classDef ok fill:#e0ffe0,stroke:#0a0
    class STOP1,STOP2,STOP3,STOP4 stop
    class OK ok
```

**E il rifiuto dice sempre il rimedio**: quale numero usare, quale marcatore manca, quale
file dichiarare. Un divieto senza il rimedio è un vicolo cieco.

---

## 5 · Il cancello — cosa succede a OGNI scrittura

```mermaid
flowchart TD
    W(["il programma vuole<br/>scrivere un file"]) --> GANCIO{"il programma<br/>ha un gancio?"}
    GANCIO -->|no| SOLOREG["riceve le REGOLE<br/>ma nessuno lo ferma<br/>DICHIARATO, non nascosto"]
    GANCIO -->|si| PRE["il plugin intercetta<br/>PRIMA di scrivere"]
    PRE --> DOVE{"dove sta il file?"}

    DOVE -->|"governance: .brain/ e tools/"| GOV["serve un contract<br/>+ il marcatore"]
    DOVE -->|cartella numerata| PROG["serve un contract<br/>+ il passo aperto"]
    DOVE -->|radice| RAD["solo i documenti dichiarati;<br/>un .md nuovo e' quasi sempre un errore"]
    DOVE -->|altrove| LIBERO["passa"]

    GOV --> D{"coperto?"}
    PROG --> D
    RAD --> D
    D -->|no| NEGA["NEGA, e dice cosa manca<br/>e come rimediare"]
    D -->|si| PASSA["lascia scrivere"]

    PASSA --> POST["DOPO la scrittura<br/>la meta' che AVVISA"]
    POST --> POST1["l'ordine firma/permesso e' rotto?"]
    POST --> POST2["un record dichiara un orario futuro?"]
    POST --> POST3["una scrittura in un progetto<br/>senza il passo aperto?"]
```

**Il limite dichiarato, e non nascosto**: il plugin **non disfa** la scrittura — avvisa
dopo. E l'analisi dei comandi shell è un'**euristica**: un comando che cambia cartella con
`cd` e poi scrive in modo relativo può sfuggirgli. Il confine affidabile resta il
`write_scope`.

---

## 6 · Il lavoro dentro un progetto

```mermaid
flowchart LR
    subgraph T["Milestone 3"]
        S1["Sprint 1<br/>PROMPT + REPORT"]
        S2["Sprint 2<br/>PROMPT + REPORT"]
        S3["Sprint 3<br/>PROMPT + REPORT"]
    end
    T --> ANA["Analisi-Prompt-Report/"]
    ANA --> BP["BLUEPRINT.md<br/>meta' a mano, meta' generata<br/>sigillata con un'impronta"]
    ANA --> RAP["il RAPPORTO del passo<br/>6 sezioni, e la sesta<br/>e' cosa passa al prossimo"]

    classDef giallo fill:#fffbe0,stroke:#cc0
    class RAP giallo
```

**Tutto ciò che riguarda un progetto vive nel progetto.** Nella radice del motore resta
solo la macchina: chi autorizza, chi controlla, chi ricorda.

E il rapporto ha **sei sezioni**, di cui la più importante è l'ultima:

> **«Cosa passa allo sprint successivo»** — perché è l'unica che serve all'agente che
> viene dopo. Un rapporto senza quella è un diario, non un passaggio di consegne.

---

## 7 · Cosa succede a un errore

```mermaid
flowchart LR
    E["succede un errore"] --> REG["si registra in errori/<br/>cosa e' fallito, cosa l'ha risolto,<br/>e COSA LO AVREBBE PRESO"]
    REG --> MEC{"si puo' meccanizzare?"}
    MEC -->|si| CHECK["diventa un CONTROLLO<br/>e da quel momento<br/>e' IMPOSSIBILE, non sconsigliato"]
    MEC -->|no| NOTA["resta una NOTA<br/>o un verbale"]

    CHECK --> VIVO["il file non serve piu':<br/>serve il controllo, che FALLISCE"]
    NOTA --> VIVO2["la cicatrice resta,<br/>e il sistema la cita"]

    classDef ok fill:#e0ffe0,stroke:#0a0
    class CHECK,VIVO ok
```

**Senza la terza domanda non è apprendimento** — è solo cronaca. E il registro delle
cicatrici è **curato, non completo**: contiene quelle che il sistema cita ancora, e lo
dichiara. Un registro che si dice completo quando non lo è è peggio di uno piccolo.

---

## I numeri, al 2026-10-13

| | |
|---|---|
| Comandi deterministici | **18** |
| Skill | **9** |
| Passi della sequenza | **12** |
| Controlli della suite | **458** |
| Controlli del plugin | **36** |
| Errori che un cancello puo' fermare | **4 punti** |
| Verdetti di una fotografia | **6** |

## Le tre cose che rendono questo motore diverso da un regolamento

1. **Le regole viaggiano, il cancello si installa.** Colleghi la cartella e hai le regole.
   Perché qualcuno ti **fermi** serve un gancio — e dove non c'è, si **dice** che non c'è.
2. **Ogni divieto dice il rimedio.** Un numero da usare, un marcatore da scrivere, un
   campo da aggiungere.
3. **Un errore diventa un controllo.** Una regola scritta non cambia il comportamento: un
   controllo che fallisce sì. Per questo il registro delle cicatrici è **corto**: il resto
   è diventato codice che si rompe se qualcuno sbaglia.
