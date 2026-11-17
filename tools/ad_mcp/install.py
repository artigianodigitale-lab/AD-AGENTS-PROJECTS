#!/usr/bin/env python3
"""Genera e verifica le configurazioni MCP per i cinque client (ENG-004).

    python3 tools/ad_mcp/install.py --list
    python3 tools/ad_mcp/install.py --print <client>
    python3 tools/ad_mcp/install.py --check <client>
    python3 tools/ad_mcp/install.py --check-all

Perche' esiste. La registrazione nei client e' **ENG-005** e ha due blocchi aperti:
`.brain/` e' di ADMF-008 e `tools/setup.py` e' di GOV-008. Questo strumento fa la
parte che si puo' fare senza quei permessi: produce il blocco **esatto** che ogni
client deve contenere, con il percorso assoluto alla macchina, e lo **valida**.
Non scrive niente: i file di configurazione vivono nella home dell'utente, fuori
dalla macchina, dove nessun contract arriva. Un generatore che scrivesse la'
sarebbe una scorciatoia attorno all'autorizzazione, non un passo avanti.

Esito: 0 ok · 1 verifica fallita · 2 uso o client sconosciuto.

Requisiti: Python >= 3.11 per validare il TOML di Codex (`tomllib`); sugli
interpreti piu' vecchi `--check codex` rifiuta con la ragione invece di rompersi.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys

try:  # tomllib c'e' da Python 3.11; senza, il TOML di Codex non si puo' validare
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - dipende dall'interprete
    tomllib = None  # type: ignore[assignment]
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "tools" / "ad_mcp" / "server.py"
NOME = "ad-projects"

#: Per ogni client: dove vive la configurazione, che forma ha, e la nota che
#: spiega cosa manca per eseguire la registrazione.
CLIENTI: dict[str, dict[str, str]] = {
    "dsh": {
        "file": "~/.dsh/profiles/<profilo>/cordis.patch.yml",
        "forma": "cordis",
        "nota": "entrata del loader con il plugin @deepseek-ai/dsh-mcp-client: transport stdio + serverName; il profilo lo monta al prossimo avvio",
    },
    "cursor": {
        "file": "~/.cursor/mcp.json oppure <progetto>/.cursor/mcp.json",
        "forma": "json",
        "nota": "file JSON, chiave mcpServers",
    },
    "claude": {
        "file": "~/.claude.json oppure: claude mcp add %s -- python3 %s" % (NOME, SERVER),
        "forma": "json",
        "nota": "in alternativa al file, il comando della CLI",
    },
    "codex": {
        "file": "~/.codex/config.toml",
        "forma": "toml",
        "nota": "file TOML, tabella [mcp_servers.%s]" % NOME,
    },
    "gemini": {
        "file": "~/.gemini/settings.json",
        "forma": "json",
        "nota": "file JSON, chiave mcpServers",
    },
}


class ErroreUso(Exception):
    """Raised when the request cannot be honoured."""


def _comando() -> dict[str, object]:
    """Return the command descriptor every client needs."""
    return {"command": "python3", "args": [str(SERVER)]}


def blocco(client: str) -> str:
    """Render the exact configuration block for one client."""
    voce = CLIENTI[client]
    if voce["forma"] == "cordis":
        # La forma letta dal sorgente montato di @deepseek-ai/dsh-mcp-client:
        # il plugin `mcp-client` vuole `transport: stdio` e `serverName`, e il
        # profilo DSH lo carica da `cordis.patch.yml`. Un `mcpServers` generico
        # DSH non lo carica (rilievo del gate di ENG-004).
        return "\n".join(
            [
                "- insert:",
                "    - id: ad-projects-mcp",
                '      name: "@deepseek-ai/dsh-mcp-client"',
                "      config:",
                "        transport: stdio",
                f"        serverName: {NOME}",
                "        command: python3",
                f'        args: ["{SERVER}"]',
            ]
        )
    if voce["forma"] == "toml":
        return "\n".join(
            [
                f"[mcp_servers.{NOME}]",
                'command = "python3"',
                f'args = ["{SERVER}"]',
            ]
        )
    return json.dumps({ "mcpServers": {NOME: _comando()} }, indent=2, ensure_ascii=False)


def verifica(client: str) -> list[str]:
    """Return the problems of one client's configuration, if it were installed."""
    problemi: list[str] = []
    if client not in CLIENTI:
        raise ErroreUso(f"client sconosciuto: {client}. Ammessi: {', '.join(sorted(CLIENTI))}")
    if not SERVER.is_file():
        problemi.append(f"il server non esiste: {SERVER}")
        return problemi
    if not SERVER.is_absolute():
        problemi.append(f"il percorso del server non e' assoluto: {SERVER}")
    testo = blocco(client)
    if CLIENTI[client]["forma"] == "cordis":
        try:
            caricato = yaml.safe_load(testo)
        except yaml.YAMLError as errore:
            problemi.append(f"il blocco non e' YAML valido: {errore}")
            return problemi
        if not isinstance(caricato, list) or not caricato:
            problemi.append("il blocco non e' una lista di entrate del loader")
            return problemi
        entrata = caricato[0]
        inserimenti = entrata.get("insert") if isinstance(entrata, dict) else None
        if not isinstance(inserimenti, list) or not inserimenti:
            problemi.append("manca la lista `insert` dell'entrata cordis")
            return problemi
        voce_dsh = inserimenti[0] if isinstance(inserimenti[0], dict) else {}
        if voce_dsh.get("name") != "@deepseek-ai/dsh-mcp-client":
            problemi.append("manca il plugin @deepseek-ai/dsh-mcp-client")
        config = voce_dsh.get("config")
        if not isinstance(config, dict):
            problemi.append("manca la mappa `config` dell'entrata cordis")
            return problemi
        if config.get("transport") != "stdio":
            problemi.append("transport deve essere 'stdio'")
        server_name = str(config.get("serverName") or "")
        # `isalnum()` accetta lettere Unicode: "ad-pròjects" passava qui ed era
        # rifiutato dal client. Si usa la regex del client (rilievo del gate).
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", server_name):
            problemi.append("serverName non valido (^[A-Za-z0-9_-]{1,32}$)")
        if config.get("command") != "python3":
            problemi.append("il comando non e' python3")
        argomenti = config.get("args") or []
        if not argomenti or argomenti[0] != str(SERVER):
            problemi.append("gli argomenti non puntano al server della macchina")
        return problemi
    if CLIENTI[client]["forma"] == "json":
        try:
            dati = json.loads(testo)
        except json.JSONDecodeError as errore:
            problemi.append(f"il blocco non e' JSON valido: {errore}")
            return problemi
        if not isinstance(dati, dict):
            problemi.append("il blocco non e' un oggetto JSON")
            return problemi
        servers = dati.get("mcpServers")
        if not isinstance(servers, dict):
            problemi.append("manca la mappa `mcpServers`")
            return problemi
        voce = servers.get(NOME)
        if not isinstance(voce, dict):
            problemi.append(f"manca la voce `{NOME}`")
            return problemi
        if voce.get("command") != "python3":
            problemi.append(f"il comando non e' python3: {voce.get('command')!r}")
        argomenti = voce.get("args")
        if not isinstance(argomenti, list) or not argomenti:
            problemi.append("mancano gli argomenti con il percorso del server")
            return problemi
        if argomenti[0] != str(SERVER):
            problemi.append("gli argomenti non puntano al server della macchina")
        if not Path(str(argomenti[0])).is_absolute():
            problemi.append("il percorso del server non e' assoluto")
    else:
        # TOML: si PARSA, non si cerca la stringa. Il gate di ENG-004 ha mostrato
        # che cercare `[mcp_servers...]` promuoveva `command = "node"`, una tabella
        # commentata e perfino TOML invalido: un validatore piu' debole del formato
        # che controlla e' un falso positivo, cioe' la classe di difetto peggiore.
        if tomllib is None:
            problemi.append(
                "validare il TOML di Codex richiede Python >= 3.11 (tomllib): "
                "usa un interprete piu' recente"
            )
            return problemi
        try:
            dati = tomllib.loads(testo)
        except tomllib.TOMLDecodeError as errore:
            problemi.append(f"il blocco non e' TOML valido: {errore}")
            return problemi
        if not isinstance(dati, dict):
            problemi.append("il blocco TOML non e' una tabella")
            return problemi
        servers = dati.get("mcp_servers")
        if not isinstance(servers, dict):
            problemi.append("manca la tabella [mcp_servers]")
            return problemi
        voce = servers.get(NOME)
        if not isinstance(voce, dict):
            problemi.append(f"manca la tabella [mcp_servers.{NOME}]")
            return problemi
        if voce.get("command") != "python3":
            problemi.append(f"il comando non e' python3: {voce.get('command')!r}")
        argomenti = voce.get("args") or []
        if not isinstance(argomenti, list) or not argomenti or argomenti[0] != str(SERVER):
            problemi.append("gli argomenti non puntano al server della macchina")
        if argomenti and not Path(str(argomenti[0])).is_absolute():
            problemi.append("il percorso del server non e' assoluto")
    return problemi



# ---------------------------------------------------------------------------
# Registrazione vera e portatile (ENG-011, DEC-0065)
#
# La configurazione non deve contenere il percorso di un'altra macchina: ogni
# macchina si registra da sola, `apply` risolve i percorsi QUI e ORA, e `status`
# dice quando la voce e' vecchia o punta altrove. Un solo campo dipende dalla
# macchina (il percorso del server): il comando resta `python3` dal PATH.
# ---------------------------------------------------------------------------

ESEGUIBILE = "python3"


def _home() -> Path:
    """Return the home of the current user (HOME, cosi' i test non toccano quella vera)."""
    return Path(os.environ.get("HOME") or str(Path.home())).expanduser()


def _profilo_dsh() -> str:
    """Return the DSH profile that carries a patch file (no invented paths).

    ERR-0061: senza DSH_PROFILE il default era "web", ma su questa macchina il profilo
    attivo e' "desktop": `--status dsh` diceva "non registrata" pur essendoci. Qui si
    cerca: prima il profilo che contiene GIA' la nostra voce, poi l'unico esistente.
    """
    cartella = _home() / ".dsh" / "profiles"
    if not cartella.is_dir():
        return "web"
    cartelle = [figlio.name for figlio in sorted(cartella.iterdir()) if figlio.is_dir()]
    candidati = [nome for nome in cartelle if (cartella / nome / "cordis.patch.yml").is_file()]
    if not candidati:
        if len(cartelle) == 1:
            return cartelle[0]
        raise ErroreUso(
            "nessun profilo DSH ha un cordis.patch.yml: specifica DSH_PROFILE "
            f"(cartelle: {', '.join(cartelle) or 'nessuna'}). Non si inventa un profilo"
        )
    for nome in candidati:
        testo = (cartella / nome / "cordis.patch.yml").read_text(encoding="utf-8", errors="replace")
        if re.search(
            r"^\s*(?:-\s+)?id\s*:\s*['\"]?ad-projects-mcp['\"]?\s*(?:#.*)?$",
            testo, re.MULTILINE,
        ):
            return nome
    if len(candidati) == 1:
        return candidati[0]
    raise ErroreUso(
        "piu' profili DSH e nessuno contiene la voce ad-projects: specifica DSH_PROFILE "
        f"(profili: {', '.join(candidati)}). Non si inventa un profilo"
    )


def percorso_config(client: str) -> Path:
    """Return the configuration file of a client on THIS machine."""
    if client not in CLIENTI:
        raise ErroreUso(f"client sconosciuto: {client}. Ammessi: {', '.join(sorted(CLIENTI))}")
    home = _home()
    if client == "dsh":
        grezzo = os.environ.get("DSH_PROFILE")
        if grezzo is None:
            profilo = _profilo_dsh()
        else:
            profilo = grezzo.strip()
            if not profilo:
                raise ErroreUso("DSH_PROFILE e' impostato ma vuoto: un nome di profilo serve")
        if not profilo or profilo in (".", "..") or any(c in profilo for c in ("/", "\\")):
            raise ErroreUso(
                f"DSH_PROFILE non valido: {profilo!r}. Deve essere un nome di profilo, "
                "non un percorso"
            )
        if not re.fullmatch(r"[A-Za-z0-9._-]+", profilo) or profilo in (".", ".."):
            raise ErroreUso(f"DSH_PROFILE non valido: {profilo!r}")
        return home / ".dsh" / "profiles" / profilo / "cordis.patch.yml"
    if client == "cursor":
        return home / ".cursor" / "mcp.json"
    if client == "claude":
        return home / ".claude.json"
    if client == "codex":
        return home / ".codex" / "config.toml"
    return home / ".gemini" / "settings.json"


class _YamlPermissivo(yaml.SafeLoader):
    """SafeLoader che accetta i tag `!!js` del formato DSH (non li esegue)."""


_YamlPermissivo.add_constructor(
    "tag:yaml.org,2002:js", lambda caricatore, nodo: caricatore.construct_scalar(nodo)
)


def _leggi_yaml_permissivo(testo: str) -> object:
    """Parse a DSH patch file (comments preserved elsewhere, `!!js` accepted)."""
    return yaml.load(testo, Loader=_YamlPermissivo)


def _voce_cordis() -> dict[str, object]:
    """Return the entry the DSH plugin schema really reads (rilievo di ENG-004)."""
    return {
        "id": "ad-projects-mcp",
        "name": "@deepseek-ai/dsh-mcp-client",
        "config": {
            "transport": "stdio",
            "serverName": NOME,
            "command": ESEGUIBILE,
            "args": [str(SERVER)],
        },
    }


def _sha(percorso: Path) -> str:
    return hashlib.sha256(percorso.read_bytes()).hexdigest()


def stato(client: str) -> tuple[str, str]:
    """Return (stato, dettaglio) of the registration: aggiornata/assente/... /stale/rotta."""
    percorso = percorso_config(client)
    if not percorso.is_file():
        if percorso.is_dir():
            return "rotta", f"{percorso} e' una directory, non un file"
        return "assente", f"{percorso} non esiste"
    if not SERVER.is_file():
        return "stale", f"il server non esiste: {SERVER}"
    if percorso.is_dir():
        return "rotta", f"{percorso} e' una directory, non un file"
    try:
        grezzo = percorso.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "rotta", f"{percorso} non e' UTF-8"
    except OSError as errore:
        return "rotta", f"{percorso} illeggibile: {errore.__class__.__name__}"
    if CLIENTI[client]["forma"] == "cordis":
        try:
            documento = _leggi_yaml_permissivo(grezzo) or []
        except yaml.YAMLError as errore:
            return "rotta", f"YAML invalido: {errore}"
        voci = []
        if isinstance(documento, list):
            for patch in documento:
                if isinstance(patch, dict) and isinstance(patch.get("insert"), list):
                    voci += [voce for voce in patch["insert"] if isinstance(voce, dict)]
        nostra = next((voce for voce in voci if voce.get("id") == "ad-projects-mcp"), None)
    elif CLIENTI[client]["forma"] == "toml":
        if tomllib is None:
            return "rotta", "tomllib non disponibile"
        try:
            documento = tomllib.loads(grezzo)
        except tomllib.TOMLDecodeError as errore:
            return "rotta", f"TOML invalido: {errore}"
        servers = documento.get("mcp_servers")
        if servers is not None and not isinstance(servers, dict):
            return "rotta", "'mcp_servers' non e' una tabella"
        nostra = (servers or {}).get(NOME)
    else:
        try:
            documento = json.loads(grezzo)
        except json.JSONDecodeError as errore:
            return "rotta", f"JSON invalido: {errore}"
        if not isinstance(documento, dict):
            return "rotta", "il file JSON non e' un oggetto"
        servers = documento.get("mcpServers")
        if servers is not None and not isinstance(servers, dict):
            return "rotta", "'mcpServers' non e' un oggetto"
        nostra = (servers or {}).get(NOME)
    if not isinstance(nostra, dict):
        return "non registrata", f"{percorso}: manca la voce {NOME}"
    config = nostra.get("config") if CLIENTI[client]["forma"] == "cordis" else nostra
    config = config if isinstance(config, dict) else {}
    comando = config.get("command")
    argomenti = config.get("args") or []
    primo = str(argomenti[0]) if isinstance(argomenti, list) and argomenti else ""
    if CLIENTI[client]["forma"] == "cordis":
        plugin = str(nostra.get("name") or "")
        if plugin != "@deepseek-ai/dsh-mcp-client":
            return "stale", f"plugin {plugin!r} invece di '@deepseek-ai/dsh-mcp-client'"
        config_voce = nostra.get("config") if isinstance(nostra.get("config"), dict) else {}
        trasporto = str(config_voce.get("transport") or "")
        if trasporto != "stdio":
            return "stale", f"transport {trasporto!r} invece di 'stdio'"
        nome_server = str(config_voce.get("serverName") or "")
        if nome_server != NOME:
            return "stale", f"serverName {nome_server!r} invece di {NOME!r}"
        if nostra.get("disabled") is True:
            return "stale", "la voce e' disabilitata (disabled: true)"
    if comando != ESEGUIBILE:
        return "stale", f"comando {comando!r} invece di {ESEGUIBILE!r}"
    if primo != str(SERVER):
        return "stale", f"punta a un altro percorso ({primo}) invece che a {SERVER}"
    return "aggiornata", f"{percorso}: registrata per questa macchina"


def _backup(percorso: Path) -> Path | None:
    """Keep the FIRST backup of a configuration (byte-identical), even when absent.

    Se il file non esiste si lascia un marcatore `.ad-bak.absent`: cosi' il rollback
    sa riportare il target allo stato "assente", e non promette un ripristino che non
    puo' fare.
    """
    copia = percorso.with_name(percorso.name + ".ad-bak")
    marcatore = percorso.with_name(percorso.name + ".ad-bak.absent")
    if percorso.is_file():
        if not copia.is_file():
            shutil.copy2(percorso, copia)
        return copia
    if not marcatore.is_file():
        marcatore.parent.mkdir(parents=True, exist_ok=True)
        marcatore.write_text("assente prima della registrazione\n", encoding="utf-8")
    return marcatore


def _scrivi_atomico(percorso: Path, testo: str) -> None:
    """Write atomically and PRESERVE the file mode (ERR-0061: 600 restava 664)."""
    percorso.parent.mkdir(parents=True, exist_ok=True)
    modo = percorso.stat().st_mode & 0o777 if percorso.is_file() else 0o600
    temporaneo = percorso.with_name(percorso.name + ".ad-tmp")
    temporaneo.write_text(testo, encoding="utf-8")
    os.chmod(temporaneo, modo)
    temporaneo.replace(percorso)
    os.chmod(percorso, modo)


def _voce_cordis_esistente(documento: object) -> dict:
    """Return our entry as found in the patch file (empty dict if absent)."""
    if not isinstance(documento, list):
        return {}
    for patch in documento:
        if not isinstance(patch, dict):
            continue
        voci = patch.get("insert")
        if not isinstance(voci, list):
            continue
        for voce in voci:
            if isinstance(voce, dict) and voce.get("id") == "ad-projects-mcp":
                return voce
    return {}


def _righe_voce_cordis(esistente: dict, indent: int = 4) -> list[str]:
    """Our entry as YAML TEXT: conserva le chiavi utente (env, timeout), NON `disabled`.

    `disabled` si toglie di proposito: `--apply` riabilita la voce, e la
    post-condizione verifica che sia "aggiornata" (ERR-0061 / ENG-013).
    """
    config: dict[str, object] = {
        "transport": "stdio",
        "serverName": NOME,
        "command": ESEGUIBILE,
        "args": [str(SERVER)],
    }
    voce: dict[str, object] = {"id": "ad-projects-mcp", "name": "@deepseek-ai/dsh-mcp-client"}
    if isinstance(esistente, dict):
        esistenti_config = esistente.get("config")
        if isinstance(esistenti_config, dict):
            for chiave, valore in esistenti_config.items():
                if chiave not in config:
                    config[chiave] = valore
    voce["config"] = config
    testo = yaml.safe_dump([voce], allow_unicode=True, sort_keys=False).rstrip("\n")
    spazi = " " * max(indent, 0)
    return [spazi + riga for riga in testo.splitlines()]


MODELLO_ID = re.compile(r"^\s*(?:-\s+)?id\s*:\s*['\"]?ad-projects-mcp['\"]?\s*(?:#.*)?$")


def _blocchi_voce(righe: list[str]) -> list[tuple[int, int, int]]:
    """Return [(item_start, item_end, indent)] for the items declaring OUR id.

    L'id si riconosce ESATTO (una voce sorella con id che lo contiene non e' nostra);
    l'item puo' avere `id` non come prima chiave, e accetta spazi dopo il `-`
    (ERR-0061 / gate ENG-012).
    """
    blocchi: list[tuple[int, int, int]] = []
    for indice, riga in enumerate(righe):
        if not MODELLO_ID.match(riga):
            continue
        indent_id = len(riga) - len(riga.lstrip())
        inizio = indice
        if riga.lstrip().startswith("- "):
            indent = indent_id
        else:
            indent = indent_id - 2
            while inizio > 0:
                precedente = righe[inizio - 1]
                if not precedente.strip():
                    inizio -= 1
                    continue
                ind_prec = len(precedente) - len(precedente.lstrip())
                if ind_prec < indent_id and precedente.lstrip().startswith("- "):
                    inizio -= 1
                    indent = ind_prec
                    break
                inizio -= 1
            else:
                inizio = indice
        fine = indice + 1
        while fine < len(righe):
            successiva = righe[fine]
            if not successiva.strip():
                fine += 1
                continue
            ind = len(successiva) - len(successiva.lstrip())
            if ind < indent or (ind == indent and successiva.lstrip().startswith("- ")):
                break
            fine += 1
        blocchi.append((inizio, fine, indent))
    return blocchi


def _merge_cordis(percorso: Path, dry: bool) -> None:
    """Update ONLY our entry (exact id): siblings, comments, indentation, duplicates.

    ERR-0061 + gate ENG-012: l'id si confronta ESATTO; l'item puo' essere indentato
    diversamente o avere `id` non come prima chiave; le chiavi utente (env, timeout)
    restano; `disabled` si toglie (apply riabilita, e la post-condizione lo verifica);
    una voce con `!!js` non viene toccata (si rifiuta, non si perde il tag).
    """
    esistente = ""
    if percorso.is_file():
        try:
            esistente = percorso.read_text(encoding="utf-8")
        except UnicodeDecodeError as errore:
            raise ErroreUso(f"{percorso} non e' UTF-8: {errore.reason}") from errore
    documento: object = []
    if esistente.strip():
        try:
            documento = _leggi_yaml_permissivo(esistente)
        except yaml.YAMLError as errore:
            raise ErroreUso(f"{percorso}: YAML invalido, non lo tocco: {errore}") from errore
    voce_esistente = _voce_cordis_esistente(documento)

    righe = esistente.splitlines()
    blocchi = _blocchi_voce(righe)
    for inizio_voce, fine_voce, _indent in blocchi:
        if any("!!js" in riga for riga in righe[inizio_voce:fine_voce]):
            raise ErroreUso(
                f"{percorso}: la voce ad-projects contiene un tag `!!js`; non la tocco "
                "(il tag non e' ricostruibile senza perdere informazione)"
            )
    if not blocchi:
        nuovo_indent = 4
        corpo = esistente.rstrip("\n")
        blocco = ["- insert:"] + _righe_voce_cordis(voce_esistente, nuovo_indent)
        testo = (corpo + "\n" if corpo else "") + "\n".join(blocco) + "\n"
    else:
        for inizio_voce, fine_voce, _indent in sorted(blocchi[1:], reverse=True):
            del righe[inizio_voce:fine_voce]
        inizio_voce, fine_voce, indent = blocchi[0]
        righe[inizio_voce:fine_voce] = _righe_voce_cordis(voce_esistente, indent)
        # un blocco `- insert:` rimasto vuoto dopo la rimozione di un duplicato
        # sarebbe rumore (e YAML con `insert: None`): si toglie.
        pulite: list[str] = []
        for indice, riga in enumerate(righe):
            if riga.strip() == "- insert:":
                successive = [r for r in righe[indice + 1:] if r.strip()]
                if not successive or successive[0].lstrip().startswith("#"):
                    pulite.append(riga)  # un commento appartiene al blocco: resta
                    continue
                if not successive[0].lstrip().startswith("- "):
                    continue
            pulite.append(riga)
        righe = pulite
        testo = "\n".join(righe).rstrip("\n") + "\n"
    if esistente.strip():
        try:
            _leggi_yaml_permissivo(testo)
        except yaml.YAMLError as errore:
            raise ErroreUso(f"{percorso}: la scrittura produrrebbe YAML invalido: {errore}") from errore
    if dry:
        return
    _backup(percorso)
    _scrivi_atomico(percorso, testo)


def _merge_json(percorso: Path, dry: bool) -> None:
    documento: dict = {}
    if percorso.is_file():
        try:
            caricato = json.loads(percorso.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as errore:
            raise ErroreUso(f"{percorso}: JSON invalido, non lo tocco: {errore}") from errore
        if not isinstance(caricato, dict):
            raise ErroreUso(f"{percorso}: non e' un oggetto JSON, non lo tocco")
        documento = caricato
    servers = documento.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
    esistente = servers.get(NOME) if isinstance(servers.get(NOME), dict) else {}
    voce = dict(esistente)
    voce["command"] = ESEGUIBILE
    voce["args"] = [str(SERVER)]
    servers[NOME] = voce
    documento["mcpServers"] = servers
    testo = json.dumps(documento, indent=2, ensure_ascii=False) + "\n"
    if dry:
        return
    _backup(percorso)
    _scrivi_atomico(percorso, testo)


def _merge_toml(percorso: Path, dry: bool) -> None:
    """Replace (or append) the [mcp_servers.ad-projects] table, line by line.

    tomllib sa solo leggere: scrivere TOML a mano richiede di toccare la sezione
    giusta e lasciare il resto intatto.
    """
    esistente = ""
    if percorso.is_file():
        try:
            esistente = percorso.read_text(encoding="utf-8")
        except UnicodeDecodeError as errore:
            raise ErroreUso(f"{percorso} non e' UTF-8: {errore.reason}") from errore
    if esistente.strip() and tomllib is not None:
        try:
            documento_esistente = tomllib.loads(esistente)
        except tomllib.TOMLDecodeError as errore:
            raise ErroreUso(f"{percorso}: TOML invalido, non lo tocco (prima si ripara a mano): {errore}") from errore
        servers = documento_esistente.get("mcp_servers")
        if isinstance(servers, list):
            raise ErroreUso(
                f"{percorso}: 'mcp_servers' e' una LISTA di tabelle ([[mcp_servers]]): "
                "formato non supportato, non lo tocco (ERR-0061)"
            )
    if esistente.strip() and tomllib is not None:
        try:
            tomllib.loads(esistente)
        except tomllib.TOMLDecodeError as errore:
            raise ErroreUso(
                f"{percorso}: TOML invalido, non lo tocco (prima si ripara a mano): {errore}"
            ) from errore
    sezione = f"[mcp_servers.{NOME}]"
    blocco = "\n".join([sezione, f'command = "{ESEGUIBILE}"', f'args = ["{SERVER}"]'])
    righe = esistente.splitlines()
    modello = re.compile(r"^\s*\[\s*mcp_servers\s*\.\s*\"?" + re.escape(NOME) + r"\"?\s*\]\s*(#.*)?$")
    inizio = next((i for i, riga in enumerate(righe) if modello.match(riga)), None)
    if inizio is None:
        testo = esistente.rstrip("\n") + ("\n\n" if esistente.strip() else "") + blocco + "\n"
    else:
        fine = len(righe)
        for indice in range(inizio + 1, len(righe)):
            if righe[indice].strip().startswith("["):
                fine = indice
                break
        # Data loss evitato: le righe utente della tabella (env, timeout...) restano;
        # si sostituiscono solo command e args.
        resto = [
            riga for riga in righe[inizio + 1 : fine]
            if not riga.strip().startswith(("command =", "args ="))
        ]
        righe[inizio:fine] = [sezione, f'command = "{ESEGUIBILE}"', f'args = ["{SERVER}"]'] + resto
        testo = "\n".join(righe).rstrip("\n") + "\n"
    if tomllib is not None:
        try:
            tomllib.loads(testo)
        except tomllib.TOMLDecodeError as errore:
            raise ErroreUso(f"{percorso}: la scrittura produrrebbe TOML invalido: {errore}") from errore
    if dry:
        return
    _backup(percorso)
    _scrivi_atomico(percorso, testo)


def applica(client: str, dry: bool = False) -> tuple[str, str]:
    """Write the registration for one client on THIS machine (backup first)."""
    if not SERVER.is_file():
        raise ErroreUso(f"il server non esiste: {SERVER}: non registro niente")
    percorso = percorso_config(client)
    stato_prima, dettaglio = stato(client)
    forma = CLIENTI[client]["forma"]
    prima = percorso.read_bytes() if percorso.is_file() else None
    try:
        if forma == "cordis":
            _merge_cordis(percorso, dry)
        elif forma == "toml":
            _merge_toml(percorso, dry)
        else:
            _merge_json(percorso, dry)
    except (OSError, PermissionError) as errore:
        raise ErroreUso(f"impossibile scrivere {percorso}: {errore.__class__.__name__}") from errore
    if dry:
        return "anteprima", f"{percorso}: scriverebbe la voce {NOME} (stato prima: {stato_prima})"
    stato_dopo, dettaglio_dopo = stato(client)
    if stato_dopo != "aggiornata":
        # Post-condizione non soddisfatta: si ripristina ESATTAMENTE lo stato di
        # prima di questo apply (non il primo backup, che puo' essere di un altro).
        if prima is None:
            if percorso.is_file():
                percorso.unlink()
        else:
            percorso.write_bytes(prima)
        raise ErroreUso(
            f"{client}: la registrazione non e' valida dopo la scrittura ({stato_dopo}: "
            f"{dettaglio_dopo}); file ripristinato"
        )
    return "registrata", f"{percorso} (prima: {stato_prima} — {dettaglio})"


def ripristina(client: str) -> str:
    """Restore the first backup, byte-identical (rollback)."""
    percorso = percorso_config(client)
    copia = percorso.with_name(percorso.name + ".ad-bak")
    marcatore = percorso.with_name(percorso.name + ".ad-bak.absent")
    if marcatore.is_file():
        if percorso.is_file():
            percorso.unlink()
        marcatore.unlink()
        return f"{percorso} riportato allo stato ASSENTE (non esisteva prima)"
    if not copia.is_file():
        raise ErroreUso(f"nessun backup per {client}: non c'e' niente da ripristinare")
    impronta_prima = _sha(copia)
    shutil.copy2(copia, percorso)
    if _sha(percorso) != impronta_prima:
        raise ErroreUso(f"ripristino di {percorso} non byte-identico: fermato")
    copia.unlink()
    return f"{percorso} ripristinato (sha256 {impronta_prima[:16]}...)"


def client_installati() -> list[str]:
    """Return the clients detectable on this machine, without inventing paths."""
    home = _home()
    rilevati: list[str] = []
    if (home / ".dsh").is_dir() or shutil.which("dsh"):
        rilevati.append("dsh")
    if (home / ".cursor").is_dir() or shutil.which("cursor"):
        rilevati.append("cursor")
    if (home / ".claude.json").is_file() or shutil.which("claude"):
        rilevati.append("claude")
    if (home / ".codex").is_dir() or shutil.which("codex"):
        rilevati.append("codex")
    if (home / ".gemini").is_dir() or shutil.which("gemini"):
        rilevati.append("gemini")
    return rilevati


def elenco() -> str:
    """Return the human-readable list of clients."""
    righe = ["client · dove vive la configurazione · cosa manca"]
    for nome, voce in CLIENTI.items():
        righe.append(f"- {nome} · {voce['file']} · {voce['nota']}")
    return "\n".join(righe)


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Genera e verifica le configurazioni MCP dei client")
    parser.add_argument("--list", action="store_true", help="elenca i client")
    parser.add_argument("--print", dest="stampa", metavar="CLIENT", help="stampa il blocco di un client")
    parser.add_argument("--check", dest="controlla", metavar="CLIENT", help="verifica il blocco di un client")
    parser.add_argument("--check-all", action="store_true", help="verifica tutti i client")
    parser.add_argument("--status", metavar="CLIENT|auto", help="stato della registrazione su QUESTA macchina")
    parser.add_argument("--apply", metavar="CLIENT|auto", help="registra il client (con backup) su QUESTA macchina")
    parser.add_argument("--rollback", metavar="CLIENT", help="ripristina il backup (byte-identico)")
    parser.add_argument("--dry-run", action="store_true", help="mostra cosa farebbe, senza scrivere")
    args = parser.parse_args(argv)

    try:
        if args.list:
            print(elenco())
            return 0
        if args.stampa:
            if args.stampa not in CLIENTI:
                raise ErroreUso(
                    f"client sconosciuto: {args.stampa}. Ammessi: {', '.join(sorted(CLIENTI))}"
                )
            print(blocco(args.stampa))
            return 0
        if args.controlla:
            problemi = verifica(args.controlla)
            for problema in problemi:
                print(f"ERRORE  {problema}", file=sys.stderr)
            if problemi:
                return 1
            stato_voce, dettaglio_stato = stato(args.controlla)
            print(f"OK   {args.controlla}: BLOCCO generato valido per questa macchina")
            print(f"     stato installazione: {stato_voce} — {dettaglio_stato}")
            return 0
        if args.status:
            nomi = client_installati() if args.status == "auto" else [args.status]
            if not nomi:
                print("nessun client rilevato su questa macchina")
                return 1
            problemi = 0
            for nome in nomi:
                stato_voce, dettaglio = stato(nome)
                print(f"{stato_voce:16} {nome:8} {dettaglio}")
                if stato_voce != "aggiornata":
                    problemi += 1
            return 1 if problemi else 0
        if args.apply:
            nomi = client_installati() if args.apply == "auto" else [args.apply]
            if not nomi:
                print("nessun client rilevato: non registro niente")
                return 1
            guasti = 0
            for nome in nomi:
                try:
                    esito, dettaglio = applica(nome, dry=args.dry_run)
                except ErroreUso as errore:
                    guasti += 1
                    print(f"{'ERRORE':12} {nome:8} {errore}")
                    continue
                print(f"{esito:12} {nome:8} {dettaglio}")
            if guasti:
                return 1
            if args.apply == "auto":
                saltati = [nome for nome in CLIENTI if nome not in nomi]
                if saltati:
                    print(f"non rilevati (saltati): {', '.join(saltati)}")
            return 0
        if args.rollback:
            print(ripristina(args.rollback))
            return 0
        if args.check_all:
            falliti = 0
            for nome in CLIENTI:
                problemi = verifica(nome)
                if problemi:
                    falliti += 1
                    for problema in problemi:
                        print(f"ERRORE  {nome}: {problema}", file=sys.stderr)
            if falliti:
                return 1
            print(f"OK   tutti e {len(CLIENTI)} i client: BLOCCHI generati validi per questa macchina")
            for nome in CLIENTI:
                stato_voce, dettaglio_stato = stato(nome)
                print(f"     installazione {nome}: {stato_voce} — {dettaglio_stato}")
            return 0
        parser.print_help()
        return 2
    except ErroreUso as errore:
        print(f"ERRORE  {errore}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
