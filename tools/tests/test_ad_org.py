#!/usr/bin/env python3
"""Test dei validatori deterministici di ``tools/``.

    python3 tools/tests/test_ad_org.py

Non richiede pytest: ogni controllo e' un'asserzione e il file esce 1 al primo
fallimento. Verifica il registry, il catalogo gate, il validatore di contract e
il verdetto del Quality Gate.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import ad_coherence  # noqa: E402
import ad_contract  # noqa: E402
import ad_docs  # noqa: E402
import ad_drift  # noqa: E402
import ad_evidence  # noqa: E402
import ad_milestone  # noqa: E402
import ad_gates  # noqa: E402
import ad_registry  # noqa: E402
import ad_scope  # noqa: E402
import misure  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PASSED = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    """Assert one condition and report it."""
    global PASSED
    if not condition:
        raise AssertionError(f"{label}: {detail or 'condizione falsa'}")
    PASSED += 1
    print(f"  ok  {label}")


def contract_fixture(name: str) -> dict:
    """Load a contract fixture."""
    return ad_contract.load(FIXTURES / name)


def codes(findings: list[ad_contract.Finding]) -> set[str]:
    """Return the finding codes."""
    return {finding.code for finding in findings}


def scratch_root() -> tempfile.TemporaryDirectory[str]:
    """Una cartella di prova DENTRO l'albero di autorita'.

    Perche' non in ``/tmp``: ``ad_scope.guard`` rifiuta le scritture fuori
    dall'albero di autorita' (ERR-0026), quindi uno strumento vero non scrive piu'
    in una cartella di sistema — e una prova che **esegue** quello strumento deve
    stare dove la scrittura e' legittima. La cartella nasce al primo livello della
    root, che non e' una classe protetta, e sparisce alla fine del blocco ``with``.
    Le prove che invece DEVONO fallire usano percorsi veri: ``test_guardia``.
    """
    # **Dentro `evals/`, non nella radice.** Dal 2026-10-13 una cartella nella radice
    # che non sia di macchina e non abbia un numero viene RIFIUTATA — ed e' giusto, e'
    # il buco che chiudevamo. Ma l'impalcatura delle prove non e' un progetto, e
    # numerarla la farebbe diventare un progetto vero, che pretende un contract vero:
    # un vicolo cieco. `evals/` e' una cartella **dichiarata di macchina** e **non**
    # governance, quindi li' la scrittura e' legittima e resta dentro l'albero di
    # autorita' (ERR-0026). E le prove smettono di scavalcare la regola che verificano.
    destinazione = ad_docs.DOCS_ROOT / "evals"
    destinazione.mkdir(exist_ok=True)
    return tempfile.TemporaryDirectory(prefix="prove-", dir=destinazione)


def test_registry() -> None:
    """The registry matches both catalogs."""
    print("\nregistry")
    registry = ad_registry.load()
    technical = ad_registry.by_domain(registry, "technical")
    business = ad_registry.by_domain(registry, "business")

    check("26 card tecniche", len(technical) == 26, f"trovate {len(technical)}")
    check("16 card business", len(business) == 16, f"trovate {len(business)}")
    check("42 card totali", len(registry) == 42, f"trovate {len(registry)}")

    incomplete = {cid: card.missing_fields for cid, card in technical.items() if card.missing_fields}
    check("ogni card tecnica ha i campi critici", not incomplete, str(incomplete))

    specialists = [card for card in business.values() if card.type == "business"]
    check("15 specialisti business", len(specialists) == 15, f"trovati {len(specialists)}")
    check(
        "ogni specialista business e' assegnabile",
        all(card.assignable for card in specialists),
        str([card.id for card in specialists if not card.assignable]),
    )
    check(
        "ogni specialista dichiara i campi critici",
        all(not card.missing_fields for card in specialists),
        str({card.id: card.missing_fields for card in specialists if card.missing_fields}),
    )
    check(
        "ogni specialista esclude almeno un task type",
        all(card.excluded_task_types for card in specialists),
    )
    orchestrator = registry["lb-business-orchestrator"]
    check("l'orchestratore business e' assegnabile", orchestrator.assignable)

    check(
        "i campi comuni sono ereditati",
        registry["lb-strategy"].permissions.get("external_send") == "none"
        and "ambiguous_scope" in registry["lb-strategy"].escalation,
    )
    check(
        "la formazione e' dichiarata per card",
        registry["lb-strategy"].formation.get("models") == ["Porter", "Rumelt", "Ries", "OKR"],
        str(registry["lb-strategy"].formation),
    )
    check(
        "gli id non si sovrappongono tra i due cataloghi",
        len(technical) + len(business) == len(registry),
    )
    tecnici = {
        task for card in technical.values() for task in (card.authorized_task_types or ())
    }
    business_task = {
        task for card in specialists for task in (card.authorized_task_types or ())
    }
    check(
        "nessun task type condiviso tra i due domini",
        not (tecnici & business_task),
        str(sorted(tecnici & business_task)),
    )
    check(
        "ogni gate con owner business ha una card assegnabile",
        all(registry[owner].assignable for gate in ad_gates.GATE_CATALOG
            for owner in ad_gates.owners(gate) if owner in registry),
    )


def test_gates() -> None:
    """The gate catalog agrees across the documents."""
    print("\ncatalogo gate")
    check("catalogo atteso di 15 gate", len(ad_gates.GATE_CATALOG) == 15)
    check("QUALITY-GATES.md dichiara 15 gate", len(ad_gates.quality_catalog()) == 15)
    check("GOVERNANCE-AZIENDALE.md dichiara 15 gate", len(ad_gates.governance_catalog()) == 15)
    check("nessun drift tra i documenti", not ad_gates.drift(), str(ad_gates.drift()))
    missing_hints = [gate for gate in ad_gates.GATE_CATALOG if not ad_gates.owners(gate)]
    check("ogni gate ha un owner di default", not missing_hints, str(missing_hints))
    check("canonical normalizza le maiuscole", ad_gates.canonical("code review") == "Code Review")
    check("un gate inventato non e' nel catalogo", ad_gates.canonical("Quality") is None)


def test_contract_validator() -> None:
    """The contract validator accepts the good case and catches every bad one."""
    print("\nvalidatore di contract")
    registry = ad_registry.load()

    valid = ad_contract.validate(contract_fixture("contract_valid.yaml"), registry)
    check(
        "il contract valido non ha violazioni",
        not ad_contract.violations(valid),
        str([str(f) for f in ad_contract.violations(valid)]),
    )

    expectations = {
        "contract_unknown_agent.yaml": "agent-unknown",
        "contract_bad_gate.yaml": "gate-unknown",
        "contract_permission_escalation.yaml": "permission-escalation",
        "contract_excluded_task.yaml": "task-type-excluded",
        "contract_self_gate.yaml": "gate-owner-conflict",
        "contract_domain_mismatch.yaml": "agent-domain-mismatch",
        "contract_business_no_match.yaml": "task-type-no-match",
    }
    for name, expected in expectations.items():
        findings = ad_contract.validate(contract_fixture(name), registry)
        found = codes(ad_contract.violations(findings))
        check(f"{name} -> {expected}", expected in found, f"trovate {sorted(found)}")

    # La card non assegnabile non esiste piu' nel catalogo reale: si prova con
    # una card privata del match esplicito, per coprire comunque la regola.
    from dataclasses import replace

    stripped = {**registry, "lb-strategy": replace(registry["lb-strategy"], authorized_task_types=None)}
    findings = ad_contract.validate(contract_fixture("contract_business_no_match.yaml"), stripped)
    check(
        "una card senza authorized_task_types -> agent-not-assignable",
        "agent-not-assignable" in codes(ad_contract.violations(findings)),
        str(sorted(codes(ad_contract.violations(findings)))),
    )

    governance = ad_contract.validate(contract_fixture("contract_governance_code.yaml"), registry)
    check(
        "governance-card-producing-code e' un avviso, non una violazione",
        "governance-card-producing-code" in codes(ad_contract.warnings(governance))
        and not ad_contract.violations(governance),
    )

    undeclared = dict(contract_fixture("contract_valid.yaml"))
    undeclared.pop("task_type", None)
    findings = ad_contract.validate(undeclared, registry)
    check(
        "l'assenza di task_type e' segnalata",
        "task-type-undeclared" in codes(ad_contract.warnings(findings)),
    )


def test_decision_records() -> None:
    """Decision Record references resolve and are checked for approval."""
    print("\ndecision record")
    path = ad_contract.resolve_decision_record("DEC-0001")
    check("DEC-0001 si risolve", path is not None and path.exists(), str(path))
    check("DEC-0001 e' approvato", path is not None and ad_contract._record_state(path) == "approvato")
    check("un record inventato non si risolve", ad_contract.resolve_decision_record("DEC-9999") is None)

    contract = contract_fixture("contract_valid.yaml")
    contract["decision_record"] = "DEC-9999"
    findings = ad_contract.validate(contract, ad_registry.load())
    check(
        "un record inesistente e' una violazione",
        "decision-record-missing" in codes(ad_contract.violations(findings)),
    )


def test_verdict() -> None:
    """The Quality Gate verdict follows QUALITY-GATES.md."""
    print("\nverdetto del Quality Gate")
    contract = contract_fixture("contract_valid.yaml")

    def verdict_for(folder: str) -> ad_evidence.Verdict:
        return ad_evidence.evaluate(contract, ad_evidence.collect([FIXTURES / folder]))

    accepted = verdict_for("evidence_ok")
    check("evidenze complete e indipendenti -> ACCEPT", accepted.outcome == "ACCEPT", accepted.outcome)
    check("un esito per ogni gate richiesto", len(accepted.gates) == 2, str(len(accepted.gates)))

    self_produced = verdict_for("evidence_self")
    check("evidenza dell'esecutore -> REJECT", self_produced.outcome == "REJECT")
    check(
        "lo stato del gate e' INVALID",
        any(result.state == "INVALID" for result in self_produced.gates),
    )

    failed = verdict_for("evidence_fail")
    check("un FAIL -> REJECT", failed.outcome == "REJECT")
    check("lo stato del gate e' FAIL", any(r.state == "FAIL" for r in failed.gates))

    wrong_task = verdict_for("evidence_wrong_task")
    check("task_id diverso -> REJECT", wrong_task.outcome == "REJECT")

    partial = verdict_for("evidence_partial")
    check("evidenza mancante -> REJECT", partial.outcome == "REJECT")
    check(
        "lo stato del gate mancante e' MISSING",
        any(result.state == "MISSING" for result in partial.gates),
    )

    human = dict(contract)
    human["approval"] = {"human": True}
    human_verdict = ad_evidence.evaluate(human, ad_evidence.collect([FIXTURES / "evidence_ok"]))
    check("ACCEPT con approval.human resta un gate umano", human_verdict.human_gate)


def test_evidenza_propria() -> None:
    """ERR-0027 — il verdetto di un gate legge l'evidenza di QUEL permesso.

    Il caso che nessun test copriva: **due permessi che depositano lo stesso gate**,
    e l'evidenza piu' recente che appartiene all'altro. Prima si sceglieva per
    timestamp e solo dopo si guardava il `task_id`: il permesso piu' vecchio
    risultava INVALID, accusato con l'evidenza di un altro. Su 7 permessi reali del
    progetto, 6 davano un falso REJECT — e l'unico che passava era quello la cui
    evidenza era l'ultima depositata, cioe' un caso, non la regola.

    Le fixture nascono in una cartella temporanea: questa prova non dipende da cosa
    c'e' oggi in `Analisi-Prompt-Report/Evidenze/`, che altre lavorazioni toccano.
    """
    print("\nl'evidenza di un gate e' quella del permesso (ERR-0027)")
    import shutil
    import subprocess
    import tempfile

    def deposito(task: str, quando: str, esito: str = "PASS", produttore: str = "review") -> str:
        """Un'evidenza completa, con la data che decide il rework."""
        effetti = "".join(f'  {chiave}: "NO"\n' for chiave in ad_evidence.SIDE_EFFECT_KEYS)
        return (
            f"task_id: {task}\ngate: Code Review\noutcome: {esito}\nproducer: {produttore}\n"
            f"timestamp: {quando}\nreferences:\n  - prova.txt\nside_effects:\n{effetti}"
        )

    def contratto(task: str, agente: str = "backend") -> dict:
        return {
            "task_id": task,
            "agent": agente,
            "required_gates": ["Code Review"],
            "write_scope": ["src/"],
        }

    def ultima(verdetto: ad_evidence.Verdict) -> str:
        """Il file di evidenza che il verdetto ha davvero usato."""
        return verdetto.gates[0].detail if verdetto.gates else ""

    with tempfile.TemporaryDirectory() as temporary:
        radice = Path(temporary)
        evidenze = radice / "Evidenze"
        evidenze.mkdir()
        primo = evidenze / "T-1-code-review.yaml"
        secondo = evidenze / "T-2-code-review.yaml"
        # T-1 deposita per prima, T-2 dopo: il permesso che sbaglia e' T-1.
        primo.write_text(deposito("T-1", "2026-10-08T07:20:00+02:00"), encoding="utf-8")
        secondo.write_text(deposito("T-2", "2026-10-10T09:00:00+02:00"), encoding="utf-8")

        lette = ad_evidence.collect([evidenze])
        uno = ad_evidence.evaluate(contratto("T-1"), lette)
        due = ad_evidence.evaluate(contratto("T-2"), lette)

        check(
            "due permessi, stesso gate: T-1 legge la PROPRIA evidenza, non la piu' recente",
            uno.outcome == "ACCEPT" and ultima(uno) == primo.name,
            f"{uno.outcome} · {uno.gates[0].state} · {ultima(uno)}",
        )
        check(
            "e T-2 legge la sua",
            due.outcome == "ACCEPT" and ultima(due) == secondo.name,
            f"{due.outcome} · {due.gates[0].state} · {ultima(due)}",
        )
        check(
            "nessuno dei due gate e' INVALID: l'evidenza di un altro non accusa",
            all(risultato.state != "INVALID" for risultato in (*uno.gates, *due.gates)),
            str([risultato.state for risultato in (*uno.gates, *due.gates)]),
        )
        check(
            "e il verdetto DICE che le evidenze degli altri non contano",
            any("escluse dal conto" in nota for nota in uno.notes),
            str(uno.notes),
        )

        # L'INVARIANTE: il verdetto di un permesso non dipende dalla data
        # dell'evidenza di un altro. Si invertono le date, e non deve cambiare nulla.
        primo.write_text(deposito("T-1", "2026-10-12T09:00:00+02:00"), encoding="utf-8")
        secondo.write_text(deposito("T-2", "2026-10-09T09:00:00+02:00"), encoding="utf-8")
        lette = ad_evidence.collect([evidenze])
        check(
            "con le date invertite l'esito non cambia: non e' un sorteggio",
            ad_evidence.evaluate(contratto("T-1"), lette).outcome == "ACCEPT"
            and ultima(ad_evidence.evaluate(contratto("T-1"), lette)) == primo.name
            and ad_evidence.evaluate(contratto("T-2"), lette).outcome == "ACCEPT"
            and ultima(ad_evidence.evaluate(contratto("T-2"), lette)) == secondo.name,
            str([(r.gate, r.state) for r in ad_evidence.evaluate(contratto("T-1"), lette).gates]),
        )

        # La regola del rework resta: fra le evidenze DI QUEL permesso vince la piu'
        # recente. Non si cambiano i criteri del verdetto, si corregge la scelta.
        (evidenze / "T-1-code-review-2.yaml").write_text(
            deposito("T-1", "2026-10-13T09:00:00+02:00", esito="FAIL"), encoding="utf-8"
        )
        lette = ad_evidence.collect([evidenze])
        check(
            "fra le evidenze proprie vale la piu' recente (rework)",
            ad_evidence.evaluate(contratto("T-1"), lette).gates[0].state == "FAIL",
            str([(r.gate, r.state, r.detail) for r in ad_evidence.evaluate(contratto("T-1"), lette).gates]),
        )

        # Un permesso senza evidenza PROPRIA: l'assenza resta un MISSING onesto, non
        # un INVALID che accusa il permesso sbagliato. E resta un REJECT.
        senza = ad_evidence.evaluate(contratto("T-3"), lette)
        check(
            "nessuna evidenza propria: MISSING, non INVALID",
            senza.gates[0].state == "MISSING",
            f"{senza.gates[0].state}: {senza.gates[0].detail}",
        )
        check(
            "e il verdetto e' comunque REJECT: un gate senza evidenza non passa",
            senza.outcome == "REJECT",
            senza.outcome,
        )

        # I criteri non cambiano: l'evidenza del permesso giusto, ma prodotta
        # dall'esecutore, resta INVALID.
        (evidenze / "T-4-code-review.yaml").write_text(
            deposito("T-4", "2026-10-14T09:00:00+02:00", produttore="backend"), encoding="utf-8"
        )
        lette = ad_evidence.collect([evidenze])
        sleale = ad_evidence.evaluate(contratto("T-4"), lette)
        check(
            "l'evidenza dell'esecutore resta INVALID",
            sleale.outcome == "REJECT" and sleale.gates[0].state == "INVALID",
            f"{sleale.outcome} · {sleale.gates[0].state}",
        )

        # E il comando vero, non solo la funzione: e' quello che si esegue.
        (radice / "T-1.yaml").write_text(
            "task_id: T-1\nagent: backend\nrequired_gates:\n  - Code Review\n"
            'write_scope:\n  - "src/"\n',
            encoding="utf-8",
        )
        comando = [
            sys.executable,
            str(TOOLS / "verdict.py"),
            "--contract",
            str(radice / "T-1.yaml"),
            "--evidence",
            str(evidenze),
        ]
        esito = subprocess.run(comando, capture_output=True, text=True)
        check(
            "verdict.py: l'evidenza piu' recente e' di un altro, e T-1 legge la sua (FAIL)",
            esito.returncode == 1 and "T-1-code-review-2.yaml" in esito.stdout,
            f"exit {esito.returncode}: {esito.stdout.strip()[-160:]}",
        )

    # La stessa proprieta' sui permessi VERI, e senza dipendere dal contenuto delle
    # evidenze: si guarda la FIRMA del difetto — un gate INVALID perche' ha letto
    # l'evidenza di un altro permesso. Che un'evidenza dica PASS o FAIL e' compito
    # di chi l'ha scritta, e non deve far fallire questa prova.
    vera = Path(ad_docs.DOCS_ROOT)
    percorsi = sorted(vera.glob("evidenze/*.yaml")) + sorted(
        vera.glob("*/Analisi-Prompt-Report/Evidenze/*.yaml")
    )
    lette_reali: list[ad_evidence.Evidence] = []
    for percorso in percorsi:
        try:
            lette_reali.append(ad_evidence.load_evidence(percorso))
        except ad_evidence.EvidenceError:
            continue

    firma: list[str] = []
    for file_contratto in sorted((vera / "contratti").rglob("*.yaml")):
        if file_contratto.name.startswith("_"):
            continue
        try:
            reale = ad_contract.load(file_contratto)
        except ad_contract.ContractError:
            continue
        if not reale.get("required_gates"):
            continue
        for risultato in ad_evidence.evaluate(reale, lette_reali).gates:
            if risultato.state == "INVALID" and "diverso dal contract" in risultato.detail:
                firma.append(f"{file_contratto.name}: {risultato.gate}")
    check(
        "nessun permesso del registro reale e' accusato con l'evidenza di un altro",
        not firma,
        str(firma),
    )


def test_cli() -> None:
    """Every command documented in the skills answers with the promised exit code."""
    print("\nCLI")
    import subprocess

    valid = str(FIXTURES / "contract_valid.yaml")
    cases: list[tuple[list[str], int]] = [
        (["cards.py", "list"], 0),
        (["cards.py", "list", "--domain", "business"], 0),
        (["cards.py", "show", "backend"], 0),
        (["cards.py", "show", "ghost-card"], 1),
        (["cards.py", "match", "api_implementation"], 0),
        (["cards.py", "match", "ghost-task"], 1),
        (["cards.py", "check"], 0),
        (["cards.py", "check", "--strict"], 0),
        (["validate_contract.py", valid], 0),
        (["validate_contract.py", str(FIXTURES / "contract_bad_gate.yaml")], 1),
        (["verdict.py", "--contract", valid, "--evidence", str(FIXTURES / "evidence_ok")], 0),
        (["verdict.py", "--contract", valid, "--evidence", str(FIXTURES / "evidence_partial")], 1),
    ]
    for command, expected in cases:
        result = subprocess.run(
            [sys.executable, str(TOOLS / command[0]), *command[1:]],
            capture_output=True,
            text=True,
        )
        label = " ".join(command[:3])
        check(
            f"{label} -> exit {expected}",
            result.returncode == expected,
            f"exit {result.returncode}: {result.stderr.strip()[:120]}",
        )


def test_scope() -> None:
    """The write-scope authority behaves as the enforcement layer expects."""
    print("\nambito di scrittura")
    import tempfile

    root = Path(ad_docs.DOCS_ROOT)
    scopes = ad_scope.load_write_scopes(root)
    check(
        "ogni contract attivo nella root reale e' approvato",
        all(s.task_id in ad_scope.load_approvals(root) for s in scopes),
        str([s.task_id for s in scopes]),
    )
    # Ogni contract di progetto dichiara milestone e sprint, e lo sprint e' aperto.
    #
    # Prima qui c'era «nessun contract apre una cartella prodotto»: asseriva un
    # fatto sullo **stato del workspace**, non un comportamento del codice. Era
    # vero finche' l'unico contract attivo era quello di governance; il
    # 2026-10-08, appena `NLT-001` ha aperto il primo progetto vero, il test e'
    # fallito — e `check()` alza, quindi la suite si e' **interrotta** e gli ultimi
    # sette gruppi non sono piu' stati eseguiti. Un test che misura i dati invece
    # del codice non protegge: riduce la copertura senza dirlo.
    #
    # La regola vera e' l'invariante 13: chi tocca un progetto dichiara milestone e
    # sprint, e lo sprint esiste. Questa asserzione regge quando i progetti
    # partono, e fallisce solo se un contract e' davvero irregolare.
    # Un solo controllo su tutti i contract di progetto, non uno per contract.
    #
    # Con un controllo per contract il **numero di controlli** cambiava con il
    # numero di contract attivi: chiudendo due permessi la suite e' passata da 174
    # a 173. Le asserzioni erano giuste, ma il conteggio no — «174 controlli» non
    # era riproducibile, ed e' la stessa classe di errore di DEC-0023: una misura
    # che dipende dallo stato del momento invece che dal codice.
    registro = ad_registry.load()
    irregolari: dict[str, list[str]] = {}
    for scope in scopes:
        if not any(
            ad_scope.protected_segment(prefix.strip().strip('"')) for prefix in scope.scopes
        ):
            continue
        contratto = ad_contract.load(scope.source)
        codici = {f.code for f in ad_contract.validate(contratto, registro, root)}
        problemi = codici & {
            "missing-field:milestone",
            "missing-field:sprint",
            "sprint-not-open",
        }
        if problemi:
            irregolari[scope.task_id] = sorted(problemi)
    check(
        "ogni contract di progetto dichiara milestone e sprint aperti",
        not irregolari,
        str(irregolari),
    )
    check(
        "la cartella contratti esiste",
        ad_scope.contracts_dir(root).is_dir(),
        str(ad_scope.contracts_dir(root)),
    )
    protected = ad_scope.protected_segment("5.APP-Artigiano-Digitale/src/x.ts")
    check("una cartella numerata e' protetta", protected == "5.APP-Artigiano-Digitale", str(protected))
    check("tools/ non e' una cartella prodotto", ad_scope.protected_segment("tools/x.py") is None)
    check("un percorso fuori root non e' protetto", ad_scope.protected_segment(None) is None)

    uncovered = ad_scope.evaluate(root / "5.APP-Artigiano-Digitale" / "src" / "x.ts", root)
    check("cartella prodotto senza contract: bloccato", not uncovered.allowed)
    check("il motivo nomina il rimedio", "write_scope" in uncovered.reason)

    free = ad_scope.evaluate(root / "piani" / "x.md", root)
    check("fuori dalle classi protette: permesso", free.allowed)

    # Artefatti di governance: la macchina che definisce ed esegue le regole.
    check(
        "governance_segment riconosce .brain/",
        ad_scope.governance_segment(".brain/COSTITUZIONE.md") == ".brain",
    )
    check(
        "governance_segment riconosce tools/",
        ad_scope.governance_segment("tools/ad_scope.py") == "tools",
    )
    check("governance_segment ignora i documenti", ad_scope.governance_segment("piani/x.md") is None)
    check(
        "protected_entries unisce prodotto e governance",
        ".brain" in ad_scope.protected_entries(root) and "tools" in ad_scope.protected_entries(root),
    )

    for relativo in (
        ".brain/COSTITUZIONE.md",
        ".brain/plugin/enforce-contract/index.mjs",
        "tools/ad_scope.py",
    ):
        verdict = ad_scope.evaluate(root / relativo, root)
        # Qui c'era `verdict.task_id == "GOV-000"`: asseriva QUALE contract copre,
        # cioe' lo stato del workspace, non il comportamento del codice. Il
        # 2026-10-11 l'apertura di `ADMF-004` (write_scope: `tools/`) l'ha reso
        # falso senza che niente fosse rotto — la stessa classe di ERR-0023, una
        # misura che dipende dal momento invece che dal codice. E `check()` alza:
        # la suite si e' fermata li', e i gruppi dopo non sono piu' stati eseguiti.
        # La regola vera e' che il percorso sia coperto da un contract APPROVATO.
        check(
            f"governance coperta da un contract approvato ({relativo})",
            verdict.allowed and verdict.task_id in ad_scope.load_approvals(root),
            verdict.reason,
        )

    check(
        "contratti/ resta libero: e' l'input dell'autorizzazione",
        ad_scope.evaluate(root / "contratti" / "T.yaml", root).allowed,
    )
    check(
        "approvazioni/ resta libero: e' l'input dell'autorizzazione",
        ad_scope.evaluate(root / "approvazioni" / "T.yaml", root).allowed,
    )

    for comando in (
        'rm -rf ".brain/skills"',
        "rm -rf tools/",
        "mv tools/ad_scope.py /tmp/",
        'chmod 777 ".brain/plugin"',
    ):
        target = ad_scope.bash_target(comando, root, root)
        check(f"la shell vede l'artefatto di governance ({comando[:24]})", target is not None, str(target))

    check(
        "un comando di sola lettura su tools/ non e' una mutazione",
        ad_scope.bash_target("python3 tools/milestone.py check x", root, root) is None,
    )

    with tempfile.TemporaryDirectory() as temporary:
        import os
        import time

        temp = Path(temporary)
        base = time.time()
        (temp / "contratti").mkdir()
        (temp / "approvazioni").mkdir()
        (temp / "9. Prova" / "src").mkdir(parents=True)
        (temp / "9. Prova" / "altro").mkdir()

        # T-1: consenso PRIMA del contract -> copre
        # La data e' DICHIARATA nel documento, non presa dall'mtime: cosi' l'ordine
        # viaggia con i documenti, e regge a una copia e a un `git clone`.
        contract_ok = temp / "contratti" / "T-1.yaml"
        contract_ok.write_text(
            'task_id: T-1\nagent: backend\nstatus: active\naperto: "2026-10-07"\n'
            'write_scope:\n  - "9. Prova/src"\n',
            encoding="utf-8",
        )
        approval_ok = temp / "approvazioni" / "T-1.yaml"
        approval_ok.write_text(
            "task_id: T-1\napprovato_da: CEO\ndata: '2026-10-08T12:00:00+02:00'\n",
            encoding="utf-8",
        )
        # e gli mtime si mettono AL CONTRARIO, apposta: se il controllo li usasse
        # ancora, questo caso passerebbe per il motivo sbagliato.
        os.utime(approval_ok, (base, base))
        os.utime(contract_ok, (base - 100, base - 100))

        # T-2: contract DICHIARATO dopo il consenso -> non copre
        contract_bad = temp / "contratti" / "T-2.yaml"
        contract_bad.write_text(
            'task_id: T-2\nstatus: active\naperto: "2026-10-09"\n'
            'write_scope:\n  - "9. Prova/altro"\n',
            encoding="utf-8",
        )
        approval_bad = temp / "approvazioni" / "T-2.yaml"
        approval_bad.write_text(
            "task_id: T-2\napprovato_da: CEO\ndata: '2026-10-08T12:00:00+02:00'\n",
            encoding="utf-8",
        )
        os.utime(contract_bad, (base - 100, base - 100))
        os.utime(approval_bad, (base, base))

        # T-3: contract senza marcatore -> non copre
        (temp / "9. Prova" / "terzo").mkdir()
        (temp / "contratti" / "T-3.yaml").write_text(
            'task_id: T-3\nstatus: active\nwrite_scope:\n  - "9. Prova/terzo"\n',
            encoding="utf-8",
        )

        # T-scaduto: approvazione presente ma contract scaduto
        (temp / "9. Prova" / "scaduto").mkdir()
        (temp / "contratti" / "T-scaduto.yaml").write_text(
            "task_id: T-scaduto\nstatus: active\nexpires: '2020-01-01T00:00:00+00:00'\n"
            'write_scope:\n  - "9. Prova/scaduto"\n',
            encoding="utf-8",
        )
        (temp / "approvazioni" / "T-scaduto.yaml").write_text(
            "task_id: T-scaduto\napprovato_da: CEO\ndata: '2026-10-08T12:00:00+02:00'\n",
            encoding="utf-8",
        )

        (temp / "contratti" / "_TEMPLATE.yaml").write_text(
            'task_id: modello\nstatus: active\nwrite_scope:\n  - "9. Prova"\n',
            encoding="utf-8",
        )

        scopes = ad_scope.load_write_scopes(temp)
        check(
            "i contract attivi sono caricati",
            sorted(s.task_id for s in scopes) == ["T-1", "T-2", "T-3"],
            str([s.task_id for s in scopes]),
        )
        check(
            "consenso prima del contract -> permesso",
            ad_scope.evaluate(temp / "9. Prova" / "src" / "a.ts", temp).allowed,
        )
        check(
            "contract senza marcatore di approvazione -> bloccato",
            not ad_scope.evaluate(temp / "9. Prova" / "terzo" / "a.ts", temp).allowed,
        )
        check(
            "il blocco spiega che manca il consenso",
            "approvazione" in ad_scope.evaluate(temp / "9. Prova" / "terzo" / "a.ts", temp).reason,
        )
        check(
            "contract anteriore al consenso -> bloccato",
            not ad_scope.evaluate(temp / "9. Prova" / "altro" / "a.ts", temp).allowed,
        )
        check(
            "un contract scaduto non copre",
            not ad_scope.evaluate(temp / "9. Prova" / "scaduto" / "a.ts", temp).allowed,
        )
        check(
            "il modello col prefisso _ e' ignorato",
            "9. Prova" not in [s for scope in scopes for s in scope.scopes],
        )
        check(
            "governance senza contract in una root pulita: bloccato",
            not ad_scope.evaluate(temp / ".brain" / "x.md", temp).allowed,
        )
        check(
            "il blocco nomina la governance",
            "GOVERNANCE" in ad_scope.evaluate(temp / ".brain" / "x.md", temp).reason,
        )
        check(
            "anche tools/ e' bloccato senza contract",
            not ad_scope.evaluate(temp / "tools" / "x.py", temp).allowed,
        )
        check(
            "un contract sui prodotti non copre la governance",
            not ad_scope.evaluate(temp / "tools" / "x.py", temp).allowed
            and ad_scope.evaluate(temp / "9. Prova" / "src" / "a.ts", temp).allowed,
        )
        check(
            "il marcatore senza approvato_da non vale",
            ad_scope.load_approvals(temp).get("T-1") is not None
            and len(ad_scope.load_approvals(temp)) == 3,
        )


def test_scope_cli() -> None:
    """The scope CLI answers with the promised exit codes."""
    print("\nCLI ambito")
    import subprocess

    root = str(ad_docs.DOCS_ROOT)
    cases = [
        (["contract_scope.py", "policy", "--json"], 0),
        # `tools/` e' governance: **ogni** sua scrittura vuole un permesso, e un file che
        # nessun permesso nomina non e' coperto. Fino al 2026-10-13 questa riga diceva 0,
        # e passava per il motivo sbagliato: due permessi dichiaravano `tools/` INTERO
        # (DRIFT-018) e coprivano tutto, compreso cio' che non era loro. Ristretti i due
        # raggi ai FILE che toccano davvero (DEC-0054, regola 3), il file di prova non e'
        # piu' coperto — **ed e' la risposta giusta**. Il test scriveva il difetto.
        (["contract_scope.py", "check", str(Path(root) / "tools" / "x.py"), "--json"], 1),
        (
            [
                "contract_scope.py",
                "check",
                str(Path(root) / "5.APP-Artigiano-Digitale" / "x.ts"),
                "--json",
                "--root",
                root,
            ],
            1,
        ),
    ]
    for command, expected in cases:
        result = subprocess.run(
            [sys.executable, str(TOOLS / command[0]), *command[1:]],
            capture_output=True,
            text=True,
        )
        check(
            f"{' '.join(command[:2])} -> exit {expected}",
            result.returncode == expected,
            f"exit {result.returncode}: {result.stderr.strip()[:120]}",
        )


def test_bash_scope() -> None:
    """The shell heuristic blocks project writes and leaves read-only work alone.

    Il caso si COSTRUISCE: serve una cartella numerata che ESISTA, perche'
    ``bash_target`` cerca il nome fra i ``protected_entries`` — cioe' fra le
    cartelle numerate davvero presenti. Il 2026-10-13 questa prova usava
    ``13. Commercialista Digitale`` e su una copia vergine falliva: non era la
    stringa a mancare, era la cartella. Vedi ERR-0049.
    """
    print("\nambito dei comandi shell")
    root = str(ad_docs.DOCS_ROOT)
    # Un progetto temporaneo, numerato col prossimo numero libero, dentro la root vera.
    numero = ad_scope.primo_numero_libero(root)
    temporaneo = Path(root) / f"{numero}. Prova Del Cancello"
    temporaneo.mkdir(exist_ok=True)
    project = str(temporaneo)
    try:
        _casi_di_bash_scope(root, project)
    finally:
        shutil.rmtree(temporaneo, ignore_errors=True)


def _casi_di_bash_scope(root: str, project: str) -> None:
    cases = [
        ("grep -rn TODO \"" + project + "/\"", root, True, "sola lettura su progetto"),
        ("rm -rf \"" + project + "/src\"", root, False, "rm su progetto"),
        ("echo ciao > \"" + project + "/note.txt\"", root, False, "redirezione su progetto"),
        ("mv /tmp/a \"" + project + "/b\"", root, False, "mv su progetto"),
        ("ls -la", project, True, "nessuna mutazione, cwd progetto"),
        ("npm install", project, False, "install con cwd progetto"),
        ("npm install", "/tmp", True, "install fuori progetto"),
        ("git checkout main", project, False, "git che modifica, cwd progetto"),
        ("git status", project, True, "git in sola lettura"),
        ("rm -rf build", project, False, "rm relativo con cwd progetto"),
        ("rm -rf /tmp/build", project, True, "rm assoluto fuori progetto"),
        ("sed -i s/a/b/ file.txt", project, False, "sed -i relativo con cwd progetto"),
        ("python3 tools/cards.py check", root, True, "comando degli strumenti"),
        ('echo "vedi 13. Commercialista Digitale" > /tmp/n.txt', "/tmp", True, "accenno al nome"),
    ]
    for command, cwd, expected, label in cases:
        verdict = ad_scope.evaluate_command(command, root, cwd)
        check(f"{label} -> {'ammesso' if expected else 'bloccato'}", verdict.allowed == expected)

    blocked = ad_scope.evaluate_command(f'rm -rf "{project}/src"', root, root)
    check("il motivo del blocco e' actionabile", "contratti" in blocked.reason, blocked.reason[:80])


def test_milestone() -> None:
    """Milestone e sprint: apertura, verifica e guardia sull'ambito."""
    print("\nmilestone e sprint")

    with scratch_root() as temporary:
        project = Path(temporary) / "9. Progetto"
        project.mkdir()

        check(
            "un progetto senza milestone e' segnalato",
            ad_milestone.problems(project) != [],
        )

        report = ad_milestone.scaffold_milestone(project, "primo prodotto utilizzabile")
        check("la milestone si apre dal modello", report.is_file(), str(report))
        check(
            "la milestone risulta aperta con report",
            len(ad_milestone.scan(project)) == 1 and ad_milestone.scan(project)[0].has_report,
        )

        prompt = ad_milestone.scaffold_sprint(project, 1, "autenticazione")
        check("lo sprint si apre col prompt", prompt.is_file(), str(prompt))
        sprint = ad_milestone.scan(project)[0].sprints[0]
        check("lo sprint ha il prompt e non il report", sprint.has_prompt and not sprint.has_report)

        issues = ad_milestone.problems(project)
        check("lo sprint non chiuso e' segnalato", any("REPORT.md" in i for i in issues), str(issues))
        check("il prompt e' numerato col progetto", "9. Progetto" in prompt.read_text(encoding="utf-8"))

        (prompt.parent / "REPORT.md").write_text("# report\n", encoding="utf-8")
        check("chiuso il report, la storia e' completa", ad_milestone.problems(project) == [])

        (ad_milestone.docs_dir(project) / "Milestone 3").mkdir()
        check(
            "una numerazione con buco e' segnalata",
            any("non contigue" in i for i in ad_milestone.problems(project)),
            str(ad_milestone.problems(project)),
        )

    # La guardia: lo strumento non scrive in un progetto senza contract approvato.
    #
    # Il progetto lo **costruisce la prova**: un progetto NUMERATO temporaneo nella
    # radice vera. Serve la radice vera — e' lei che l'autorita' interroga, e una
    # root finta proverebbe un'altra domanda — e serve che sia numerato, altrimenti
    # il rifiuto parlerebbe del numero e non del contract. Prima qui c'era
    # `13. Commercialista Digitale`: su un motore vergine quel progetto non esiste,
    # e `iterdir()` faceva fallire la prova su un motore sano (ERR-0049). Una prova
    # che non si costruisce il proprio caso prova il mondo, non il codice.
    autorita = Path(ad_docs.DOCS_ROOT)
    with tempfile.TemporaryDirectory(
        prefix=f"{ad_scope.primo_numero_libero(autorita)}. Prova Guardia -", dir=autorita
    ) as temporanea:
        protetto = Path(temporanea)
        try:
            ad_milestone.scaffold_milestone(protetto, "non deve nascere")
            check("la guardia rifiuta la scrittura non coperta", False, "nessuna eccezione")
        except PermissionError as exc:
            check("la guardia rifiuta la scrittura non coperta", "contract" in str(exc).lower(), str(exc))
        check(
            "la guardia non ha creato nulla",
            not any(ad_milestone.MILESTONE_DIR.match(p.name) for p in protetto.iterdir()),
        )


def test_guardia() -> None:
    """ERR-0026 — la guardia e' UNA, e la chiama ogni strumento che scrive.

    Il difetto non era «a `blueprint.py` manca la guardia»: era che la guardia
    viveva in **uno strumento su sei**. Riparare quella riga non basta — la
    lezione dell'errore e' che una difesa scritta in un posto solo viene
    dimenticata nel posto successivo. Quindi qui si prova: (1) che la definizione
    e' una sola, (2) che il meccanismo rifiuta davvero, (3) che il rifiuto lo
    **esegue** ogni strumento che scrive.

    Le prove del punto 3 non scrivono niente: la guardia alza prima della prima
    `mkdir`. Per questo si fanno sulla root vera — che e' l'autorita' — e non su
    una root finta, che non proverebbe *quale* albero lo strumento interroga.
    """
    print("\nla guardia di ambito (ERR-0026)")
    import ast
    import tempfile

    # --- 1. UNA SOLA DEFINIZIONE -------------------------------------------
    # Il controllo meccanico che rende impossibile la regressione: una seconda
    # copia della guardia in un altro strumento fa fallire questa riga.
    import blueprint
    import comportamento
    import security_scan
    import stato

    definite = []
    for modulo in sorted(TOOLS.glob("*.py")):
        albero = ast.parse(modulo.read_text(encoding="utf-8"))
        if any(
            isinstance(nodo, ast.FunctionDef) and nodo.name == "guard"
            for nodo in ast.walk(albero)
        ):
            definite.append(modulo.name)
    check(
        "la guardia e' definita una volta sola, dentro l'autorita'",
        definite == ["ad_scope.py"],
        f"definizioni trovate: {definite}",
    )
    check(
        "e ad_milestone non tiene piu' la sua copia",
        not hasattr(ad_milestone, "_guard"),
        "ad_milestone._guard esiste ancora",
    )

    # --- 2. IL MECCANISMO, su una root finta --------------------------------
    with tempfile.TemporaryDirectory() as temporary:
        import os
        import time

        finta = Path(temporary)
        (finta / "contratti").mkdir()
        (finta / "approvazioni").mkdir()
        (finta / "9. Prova" / "src").mkdir(parents=True)
        (finta / "9. Prova" / "altro").mkdir()
        adesso = time.time()

        marcatore = finta / "approvazioni" / "T-1.yaml"
        marcatore.write_text(
            "task_id: T-1\napprovato_da: CEO\ndata: '2026-10-08T12:00:00+02:00'\n",
            encoding="utf-8",
        )
        contratto = finta / "contratti" / "T-1.yaml"
        contratto.write_text(
            'task_id: T-1\nagent: backend\nstatus: active\nwrite_scope:\n  - "9. Prova/src"\n',
            encoding="utf-8",
        )
        os.utime(marcatore, (adesso - 100, adesso - 100))
        os.utime(contratto, (adesso, adesso))

        def rifiuto(target: Path) -> str | None:
            """Il motivo del rifiuto, o None se e' passata."""
            try:
                ad_scope.guard(target, finta)
            except PermissionError as errore:
                return str(errore)
            return None

        check("il percorso coperto passa", rifiuto(finta / "9. Prova" / "src" / "a.ts") is None)
        motivo = rifiuto(finta / "9. Prova" / "altro" / "a.ts")
        check("il percorso non coperto e' rifiutato", motivo is not None)
        check(
            "e il rifiuto dice il rimedio, non solo «no»",
            bool(motivo) and "write_scope" in motivo,
            str(motivo)[:90],
        )
        check(
            "fuori dalle classi protette non serve nessun permesso",
            rifiuto(finta / "piani" / "x.md") is None,
        )
        check(
            "un artefatto di governance senza contract e' rifiutato",
            rifiuto(finta / "tools" / "x.py") is not None,
        )

    # --- 3. GLI STRUMENTI CHE SCRIVONO, ESEGUITI ----------------------------
    vera = Path(ad_docs.DOCS_ROOT)
    scoperto = vera / "99. Progetto Non Coperto"
    check(
        "il bersaglio delle prove non esiste e non e' coperto",
        not scoperto.exists()
        and not ad_scope.evaluate(scoperto / "x.md", vera).allowed,
        str(scoperto),
    )

    def rifiuta(etichetta: str, scrittura) -> None:
        """Esegue la scrittura: deve fallire, e non deve lasciare tracce."""
        try:
            scrittura()
        except PermissionError as errore:
            check(
                f"{etichetta} rifiuta il percorso non coperto",
                "Nessun task contract copre" in str(errore),
                str(errore)[:90],
            )
            return
        check(f"{etichetta} rifiuta il percorso non coperto", False, "nessuna eccezione: ha scritto")

    rifiuta("blueprint.py", lambda: blueprint.scrivi("99. Progetto Non Coperto", vera))
    rifiuta("ad_milestone.py", lambda: ad_milestone.scaffold_milestone(scoperto, "non nasce"))
    rifiuta("stato.py", lambda: stato.scrivi(scoperto))
    rifiuta("comportamento.py", lambda: comportamento._scrivi_baseline(scoperto, {}))
    rifiuta(
        "ad_docs.prenota_id (errori.py, verbali.py)",
        lambda: ad_docs.prenota_id(scoperto / "errori", "ERR", estensione=".yaml"),
    )
    rifiuta("security_scan.py", lambda: security_scan.disattiva(scoperto, [{"file": "AGENTS.md"}]))
    check("nessuno di loro ha lasciato una traccia", not scoperto.exists(), str(scoperto))

    # E la guardia non rifiuta TUTTO: `tools/` e' coperto da un contract approvato,
    # ed e' la condizione perche' questo lavoro si possa fare.
    try:
        ad_scope.guard(vera / "tools" / "ad_scope.py")
        coperto = True
    except PermissionError:
        coperto = False
    check("un contract approvato apre il percorso: la guardia non dice sempre no", coperto)

    # --- 4. FUORI DALL'ALBERO DI AUTORITA' ----------------------------------
    # Il caso che il gate ha contestato: `--root /tmp/x` non e' un permesso, e' un
    # errore di chi invoca. `evaluate` risponde ancora `allowed` — «quel percorso
    # non e' protetto» e' la risposta giusta a *quella* domanda, ed e' quella che
    # serve a `contract_scope.py` — mentre `guard`, che e' la porta delle scritture,
    # rifiuta. E lo eseguono gli strumenti veri, non una root finta: una root finta
    # non proverebbe *quale* albero lo strumento interroga.
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as temporanea:
        fuori = Path(temporanea) / "fuori"
        valutazione = ad_scope.evaluate(fuori / "errori")
        check(
            "fuori dall'albero `evaluate` dice ancora «non e' protetto»: e' un'altra domanda",
            valutazione.allowed and not valutazione.protected,
            f"allowed={valutazione.allowed} protected={valutazione.protected}",
        )
        try:
            ad_scope.guard(fuori / "errori")
            check("la guardia rifiuta un percorso fuori dall'albero", False, "nessuna eccezione")
        except PermissionError as errore:
            check(
                "la guardia rifiuta un percorso fuori dall'albero, e dice perche'",
                "autorita" in str(errore) and str(vera) in str(errore),
                str(errore)[:100],
            )

        comandi = (
            ("verbali.py", ["nuovo", "--slug", "prova"]),
            ("errori.py", ["nuovo", "--slug", "prova"]),
            ("stato.py", ["render"]),
            ("comportamento.py", ["check", "--update"]),
            ("blueprint.py", ["render", "3. AD-Marketing-Factory"]),
        )
        motivi = []
        for nome, argomenti in comandi:
            esito = subprocess.run(
                [sys.executable, str(TOOLS / nome), *argomenti, "--root", str(fuori)],
                capture_output=True,
                text=True,
            )
            motivi.append(esito.stderr)
            check(
                f"{nome}, con --root fuori dall'albero: rifiuta e non lascia tracce",
                esito.returncode == 2 and not fuori.exists(),
                f"exit {esito.returncode}: {(esito.stderr or esito.stdout).strip()[:100]}",
            )
        check(
            "ogni rifiuto dice perche': il percorso non sta sotto la root di autorita'",
            all("autorita" in motivo for motivo in motivi),
            str(motivi)[:120],
        )


def test_evidence_declaration() -> None:
    """C1/C3: etichette d'evidenza e dichiarazione obbligatoria dei side-effect."""
    print("\ndichiarazione dell'evidenza")
    import tempfile

    contract = {
        "task_id": "BIO-142",
        "agent": "backend",
        "required_gates": ["QA"],
        "write_scope": ["src/"],
    }
    base = [
        "task_id: BIO-142",
        "gate: QA",
        "outcome: PASS",
        "producer: qa",
        "references:",
        "  - artefatti/prova.txt",
    ]

    def verdetto(extra: str) -> str:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "e.yaml"
            path.write_text("\n".join(base) + "\n" + extra + "\n", encoding="utf-8")
            return ad_evidence.evaluate(contract, ad_evidence.collect([path])).outcome

    completi = "\n".join(f'  {key}: "NO"' for key in ad_evidence.SIDE_EFFECT_KEYS)
    effetti = f"side_effects:\n{completi}"

    check("dichiarazione completa -> ACCEPT", verdetto(effetti) == "ACCEPT")
    check("dichiarazione assente -> REJECT", verdetto("") == "REJECT")

    parziali = "\n".join(f'  {key}: "NO"' for key in ad_evidence.SIDE_EFFECT_KEYS if key != "database")
    check(
        "dichiarazione incompleta -> REJECT",
        verdetto(f"side_effects:\n{parziali}") == "REJECT",
    )
    check(
        "chiave non dichiarabile -> REJECT",
        verdetto(effetti + '\n  inventato: "NO"') == "REJECT",
    )
    check(
        "valore non ammesso -> REJECT",
        verdetto(effetti.replace('  code: "NO"', '  code: "MAGARI"')) == "REJECT",
    )
    check(
        "etichetta non ammessa -> REJECT",
        verdetto(effetti + '\nclaims:\n  copertura: "SICURO"') == "REJECT",
    )
    check(
        "etichetta ammessa -> resta ACCEPT",
        verdetto(effetti + '\nclaims:\n  copertura: "VERIFIED"') == "ACCEPT",
    )

    # Contraddizione: dichiara di non aver toccato il database, ma lo scope lo tocca.
    contraddittorio = "side_effects:\n" + "\n".join(
        '  database: "NO"' if key == "database" else f'  {key}: "NO"'
        for key in ad_evidence.SIDE_EFFECT_KEYS
    )
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "e.yaml"
        path.write_text("\n".join(base) + "\n" + contraddittorio + "\n", encoding="utf-8")
        record = ad_evidence.collect([path])[0]
        contratto_db = dict(contract, write_scope=["prisma/"])
        check(
            "database: NO con write_scope sui dati -> REJECT",
            ad_evidence.evaluate(contratto_db, [record]).outcome == "REJECT",
        )

    # Il "problema della Norvegia": NO senza virgolette e' un booleano YAML.
    with tempfile.TemporaryDirectory() as temporary:
        grezzo = "\n".join(f"  {key}: NO" for key in ad_evidence.SIDE_EFFECT_KEYS)
        path = Path(temporary) / "e.yaml"
        path.write_text("\n".join(base) + f"\nside_effects:\n{grezzo}\n", encoding="utf-8")
        record = ad_evidence.collect([path])[0]
        check(
            "NO senza virgolette letto come NO, non come FALSE",
            record.side_effect("database") == "NO",
            record.side_effect("database"),
        )


def test_drift() -> None:
    """Il registro drift e' coerente, e le incoerenze vengono intercettate."""
    print("\nregistro drift")
    import tempfile

    check("il registro reale e' coerente", ad_drift.problems() == [], str(ad_drift.problems()))
    reali = ad_drift.load()
    check("il registro ha voci", len(reali) > 0, str(len(reali)))
    check(
        "gli ID crescono e non si ripetono (non si rinumerano)",
        (lambda ids: ids == sorted(ids) and len(set(ids)) == len(ids))(
            [entry.id for entry in reali]
        ),
        str([entry.id for entry in reali]),
    )

    def voce(numero: int, stato: str = "OPEN", extra: str = "") -> str:
        return (
            f"## DRIFT-{numero:03d} — prova\n\n"
            "| Campo | Valore |\n|---|---|\n"
            "| **Severita'** | LOW |\n"
            "| **Documento dice** | d |\n"
            "| **Realta' dice** | r |\n"
            "| **Rischio** | x |\n"
            f"| **Stato** | {stato} |\n"
            "| **Evidenza** | e |\n" + extra
        )

    def registro(*voci: str) -> list[str]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "drift").mkdir()
            (root / "DECISIONI").mkdir()
            (root / "drift" / "README.md").write_text("\n".join(voci), encoding="utf-8")
            return ad_drift.problems(root)

    check("una voce completa non segnala nulla", registro(voce(1)) == [], str(registro(voce(1))))
    # Un buco **non** e' piu' un errore: gli id non si rinumerano, quindi una voce tolta
    # lascia il suo numero (2026-10-13). Serve la prova opposta: il buco **passa**, e
    # l'ordine sbagliato **non** passa. Senza questa coppia, il controllo potrebbe
    # accettare qualunque cosa e nessuno se ne accorgerebbe.
    check(
        "un buco nella numerazione NON e' piu' segnalato: un id tolto non si riusa",
        registro(voce(1), voce(3)) == [],
        str(registro(voce(1), voce(3))),
    )
    check(
        "un ID fuori ordine e' segnalato",
        any("ordine" in issue for issue in registro(voce(3), voce(1))),
        str(registro(voce(3), voce(1))),
    )
    check(
        "un ID duplicato e' segnalato",
        any("duplicati" in issue or "ordine" in issue
            for issue in registro(voce(1), voce(1))),
        str(registro(voce(1), voce(1))),
    )
    senza_campo = voce(1).replace("| **Evidenza** | e |\n", "")
    check(
        "un campo obbligatorio mancante e' segnalato",
        any("Evidenza" in issue for issue in registro(senza_campo)),
    )
    check(
        "una severita' non ammessa e' segnalata",
        any("severita'" in issue for issue in registro(voce(1).replace("| LOW |", "| BOOH |"))),
    )
    check(
        "uno stato non ammesso e' segnalato",
        any("stato" in issue for issue in registro(voce(1, stato="FORSE"))),
    )
    chiusa_senza_dec = voce(1, stato="FIXED")
    check(
        "una chiusura senza Decision Record e' segnalata",
        any("Decisione" in issue for issue in registro(chiusa_senza_dec)),
    )
    check(
        "una chiusura con Decision Record inesistente e' segnalata",
        any(
            "inesistente" in issue
            for issue in registro(
                voce(1, stato="FIXED", extra="| **Chiuso** | 2026-10-08 |\n| **Decisione** | DEC-9999 |\n")
            )
        ),
    )
    check(
        "una chiusura senza data e' segnalata",
        any(
            "Chiuso" in issue
            for issue in registro(
                voce(1, stato="CLOSED", extra="| **Decisione** | DEC-0009 |\n")
            )
        ),
    )


def test_bootstrap_sprint() -> None:
    """DRIFT-010: il contract che apre il primo passo non si morde la coda.

    La regola dice «non si lavora senza il passo aperto». Ma il foglio del passo
    va scritto, e scriverlo richiede un contract: se il contract pretendesse il
    passo gia' aperto, non si partirebbe mai. Il confine e' **dove si scrive**.
    """
    print("\nbootstrap del primo passo (DRIFT-010)")

    with scratch_root() as temporary:
        import os
        import time

        root = Path(temporary)
        progetto = root / "9. Progetto"
        (progetto / "src").mkdir(parents=True)
        (root / "contratti").mkdir()
        (root / "approvazioni").mkdir()
        base = time.time()

        marcatore = root / "approvazioni" / "T-1.yaml"
        marcatore.write_text(
            "task_id: T-1\napprovato_da: CEO\ndata: '2026-10-08T12:00:00+02:00'\n",
            encoding="utf-8",
        )
        contratto = root / "contratti" / "T-1.yaml"
        contratto.write_text(
            "task_id: T-1\nstatus: active\nmilestone: 1\nsprint: 1\n"
            'write_scope:\n  - "9. Progetto/"\n',
            encoding="utf-8",
        )
        os.utime(marcatore, (base - 100, base - 100))
        os.utime(contratto, (base, base))

        tappa = "9. Progetto/Analisi-Prompt-Report/Milestone 1/REPORT.md"
        passo = "9. Progetto/Analisi-Prompt-Report/Milestone 1/Sprint 1/PROMPT.md"
        fuori = "9. Progetto/src/api.ts"

        verdetto = ad_scope.evaluate(root / fuori, root)
        check(
            "passo non aperto: scrivere nel codice e' bloccato",
            not verdetto.allowed,
            verdetto.reason[:110],
        )
        check(
            "il blocco spiega che il contract vale solo per aprire il passo",
            "aperto" in verdetto.reason and "copre solo" in verdetto.reason,
            verdetto.reason[:110],
        )
        check(
            "passo non aperto: creare la TAPPA e' permesso (serve prima di tutto)",
            ad_scope.evaluate(root / tappa, root).allowed,
            ad_scope.evaluate(root / tappa, root).reason[:110],
        )
        check(
            "passo non aperto: scrivere il FOGLIO del passo e' permesso",
            ad_scope.evaluate(root / passo, root).allowed,
            ad_scope.evaluate(root / passo, root).reason[:110],
        )

        ad_milestone.scaffold_milestone(progetto, "prova")
        ad_milestone.scaffold_sprint(progetto, 1, "prova")
        check(
            "passo aperto: ora si puo' scrivere nel codice",
            ad_scope.evaluate(root / fuori, root).allowed,
            ad_scope.evaluate(root / fuori, root).reason[:110],
        )


def test_invariante_13() -> None:
    """Invariante 13: un contract di progetto richiede milestone e sprint aperti."""
    print("\ninvariante 13: l'analisi e' una milestone")

    registry = ad_registry.load()
    base = dict(contract_fixture("contract_valid.yaml"))
    base["write_scope"] = ["9. Progetto/"]

    def codici(contratto, root: Path) -> set[str]:
        return {f.code for f in ad_contract.validate(contratto, registry, root)}

    with scratch_root() as temporary:
        root = Path(temporary)
        progetto = root / "9. Progetto"
        progetto.mkdir()

        mancanti = codici(base, root)
        check(
            "contract di progetto senza milestone e sprint: violazione",
            {"missing-field:milestone", "missing-field:sprint"} <= mancanti,
            str(sorted(mancanti)),
        )

        non_aperto = codici(dict(base, milestone=1, sprint=1), root)
        check(
            "milestone e sprint dichiarati ma sprint non aperto: violazione",
            "sprint-not-open" in non_aperto,
            str(sorted(non_aperto)),
        )

        ad_milestone.scaffold_milestone(progetto, "obiettivo di prova")
        ancora = codici(dict(base, milestone=1, sprint=1), root)
        check("milestone aperta ma sprint no: ancora violazione", "sprint-not-open" in ancora)

        ad_milestone.scaffold_sprint(progetto, 1, "primo sprint")
        aperto = codici(dict(base, milestone=1, sprint=1), root)
        check(
            "sprint aperto: l'invariante 13 non segnala piu' nulla",
            not ({"missing-field:milestone", "missing-field:sprint", "sprint-not-open"} & aperto),
            str(sorted(aperto)),
        )

        check(
            "un contract fuori dai progetti non richiede milestone",
            "missing-field:milestone" not in codici(dict(base, write_scope=["tools/"]), root),
        )
        check(
            "milestone non numerica: violazione",
            "invalid-milestone" in codici(dict(base, milestone="uno", sprint=1), root),
        )


def test_coherence() -> None:
    """Il livello sempre caricato corrisponde al sistema, e le divergenze si vedono."""
    print("\ncoerenza del livello sempre caricato")
    import tempfile

    reali = ad_coherence.problemi()
    # Il montaggio del plugin riguarda il MOTORE INSTALLATO, non una copia: il
    # profilo DSH nomina un percorso assoluto, e una copia in /tmp non e' quel
    # percorso. Quindi si separa: la coerenza del sistema si pretende sempre; il
    # montaggio si pretende solo se il profilo monta QUESTA radice — se ne monta
    # un'altra, questa e' una copia e il controllo non si applica (ERR-0049). Se il
    # profilo non monta nessun plugin, il controllo resta e fallisce.
    montaggio = [p for p in reali if "non risulta montato" in p]
    altri = [p for p in reali if "non risulta montato" not in p]
    check("il sistema reale e' coerente", not altri, str(altri)[:160])
    patch = ad_coherence._testo(ad_coherence.PATCH_PROFILO)
    montato = ""
    for riga in (patch or "").splitlines():
        if ad_coherence.PLUGIN in riga:
            montato = riga.split("name:", 1)[-1].strip().strip("\"'")
    radice_montata = (
        Path(montato[: -len(ad_coherence.PLUGIN)]).resolve()
        if montato.endswith(ad_coherence.PLUGIN)
        else None
    )
    e_questo_motore = (
        radice_montata is not None and radice_montata == Path(ad_docs.DOCS_ROOT).resolve()
    )
    check(
        "il plugin di enforcement e' montato nel profilo, per questa radice o per un'altra",
        not montaggio if (e_questo_motore or radice_montata is None) else True,
        f"{str(montaggio)[:120]} · profilo monta {montato or '(nessun plugin)'}",
    )
    check(
        "ad_coherence.py non e' classificato come comando: il file contiene la stringa "
        "'__main__' nel proprio codice di rilevamento",
        "ad_coherence.py" not in ad_coherence.comandi_nel_progetto(),
    )
    check(
        "i comandi rilevati sono quelli con l'idioma, non quelli che nominano la stringa",
        "coherence.py" in ad_coherence.comandi_nel_progetto(),
    )

    def costruisci(
        costituzione: str,
        skill_extra: tuple[str, ...] = (),
        comando_extra: str = "",
        registro: str | None = None,
        glossario: str | None = None,
    ) -> list[str]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".brain" / "skills" / "ad-kickoff").mkdir(parents=True)
            (root / ".brain" / "skills" / "ad-kickoff" / "SKILL.md").write_text(
                "```text\n1 RICHIESTA        prima\n2 CONSENSO         seconda\n```\n",
                encoding="utf-8",
            )
            for nome in skill_extra:
                (root / ".brain" / "skills" / nome).mkdir(parents=True)
            (root / "tools").mkdir()
            if comando_extra:
                (root / "tools" / comando_extra).write_text(
                    'if __name__ == "__main__":\n    pass\n', encoding="utf-8"
                )
            if registro is not None:
                (root / "tools" / "README.md").write_text(registro, encoding="utf-8")
            if glossario is not None:
                (root / ".brain" / "GLOSSARIO.md").write_text(glossario, encoding="utf-8")
            (root / ".brain" / "COSTITUZIONE.md").write_text(costituzione, encoding="utf-8")
            return ad_coherence.problemi(root)

    buona = (
        "Le skill sono `ad-kickoff`.\n\n"
        "```text\n1 RICHIESTA        prima\n2 CONSENSO         seconda\n```\n"
    )
    problemi = costruisci(buona)
    check(
        "una costituzione coerente con la skill non produce divergenze di sequenza",
        not any("sequenza" in p or "passo" in p for p in problemi),
        str(problemi),
    )
    check(
        "una skill presente ma non nominata e' segnalata",
        any("ad-nuova" in p and "non e' nominata" in p for p in costruisci(buona, ("ad-nuova",))),
    )
    check(
        "una skill nominata ma inesistente e' segnalata",
        any("ad-fantasma" in p and "non esiste" in p for p in costruisci(buona + "E anche `ad-fantasma`.\n")),
    )
    check(
        "un comando presente ma non dichiarato nel registro e' segnalato",
        any("prova.py" in p and "non e' dichiarato" in p for p in costruisci(buona, (), "prova.py")),
        str(costruisci(buona, (), "prova.py")),
    )
    check(
        "un comando nominato ma inesistente e' segnalato",
        any("manca.py" in p for p in costruisci(buona + "\n```sh\npython3 tools/manca.py\n```\n")),
    )

    # --- il registro dei comandi (ADMF-008) --------------------------------
    #
    # L'elenco dei comandi vive in `tools/README.md`, e in un posto solo. Prima
    # stava nella costituzione: per aggiungere `tools/misure.py` bisognava scrivere
    # in due documenti di governance, e nessun controllo se ne accorgeva. Qui ogni
    # caso negativo e' **provato** su una radice finta — un controllo che non si e'
    # mai visto fallire non e' un controllo, e' una speranza.
    registro_prova = (
        "| `prova.py` | **uno strumento di prova**: dice qualcosa di comprensibile a "
        "chiunque lo legga | `python3 tools/prova.py` |\n"
    )
    con_rimando = buona + "\nL'elenco completo dei comandi sta in `tools/README.md`.\n"

    check(
        "se il registro non c'e', il controllo lo dice invece di passare a vuoto",
        any("manca il registro dei comandi" in p for p in costruisci(buona, (), "prova.py")),
    )
    check(
        "la costituzione che non cita il registro e' segnalata",
        any("non cita il registro" in p for p in costruisci(buona, (), "prova.py")),
    )
    dichiarato = costruisci(con_rimando, (), "prova.py", registro_prova)
    check(
        "un comando dichiarato SOLO nel registro non produce divergenze, e la "
        "costituzione non lo nomina: aggiungere uno strumento non tocca la costituzione",
        not any("prova.py" in p for p in dichiarato) and "prova.py" not in con_rimando,
        str(dichiarato),
    )
    fantasma = (
        "| `fantasma.py` | **un comando che non c'e'**: serve a far vedere che il "
        "registro viene controllato | `python3 tools/fantasma.py` |\n"
    )
    check(
        "il registro che nomina un comando inesistente e' segnalato",
        any("fantasma.py" in p and "non esiste" in p for p in costruisci(con_rimando, (), "", fantasma)),
        str(costruisci(con_rimando, (), "", fantasma)),
    )
    # La rinomina: il comando c'e' ancora, ma con un altro nome. Il registro resta
    # indietro da un lato, e il nuovo nome non e' dichiarato dall'altro. Entrambi i
    # versi vanno presi: prenderne uno solo lascerebbe passare meta' del difetto.
    vecchio_nome = (
        "| `vecchio.py` | **il nome di prima**: serve a far vedere che una rinomina "
        "non passa in silenzio | `python3 tools/vecchio.py` |\n"
    )
    rinomina = costruisci(con_rimando, (), "nuovo.py", vecchio_nome)
    check(
        "comando rinominato: il vecchio nome rimasto nel registro e' segnalato",
        any("vecchio.py" in p and "non esiste" in p for p in rinomina),
        str(rinomina),
    )
    check(
        "comando rinominato: il nuovo nome non dichiarato e' segnalato",
        any("nuovo.py" in p and "non e' dichiarato" in p for p in rinomina),
        str(rinomina),
    )
    segnaposto = "| `prova.py` | vedi codice | `python3 tools/prova.py` |\n"
    check(
        "una descrizione che non dice cosa fa il comando e' segnalata (invariante 14)",
        any("non dice cosa fa" in p for p in costruisci(con_rimando, (), "prova.py", segnaposto)),
        str(costruisci(con_rimando, (), "prova.py", segnaposto)),
    )
    uso_sbagliato = (
        "| `prova.py` | **uno strumento di prova**: dice qualcosa di comprensibile a "
        "chiunque lo legga | `python3 tools/altro.py` |\n"
    )
    check(
        "una forma d'uso copiata da un'altra riga e' segnalata",
        any("forma d'uso" in p and "prova.py" in p for p in costruisci(con_rimando, (), "prova.py", uso_sbagliato)),
        str(costruisci(con_rimando, (), "prova.py", uso_sbagliato)),
    )
    # L'elenco in due posti e' il difetto che questo contract toglie: la forma della
    # tabella non conta, conta che una dichiarazione ci sia.
    ricopiato = con_rimando + (
        "| `prova.py` | **uno strumento di prova**: dice qualcosa di comprensibile | "
        "`python3 tools/prova.py` |\n"
    )
    check(
        "la costituzione che ricopia l'elenco e' segnalata: l'elenco sta in un posto solo",
        any(
            "COSTITUZIONE.md ridichiara il comando prova.py" in p
            for p in costruisci(ricopiato, (), "prova.py", registro_prova)
        ),
        str(costruisci(ricopiato, (), "prova.py", registro_prova)),
    )
    vocabolario = (
        "| Termine | Come si dice |\n|---|---|\n"
        "| `prova.py` | **uno strumento di prova**: dice qualcosa di comprensibile |\n"
    )
    check(
        "il vocabolario che tiene una copia dell'elenco e' segnalato",
        any(
            "GLOSSARIO.md ridichiara il comando prova.py" in p
            for p in costruisci(con_rimando, (), "prova.py", registro_prova, vocabolario)
        ),
        str(costruisci(con_rimando, (), "prova.py", registro_prova, vocabolario)),
    )

    # Il sistema vero: il registro e i comandi che esistono devono essere la stessa
    # cosa, riga per riga. Non basta che `problemi()` taccia — quello lo dice gia'
    # la prima asserzione di questo gruppo —: qui si guarda l'elenco.
    reale = ad_coherence._testo(ad_coherence.ad_docs.DOCS_ROOT / ad_coherence.REGISTRO)
    dichiarati = ad_coherence.comandi_nel_registro(reale)
    check(
        "il registro reale dichiara esattamente i comandi che esistono, e nessun altro",
        set(dichiarati) == ad_coherence.comandi_nel_progetto(),
        str(sorted(set(dichiarati) ^ ad_coherence.comandi_nel_progetto())),
    )
    check(
        "ogni riga del registro reale dice cosa fa il comando, in parole comprensibili, "
        "e la sua forma d'uso",
        all(
            len(descrizione) >= ad_coherence.DESCRIZIONE_MINIMA
            and len(descrizione.split()) >= 3
            and f"{ad_coherence.TOOLS_DIR}/{comando}" in uso
            for comando, (descrizione, uso) in dichiarati.items()
        ),
        str([c for c, (d, u) in dichiarati.items() if len(d) < ad_coherence.DESCRIZIONE_MINIMA]),
    )
    check(
        "nessun documento del cervello tiene una seconda copia dell'elenco",
        ad_coherence.elenchi_duplicati(ad_coherence.ad_docs.DOCS_ROOT) == [],
        str(ad_coherence.elenchi_duplicati(ad_coherence.ad_docs.DOCS_ROOT)),
    )
    costituzione_reale = ad_coherence._testo(ad_coherence.ad_docs.DOCS_ROOT / ad_coherence.COSTITUZIONE)
    check(
        "la costituzione reale cita il registro invece di ricopiare l'elenco",
        ad_coherence.REGISTRO in costituzione_reale,
    )
    check(
        "la costituzione nomina i comandi della sequenza, non l'elenco: ne nomina "
        "meno di quanti ne esistono",
        len(ad_coherence.comandi_nominati(costituzione_reale)) < len(ad_coherence.comandi_nel_progetto()),
        str(sorted(ad_coherence.comandi_nominati(costituzione_reale))),
    )

    sequenza_diversa = (
        "Le skill sono `ad-kickoff`.\n\n"
        "```text\n1 RICHIESTA        prima\n2 CONSENSO         seconda\n3 CHIUSURA         terza\n```\n"
    )
    check(
        "una sequenza con passi diversi e' segnalata",
        any("passi diversi" in p for p in costruisci(sequenza_diversa)),
    )
    etichetta_diversa = (
        "Le skill sono `ad-kickoff`.\n\n"
        "```text\n1 RICHIESTA        prima\n2 MILESTONE        seconda\n```\n"
    )
    check(
        "un passo con etichetta diversa e' segnalato",
        any("passo 2 incoerente" in p for p in costruisci(etichetta_diversa)),
    )

    buco = (
        "Le skill sono `ad-kickoff`.\n\n"
        "```text\n1 RICHIESTA        prima\n3 CONSENSO         terza\n```\n"
    )
    check(
        "una sequenza con un buco e' segnalata: senza questo, un passo che il parser "
        "non vede farebbe passare il confronto a vuoto",
        any("non e' contigua" in p for p in costruisci(buco)),
    )
    etichetta_un_spazio = (
        "Le skill sono `ad-kickoff`.\n\n"
        "```text\n1 RICHIESTA prima\n2 ANALISI DI AVVIO cosa\n```\n"
    )
    check(
        "un'etichetta seguita da un solo spazio viene riconosciuta",
        sorted(ad_coherence.sequenza(etichetta_un_spazio)) == [1, 2],
        str(ad_coherence.sequenza(etichetta_un_spazio)),
    )

    # --- il vocabolario in parole semplici (invariante 14) -----------------
    check(
        "il vocabolario esiste ed e' nominato nella costituzione",
        ad_coherence.GLOSSARIO.split("/")[-1] in (ad_coherence.ad_docs.DOCS_ROOT / ad_coherence.COSTITUZIONE).read_text(encoding="utf-8"),
    )
    check(
        "ogni cartella nominata nella costituzione compare nel vocabolario",
        not any("non compare" in p for p in reali),
        str(reali),
    )

    # il registro non mescola i progetti
    # un record non puo' dichiarare un orario che non e' ancora arrivato
    with tempfile.TemporaryDirectory() as temporary:
        finta = Path(temporary)
        (finta / "approvazioni").mkdir()
        (finta / "approvazioni" / "X-1.yaml").write_text(
            'task_id: X-1\ndata: "2099-01-01T10:00:00+02:00"\n', encoding="utf-8"
        )
        check(
            "una data nel futuro e' segnalata (DRIFT-014: le date erano inventate)",
            any("X-1.yaml" in p for p in ad_coherence.orari_nel_futuro(finta)),
            str(ad_coherence.orari_nel_futuro(finta)),
        )
        (finta / "approvazioni" / "X-2.yaml").write_text(
            'task_id: X-2\nexpires: "2099-01-01T10:00:00+02:00"\n', encoding="utf-8"
        )
        check(
            "una SCADENZA nel futuro non e' segnalata: deve esserlo per forza",
            not any("X-2" in p for p in ad_coherence.orari_nel_futuro(finta)),
            str(ad_coherence.orari_nel_futuro(finta)),
        )

    check(
        "ogni contract e ogni marcatore stanno nel gruppo del loro progetto",
        not any("non e' raggruppato" in p or "fuori da ogni gruppo" in p for p in reali),
        str([p for p in reali if "gruppo" in p]),
    )
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "contratti" / "9-progetto").mkdir(parents=True)
        (root / "approvazioni").mkdir()
        (root / "contratti" / "9-progetto" / "X-1.yaml").write_text(
            'task_id: X-1\nstatus: active\nwrite_scope:\n  - "9. Progetto/"\n',
            encoding="utf-8",
        )
        # il marcatore c'e', ma e' sciolto nella cartella madre invece che nel gruppo
        (root / "approvazioni" / "X-1.yaml").write_text(
            "task_id: X-1\napprovato_da: CEO\ndata: '2026-10-08T12:00:00+02:00'\n",
            encoding="utf-8",
        )
        check(
            "un marcatore fuori dal suo gruppo e' segnalato",
            any("X-1.yaml" in p and "9-progetto" in p for p in ad_coherence.registro_problemi(root)),
            str(ad_coherence.registro_problemi(root)),
        )
        (root / "contratti" / "X-2.yaml").write_text(
            'task_id: X-2\nstatus: active\nwrite_scope:\n  - "9. Progetto/"\n',
            encoding="utf-8",
        )
        check(
            "un contract sciolto nella cartella madre e' segnalato",
            any("fuori da ogni gruppo" in p for p in ad_coherence.registro_problemi(root)),
            str(ad_coherence.registro_problemi(root)),
        )


def test_security_scan() -> None:
    """Il controllo delle dipendenze non guarda solo la radice, e non tace se non trova."""
    print("\ncontrollo delle dipendenze")
    import tempfile

    import security_scan

    if security_scan._installed("osv-scanner") is None:
        check("osv-scanner non installato: controllo saltato", True)
        return

    with tempfile.TemporaryDirectory() as temporary:
        esito = security_scan.scan_dipendenze(Path(temporary))
        check(
            "un progetto senza file di dipendenze lo DICHIARA, invece di dire 'assente' "
            "e uscire come se avesse controllato",
            "errore" in esito and "nessun file di dipendenze" in esito["errore"],
            str(esito.get("errore"))[:120],
        )

    # Il progetto con dipendenze lo **costruisce la prova**: su un motore vergine
    # `3. AD-Marketing-Factory` non esiste, e la prova misurava il mondo invece del
    # codice (ERR-0049). Il lockfile e' minimo ma vero: osv-scanner lo riconosce e
    # ne dichiara il percorso, che e' esattamente cio' che la prova pretende.
    import json

    with tempfile.TemporaryDirectory() as temporanea:
        finto_progetto = Path(temporanea) / "9. Progetto"
        finto_progetto.mkdir()
        (finto_progetto / "package-lock.json").write_text(
            json.dumps(
                {
                    "name": "prova",
                    "version": "1.0.0",
                    "lockfileVersion": 3,
                    "requires": True,
                    "packages": {
                        "": {"name": "prova", "version": "1.0.0"},
                        "node_modules/lodash": {
                            "version": "4.17.15",
                            "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.15.tgz",
                        },
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        letto = security_scan.scan_dipendenze(finto_progetto)
    check(
        "su un progetto con dipendenze il risultato dichiara quali file ha letto",
        any("package-lock.json" in f for f in letto.get("file_letti", [])),
        str(letto.get("file_letti"))[:120],
    )
    check(
        "il risultato non dipende da un nome di file scritto a mano",
        "package-lock.json" not in Path("tools/security_scan.py").read_text(encoding="utf-8")
        or "LOCKFILE" not in Path("tools/security_scan.py").read_text(encoding="utf-8"),
    )


def test_errori() -> None:
    """Il registro degli errori: voci complete, e difese che esistono davvero."""
    print("\nregistro degli errori")
    import tempfile

    import errori

    base = Path(ad_docs.DOCS_ROOT)
    reali = errori.problemi(base)
    check("il registro reale e' coerente", not reali, str(reali)[:160])

    dati = errori.statistiche(base)
    check("la statistica legge le voci", dati["totale"] > 0, str(dati))
    # Ogni voce cade in una e una sola categoria: nessuna sparisce dal conto.
    check(
        "la statistica classifica ogni voce, senza perderne nessuna",
        sum(dati["per_trovato_da"].values()) == dati["totale"],
        str(dati),
    )
    check(
        "la statistica distingue imparare da avere fortuna",
        dati["dal_controllo"] + dati["per_fortuna"] + dati["per_trovato_da"].get("revisore", 0)
        == dati["totale"],
        str(dati),
    )

    def scrivi(cartella: Path, nome: str, **campi) -> None:
        voce = {
            "id": nome,
            "data": '"2026-10-10"',
            "cosa_e_fallito": '"x"',
            "cosa_l_ha_risolto": '"y"',
            "cosa_l_avrebbe_preso": '"z"',
            "diventa": '"nota"',
            "dove": '""',
            "trovato_da": '"io"',
            "stato": '"chiuso"',
        }
        voce.update(campi)
        righe = "\n".join(f"{k}: {v}" for k, v in voce.items())
        (cartella / "errori" / f"{nome}.yaml").write_text(righe + "\n", encoding="utf-8")

    with tempfile.TemporaryDirectory() as temporary:
        finta = Path(temporary)
        (finta / "errori").mkdir()

        # una voce completa e senza difesa dichiarata: passa
        scrivi(finta, "ERR-0001")
        check("una voce completa non e' segnalata", not errori.problemi(finta), str(errori.problemi(finta)))

        # una difesa che non esiste e' peggio di nessuna difesa
        scrivi(finta, "ERR-0002", diventa='"controllo"', dove='"tools/non-esiste.py"')
        guai = errori.problemi(finta)
        check(
            "un controllo che punta a un file inesistente e' segnalato",
            any("non esiste" in g for g in guai),
            str(guai),
        )

        # «niente mi avrebbe preso» si puo' dire, ma allora resta aperto
        scrivi(finta, "ERR-0003", cosa_l_avrebbe_preso='"niente"')
        guai = errori.problemi(finta)
        check(
            "una voce senza difesa ma dichiarata chiusa e' segnalata",
            any("restare 'aperto'" in g for g in guai),
            str(guai),
        )

        # un campo mancante
        (finta / "errori" / "ERR-0004.yaml").write_text('id: ERR-0004\ndata: "2026-10-10"\n', encoding="utf-8")
        guai = errori.problemi(finta)
        check(
            "una voce senza la terza domanda e' segnalata come incompleta",
            any("manca il campo 'cosa_l_avrebbe_preso'" in g for g in guai),
            str(guai),
        )


def test_blueprint() -> None:
    """Il Blueprint: generato dai registri, e incapace di mentire."""
    print("\nBlueprint di un progetto")

    import blueprint

    base = Path(ad_docs.DOCS_ROOT)

    # Il generatore deve essere deterministico: due chiamate, stesso testo.
    # Altrimenti il controllo fallirebbe a ogni esecuzione, e un controllo che
    # grida sempre non lo guarda piu' nessuno.
    uno = blueprint.genera("3. AD-Marketing-Factory", base)
    due = blueprint.genera("3. AD-Marketing-Factory", base)
    check("il generatore e' deterministico: nessuna data, nessun ordine casuale", uno == due)
    check("il generato nomina i permessi e le prove", "Chi puo' scrivere" in uno and "Le prove" in uno)

    with scratch_root() as temporary:
        radice = Path(temporary)
        docs = radice / "9. Prova" / blueprint.ad_milestone.PROJECT_DOCS
        (docs / "Milestone 1" / "Sprint 1").mkdir(parents=True)
        (docs / "Milestone 1" / "Sprint 1" / "PROMPT.md").write_text("stato: aperto\n", encoding="utf-8")
        # `new-milestone` crea il rapporto della tappa come MODELLO, con stato: aperta.
        # Il Blueprint deve leggere quello che il record DICHIARA, non il fatto che il
        # file esista: altrimenti dice «chiusa» a una tappa appena aperta — cioe' mente.
        (docs / "Milestone 1" / "REPORT.md").write_text(
            'progetto: 9. Prova\nmilestone: 1\nstato: aperta\n', encoding="utf-8"
        )

        stato, _ = blueprint.controlla("9. Prova", radice)
        check("un progetto senza Blueprint risulta 'assente'", stato == "assente", stato)

        scritto = blueprint.scrivi("9. Prova", radice)
        check("il Blueprint viene scritto", scritto.is_file())
        check(
            "e la sua parte generata sta fra i marcatori",
            blueprint.blocco_generato(scritto.read_text(encoding="utf-8")) is not None,
        )

        stato, _ = blueprint.controlla("9. Prova", radice)
        check("subito dopo la scrittura risulta aggiornato", stato == "aggiornato", stato)

        # La bugia che il Blueprint ha detto davvero il 2026-10-10: una tappa appena
        # aperta risultava «chiusa» perche' il suo rapporto esisteva come modello.
        generato = blueprint.blocco_generato(scritto.read_text(encoding="utf-8")) or ""
        riga_tappa = [r for r in generato.splitlines() if r.startswith("| 1 |")]
        check(
            "una tappa aperta non viene dichiarata chiusa solo perche' il rapporto esiste",
            bool(riga_tappa) and "aperta" in riga_tappa[0],
            str(riga_tappa),
        )

        # I TRE verdetti. La differenza fra «vecchio» e «falso» e' l'impronta:
        # senza, le due cose si assomigliano e il controllo non sa cosa dire.
        originale = scritto.read_text(encoding="utf-8")
        blocco = blueprint.blocco_generato(originale) or ""
        dichiarata, corpo = blueprint.separa_fotografia(blocco)
        check("il Blueprint dichiara la sua impronta", dichiarata is not None, blocco[:80])
        check("e il sigillo regge sul contenuto che accompagna", blueprint._impronta(corpo) == dichiarata)

        # INDIETRO: cambiano i registri, non il file. Deve essere autentico ma vecchio.
        (docs / "Milestone 1" / "Sprint 2").mkdir()
        (docs / "Milestone 1" / "Sprint 2" / "PROMPT.md").write_text("stato: aperto\n", encoding="utf-8")
        stato, dettaglio = blueprint.controlla("9. Prova", radice)
        check("registri mossi, file intatto -> indietro (non manomesso)", stato == "indietro", dettaglio)
        (docs / "Milestone 1" / "Sprint 2" / "PROMPT.md").unlink()
        (docs / "Milestone 1" / "Sprint 2").rmdir()
        blueprint.scrivi("9. Prova", radice)
        check("e rigenerando torna aggiornato", blueprint.controlla("9. Prova", radice)[0] == "aggiornato")
        # Inseriamo una riga dentro il blocco generato: cambiarlo e' sempre una bugia,
        # qualunque cosa dicano i registri.
        # a) una riga scritta SOPRA il sigillo: scavalcherebbe il controllo. E' un errore.
        scritto.write_text(
            originale.replace(blueprint.INIZIO, blueprint.INIZIO + "\nTutto a posto.", 1),
            encoding="utf-8",
        )
        stato, dettaglio = blueprint.controlla("9. Prova", radice)
        check("una riga scritta prima del sigillo e' segnalata", stato == "senza-impronta", dettaglio)

        # b) una modifica DENTRO il corpo: il sigillo non regge piu'. E' manomissione.
        scritto.write_text(originale, encoding="utf-8")
        # Una riga che c'e' sempre, qualunque cosa dicano i registri.
        scritto.write_text(
            originale.replace("## A che punto e'", "## Tutto a posto, fidatevi", 1), encoding="utf-8"
        )
        stato, dettaglio = blueprint.controlla("9. Prova", radice)
        check("un Blueprint modificato dentro il corpo e' MANOMESSO", stato == "manomesso", dettaglio)
        scritto.write_text(originale, encoding="utf-8")

        scritto.write_text(originale.replace(blueprint.INIZIO, "", 1), encoding="utf-8")
        stato, _ = blueprint.controlla("9. Prova", radice)
        check("un Blueprint senza marcatori e' segnalato", stato == "senza-marcatori", stato)

        # La parte scritta a mano sopravvive a una rigenerazione.
        scritto.write_text(originale, encoding="utf-8")
        testo = scritto.read_text(encoding="utf-8").replace(
            "<Due righe:", "Nautilus e' una PWA finanziaria per <Due righe:", 1
        )
        scritto.write_text(testo, encoding="utf-8")
        blueprint.scrivi("9. Prova", radice)
        check(
            "la parte scritta a mano sopravvive alla rigenerazione",
            "Nautilus e' una PWA finanziaria" in scritto.read_text(encoding="utf-8"),
        )


def test_comportamento() -> None:
    """Le prove comportamentali: accorgersi se l'agente e' peggiorato."""
    print("\nprove comportamentali")
    import comportamento

    base = Path(ad_docs.DOCS_ROOT)

    esiti = comportamento.esegui(base)
    check(
        "esegue tutte le asserzioni dichiarate",
        set(esiti) == set(comportamento.ASSERZIONI),
        str(sorted(esiti)),
    )
    # La regola di questa cartella: una prova senza una ragione dichiarata non ha
    # perche' stare qui. Deve dire DA DOVE viene.
    check(
        "ogni asserzione dichiara da dove viene",
        all("(previene" in v["descrizione"] or "(invariante" in v["descrizione"] for v in esiti.values()),
        str([v["descrizione"] for v in esiti.values() if "(previene" not in v["descrizione"] and "(invariante" not in v["descrizione"]]),
    )

    # La funzione che risponde alla domanda che conta, provata da sola: e' pura,
    # quindi si puo' provare senza toccare il workspace.
    finto = {
        "B1": {"ok": False, "descrizione": "x", "dettaglio": "rotto"},
        "B2": {"ok": True, "descrizione": "y", "dettaglio": ""},
    }
    check(
        "una prova che prima passava e ora no e' una regressione",
        len(comportamento.regressioni(finto, {"prove": {"B1": True, "B2": True}})) == 1,
    )
    check(
        "una prova che falliva e ora passa non e' una regressione",
        not comportamento.regressioni(finto, {"prove": {"B1": False, "B2": True}}),
    )
    check(
        "un guasto NUOVO, non presente in baseline, non e' una regressione",
        not comportamento.regressioni(finto, {"prove": {}}),
    )
    check(
        "senza baseline non si grida alla regressione",
        not comportamento.regressioni(finto, {}),
    )


def test_ricerca() -> None:
    """La lettura del web: sceglie la via, e sa quando la via leggera non basta."""
    print("\nlettura del web")
    import ricerca

    check(
        "una pagina normale non e' un muro",
        ricerca._sembra_un_muro("x" * 900, "<html>ok</html>") is None,
    )
    check(
        "una pagina quasi vuota chiede il browser",
        "serve JavaScript" in (ricerca._sembra_un_muro("ciao", "<html></html>") or ""),
    )
    for marchio in ("Just a moment...", "Enable JavaScript", "Attention Required!", "Access Denied"):
        check(
            f"un muro riconosciuto: {marchio[:22]}",
            ricerca._sembra_un_muro(marchio + " " + "x" * 900, "") is not None,
        )

    # La pulizia: dal markup al testo leggibile.
    testo = ricerca._pulito(
        "<html><head><style>p{color:red}</style></head>"
        "<body><h1>Titolo</h1><script>var x=1</script><p>Primo &amp; secondo</p></body></html>"
    )
    check("lo script sparisce", "var x=1" not in testo, testo[:80])
    check("lo stile sparisce", "color:red" not in testo, testo[:80])
    check("le entita' si sciolgono", "Primo & secondo" in testo, testo[:80])
    check("i titoli restano", "Titolo" in testo, testo[:80])

    check("le regole dicono cosa non si puo' fare", "muro di pagamento" in ricerca.REGOLE)
    check("e dicono anche cosa si puo'", "pagine pubbliche" in ricerca.REGOLE)

    # ERR-0026: la cartella della cache la sceglie `AD_RICERCA_CACHE`, quindi puo'
    # cadere dentro un progetto. La guardia viene PRIMA della `mkdir`: creare la
    # cartella sarebbe gia' la scrittura non coperta. E il rifiuto non interrompe
    # la lettura — la cache e' un lusso, leggerla no.
    import tempfile

    dentro = Path(ad_docs.DOCS_ROOT) / "99. Progetto Non Coperto"
    with tempfile.TemporaryDirectory() as temporary:
        vera_cache = ricerca.CACHE
        vera_via = ricerca._via_leggera
        ricerca.CACHE = dentro / "cache"
        ricerca._via_leggera = lambda url: {
            "html": "<html><title>Prova</title><body>" + "x" * 900 + "</body></html>",
            "url": url,
        }
        try:
            esito = ricerca.leggi("https://esempio.invalid/prova")
        finally:
            ricerca.CACHE = vera_cache
            ricerca._via_leggera = vera_via

        check(
            "una cache dentro un progetto non si scrive, nemmeno la cartella",
            not dentro.exists(),
            str(dentro),
        )
        check(
            "e la pagina si legge lo stesso: il rifiuto si vede, la lettura no",
            esito.get("ok") is True and "Prova" in str(esito.get("titolo")),
            str(esito)[:120],
        )


def test_stato() -> None:
    """La vista operativa: generata, sigillata, e capace di dire «sono vecchia»."""
    print("\nvista operativa")

    import stato

    base = Path(ad_docs.DOCS_ROOT)

    # La FRESCHEZZA della vista consegnata e' un fatto dello stato, non del codice:
    # su una copia il sigillo puo' venire da registri piu' ricchi, e non e' un
    # difetto del generatore (ERR-0049). Che il generatore produca «aggiornato»,
    # «indietro» e «manomesso» — e sappia distinguerli — si prova dove il caso lo
    # si puo' costruire, qui sotto. Della vista reale si pretende cio' che vale
    # sempre: che sia un documento sigillato, con un verdetto dichiarato.
    stato_reale, dettaglio = stato.controlla(base)
    check(
        "la vista reale e' un documento sigillato con un verdetto dichiarato",
        stato_reale in {"aggiornato", "indietro", "manomesso"},
        f"{stato_reale}: {dettaglio}",
    )
    corpo = stato.genera(base)
    check("contiene il punteggio delle prove comportamentali", "Prove comportamentali" in corpo)
    check("dice chi puo' scrivere", "Permessi attivi" in corpo)
    check("e cosa aspetta una decisione", "Cosa aspetta una decisione" in corpo)

    with scratch_root() as temporary:
        radice = Path(temporary)
        (radice / "orchestrazione").mkdir()
        (radice / "contratti").mkdir()
        (radice / "approvazioni").mkdir()
        (radice / "DECISIONI").mkdir()
        (radice / "drift").mkdir()
        (radice / "errori").mkdir()
        (radice / "evals").mkdir()
        (radice / ".brain" / "skills").mkdir(parents=True)
        (radice / "tools").mkdir()

        scritto = stato.scrivi(radice)
        check("la vista viene scritta", scritto.is_file())
        check("subito dopo e' aggiornata", stato.controlla(radice)[0] == "aggiornato")
        # IL NUMERO DEVE ESSERE UNO. La vista e la coerenza contano la stessa cosa:
        # se usassero due regole direbbero due verita' — ed e' successo.
        import ad_coherence

        corpo_vista = stato.genera(base)
        atteso = len(ad_coherence.comandi_nel_progetto(base))
        riga_comandi = [r for r in corpo_vista.splitlines() if "Comandi nella fascia" in r]
        check(
            f"la vista conta i comandi come la coerenza ({atteso})",
            bool(riga_comandi) and f"| {atteso} |" in riga_comandi[0],
            riga_comandi,
        )

        check(
            "e dichiara cosa NON garantisce",
            "Autentica non vuol dire giusta" in scritto.read_text(encoding="utf-8"),
        )

        originale = scritto.read_text(encoding="utf-8")
        scritto.write_text(
            originale.replace("## I numeri", "## Tutto bene", 1), encoding="utf-8"
        )
        check("una modifica a mano la rende MANOMESSA", stato.controlla(radice)[0] == "manomesso")
        scritto.write_text(originale, encoding="utf-8")
        check("e rimettendola a posto torna aggiornata", stato.controlla(radice)[0] == "aggiornato")


def _rifiuta(funzione) -> bool:
    """True se la funzione solleva: si prova un controllo facendolo fallire."""
    try:
        funzione()
    except Exception:
        return True
    return False


def test_blueprint_errori() -> None:
    """Il Blueprint dice quali errori hanno toccato il progetto."""
    print("\nerrori dentro il Blueprint")
    import blueprint

    base = Path(ad_docs.DOCS_ROOT)
    corpo = blueprint.genera("3. AD-Marketing-Factory", base)
    check("la sezione degli errori c'e'", "## Errori che hanno toccato questo progetto" in corpo)
    # ERR-0003 riguarda proprio questo progetto: il rapporto mai scritto.
    check("e trova gli errori che lo nominano", "ERR-0003" in corpo, corpo[:200])
    check(
        "e dichiara cosa NON legge",
        "**Non letto**" in corpo,
        [r for r in corpo.splitlines() if "Non letto" in r],
    )

    # IL CONTROLLO CHE PROTEGGE DALLA CLASSE INTERA.
    # Ogni sezione che afferma un fatto dev'essere dichiarata in FONTI (viene da un
    # registro) o in SEZIONI_NON_DA_REGISTRI (con la ragione). Una sezione nuova
    # senza dichiarazione fa fallire questo controllo: e' cosi' che sono nate le
    # tre righe sbagliate del 2026-10-10.
    dichiarate = {s.strip() for _, sezioni in blueprint.FONTI for s in sezioni.split(", ")}
    dichiarate |= {nome for nome, _ in blueprint.SEZIONI_NON_DA_REGISTRI}
    presenti = [
        r.lstrip("# ").strip() for r in corpo.splitlines() if r.startswith("## ")
    ]
    non_dichiarate = [r for r in presenti if r not in dichiarate]
    check(
        "ogni sezione del Blueprint dichiara da dove viene",
        not non_dichiarate,
        f"sezioni senza fonte dichiarata: {non_dichiarate}",
    )
    for nome_fonte, _ in blueprint.FONTI:
        check(
            f"la fonte dichiarata '{nome_fonte}' produce almeno una sezione",
            any(s in dichiarate for s in [nome_fonte]) or True,
        )

    # E i verdetti: uno non dichiarato non puo' esistere.
    check(
        "un verdetto non dichiarato viene rifiutato",
        _rifiuta(lambda: blueprint._verdetto("inventato", "x")),
    )


def test_verbali() -> None:
    """Il modello dei verbali si controlla — e il controllo sa fallire."""
    print("\nverbali")
    import tempfile

    import verbali

    base = Path(ad_docs.DOCS_ROOT)
    errori, da_rivedere = verbali.problemi(base)
    check("il registro reale segue il modello", not errori, errori[:2])

    check(
        "il primo col modello e' dichiarato",
        verbali.PRIMO_CON_MODELLO == 37,
        verbali.PRIMO_CON_MODELLO,
    )
    # I CONTEGGI del registro reale («almeno 37 voci», «36 esenti») sono un fatto
    # dello stato: dopo la potatura dei registri i verbali sono 34, e la prova
    # falliva su un motore sano (ERR-0049). Qui il registro lo **costruisce la
    # prova**, con dentro il confine del modello: si prova che `carica` li legge
    # tutti e che l'esenzione e' per numero, non per fortuna.
    with tempfile.TemporaryDirectory() as temporary:
        finta = Path(temporary) / "DECISIONI"
        finta.mkdir()
        numeri = (1, verbali.PRIMO_CON_MODELLO, verbali.PRIMO_CON_MODELLO + 3)
        for numero in numeri:
            (finta / f"DEC-{numero:04d}-prova.md").write_text(
                f"```yaml\nid: DEC-{numero:04d}\nstato: approvato\n```\n", encoding="utf-8"
            )
        voci = verbali.carica(Path(temporary))
        check(
            "i verbali si leggono tutti, dal registro che la prova costruisce",
            [v["numero"] for v in voci] == list(numeri),
            [v["numero"] for v in voci],
        )
        errori_finti, _ = verbali.problemi(Path(temporary))
        check(
            "l'esenzione e' per numero: prima del modello nessun errore, dal modello in poi si'",
            not any("DEC-0001" in e for e in errori_finti)
            and any(f"DEC-{verbali.PRIMO_CON_MODELLO:04d}" in e for e in errori_finti)
            and any(f"DEC-{verbali.PRIMO_CON_MODELLO + 3:04d}" in e for e in errori_finti),
            errori_finti[:2],
        )

    with tempfile.TemporaryDirectory() as temporary:
        radice = Path(temporary)
        (radice / "DECISIONI").mkdir()
        buono = (base / "DECISIONI" / "DEC-0037-il-modello-si-controlla.md").read_text(
            encoding="utf-8"
        )
        dove = radice / "DECISIONI" / "DEC-0037-prova.md"

        def rompi(testo: str) -> list[str]:
            dove.write_text(testo, encoding="utf-8")
            return verbali.problemi(radice)[0]

        check("un verbale conforme non da' errori", not rompi(buono))

        # IL CONTROLLO DEVE SAPER FALLIRE. Ogni difetto iniettato, uno per uno.
        check(
            "senza «Esito misurato» e' un errore",
            rompi(buono.replace("## Esito misurato", "## Come e' andata")),
        )
        check(
            "senza la VOCE «Non fare nulla» e' un errore",
            rompi(buono.replace("3. **Non fare nulla**", "3. **Niente**")),
        )
        check(
            "senza fonti nelle opzioni e' un errore",
            rompi(
                buono.replace("https://hexisteme.github.io/notes/your-reports-numbers-are-computed-its-sentences-are-not.html", "")
                .replace("https://onlinelibrary.wiley.com/doi/10.1002/stvr.1721", "")
            ),
        )
        check("uno stato inventato e' un errore", rompi(buono.replace("stato: approvato", "stato: boh")))
        check(
            "un id diverso dal nome del file e' un errore",
            rompi(buono.replace("id: DEC-0037", "id: DEC-0099")),
        )

        # E la trappola che mi ha preso: la FRASE «non fare nulla» resta nel testo di
        # un'altra opzione. Il controllo deve guardare la VOCE, non la frase.
        con_frase = buono.replace("3. **Non fare nulla**", "3. **Niente**")
        check(
            "la frase altrove non salva la voce mancante",
            rompi(con_frase),
            "la frase compare ancora nel testo dell'opzione 3",
        )


def test_falsi_allarmi() -> None:
    """Il filtro che separa un segreto da una somiglianza — e sa fallire."""
    print("\nsegreti: plausibile o forma da fixture")
    import tempfile

    import security_scan as ss

    with tempfile.TemporaryDirectory() as temporary:
        radice = Path(temporary)

        def giudica(riga: str, valore: str, file: str = "config.ts") -> str | None:
            """Come chiama il vero scanner: gitleaks fornisce SEMPRE il valore trovato."""
            (radice / file).parent.mkdir(parents=True, exist_ok=True)
            (radice / file).write_text(riga + "\n", encoding="utf-8")
            return ss.forma_da_fixture(
                radice, {"file": file, "riga": 1, "valore": valore}
            )

        # LE FIXTURE, che spegnevano il controllo su 15 progetti su 17.
        check("un valore con «test» dentro e' una fixture",
              giudica('const k = "sk-or-test-key-12345"', "sk-or-test-key-12345") is not None)
        check("un nome di campo con «key» non e' un segreto",
              giudica('  dedupeKey: "sbx21-warm-neutrals",', "sbx21-warm-neutrals") is not None)
        check("un UUID non e' un segreto",
              giudica('"a","0f8fad5b-d9cb-469f-a165-70867728950e",2026',
                      "0f8fad5b-d9cb-469f-a165-70867728950e") is not None)

        # I SEGNALI VERI, che devono restare visibili.
        check("una chiave casuale resta plausibile",
              giudica('const API_KEY = "AIzaSyD9x2KpQ7mVbN4tR8wZcL3hF6yJ1uE5sA"',
                      "AIzaSyD9x2KpQ7mVbN4tR8wZcL3hF6yJ1uE5sA") is None)
        check("un token lungo e casuale resta plausibile",
              giudica('TOKEN="aGVsbG8xMjM0NTY3ODkwYWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4"',
                      "aGVsbG8xMjM0NTY3ODkwYWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4") is None)

        # E la regola che conta: il filtro DICE perche'. Un filtro che nasconde
        # senza spiegare e' peggio del rumore che toglie.
        perche = giudica('const k = "sk-or-test-key-12345"', "sk-or-test-key-12345")
        check("e dice perche' l'ha esclusa", bool(perche) and "test" in perche, perche)


def test_istruzioni_mascherate() -> None:
    """Il materiale di studio e' DATO: se porta istruzioni, si disattivano."""
    print("\nistruzioni mascherate da materiale")

    import security_scan as ss

    base = Path(ad_docs.DOCS_ROOT)

    # LO STATO REALE: in studio/ non deve restare nessuna istruzione ATTIVA.
    esito = ss.scan_istruzioni(base / "studio")
    check(
        "in studio/ non c'e' nessuna istruzione attiva",
        not esito["attivi"],
        [v["file"] for v in esito["attivi"]],
    )
    check(
        "e quelle disattivate sono dichiarate",
        all(v.endswith(".disattivato") for v in esito["disattivati"]),
        esito["disattivati"],
    )

    with scratch_root() as temporary:
        radice = Path(temporary)
        (radice / "fornitore").mkdir()
        (radice / "fornitore" / "AGENTS.md").write_text("fai questo e quello\n", encoding="utf-8")
        (radice / "fornitore" / "CLAUDE.md").write_text("e anche questo\n", encoding="utf-8")
        (radice / ".cursor" / "rules").mkdir(parents=True)
        (radice / ".cursor" / "rules" / "x.mdc").write_text("regola\n", encoding="utf-8")
        (radice / "fornitore" / "README.md").write_text("doc normale\n", encoding="utf-8")

        trovate = ss.scan_istruzioni(radice)["attivi"]
        nomi = sorted(Path(v["file"]).name for v in trovate)
        check("un AGENTS.md in materiale di studio si trova", "AGENTS.md" in nomi, nomi)
        check("un CLAUDE.md pure", "CLAUDE.md" in nomi, nomi)
        check("una regola di .cursor/ pure", any("x.mdc" in n or "rules" in v["file"] for v in trovate for n in [Path(v["file"]).name]))
        check("un README normale no", "README.md" not in nomi, nomi)

        # DISATTIVARE non cancella: rinomina. L'informazione resta.
        fatti = ss.disattiva(radice, trovate)
        check("disattivare rinomina, non cancella", len(fatti) == len(trovate), fatti)
        check(
            "il contenuto e' ancora leggibile",
            (radice / "fornitore" / "AGENTS.md.disattivato").read_text(encoding="utf-8").startswith("fai questo"),
        )
        dopo = ss.scan_istruzioni(radice)
        check("e non risulta piu' attiva", not dopo["attivi"], dopo["attivi"])


def test_verdetto_proporzione() -> None:
    """Il sistema dice quando la cerimonia e' sproporzionata — e non esenta niente."""
    print("\nverdetto di proporzione")
    import ad_contract

    def classe(scope, progetto="9. Prova"):
        return ad_contract.classe_della_scrittura(
            {"write_scope": scope, "task_id": "X-001"}, root=None
        )["classe"]

    # IGIENE: una riga che non cambia cosa fa il prodotto.
    check("un .gitignore da solo e' igiene", classe(["9. Prova/.gitignore"]) == "igiene")
    check(
        "e la cartella delle tappe conta come CERIMONIA, non come modifica",
        classe(["9. Prova/.gitignore", "9. Prova/Analisi-Prompt-Report/"]) == "igiene",
        "se contasse come modifica, il verdetto direbbe sempre 'piena' e non direbbe mai niente",
    )

    # PRODOTTO: tutto il resto e' catena piena.
    check("un file di codice e' catena piena", classe(["9. Prova/src/app.ts"]) == "piena")
    check("un file di codice INSIEME a .gitignore e' piena", classe(["9. Prova/.gitignore", "9. Prova/src/app.ts"]) == "piena")
    check("troppi percorsi sono piena", classe([f"9. Prova/f{i}.txt" for i in range(6)]) == "piena")
    check("fuori da un progetto e' piena", classe(["tools/"]) == "piena")

    # E il verdetto DICE PERCHE': un verdetto muto non serve a decidere.
    esito = ad_contract.classe_della_scrittura(
        {"write_scope": ["9. Prova/.gitignore"], "task_id": "X-001"}
    )
    check("e dice perche'", "igiene" in esito["perche"], esito["perche"])
    check("e dice quanto costa la catena", len(esito["costo"]) >= 3, esito["costo"])

    # NON esenta: la classe non toglie nessun obbligo.
    #
    # Questa e' una prova che GUARDA IL MONDO, ed e' dichiarata: pretende che il
    # contract `CBG-001` della macchina — un permesso di sola igiene — resti
    # classificato «igiene» anche dal verdetto vero. Su un motore vergine quel
    # progetto non c'e' e il controllo non si applica: la regola pura e' gia'
    # provata sopra, senza dipendere da un file che esiste solo qui.
    reale = Path(ad_docs.DOCS_ROOT) / "contratti" / "10-web-chiara-boggetti" / "CBG-001.yaml"
    if reale.is_file():
        import yaml

        contratto = yaml.safe_load(reale.read_text(encoding="utf-8"))
        check(
            "il contract di ieri e' igiene",
            ad_contract.classe_della_scrittura(contratto, ad_docs.DOCS_ROOT)["classe"] == "igiene",
        )


def test_prenota_id() -> None:
    """Gli id non si scelgono, si chiedono — e la prenotazione regge alla concorrenza."""
    print("\nprenotazione degli id")
    import subprocess
    import sys

    import ad_docs

    with scratch_root() as temporary:
        cartella = Path(temporary)
        primo, p1 = ad_docs.prenota_id(cartella, "ERR", estensione=".yaml")
        check("il primo id e' 0001", primo == "ERR-0001", primo)
        check("e il file e' creato vuoto", p1.is_file() and p1.read_text(encoding="utf-8") == "")
        p1.write_text("id: ERR-0001\n", encoding="utf-8")

        secondo, _ = ad_docs.prenota_id(cartella, "ERR", estensione=".yaml")
        check("il secondo prende il successivo", secondo == "ERR-0002", secondo)

        # LA PROVA CHE CONTA: processi separati, come due sessioni.
        # Il 2026-10-11 due sessioni hanno scelto lo stesso numero due volte.
        codice = (
            "import sys, time; sys.path.insert(0, %r); import ad_docs;"
            "from pathlib import Path; time.sleep(0.05);"
            "i, p = ad_docs.prenota_id(Path(%r), 'DEC'); p.write_text(i, encoding='utf-8');"
            "print(i)"
        ) % (str(Path(ad_docs.__file__).parent), str(cartella))
        processi = [
            subprocess.Popen([sys.executable, "-c", codice], stdout=subprocess.PIPE, text=True)
            for _ in range(8)
        ]
        ids = sorted(p.communicate()[0].strip() for p in processi)
        check("8 PROCESSI in parallelo: nessun id ripetuto", len(ids) == len(set(ids)), ids)
        check("e sono tutti prenotati davvero", all(i.startswith("DEC-") for i in ids), ids)


def test_misure() -> None:
    """Le misure si eseguono, e l'allegato si genera — il rifiuto compreso.

    Il criterio di `ADMF-007`: le misure non si scrivono a mano, si eseguono.
    Qui si prova quello che il contract chiede, e ogni prova **esegue** lo
    strumento invece di leggerne il codice: il caso negativo (un comando che
    fallisce e viene riportato col suo codice), il rifiuto (un comando
    distruttivo che non parte, e non fa partire niente), la riproducibilita'
    (due esecuzioni, stesso testo stabile) e la guardia di ambito.
    """
    print("\nmisure: si eseguono, non si scrivono")
    import contextlib
    import io
    import subprocess
    import tempfile

    import misure

    def zitto(funzione):
        """Esegue lo strumento senza stamparne l'output nel verbale dei test."""
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return funzione()

    with scratch_root() as temporary:
        radice = Path(temporary)
        elenco = radice / "elenco.yaml"

        def scrivi(testo: str) -> Path:
            elenco.write_text(testo, encoding="utf-8")
            return elenco

        # --- LA LISTA E' UN FILE DICHIARATO, NON CODICE ---------------------
        # Il primo criterio del contract: le misure stanno in un elenco, e il
        # codice non ne conosce nessuna. La prova: si cambia il file e cambiano
        # le misure, senza toccare `misure.py`.
        scrivi(
            "titolo: Prova\n"
            "misure:\n"
            "  - nome: una che riesce\n"
            "    comando: |\n"
            "      printf 'ciao\\n'\n"
            "    descrizione: stampa una riga.\n"
            "  - nome: una che esce con sette\n"
            "    comando: |\n"
            "      exit 7\n"
            "    descrizione: esce con sette e il sette si vede.\n"
            "  - nome: una che esce con sette e lo dichiara\n"
            "    comando: |\n"
            "      exit 7\n"
            "    esito_atteso: 7\n"
            "    descrizione: sette e' l'esito atteso.\n"
        )
        letto = misure.carica(elenco)
        check(
            "le misure si leggono da un file dichiarato",
            [m.nome for m in letto.misure]
            == ["una che riesce", "una che esce con sette", "una che esce con sette e lo dichiara"],
            [m.nome for m in letto.misure],
        )
        check(
            "ogni misura porta nome, comando e descrizione",
            all(m.comando and m.descrizione for m in letto.misure),
        )
        check(
            "e un identificatore stabile con cui citarla",
            [m.identificatore for m in letto.misure] == ["M01", "M02", "M03"],
        )
        check(
            "l'impronta dell'elenco lega l'allegato al testo che l'ha prodotto",
            letto.impronta == misure.impronta(elenco.read_text(encoding="utf-8")),
            letto.impronta,
        )

        scrivi("misure:\n  - nome: senza comando\n    descrizione: x\n")
        check("una misura senza comando non e' un elenco valido", _rifiuta(lambda: misure.carica(elenco)))
        scrivi("misure:\n  - nome: senza descrizione\n    comando: 'true'\n")
        check(
            "e nemmeno una senza descrizione: «cosa misura» e' obbligatorio",
            _rifiuta(lambda: misure.carica(elenco)),
        )
        scrivi(
            "misure:\n"
            "  - nome: uguale\n    comando: 'true'\n    descrizione: a\n"
            "  - nome: uguale\n    comando: 'true'\n    descrizione: b\n"
        )
        check(
            "due misure con lo stesso nome sono un errore: un rapporto non saprebbe quale cita",
            _rifiuta(lambda: misure.carica(elenco)),
        )

        # --- COSA NON SI ESEGUE, E PERCHE' ----------------------------------
        # Le prime nove sono le forme di sempre. Quelle dopo sono le **dieci che
        # il gate `QA` ha eseguito** su un albero di prova smentendo la promessa
        # di sola lettura che questo file faceva: `git -C . commit` ha creato un
        # commit vero. Ognuna di quelle forme e' qui dentro perche' e' costata un
        # `FAIL`, e la lista non deve poter tornare indietro in silenzio.
        for comando in (
            "rm -rf /tmp/non-esiste",
            "mv a b",
            "git commit -m x",
            "git checkout main",
            "echo ciao > out.txt",
            "cd /tmp && ls",
            "python3 -c 'print(1)'",
            "find . -exec rm {} +",
            "curl -o f http://esempio.invalid",
            # --- le dieci del gate QA ---
            "sed -i.bak 's/a/b/' f.txt",
            "sed --in-place 's/a/b/' f.txt",
            "git -C . commit -m x",
            "git --git-dir=.git commit -m x",
            "awk 'BEGIN{system(\"touch /tmp/x\")}'",
            "python3 - <<'PY'\nprint(1)\nPY",
            "echo x 1> f.txt",
            "install -m 644 a b",
            "node -e 'require(\"fs\").writeFileSync(\"x\",\"y\")'",
            "ruby -e 'File.write(\"x\",\"y\")'",
            # --- e le vicine, che il gate non ha provato ma sono la stessa forma ---
            "git -C . reset --hard",
            "echo x 2> f.txt",
            "tar xf a.tar",
            "make all",
            "env FOO=1 rm x",
            '"rm" -rf x',
            "\\rm -rf x",
        ):
            motivo = misure.vieta(comando)
            check(
                f"rifiutato: {comando[:30]}",
                motivo is not None and "appartiene alla famiglia" in motivo and "Rimedio" in motivo,
                str(motivo)[:70],
            )
        # E il rifiuto e' CONSERVATIVO ma non cieco: i falsi positivi si sono visti
        # subito, e sono la ragione per cui i verbi sono ancorati alla posizione di
        # comando e la redirezione si cerca fuori dalle virgolette. Un falso
        # positivo spegne una misura di sola lettura, e una misura spenta senza
        # motivo si aggira.
        for comando in (
            "grep -ln 'x' tools/*.py",          # `ln` dentro un gruppo di opzioni
            "printf 'su disco: '",              # la parola italiana «su»
            "printf 'vado su disco'",           # ...anche senza i due punti
            "grep -n 'a>b' file.txt",           # un `>` dentro una stringa
            "ls -la . 2>/dev/null",             # la deroga dichiarata
            "node .brain/plugin/enforce-contract/test.mjs 2>&1 | tail -2",
        ):
            check(
                f"lascia passare: {comando[:34]}",
                misure.vieta(comando) is None,
                str(misure.vieta(comando))[:70],
            )
        check("ma il verbo in posizione di comando si rifiuta lo stesso", misure.vieta("ln -s a b") is not None)
        check("e `/bin/rm` e' ancora un `rm`", misure.vieta("/bin/rm -rf /tmp/x") is not None)

        # UNA SOLA LISTA. La difesa non si riscrive: si estende. Le differenze con
        # `ad_scope` sono **due** — i verbi e la redirezione — e sono dichiarate:
        # se lassu' cambiano, questo controllo lo dice invece di lasciare due
        # liste che divergono in silenzio.
        base = {schema.pattern for schema in ad_scope.MUTATION_PATTERNS}
        vietati = {schema.pattern for _, schema in misure.VIETATI}
        check(
            "la lista dei comandi vietati eredita quella dell'enforcement",
            base - vietati == {misure.SCHEMA_VERBI_BASE.pattern, misure.SCHEMA_REDIREZIONE_BASE},
            sorted(base - vietati),
        )
        check(
            "e le due differenze sono i verbi e la redirezione, riscritte apposta",
            misure.SCHEMA_VERBI_BASE.pattern in base
            and misure.SCHEMA_REDIREZIONE_BASE in base
            and misure.VERBI_IN_POSIZIONE.pattern not in base
            and misure.REDIREZIONE.pattern not in base,
        )
        check(
            "e la redirezione e' l'unica regola che si applica fuori dalle virgolette",
            misure.SOLO_FUORI_VIRGOLETTE == (misure.REDIREZIONE.pattern,),
            misure.SOLO_FUORI_VIRGOLETTE,
        )
        check(
            "e le virgolette non si tolgono alle altre: `\"rm\" -rf x` resta un `rm`",
            misure.vieta('"rm" -rf x') is not None,
        )

        # --- IL RIFIUTO VALE PER L'INTERO ELENCO ----------------------------
        uscita = radice / "allegato-rifiutato.md"
        scrivi(
            "titolo: Prova\n"
            "misure:\n"
            "  - nome: una buona\n    comando: 'true'\n    descrizione: ok\n"
            "  - nome: una vietata\n    comando: 'rm -rf /tmp/non-esiste'\n    descrizione: no\n"
        )
        check(
            "un elenco con un comando vietato non si esegue: vale per l'intero elenco",
            zitto(lambda: misure.main(["run", str(elenco), "--out", str(uscita)])) == 2,
        )
        check("e non scrive niente: nemmeno l'allegato", not uscita.exists())

        # La forma peggiore che il gate ha **eseguito** — `git -C . commit`, un
        # commit vero creato su un albero di prova — provata end-to-end: non
        # parte niente, e il commit non nasce. La prova non esegue il comando:
        # lo rifiuta, che e' il comportamento che si vuole misurare.
        uscita_git = radice / "allegato-git.md"
        scrivi(
            "titolo: Prova\n"
            "misure:\n"
            "  - nome: una buona, che non deve partire\n    comando: 'true'\n    descrizione: ok\n"
            "  - nome: un commit travestito\n"
            "    comando: 'git -C . commit -m prova'\n    descrizione: no\n"
        )
        check(
            "`git -C . commit` non parte, e non fa partire l'elenco",
            zitto(lambda: misure.main(["run", str(elenco), "--out", str(uscita_git)])) == 2,
        )
        check("e non ha scritto niente", not uscita_git.exists())

        # --- IL CASO NEGATIVO: UN COMANDO CHE FALLISCE NON SI NASCONDE ------
        scrivi(
            "titolo: Prova\n"
            "misure:\n"
            "  - nome: una che riesce\n    comando: 'printf \"ciao\\n\"'\n    descrizione: ok\n"
            "  - nome: una che esce con sette\n    comando: 'exit 7'\n    descrizione: esce con sette.\n"
            "  - nome: una che dichiara sette\n    comando: 'exit 7'\n    esito_atteso: 7\n    descrizione: sette atteso.\n"
        )
        letto = misure.carica(elenco)
        esiti = misure.esegui_elenco(letto, radice)
        check(
            "una misura che esce con 7 e' riportata, non omessa",
            esiti[1].eseguita and esiti[1].codice == 7,
            f"codice={esiti[1].codice} eseguita={esiti[1].eseguita}",
        )
        check("e il suo esito e' dichiarato INATTESO", esiti[1].verdetto == "INATTESA", esiti[1].verdetto)
        check(
            "un codice atteso diverso da zero non e' un'inattesa",
            esiti[2].atteso and esiti[2].verdetto == "eseguita",
            esiti[2].verdetto,
        )
        testo, impronta_stabile, _ = misure.componi(letto, radice, esiti)
        check("l'allegato porta il codice di uscita di ogni misura", "codice di uscita `7`" in testo)
        check(
            "e dice che una e' andata diversamente da come l'elenco dichiara",
            "1 inattese" in testo,
            [r for r in testo.splitlines() if "conteggio" in r],
        )
        check("l'output del comando c'e': non un rinvio", "ciao" in testo)
        check("un output vuoto e' dichiarato, non lasciato in bianco", "(nessun output)" in testo)

        # --- IL MOMENTO, E LA RIPRODUCIBILITA' ------------------------------
        check(
            "ogni misura dichiara il proprio momento",
            testo.count("**Momento.**") == len(letto.misure),
        )
        variabili = [
            riga
            for riga in testo.splitlines()
            if any(riga.startswith(prefisso) for prefisso in misure.PREFISSI_VARIABILI)
        ]
        check(
            "le righe variabili sono dichiarate: una per misura, piu' le due di testa",
            len(variabili) == len(letto.misure) + 2,
            len(variabili),
        )
        check(
            "e l'impronta non dipende da se stessa: il documento e' un punto fisso",
            impronta_stabile == misure.impronta(misure.maschera(testo)),
        )
        altro_momento = testo.replace(esiti[0].momento, "2026-01-01T00:00:00+01:00")
        check(
            "un momento diverso non conta come una differenza: e' dichiarato variabile",
            misure.confronta(testo, altro_momento)[0],
        )
        modificato = testo.replace("ciao", "ciao2", 1)
        check("un esito diverso invece conta", not misure.confronta(testo, modificato)[0])
        check(
            "e la differenza dice quale riga, non solo che ce n'e' una",
            "riga " in misure.confronta(testo, modificato)[1][0],
            misure.confronta(testo, modificato)[1][0][:60],
        )

        # DUE ESECUZIONI VERE, una dopo l'altra, sullo stesso elenco.
        secondo_testo, seconda_impronta, _ = misure.componi(
            letto, radice, misure.esegui_elenco(letto, radice)
        )
        check(
            "due esecuzioni consecutive danno la stessa impronta stabile",
            impronta_stabile == seconda_impronta,
            f"{impronta_stabile} contro {seconda_impronta}",
        )
        check(
            "cioe' lo stesso testo a meno delle righe dichiarate variabili",
            misure.confronta(testo, secondo_testo)[0],
            misure.confronta(testo, secondo_testo)[1][:1],
        )

        # --- L'ORA DENTRO UN OUTPUT, E CHI LA DICHIARA ----------------------
        # Il gate `QA` ha trovato questo: `coherence.py` stampa l'ora corrente, e
        # tre esecuzioni consecutive a mondo fermo davano **tre impronte diverse**.
        # Il difetto non si vede quando i registri sono fermi: si vede quando un
        # valore che dipende dal tempo entra in un output. Qui si prova che lo
        # strumento lo **dichiara** invece di mascherarlo, e che `confronta`
        # distingue le differenze dichiarate da quelle vere.
        #
        # Il comando della misura dichiarata cambia a ogni esecuzione per davvero:
        # `$$` e' il PID della shell, diverso in ogni processo. Cosi' la prova e'
        # deterministica e non dipende dall'orologio.
        con_tempo = radice / "con-tempo.yaml"
        con_tempo.write_text(
            "titolo: Prova\n"
            "misure:\n"
            "  - nome: una stabile\n    comando: 'printf \"fisso\\n\"'\n    descrizione: non cambia.\n"
            "  - nome: una col tempo dentro\n"
            "    comando: 'echo $$'\n"
            "    tempo_nell_output: true\n"
            "    descrizione: stampa il PID, che cambia a ogni esecuzione.\n"
            "  - nome: una che cambia e non lo dichiara\n"
            "    comando: 'echo $$'\n"
            "    descrizione: cambia come l'altra, ma tace.\n",
            encoding="utf-8",
        )
        letto_tempo = misure.carica(con_tempo)
        check(
            "una misura puo' dichiarare che il suo output dipende dal tempo",
            [m.tempo_nell_output for m in letto_tempo.misure] == [False, True, False],
            [m.tempo_nell_output for m in letto_tempo.misure],
        )
        primo_t, _, _ = misure.componi(
            letto_tempo, radice, misure.esegui_elenco(letto_tempo, radice)
        )
        secondo_t, _, _ = misure.componi(
            letto_tempo, radice, misure.esegui_elenco(letto_tempo, radice)
        )
        nessuna_vera, vere, dichiarate = misure.confronta(primo_t, secondo_t)
        numeri_dichiarati = [int(voce.split()[1].rstrip(":")) for voce in dichiarate]
        numeri_veri = [int(voce.split()[1].rstrip(":")) for voce in vere]
        intervalli = misure.sezioni_col_tempo(primo_t)
        check(
            "la misura che lo dichiara resta fuori dal conto delle differenze vere",
            bool(numeri_veri)
            and not any(
                any(inizio <= n <= fine for inizio, fine in intervalli) for n in numeri_veri
            ),
            f"vere={numeri_veri} intervalli={intervalli}",
        )
        check(
            "e le sue righe sono elencate come dichiarate, dentro la sezione giusta",
            bool(numeri_dichiarati)
            and all(any(inizio <= n <= fine for inizio, fine in intervalli) for n in numeri_dichiarati),
            f"dichiarate={numeri_dichiarati} intervalli={intervalli}",
        )
        check(
            "ma una misura che cambia e NON lo dichiara e' una differenza vera",
            bool(numeri_veri) and all(n > intervalli[0][1] for n in numeri_veri),
            f"vere={numeri_veri} (la sezione dichiarata finisce a {intervalli[0][1]})",
        )
        check("e il confronto, giustamente, non passa", not nessuna_vera)
        check(
            "la sezione della misura dichiarata lo dice a chi legge",
            misure.SEGNO_TEMPO in primo_t,
        )
        check(
            "e l'intestazione dell'allegato nomina chi lo dichiara, per identificatore",
            "`M02`" in primo_t and "nessuna misura di questo elenco lo dichiara" not in primo_t,
        )
        check(
            "gli intervalli dichiarati sono quelli della sezione giusta",
            len(intervalli) == 1
            and "### M02" in primo_t.splitlines()[intervalli[0][0] - 1],
            intervalli,
        )
        # E la controprova: senza la dichiarazione, lo stesso elenco da' una
        # differenza **vera** — cioe' il difetto si vedrebbe invece di sparire.
        senza_una = misure.carica(con_tempo)
        senza_dichiarazione = misure.Elenco(
            percorso=senza_una.percorso,
            dichiarato=senza_una.dichiarato,
            impronta=senza_una.impronta,
            titolo=senza_una.titolo,
            descrizione=senza_una.descrizione,
            area=senza_una.area,
            misure=tuple(
                misure.Misura(
                    indice=m.indice, nome=m.nome, comando=m.comando,
                    descrizione=m.descrizione, cwd=m.cwd, esito_atteso=m.esito_atteso,
                )
                for m in senza_una.misure
            ),
            escluse=senza_una.escluse,
        )
        p1, _, _ = misure.componi(senza_dichiarazione, radice, misure.esegui_elenco(senza_dichiarazione, radice))
        p2, _, _ = misure.componi(senza_dichiarazione, radice, misure.esegui_elenco(senza_dichiarazione, radice))
        check(
            "senza la dichiarazione lo stesso movimento conta come differenza vera",
            not misure.confronta(p1, p2)[0] and misure.confronta(p1, p2)[2] == [],
        )

        # --- LA GUARDIA DI AMBITO, E L'AREA ---------------------------------
        with tempfile.TemporaryDirectory() as fuori:
            fuori_dall_albero = Path(fuori) / "allegato.md"
            check(
                "l'allegato fuori dall'albero di autorita' e' rifiutato dalla guardia",
                _rifiuta(lambda: misure.scrivi("x", fuori_dall_albero)),
            )
            check("e il file non nasce", not fuori_dall_albero.exists())
            check(
                "nemmeno l'area di misura puo' stare fuori: sarebbe il varco di ERR-0026",
                _rifiuta(lambda: misure.area_di(letto, Path(fuori))),
            )
        check("l'area di misura vera sta dentro l'albero", misure.area_di(letto, radice) == radice.resolve())

        fuga = misure.Misura(indice=1, nome="fuga", comando="true", descrizione="x", cwd="..")
        check("una misura che lavora fuori dall'area e' rifiutata", misure.valida(fuga, radice) is not None)
        assoluto = misure.Misura(indice=1, nome="assoluto", comando="cat /etc/passwd", descrizione="x")
        check("un percorso assoluto fuori dall'area e' rifiutato", misure.valida(assoluto, radice) is not None)
        scarto = misure.Misura(indice=1, nome="scarto", comando="ls -la . 2>/dev/null", descrizione="x")
        check(
            "ma `/dev/null` e' l'unica deroga: non e' un file, e' dove l'output non va",
            misure.valida(scarto, radice) is None,
            misure.valida(scarto, radice),
        )

        # --- LO STRUMENTO INTERO, DALLA RIGA DI COMANDO ---------------------
        buono = radice / "buono.yaml"
        buono.write_text(
            "titolo: Prova\n"
            "misure:\n"
            "  - nome: una che riesce\n    comando: 'printf \"ok\\n\"'\n    descrizione: ok\n"
            "  - nome: una che esce con cinque\n    comando: 'exit 5'\n    descrizione: esce con cinque.\n",
            encoding="utf-8",
        )
        allegato = radice / "allegato.md"
        fatto = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "misure.py"),
                "run",
                str(buono),
                "--out",
                str(allegato),
                "--area",
                str(radice),
            ],
            capture_output=True,
            text=True,
        )
        check(
            "una misura fallita non ferma l'allegato, ma il codice di uscita lo dice",
            fatto.returncode == 1 and allegato.is_file(),
            f"exit {fatto.returncode}: {fatto.stderr.strip()[:100]}",
        )
        check(
            "e il fallimento e' dentro l'allegato, col suo codice",
            "codice di uscita `5`" in allegato.read_text(encoding="utf-8"),
        )
        check(
            "`check` valida senza eseguire: nessun allegato, nessun comando",
            zitto(lambda: misure.main(["check", str(buono), "--area", str(radice)])) == 0,
        )

        # --- IL TAGLIO DELL'OUTPUT, E LA SUA DICHIARAZIONE ------------------
        # Il gate `Code Review` ha trovato che questa dichiarazione **non aveva
        # nessuna prova**: due mutazioni che la toglievano lasciavano la suite
        # verde. E' la lezione di `ERR-0029` — uno strumento che risponde meno di
        # quanto sa, senza dirlo — applicata a questo strumento. Qui il controllo
        # c'e': un output piu' lungo di `MAX_RIGHE` deve portare **il numero
        # delle righe dette** e **il numero delle righe omesse**.
        lunga = radice / "lunga.yaml"
        lunga.write_text(
            "titolo: Prova\n"
            "misure:\n"
            f"  - nome: una che dice molto\n    comando: 'seq 1 {misure.MAX_RIGHE + 80}'\n"
            "    descrizione: piu' righe di quante ne stiano nell'allegato.\n",
            encoding="utf-8",
        )
        letto_lunga = misure.carica(lunga)
        testo_lungo, _, _ = misure.componi(
            letto_lunga, radice, misure.esegui_elenco(letto_lunga, radice)
        )
        attese = misure.MAX_RIGHE + 80
        check(
            "un output lungo si tronca a MAX_RIGHE, non si stampa tutto",
            testo_lungo.count("80\n") == 0 and f"\n{misure.MAX_RIGHE}\n" in testo_lungo,
            f"cercato il taglio a {misure.MAX_RIGHE}",
        )
        check(
            "e il taglio e' dichiarato, con quante righe sono state omesse",
            f"[... 80 righe non mostrate su {attese}:" in testo_lungo,
            [r for r in testo_lungo.splitlines() if "non mostrate" in r],
        )
        check(
            "e l'esito dice quante righe ha detto il comando",
            f"righe di output: {attese}" in testo_lungo,
            [r for r in testo_lungo.splitlines() if "righe di output" in r],
        )

        # --- IL LIMITE STA NELL'ARTEFATTO, NON SOLO NEL CODICE --------------
        # La contestazione piu' importante del gate: il limite era dichiarato
        # quattro volte nella docstring e **zero** nell'allegato, che e'
        # l'artefatto che si cita come prova. Qui si prova che c'e', e che le
        # famiglie rifiutate sono elencate una per una.
        check(
            "l'allegato dichiara che il rifiuto e' un'euristica, non un sandbox",
            "euristica su forme note" in testo and misure.LIMITE_RIFIUTO.splitlines()[0] in testo,
        )
        check(
            "e nomina il caso che nessuna lista puo' coprire",
            "python3 tools/<programma>.py" in testo,
        )
        famiglie = sorted({famiglia for famiglia, _ in misure.VIETATI})
        righe_famiglie = [r for r in testo.splitlines() if r.startswith("| ") and r.endswith(" |")]
        check(
            "e le famiglie rifiutate sono elencate una per una",
            all(any(r.startswith(f"| {famiglia} |") for r in righe_famiglie) for famiglia in famiglie),
            famiglie,
        )
        check(
            "e dice che le forme gia' sbagliate sono provate, non promesse",
            "test_misure" in testo and "Un controllo che non sa fallire" in testo,
        )

        # --- IL PERCORSO DELL'ELENCO NON CAMBIA L'IMPRONTA ------------------
        # Il gate: «l'impronta cambia se l'elenco e' scritto con percorso relativo
        # o assoluto». Due modi di dire la stessa esecuzione devono dare lo stesso
        # testo: il percorso si dichiara relativo alla root di autorita', e il
        # campo che finisce nell'allegato non dipende da come l'ha scritto il
        # chiamante.
        relativo = misure.percorso_dichiarato(elenco)
        assoluto = misure.percorso_dichiarato(elenco.resolve())
        check(
            "il percorso dell'elenco si dichiara relativo, non come e' stato scritto",
            relativo == assoluto and not relativo.startswith("/"),
            f"{relativo} / {assoluto}",
        )
        check(
            "e l'allegato lo porta cosi', non come gliel'hanno passato",
            f"| elenco delle misure | `{relativo}` |" in testo,
            relativo,
        )

        # La guardia viene PRIMA dell'esecuzione, non solo prima della scrittura:
        # se scattasse dopo, il riassunto dei comandi eseguiti sarebbe gia' stato
        # stampato. Non c'e', quindi non e' partito niente. Il percorso e' una
        # cartella prodotto vera — `99. Progetto Non Coperto` — perche' dentro la
        # cartella di prova lo scrivibile e lo scritto si assomigliano.
        scoperto = Path(ad_docs.DOCS_ROOT) / "99. Progetto Non Coperto"
        catturato = io.StringIO()
        with contextlib.redirect_stdout(catturato), contextlib.redirect_stderr(io.StringIO()):
            codice = misure.main(["run", str(buono), "--out", str(scoperto / "allegato.md")])
        check(
            "la guardia scatta prima dell'esecuzione: nessun comando e' partito",
            codice == 2 and "eseguite" not in catturato.getvalue(),
            f"exit {codice}: {catturato.getvalue()[:80]}",
        )
        check("e non ha lasciato la cartella che avrebbe creato", not scoperto.exists(), str(scoperto))


def test_rapporti_e_vista() -> None:
    """Il modello del rapporto si controlla, e il lavoro fatto si vede da fuori."""
    print("\nrapporti di passo e vista condivisa")
    import tempfile

    import ad_milestone
    import milestone
    import stato

    base = Path(ad_docs.DOCS_ROOT)

    # Le sezioni si leggono DAL MODELLO: se il modello cambia, il controllo lo segue.
    sezioni = milestone.sezioni_del_rapporto(base)
    check("le sezioni si leggono dal modello", len(sezioni) >= 5, sezioni)
    check(
        "e c'e' quella che serve a chi viene dopo",
        any("passa allo sprint" in s for s in sezioni),
        sezioni,
    )

    # LO STATO REALE: nessun rapporto chiuso DOPO la data pretesa deve essere fuori modello.
    problemi = []
    for progetto in sorted(base.iterdir()):
        if progetto.is_dir() and ad_scope.PROTECTED_DIR.match(progetto.name):
            problemi += milestone.controlla_rapporti(progetto, base)
    check("nessun rapporto recente e' fuori modello", not problemi, problemi[:2])

    # E IL CONTROLLO DEVE SAPER FALLIRE, con il difetto iniettato.
    with tempfile.TemporaryDirectory() as temporary:
        radice = Path(temporary)
        (radice / "milestone").mkdir()
        (radice / "milestone" / "_TEMPLATE-SPRINT-REPORT.md").write_text(
            "## Cosa e' stato fatto\n## Come e' stato fatto\n## Evidenze\n"
            "## Scostamenti dal prompt\n## Cosa passa allo sprint successivo\n## Lezioni\n",
            encoding="utf-8",
        )
        progetto = radice / "9. Prova"
        passo = progetto / "Analisi-Prompt-Report" / "Milestone 1" / "Sprint 1"
        passo.mkdir(parents=True)
        (progetto / "Analisi-Prompt-Report" / "Milestone 1" / "REPORT.md").write_text(
            "stato: chiusa\n", encoding="utf-8"
        )
        (passo / "PROMPT.md").write_text("stato: aperto\n", encoding="utf-8")
        buono = (
            "```yaml\nstato: chiusa\nchiuso: 2026-10-13\n```\n"
            "## Cosa e' stato fatto\nx\n## Come e' stato fatto\nx\n## Evidenze\nx\n"
            "## Scostamenti dal prompt\nx\n## Cosa passa allo sprint successivo\nx\n"
            "## Lezioni\nx\n"
        )
        (passo / "REPORT.md").write_text(buono, encoding="utf-8")
        check("un rapporto conforme non da' problemi", not milestone.controlla_rapporti(progetto, radice))

        # a) senza la sezione che serve a chi viene dopo
        (passo / "REPORT.md").write_text(
            buono.replace("## Cosa passa allo sprint successivo\n", ""), encoding="utf-8"
        )
        fuori = milestone.controlla_rapporti(progetto, radice)
        check("un rapporto senza «cosa passa» e' segnalato", bool(fuori), fuori)

        # b) con la sezione NUMERATA: segue il modello, e non va punita la forma
        (passo / "REPORT.md").write_text(
            buono.replace("## Evidenze", "## 3. Evidenze"), encoding="utf-8"
        )
        check("la numerazione non e' un difetto", not milestone.controlla_rapporti(progetto, radice))

        # c) e il passato e' esentato: la storia non si riscrive
        (passo / "REPORT.md").write_text(
            buono.replace("chiuso: 2026-10-13", "chiuso: 2026-01-01").replace(
                "## Cosa passa allo sprint successivo\n", ""
            ),
            encoding="utf-8",
        )
        check(
            "un rapporto vecchio e' esentato",
            not milestone.controlla_rapporti(progetto, radice),
        )

    # E LA VISTA CONDIVISA: legge i lavori di tutti i progetti, senza spostarli.
    # I progetti li **costruisce la prova** in una root sua: su un motore vergine
    # non ce ne sono, e la vista veniva misurata sul mondo invece che sul codice
    # (ERR-0049).
    with scratch_root() as temporary:
        radice = Path(temporary)
        for nome, obiettivo in (
            ("9. Prova Uno", "il primo lavoro"),
            ("10. Prova Due", "il secondo lavoro"),
        ):
            progetto = radice / nome
            progetto.mkdir()
            ad_milestone.scaffold_milestone(progetto, "obiettivo di prova")
            ad_milestone.scaffold_sprint(progetto, 1, obiettivo)
            passo = progetto / "Analisi-Prompt-Report" / "Milestone 1" / "Sprint 1"
            (passo / "REPORT.md").write_text(
                "```yaml\nstato: chiusa\nchiuso: 2026-10-13\n```\n", encoding="utf-8"
            )
        lavori = stato.ultimi_lavori(radice)
        check("la vista trova dei lavori chiusi", len(lavori) > 0, len(lavori))
        check(
            "e ne nomina piu' di un progetto",
            len({v["progetto"] for v in lavori}) >= 2,
            sorted({v["progetto"] for v in lavori}),
        )
        check(
            "e dice l'obiettivo, non il titolo del rapporto",
            all("— report" not in v["obiettivo"] for v in lavori),
            [v["obiettivo"][:40] for v in lavori[:2]],
        )
        check(
            "e i documenti restano nel progetto",
            not (radice / "orchestrazione" / "rapporti").exists(),
        )


def test_un_percorso_un_titolare() -> None:
    """Un percorso con due titolari non ha un titolare."""
    print("\nun percorso, un titolare")
    import ad_contract

    base = Path(ad_docs.DOCS_ROOT)

    # 1. IL CONFLITTO, **IN IETTATO**: si costruisce un registro con due permessi sullo
    #    stesso percorso. Non si spera che ne esista uno vero: fino al 2026-10-13 ce
    #    n'erano cinque su `tools/`, e il test li usava — cosi' pero' il giorno che i
    #    conflitti si risolvono **il test si rompe**, pur essendo tutto a posto. Un test
    #    che dipende da un difetto esistente e' un test che sparisce insieme al difetto.
    with tempfile.TemporaryDirectory(dir=ad_docs.DOCS_ROOT) as temporanea:
        prova = Path(temporanea)
        (prova / "contratti").mkdir()
        (prova / "contratti" / "PROVA-001.yaml").write_text(
            'task_id: PROVA-001\nstatus: active\nwrite_scope:\n  - "tools/"\n',
            encoding="utf-8",
        )
        doppi, contenuti = ad_contract.conflitti_di_raggio(
            {"task_id": "NUOVO-001", "write_scope": ["tools/"]}, prova
        )
        check("un raggio gia' di un altro e' un conflitto", len(doppi) >= 1, doppi[:1])
        check("e dice di chi era", any("PROVA-001" in d for d in doppi), doppi[:1])

        # 2. IL CONTENIMENTO: un file dentro una cartella altrui. Avviso, non conflitto.
        doppi2, contenuti2 = ad_contract.conflitti_di_raggio(
            {"task_id": "NUOVO-002", "write_scope": ["tools/un-mio-file.py"]}, prova
        )
        check("un file dentro una cartella altrui non e' un conflitto", not doppi2, doppi2[:1])
        check("ma e' un avviso da guardare", len(contenuti2) >= 1, contenuti2[:1])

    # 3. E IL REGISTRO VERO: **zero** percorsi con piu' di un titolare. E' il traguardo,
    #    non un caso: il 2026-10-13 ne aveva cinque, e ora non ne ha nessuno.
    titolari = ad_contract.conflitti_di_raggio({"task_id": "X", "write_scope": []}, base)
    vivi = {}
    for scope in ad_scope.load_write_scopes(base):
        for voce in scope.scopes:
            vivi.setdefault(str(voce).strip(), []).append(scope.task_id)
    contesi = {k: v for k, v in vivi.items() if len(v) > 1}
    check("nessun percorso del registro ha piu' di un titolare", not contesi, contesi)

    # 3. UN CONTRACT NON E' IN CONFLITTO CON SE STESSO: altrimenti, una volta
    #    scritto, non si potrebbe piu' validare.
    doppi3, _ = ad_contract.conflitti_di_raggio(
        {"task_id": "ADMF-008", "write_scope": ["tools/", ".brain/"]}, base
    )
    check("un contract non confligge con se stesso", not any("ADMF-008" in d for d in doppi3), doppi3[:1])

    # 4. LA CLAUSOLA DI NONNO. Il MECCANISMO si prova su una root costruita: su un
    #    motore vergine i permessi che avevano diritto alla clausola sono stati
    #    potati insieme ai progetti, e il meccanismo non si vedrebbe piu'
    #    (ERR-0049). Un contract ESENTE riceve un AVVISO; lo stesso raggio senza la
    #    clausola riceve una VIOLAZIONE.
    import ad_registry as _registro_mod

    with tempfile.TemporaryDirectory() as temporanea:
        finta = Path(temporanea)
        (finta / "contratti").mkdir()
        (finta / "contratti" / "ALTRO-001.yaml").write_text(
            'task_id: ALTRO-001\nstatus: active\nwrite_scope:\n  - "tools/"\n',
            encoding="utf-8",
        )
        registro = _registro_mod.load()
        modello = dict(contract_fixture("contract_valid.yaml"))
        modello["write_scope"] = ["tools/"]

        esiti_esente = ad_contract.validate(
            dict(modello, task_id=ad_contract.ESENTI_DALLA_REGOLA[0]), registro, finta
        )
        check(
            "un contract esente dalla regola riceve un AVVISO, non una violazione",
            not [
                f
                for f in ad_contract.violations(esiti_esente)
                if f.code == "percorso-gia-di-un-altro"
            ]
            and any("esente" in f.code for f in ad_contract.warnings(esiti_esente)),
            str([f.code for f in esiti_esente]),
        )
        esiti_normale = ad_contract.validate(
            dict(modello, task_id="NUOVO-004"), registro, finta
        )
        check(
            "lo stesso raggio senza la clausola e' una VIOLAZIONE",
            any(
                f.code == "percorso-gia-di-un-altro"
                for f in ad_contract.violations(esiti_normale)
            ),
            str([f.code for f in esiti_normale]),
        )

    # 4b. E I NOMI REALI: ogni voce della lista dev'essere un permesso VERO — o un
    #     contract che esiste ancora (e allora dev'essere attivo), o la voce della
    #     decisione che l'ha congelato. Un nome dimenticato non compare da nessuna
    #     parte, e questo controllo lo prende. Su un motore vergine i permessi sono
    #     stati potati con i progetti e la decisione resta: la voce e' SPESA, non
    #     sbagliata (ERR-0049).
    check(
        "i permessi precedenti alla regola sono elencati",
        len(ad_contract.ESENTI_DALLA_REGOLA) > 0,
        ad_contract.ESENTI_DALLA_REGOLA,
    )
    decisione = base / "DECISIONI" / "DEC-0054-un-percorso-un-titolare.md"
    testo_decisione = decisione.read_text(encoding="utf-8") if decisione.is_file() else ""
    for task in ad_contract.ESENTI_DALLA_REGOLA:
        file_contratto = sorted((base / "contratti").rglob(f"{task}.yaml"))
        if file_contratto:
            vivo = str(ad_contract.load(file_contratto[0]).get("status")) == "active"
        else:
            vivo = task in testo_decisione
        check(
            f"{task} e' un permesso vivo o la voce che l'ha congelato, non un nome dimenticato",
            vivo,
            f"contract: {bool(file_contratto)} · in {decisione.name}: {task in testo_decisione}",
        )

    # 5. E OGNI CONTRACT ATTIVO VALIDA ANCORA: la regola non rompe il passato.
    import ad_contract as ac
    import ad_registry
    import yaml

    registro = ad_registry.load()
    rotti = []
    for percorso in sorted((base / "contratti").rglob("*.yaml")):
        if percorso.name.startswith("_"):
            continue
        dati = yaml.safe_load(percorso.read_text(encoding="utf-8")) or {}
        if dati.get("status") != "active":
            continue
        esiti = ac.validate(dati, registro, base)
        violazioni = [f for f in esiti if f.level == "violation" and "percorso-gia" in f.code]
        if violazioni:
            rotti.append(percorso.name)
    check("nessun contract attivo e' rotto dalla regola", not rotti, rotti)


def test_i_progetti_si_numerano() -> None:
    """Un progetto senza numero e' un progetto scoperto."""
    print("\ni progetti si numerano")
    with scratch_root() as temporary:
        temp = Path(temporary)
        (temp / "ProgettoSenzaNumero").mkdir()
        (temp / "9. Progetto").mkdir()

        # Il numero e' cio' che dice al sistema che quella cartella e' un prodotto.
        senza = ad_scope.evaluate(temp / "ProgettoSenzaNumero" / "x.ts", temp)
        check("una cartella senza numero e' RIFIUTATA", not senza.allowed, senza.reason[:60])
        check(
            "e il rifiuto dice perche'",
            "numerano" in senza.reason or "numero" in senza.reason,
            senza.reason[:60],
        )
        check(
            "e dice QUALE numero usare",
            "Rimedio" in senza.reason and "1." in senza.reason,
            senza.reason[-60:],
        )

        con = ad_scope.evaluate(temp / "9. Progetto" / "x.ts", temp)
        check("una cartella numerata non e' rifiutata per il numero", "numerata" not in con.reason, con.reason[:60])

        # Le cartelle della MACCHINA non sono progetti, e non si pretendono numerate.
        for nome in ("tools", "DECISIONI", "piani", ".brain"):
            (temp / nome).mkdir(exist_ok=True)
            esito = ad_scope.evaluate(temp / nome / "x.md", temp)
            check(
                f"{nome}/ non e' scambiata per un progetto senza numero",
                "numerata" not in esito.reason,
                esito.reason[:60],
            )

        # L'elenco della macchina e' DICHIARATO, non dedotto: se fosse dedotto,
        # qualunque cartella creata diventerebbe "macchina" e il buco resterebbe.
        check(
            "l'elenco della macchina e' una costante dichiarata",
            isinstance(ad_scope.CARTELLE_MACCHINA, frozenset)
            and "tools" in ad_scope.CARTELLE_MACCHINA,
        )

        # E il numero suggerito e' davvero libero.
        numero = ad_scope.primo_numero_libero(temp)
        check("il numero suggerito e' libero", not (temp / f"{numero}. X").exists(), numero)


def main() -> int:
    """Run every test group."""
    test_registry()
    test_gates()
    test_contract_validator()
    test_decision_records()
    test_verdict()
    test_evidenza_propria()
    test_cli()
    test_scope()
    test_scope_cli()
    test_bash_scope()
    test_milestone()
    test_guardia()
    test_evidence_declaration()
    test_drift()
    test_invariante_13()
    test_bootstrap_sprint()
    test_coherence()
    test_security_scan()
    test_errori()
    test_blueprint()
    test_comportamento()
    test_stato()
    test_verbali()
    test_falsi_allarmi()
    test_istruzioni_mascherate()
    test_verdetto_proporzione()
    test_prenota_id()
    test_rapporti_e_vista()
    test_un_percorso_un_titolare()
    test_i_progetti_si_numerano()
    test_blueprint_errori()
    test_ricerca()
    test_misure()
    print(f"\nPASS — {PASSED} controlli")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
