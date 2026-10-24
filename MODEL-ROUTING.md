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

Le superfici di lavoro sono due, e leggono le stesse fonti normative dalla root di `AD Projects`:

- **DeepSeek Harness** (GUI e CLI) — **la superficie operativa**. Il cervello è in `.brain/`, symlinkato da `$DSH_HOME/AGENTS.md` e da `~/.agents/skills/ad-*`: la costituzione entra in **ogni** sessione qualunque sia il workspace, e le skill sono nel catalogo di ogni sessione.
- **Cursor** (IDE) — **strumento di lettura del CEO**, non superficie di esecuzione. Si usa per **analisi comparativa**, e **non** per lavorare ai progetti. **Non ha un cancello, e non deve averlo**: lo lancial CEO, e un controllo che difende il sistema dal suo proprietario non è un controllo. Chi legge questo documento sappia che **l'enforcement vale su DSH**, e che una scrittura fatta da Cursor non passa dal plugin — è una scelta dichiarata, non una dimenticanza (DEC-0039).

Il layer sempre attivo resta **minimo** e non duplica la catena documentale: contiene solo gli invarianti di `GOVERNANCE-AZIENDALE.md` e i puntatori a `AGENT-CARDS-V2.md`, `AGENT-CARDS-BUSINESS.md`, `TASK-CONTRACTS.md`, `RUNTIME.md` e `QUALITY-GATES.md`. Card, check-list dei gate, `strategic_memory/` e memoria di prodotto si caricano a chiamata, come richiesto dalla sezione Budget e contesto. Un layer che inietta il corpus intero viola questa specifica e non va adottato.

La fascia 1 è implementata come codice e non consuma token. Il workflow mantiene stati, contratti, evidenze e approvazioni; una macchina a stati esplicita (o LangGraph) serve quando serviranno persistenza e pause umane. Ollama copre le fasce 2 e 3; la scelta del modello dipende dall'hardware e viene verificata su una suite di task prima dell'adozione.
