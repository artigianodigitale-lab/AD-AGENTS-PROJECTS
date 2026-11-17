#!/usr/bin/env python3
"""La cache verificabile: hit, scadenza, provenienza, pulizia (M4, `DEC-0116`).

Si prova il comportamento, non l'esistenza delle funzioni:
  - salva/leggi: il corpo torna uguale e la provenienza c'e';
  - hit/miss: una voce assente non e' un errore silenzioso;
  - scadenza: dopo il TTL la voce NON si usa (e non si rinnova da sola);
  - manomissione: se il corpo non corrisponde all'impronta, la voce si tratta come assente;
  - `verifica` dice quali voci sono rotte; `pulisci` svuota la cache;
  - la cache NON vive nel repository (guardia).

Si esegue dalla radice:
    python3 tools/tests/test_cache.py
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import cache  # noqa: E402

FALLITI: list[str] = []
PASSATI = 0


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    global PASSATI
    if condizione:
        print(f"  ok   {etichetta}")
        PASSATI += 1
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ad-cache-prova-") as tmp:
        os.environ["AD_CACHE_DIR"] = tmp
        print("la cache")

        salvata = cache.salva("https://Example.com/a/?b=2&a=1#frammento", b"contenuto di prova")
        check("salva restituisce la chiave", len(salvata["chiave"]) == 64, str(salvata["chiave"])[:20])
        check("la chiave e' canonica", salvata["chiave"] == cache.chiave("https://example.com/a?a=1&b=2"))
        check("la provenienza c'e'", salvata["via"] == "http" and salvata["presa_il"] > 0, str(salvata))

        voce = cache.leggi("https://example.com/a/?a=1&b=2")
        check("hit: il corpo torna uguale", voce is not None and voce["corpo"] == b"contenuto di prova")
        check(
            "l'impronta e' del corpo",
            voce is not None and voce["meta"]["sha256"] == hashlib.sha256(b"contenuto di prova").hexdigest(),
        )
        check("l'hit e' contato", voce is not None and voce["meta"]["hit"] == 1)

        assente = cache.leggi("https://example.com/mai-vista")
        check("miss: None, non un errore silenzioso", assente is None)

        # Scadenza: la voce del 2020 e' scaduta.
        cache.salva("https://example.com/vecchia", b"vecchia", adesso=1.0)
        check("una voce scaduta non si legge", cache.leggi("https://example.com/vecchia") is None)

        # Manomissione del corpo: si tratta come assente, non si «ripara».
        chiave_rotta = cache.chiave("https://example.com/rotta")
        cache.salva("https://example.com/rotta", b"buona")
        (cache.cartella_cache() / f"{chiave_rotta}.bin").write_bytes(b"manomessa")
        check("un corpo manomesso non si legge", cache.leggi("https://example.com/rotta") is None)
        esito = cache.verifica()
        check("verifica nomina la voce rotta", chiave_rotta in esito["rotte"], str(esito))

        dati = cache.stato()
        check("stato conta le voci", dati["voci"] >= 3, str(dati))
        check("stato dichiara i byte", dati["byte"] > 0)

        # File ESTRANEI nella cartella: non sono voci della cache e non vanno toccati.
        cartella = cache.cartella_cache()
        estraneo_json = cartella / "estraneo.json"
        estraneo_bin = cartella / "documento.bin"
        estranea_nota = cartella / "nota.txt"
        estraneo_json.write_text('{"marcatore": "altro"}', encoding="utf-8")
        estraneo_bin.write_bytes(b"roba di un altro")
        estranea_nota.write_text("nota", encoding="utf-8")
        check("stato non conta i file estranei", cache.stato()["voci"] >= 3 and cache.stato()["voci"] <= 4,
              str(cache.stato()))

        esito_pulizia = cache.pulisci()
        check("pulisci svuota le voci", esito_pulizia["rimosse"] >= 3 and cache.stato()["voci"] == 0, str(esito_pulizia))
        check("pulisci lascia i file estranei", estraneo_json.exists() and estraneo_bin.exists() and estranea_nota.exists(),
              str(esito_pulizia))
        check("pulisci lascia la cartella fuori dal repository", str(cache.cartella_cache()).startswith(tmp))

        # Guardia: una cache dentro il repository non e' ammessa.
        os.environ["AD_CACHE_DIR"] = str(RADICE / "cache-vietata")
        try:
            cache.cartella_cache()
            check("una cache nel repository e' rifiutata", False)
        except cache.ErroreCache:
            check("una cache nel repository e' rifiutata", True)
        os.environ.pop("AD_CACHE_DIR", None)

    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — la cache è verificabile: hit, scadenza, provenienza")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
