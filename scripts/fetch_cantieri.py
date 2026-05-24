#!/usr/bin/env python3
"""
Building Radar Italia — Data Fetcher
Scarica i CSV da MIT SCP e ANAC, li converte in JSON e salva in /data/.
Eseguito ogni giorno da GitHub Actions.
"""

import csv
import io
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

TIMEOUT = 60  # secondi
HEADERS = {"User-Agent": "CantierTrack/1.0 (github.com; open-data aggregator)"}
MAX_ROWS = 15000  # per fonte

# ── Fonti ─────────────────────────────────────────────────────
# Solo fonti con bandi ATTIVI — gli Atti MIT sono archivi storici
# di gare già concluse, quindi esclusi
FONTI = [
    {
        "id": "mit_bandi",
        "nome": "MIT SCP — Bandi attivi",
        "url": "https://dati.mit.gov.it/scp/v_od_bandi.csv",
        "parser": "mit_bandi",
        "ente": "MIT",
    },
    {
        "id": "anac_cig_2025_05",
        "nome": "ANAC BandiCIG — Mag 2025",
        "url": "https://dati.anticorruzione.it/opendata/download/dataset/cig-2025/filesystem/cig_csv_2025_05.csv",
        "parser": "anac_cig",
        "ente": "ANAC",
    },
    {
        "id": "anac_cig_2025_04",
        "nome": "ANAC BandiCIG — Apr 2025",
        "url": "https://dati.anticorruzione.it/opendata/download/dataset/cig-2025/filesystem/cig_csv_2025_04.csv",
        "parser": "anac_cig",
        "ente": "ANAC",
    },
    {
        "id": "anac_cig_2025_03",
        "nome": "ANAC BandiCIG — Mar 2025",
        "url": "https://dati.anticorruzione.it/opendata/download/dataset/cig-2025/filesystem/cig_csv_2025_03.csv",
        "parser": "anac_cig",
        "ente": "ANAC",
    },
    {
        "id": "anac_cig_2025_02",
        "nome": "ANAC BandiCIG — Feb 2025",
        "url": "https://dati.anticorruzione.it/opendata/download/dataset/cig-2025/filesystem/cig_csv_2025_02.csv",
        "parser": "anac_cig",
        "ente": "ANAC",
    },
    {
        "id": "anac_cig_2025_01",
        "nome": "ANAC BandiCIG — Gen 2025",
        "url": "https://dati.anticorruzione.it/opendata/download/dataset/cig-2025/filesystem/cig_csv_2025_01.csv",
        "parser": "anac_cig",
        "ente": "ANAC",
    },
    {
        "id": "anac_cig_2024_12",
        "nome": "ANAC BandiCIG — Dic 2024",
        "url": "https://dati.anticorruzione.it/opendata/download/dataset/cig-2024/filesystem/cig_csv_2024_12.csv",
        "parser": "anac_cig",
        "ente": "ANAC",
    },
    {
        "id": "anac_pnrr",
        "nome": "ANAC — Bandi PNRR",
        "url": "https://dati.anticorruzione.it/opendata/download/dataset/pnrr/filesystem/pnrr_csv.csv",
        "parser": "anac_pnrr",
        "ente": "ANAC",
    },
]


# ── CSV helpers ───────────────────────────────────────────────
def read_csv(text: str, max_rows: int = MAX_ROWS) -> list[dict]:
    text = text.strip()
    if not text:
        return []
    first_line = text.split("\n")[0]
    delim = ";" if first_line.count(";") >= first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    rows = []
    for i, row in enumerate(reader):
        if i >= max_rows:
            break
        rows.append({k.strip(): (v or "").strip() for k, v in row.items()})
    return rows


def pfloat(val: str) -> float:
    try:
        return float(val.replace(",", ".").replace(" ", "").replace(".", "", val.count(".") - 1) if val.count(".") > 1 else val.replace(",", "."))
    except Exception:
        return 0.0


# ── Parsers ───────────────────────────────────────────────────
def parse_mit_bandi(rows: list[dict], fonte: dict) -> list[dict]:
    items = []
    for r in rows:
        imp = pfloat(r.get("importo", "0"))
        if imp <= 0:
            continue
        # Stato reale dal CSV — se non presente considera attivo
        stato_raw = (r.get("stato_bando") or r.get("stato") or "").upper()
        if "SCAD" in stato_raw or "CHIUSO" in stato_raw or "ANNULL" in stato_raw:
            stato = "completato"
        elif "SOSP" in stato_raw:
            stato = "sospeso"
        else:
            stato = "attivo"  # PUBBLICATO, IN CORSO, o vuoto → attivo
        items.append({
            "nome": r.get("oggetto") or "Bando SCP",
            "citta": r.get("luogo_esecuzione") or "—",
            "regione": "",
            "indirizzo": r.get("luogo_esecuzione") or "—",
            "lat": None, "lng": None,
            "valore": imp,
            "stato": stato,
            "tipo": r.get("tipo_bando") or "Lavori",
            "tipoIntervento": r.get("tipo_intervento") or "—",
            "inizio": r.get("data_pubb_bando_scp") or "—",
            "fine_prevista": r.get("termine_pres_dom_off") or "—",
            "fonte": fonte["nome"],
            "ente": fonte["ente"],
            "cig": r.get("cig") or "—",
            "cup": r.get("cup") or "—",
            "rup": r.get("rup") or "—",
            "stazione": r.get("denominazione_stazione_appaltante") or "—",
            "impresa": "—",
            "tipoProcedura": r.get("tipo_procedura") or "—",
            "url": r.get("url") or None,
            "professionisti": [], "permessi": [],
        })
    return items


def parse_mit_atti(rows: list[dict], fonte: dict) -> list[dict]:
    items = []
    for r in rows:
        imp = pfloat(r.get("imp_lotto") or r.get("importo_gara") or "0")
        if imp <= 0:
            continue
        items.append({
            "nome": r.get("oggetto_lotto") or r.get("oggetto_della_gara") or "Atto SCP",
            "citta": r.get("luogo_esecuzione_istat") or "—",
            "regione": "",
            "indirizzo": r.get("luogo_esecuzione_istat") or "—",
            "lat": None, "lng": None,
            "valore": imp,
            "stato": "completato",
            "tipo": r.get("tipo_appalto") or "Lavori",
            "tipoIntervento": r.get("tipo_appalto") or "—",
            "inizio": r.get("data_pubblicazione_bando") or "—",
            "fine_prevista": r.get("data_scadenza_bando") or "—",
            "fonte": fonte["nome"],
            "ente": fonte["ente"],
            "cig": r.get("cig") or "—",
            "cup": r.get("cup") or "—",
            "rup": r.get("rup") or "—",
            "stazione": r.get("denominazione_stazione_appaltante") or "—",
            "impresa": "—",
            "tipoProcedura": r.get("tipo_procedura") or "—",
            "url": r.get("url_documento") or None,
            "professionisti": [], "permessi": [],
        })
    return items


def parse_anac_cig(rows: list[dict], fonte: dict) -> list[dict]:
    items = []
    for r in rows:
        imp = pfloat(r.get("importo_complessivo_gara") or r.get("importo") or "0")
        if imp <= 0:
            continue
        items.append({
            "nome": r.get("oggetto") or r.get("oggetto_gara") or "Appalto ANAC",
            "citta": r.get("provincia") or r.get("luogo_istat") or "—",
            "regione": r.get("regione") or "",
            "indirizzo": r.get("luogo_istat") or r.get("provincia") or "—",
            "lat": None, "lng": None,
            "valore": imp,
            "stato": "attivo",
            "tipo": r.get("tipo_appalto") or "Lavori",
            "tipoIntervento": r.get("tipo_appalto") or "—",
            "inizio": r.get("data_pubblicazione") or "—",
            "fine_prevista": r.get("data_scadenza") or "—",
            "fonte": fonte["nome"],
            "ente": fonte["ente"],
            "cig": r.get("cig") or "—",
            "cup": r.get("cup") or "—",
            "rup": r.get("rup") or "—",
            "stazione": r.get("denominazione_amministrazione_appaltante") or r.get("stazione_appaltante") or "—",
            "impresa": "—",
            "tipoProcedura": r.get("modalita_realizzazione") or r.get("scelta_contraente") or "—",
            "url": None,
            "professionisti": [], "permessi": [],
        })
    return items


def parse_anac_pnrr(rows: list[dict], fonte: dict) -> list[dict]:
    items = []
    for r in rows:
        imp = pfloat(r.get("importo_complessivo_gara") or r.get("importo") or "0")
        if imp <= 0:
            continue
        nome = r.get("oggetto") or r.get("descrizione") or "Bando PNRR"
        items.append({
            "nome": "🇪🇺 " + nome,
            "citta": r.get("provincia") or "—",
            "regione": r.get("regione") or "",
            "indirizzo": r.get("provincia") or "—",
            "lat": None, "lng": None,
            "valore": imp,
            "stato": "attivo",
            "tipo": "Lavori PNRR",
            "tipoIntervento": r.get("tipo_appalto") or "PNRR",
            "inizio": r.get("data_pubblicazione") or "—",
            "fine_prevista": r.get("data_scadenza") or "—",
            "fonte": fonte["nome"],
            "ente": fonte["ente"],
            "cig": r.get("cig") or "—",
            "cup": r.get("cup") or "—",
            "rup": r.get("rup") or "—",
            "stazione": r.get("denominazione_amministrazione_appaltante") or "—",
            "impresa": "—",
            "tipoProcedura": r.get("scelta_contraente") or "—",
            "url": None,
            "professionisti": [], "permessi": [],
        })
    return items


PARSERS = {
    "mit_bandi": parse_mit_bandi,
    "mit_atti": parse_mit_atti,
    "anac_cig": parse_anac_cig,
    "anac_pnrr": parse_anac_pnrr,
}


# ── Main fetch loop ───────────────────────────────────────────
def fetch_fonte(fonte: dict) -> list[dict]:
    log.info(f"  Scarico {fonte['id']} da {fonte['url']}")
    try:
        resp = requests.get(fonte["url"], headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        # Prova encoding dichiarato, fallback utf-8, poi latin-1
        for enc in [resp.encoding, "utf-8", "latin-1"]:
            try:
                text = resp.content.decode(enc or "utf-8")
                break
            except Exception:
                continue
        rows = read_csv(text)
        if not rows:
            log.warning(f"  {fonte['id']}: CSV vuoto o non leggibile")
            return []
        parser = PARSERS[fonte["parser"]]
        items = parser(rows, fonte)
        log.info(f"  {fonte['id']}: {len(items)} cantieri estratti")
        return items
    except requests.HTTPError as e:
        log.error(f"  {fonte['id']}: HTTP {e.response.status_code}")
        return []
    except Exception as e:
        log.error(f"  {fonte['id']}: {e}")
        return []


def main():
    log.info("=== Building Radar Italia — Fetch avviato ===")
    now = datetime.now(timezone.utc).isoformat()

    all_cantieri = []
    results = []

    for fonte in FONTI:
        items = fetch_fonte(fonte)
        # Assegna ID progressivo globale
        for item in items:
            item["id"] = len(all_cantieri) + 1
            all_cantieri.append(item)
        results.append({
            "id": fonte["id"],
            "nome": fonte["nome"],
            "ente": fonte["ente"],
            "count": len(items),
            "ok": len(items) > 0,
        })

    # Salva cantieri.json
    output = {
        "aggiornato": now,
        "totale": len(all_cantieri),
        "fonti": results,
        "cantieri": all_cantieri,
    }
    out_path = DATA_DIR / "cantieri.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    log.info(f"=== Salvati {len(all_cantieri)} cantieri totali in {out_path} ===")

    # Salva anche un manifest leggero (solo stats, senza cantieri)
    manifest = {k: v for k, v in output.items() if k != "cantieri"}
    with open(DATA_DIR / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # Exit code 1 se nessuna fonte ha funzionato
    if not any(r["ok"] for r in results):
        log.error("Nessuna fonte ha restituito dati!")
        sys.exit(1)


if __name__ == "__main__":
    main()
