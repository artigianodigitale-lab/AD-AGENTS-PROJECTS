#!/usr/bin/env python3
"""Creare e collegare un progetto.

    python3 tools/progetto.py elenca
    python3 tools/progetto.py numero
    python3 tools/progetto.py nuovo "<nome>" [--si]
    python3 tools/progetto.py collega "<percorso>" [--sposta] [--si]

Perche' esiste: all'avvio AAP chiede **«progetto nuovo o esistente?»** — e non c'era
niente per rispondere. Si creava la cartella a mano, e si sperava che il numero fosse
quello giusto. Il numero non e' un'etichetta: e' **cio' che dice al sistema che quella
cartella e' un prodotto**, e da li' discendono il permesso e il cancello.

## Le due regole che conta rispettare

**Il numero si prende, non si sceglie.** Lo dice `ad_scope.primo_numero_libero()`, e il
nome completo (`18. Modelbel`) si **mostra prima di creare** e si fa approvare.

**Spostare una cartella e' irreversibile.** `collega` **non sposta niente** senza
`--sposta`, e anche con quello dice cosa sta per fare **e dove**. `ERR-0024` esiste
perche' ho spostato una cartella senza guardare dove finiva: il ripristino l'ha
infilata dentro se stessa.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ad_docs  # noqa: E402
import ad_scope  # noqa: E402


def elenca(base: Path | None = None) -> list[tuple[int, str, Path]]:
    """I progetti che ci sono, col loro numero."""
    radice = base or ad_docs.PROGETTI_ROOT
    trovati = []
    if not radice.is_dir():
        return trovati
    for voce in sorted(radice.iterdir()):
        if voce.is_dir() and ad_scope.PROTECTED_DIR.match(voce.name):
            numero = int(voce.name.split(".", 1)[0])
            nome = voce.name.split(".", 1)[1].strip()
            trovati.append((numero, nome, voce))
    return sorted(trovati)


def numero_libero() -> int:
    """Il prossimo numero di progetto."""
    return ad_scope.primo_numero_libero(ad_docs.PROGETTI_ROOT)


def nuovo(nome: str, *, conferma: bool = False, base: Path | None = None) -> int:
    """Crea un progetto numerato. **Non crea niente senza `conferma`.**"""
    radice = base or ad_docs.PROGETTI_ROOT
    nome = nome.strip()
    if not nome:
        print("  serve un nome per il progetto")
        return 2
    if ad_scope.PROTECTED_DIR.match(nome):
        print(f'  "{nome}" ha gia\' un numero: usa `collega` se e\' un progetto esistente')
        return 2

    numero = ad_scope.primo_numero_libero(radice)
    completo = f"{numero}. {nome}"
    destinazione = radice / completo

    print(f"  motore:   {ad_docs.DOCS_ROOT}")
    print(f"  progetti: {radice}")
    print(f"  nome:     {completo}")
    print()
    if destinazione.exists():
        print(f'  "{completo}" esiste gia\': non tocco niente')
        return 2
    if not conferma:
        print("  NON creato: serve la conferma del CEO.")
        print(f"  Rimedio: ripeti con --si se il nome va bene.")
        return 1

    destinazione.mkdir(parents=True)
    print(f"  creato: {destinazione}")
    print()
    print("  Il numero e' cio' che dice al sistema che questa cartella e' un prodotto:")
    print("  da qui in avanti vale il permesso, e il cancello la protegge.")
    print("  Il lavoro vero si apre con la skill `ad-kickoff`: analisi di avvio, milestone,")
    print("  e il consenso del CEO SULLE MILESTONE.")
    return 0


def collega(percorso: str, *, sposta: bool = False, conferma: bool = False,
            base: Path | None = None) -> int:
    """Collega una cartella di progetto esistente. **Non la muove senza `sposta`."""
    radice = base or ad_docs.PROGETTI_ROOT
    origine = Path(percorso).expanduser().resolve()
    if not origine.is_dir():
        print(f'  "{origine}" non e\' una cartella')
        return 2

    nome = origine.name
    gia_dentro = origine.parent == radice.resolve()
    print(f"  cartella:  {origine}")
    print(f"  progetti:  {radice}")
    print()

    if gia_dentro and ad_scope.PROTECTED_DIR.match(nome):
        print(f'  "{nome}" e\' gia\' collegata: e\' dentro la cartella dei progetti.')
        print("  Il lavoro si apre con la skill `ad-kickoff`.")
        return 0

    if not ad_scope.PROTECTED_DIR.match(nome):
        numero = ad_scope.primo_numero_libero(radice)
        print(f'  "{nome}" NON e\' numerata, e il sistema non la riconosce come prodotto.')
        print("  Senza numero **passa il cancello**: nessun permesso, nessuna approvazione,")
        print("  e nessuno se ne accorge.")
        print(f'  Rimedio: rinominala in "{numero}. {nome}", poi ripeti.')
        return 1

    destinazione = radice / nome
    if destinazione.exists():
        print(f'  "{nome}" esiste gia\' nella cartella dei progetti: non tocco niente')
        return 2
    if not sposta:
        print(f'  NON spostata. Per portarla dentro servirebbe:')
        print(f'    {origine}')
        print(f'      -> {destinazione}')
        print()
        print("  **Spostare una cartella e' irreversibile.** Serve --sposta, e serve")
        print("  che il CEO abbia detto si' sapendo DOVE finisce (ERR-0024).")
        return 1
    if not conferma:
        print("  NON spostata: serve la conferma del CEO.")
        return 1

    shutil.move(str(origine), str(destinazione))
    print(f"  collegata: {destinazione}")
    print()
    print("  Il lavoro si apre con la skill `ad-kickoff`.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Progetti: creare, collegare, elencare")
    sub = parser.add_subparsers(dest="azione", required=True)

    sub.add_parser("elenca", help="i progetti col loro numero")
    sub.add_parser("numero", help="il prossimo numero libero")

    p_nuovo = sub.add_parser("nuovo", help="crea un progetto numerato")
    p_nuovo.add_argument("nome")
    p_nuovo.add_argument("--si", action="store_true", help="conferma del CEO")

    p_coll = sub.add_parser("collega", help="collega una cartella di progetto esistente")
    p_coll.add_argument("percorso")
    p_coll.add_argument("--sposta", action="store_true", help="portala dentro (irreversibile)")
    p_coll.add_argument("--si", action="store_true", help="conferma del CEO")
    p_coll.add_argument("--base", help="cartella dei progetti (per le prove)")

    args = parser.parse_args(argv)

    if args.azione == "elenca":
        progetti = elenca()
        if not progetti:
            print(f"  nessun progetto in {ad_docs.PROGETTI_ROOT}")
            return 0
        print(f"  progetti in {ad_docs.PROGETTI_ROOT}:")
        for numero, nome, _ in progetti:
            print(f"    {numero:>3}. {nome}")
        return 0

    if args.azione == "numero":
        print(f"  prossimo numero libero: {numero_libero()}")
        return 0

    if args.azione == "nuovo":
        return nuovo(args.nome, conferma=args.si)

    return collega(
        args.percorso,
        sposta=args.sposta,
        conferma=args.si,
        base=Path(args.base).resolve() if args.base else None,
    )


if __name__ == "__main__":
    raise SystemExit(main())
