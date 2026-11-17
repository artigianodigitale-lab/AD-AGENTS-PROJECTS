# MODEL ROUTING — costo minimo, qualità sufficiente

Questo documento traduce la governance in un sistema locale-first. Non è un'autorizzazione tecnica aggiuntiva: permessi e approvazioni restano quelli della card e del contract.

## Regola principale

Un task usa un solo esecutore. Il sistema non apre una discussione tra molte card: l'orchestratore seleziona la card pertinente, esegue controlli deterministici, avvia l'istanza e richiede un revisore solo quando il contract lo impone.

## Fasce di esecuzione

1. **Deterministica, zero token:** validazione di contract e schema, permessi, soglie, test, lint, typecheck, scan, confronto di checklist e Quality Gate.
2. **Locale leggero:** classificazione, estrazione, bozze, documentazione e modifiche piccole. Deve usare output strutturato e contesto ristretto.
3. **Locale medio:** coding, revisione e analisi con tool calling, soltanto per task che lo richiedono.
4. **Modello premium:** esclusivamente per escalation, architettura critica, sicurezza complessa o quando due tentativi locali non superano i criteri. Il contract ne esplicita budget e ragione.

## Budget e contesto

- Caricare card, contract, file direttamente necessari e al massimo cinque fonti formative pertinenti.
- Non caricare chat history, copie di prompt, card altrui o l'intera biblioteca strategica.
- Riutilizzare test, evidenze, digest e retrieval cache; non rispiegare lo stesso contesto ad ogni passo.
- Massimo due tentativi locali. Dopo il secondo REJECT: evidenza del blocco ed escalation, non loop.
- Il modello produce artefatti e prove, non lunghi resoconti del ragionamento.

## Implementazione attuale

Le superfici di lavoro sono **cinque**, decise dal CEO (`DEC-0057`), e leggono le stesse fonti
normative dalla root di `AD Projects`:

- **DeepSeek Harness** (GUI e CLI) — **la superficie operativa**. Il cervello è in `.brain/`, symlinkato da `$DSH_HOME/AGENTS.md` e da `~/.agents/skills/ad-*`: la costituzione entra in **ogni** sessione qualunque sia il workspace, e le skill sono nel catalogo di ogni sessione.
- **Cursor** (IDE), **Claude Code**, **Codex**, **Gemini CLI** — **superfici di esecuzione** (elenco chiuso, `DEC-0057`). Il CEO ha deciso che **Cursor è sempre esecuzione**: la regola dell'enforcement si applica di conseguenza, non si sospende perché lo strumento è un IDE.
- **Il confine non vive in un singolo client.** `.brain/plugin/enforce-contract` è **un adattatore fra N**, non *il* cancello: la regola viaggia con lo strumento (il server MCP di AD, che i client possono chiamare) e la prova viaggia con l'evidenza. Un cancello costruito *dentro* un IDE di terzi resta escluso — la critica di `DEC-0039` vale per quello, non per un confine che viaggia.

**Limite dichiarato.** Le scritture fatte **fuori dai tool** (terminale dell'utente, DSH stesso, un client non coperto) non sono impedite: sono **rilevate** dal confronto con l'albero sigillato e dalle evidenze. Un limite dichiarato è una scelta; un limite nascosto sarebbe un inganno (`DEC-0057`).

Il layer sempre attivo resta **minimo** e non duplica la catena documentale: contiene solo gli invarianti di `GOVERNANCE-AZIENDALE.md` e i puntatori a `AGENT-CARDS-V2.md`, `AGENT-CARDS-BUSINESS.md`, `TASK-CONTRACTS.md`, `RUNTIME.md` e `QUALITY-GATES.md`. Card, check-list dei gate, `strategic_memory/` e memoria di prodotto si caricano a chiamata, come richiesto dalla sezione Budget e contesto. Un layer che inietta il corpus intero viola questa specifica e non va adottato.

La fascia 1 è implementata come codice e non consuma token. Il workflow mantiene stati, contratti, evidenze e approvazioni; una macchina a stati esplicita (o LangGraph) serve quando serviranno persistenza e pause umane. Ollama copre le fasce 2 e 3; la scelta del modello dipende dall'hardware e viene verificata su una suite di task prima dell'adozione.

## Il costo del prefisso, e perché `AGENTS.md` non si tocca per poco

`AGENTS.md` (cioè `.brain/COSTITUZIONE.md`) e le skill sono il **prefisso stabile**: il testo che ogni sessione legge prima di dire una parola. Misurato il 2026-11-06: **30 KB, circa 7.761 token** per la costituzione, **89 KB** con le dieci skill.

Il numero conta perché i provider fatturano i token di prefisso **una volta sola** finché il prefisso non cambia. Uno studio su 500 sessioni di agenti ([Don't Break the Cache, PwC](https://arxiv.org/html/2601.06007)) misura:

- **costo**: −41% a −81% con la cache dei prompt, e il risparmio cresce **linearmente** con la dimensione del prefisso (a 50.000 token: −89%);
- **latenza**: −6% a −31% al primo token, ma il *full context caching* può **peggiorare** la latenza (+8,8% su un modello), perché cacha contenuto dinamico che non verrà riusato;
- la strategia più coerente è **cachare solo il sistema stabile**, non la conversazione.

Da qui tre regole, e non sono consigli di stile:

1. **`AGENTS.md` non si modifica per una correzione piccola.** Ogni modifica invalida la cache per **tutte** le sessioni successive: costa 7.761 token a testa, non a te. Il 2026-11-02 l'ho riscritto tre volte in un giorno, pagandolo ogni volta.
2. **Il testo dinamico va in fondo.** Una data o un identificativo di sessione *in testa* rompe il prefisso; lo stesso testo *in fondo* lo lascia intatto. La differenza è dove sta, non cosa è.
3. **Le skill non si caricano tutte.** Restano a chiamata, come dice la specifica qui sopra: sommarle al layer sempre attivo lo porta a 89 KB, cioè a pagare migliaia di token prima di leggere la domanda.

`tools/prefisso.py` misura le prime due: fallisce oltre 48 KB per la costituzione o 100 KB complessivi, e se trova testo dinamico nelle prime 400 righe. È in `tests/ci.py`, quindi la guardia è meccanica — non una raccomandazione. La terza la controlla la stessa soglia sul totale.

