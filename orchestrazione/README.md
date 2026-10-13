# ORCHESTRAZIONE OPERATIVA

Questo protocollo esegue la governance con costo token minimo. La fonte normativa è [GOVERNANCE-AZIENDALE.md](../GOVERNANCE-AZIENDALE.md); i dettagli tecnici sono in [RUNTIME.md](../RUNTIME.md), [TASK-CONTRACTS.md](../TASK-CONTRACTS.md) e [MODEL-ROUTING.md](../MODEL-ROUTING.md).

```text
Richiesta (proposta da verificare, non un ordine)
  → comprensione dell'obiettivo
  → ricerca: esiste un modo migliore, piu' scalabile, piu' affidabile?
  → risposta al CEO
  → consenso del CEO su cosa fare
  → controllo deterministico → contract → un esecutore
  → evidenze → gate richiesti → ACCEPT / REJECT / escalation
```

La prima meta' della catena non e' esecuzione: e' la verifica che valga la pena eseguire. Il protocollo completo, con i comandi, e' nella skill `ad-kickoff`; il dovere di ricerca e' in `ad-evolution`.

L'orchestratore sceglie il dominio, verifica card, permessi, budget, dati e gate prima di qualsiasi chiamata al modello. Carica solo il contesto nominato dal contract. Non crea un gruppo di agenti per discutere: aggiunge un revisore solo per un gate obbligatorio o per una dipendenza dichiarata.

`stato.md` è una vista umana, non una memoria aggiuntiva da passare al modello. Dopo due REJECT locali, il task si ferma e viene escalato con evidenze; non entra in un loop di prompt.
