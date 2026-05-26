#!/usr/bin/env python3
"""
CantierTrack — Data Fetcher
Scarica CSV da MIT SCP e ANAC, converte in JSON, salva in /data/cantieri.json
"""
import csv, io, json, logging, sys
from datetime import datetime, timezone
from pathlib import Path
import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

HEADERS = {"User-Agent": "CantierTrack/1.0 (academic project, github.com)"}
TIMEOUT = 45
MAX_ROWS = 10000

FONTI = [
    {"id": "mit_bandi",        "nome": "MIT SCP — Bandi attivi",      "ente": "MIT",
     "url": "https://dati.mit.gov.it/scp/v_od_bandi.csv",             "parser": "mit_bandi"},
    {"id": "anac_cig_2025_05", "nome": "ANAC BandiCIG — Mag 2025",    "ente": "ANAC",
     "url": "https://dati.anticorruzione.it/opendata/download/dataset/cig-2025/filesystem/cig_csv_2025_05.csv", "parser": "anac_cig"},
    {"id": "anac_cig_2025_04", "nome": "ANAC BandiCIG — Apr 2025",    "ente": "ANAC",
     "url": "https://dati.anticorruzione.it/opendata/download/dataset/cig-2025/filesystem/cig_csv_2025_04.csv", "parser": "anac_cig"},
    {"id": "anac_cig_2025_03", "nome": "ANAC BandiCIG — Mar 2025",    "ente": "ANAC",
     "url": "https://dati.anticorruzione.it/opendata/download/dataset/cig-2025/filesystem/cig_csv_2025_03.csv", "parser": "anac_cig"},
    {"id": "anac_cig_2025_02", "nome": "ANAC BandiCIG — Feb 2025",    "ente": "ANAC",
     "url": "https://dati.anticorruzione.it/opendata/download/dataset/cig-2025/filesystem/cig_csv_2025_02.csv", "parser": "anac_cig"},
    {"id": "anac_pnrr",        "nome": "ANAC — Bandi PNRR",           "ente": "ANAC",
     "url": "https://dati.anticorruzione.it/opendata/download/dataset/pnrr/filesystem/pnrr_csv.csv",            "parser": "anac_pnrr"},
]

def read_csv(text):
    text = text.strip()
    if not text: return []
    first = text.split("\n")[0]
    delim = ";" if first.count(";") >= first.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    rows = []
    for i, row in enumerate(reader):
        if i >= MAX_ROWS: break
        rows.append({k.strip(): (v or "").strip() for k, v in row.items()})
    return rows

def pfloat(v):
    try: return float(str(v).replace(",", ".").strip())
    except: return 0.0

def parse_mit_bandi(rows, fonte):
    items = []
    for r in rows:
        imp = pfloat(r.get("importo", "0"))
        if imp <= 0: continue
        stato_raw = (r.get("stato_bando") or "").upper()
        stato = "completato" if any(x in stato_raw for x in ["SCAD","CHIUSO","ANNULL"]) else \
                "sospeso" if "SOSP" in stato_raw else "attivo"
        items.append({
            "nome": r.get("oggetto") or "Bando SCP",
            "citta": r.get("luogo_esecuzione") or "—", "regione": "",
            "valore": imp, "stato": stato,
            "tipo": r.get("tipo_bando") or "Lavori",
            "tipoIntervento": r.get("tipo_intervento") or "—",
            "inizio": r.get("data_pubb_bando_scp") or "—",
            "fine_prevista": r.get("termine_pres_dom_off") or "—",
            "fonte": fonte["nome"], "ente": fonte["ente"],
            "cig": r.get("cig") or "—", "cup": r.get("cup") or "—",
            "rup": r.get("rup") or "—",
            "stazione": r.get("denominazione_stazione_appaltante") or "—",
            "tipoProcedura": r.get("tipo_procedura") or "—",
            "url": r.get("url") or None,
            "lat": None, "lng": None,
        })
    return items

def parse_anac_cig(rows, fonte):
    items = []
    for r in rows:
        imp = pfloat(r.get("importo_complessivo_gara") or r.get("importo") or "0")
        if imp <= 0: continue
        items.append({
            "nome": r.get("oggetto") or "Appalto ANAC",
            "citta": r.get("provincia") or "—",
            "regione": r.get("regione") or "",
            "valore": imp, "stato": "attivo",
            "tipo": r.get("tipo_appalto") or "Lavori",
            "tipoIntervento": r.get("tipo_appalto") or "—",
            "inizio": r.get("data_pubblicazione") or "—",
            "fine_prevista": r.get("data_scadenza") or "—",
            "fonte": fonte["nome"], "ente": fonte["ente"],
            "cig": r.get("cig") or "—", "cup": r.get("cup") or "—",
            "rup": r.get("rup") or "—",
            "stazione": r.get("denominazione_amministrazione_appaltante") or "—",
            "tipoProcedura": r.get("scelta_contraente") or "—",
            "url": None, "lat": None, "lng": None,
        })
    return items

def parse_anac_pnrr(rows, fonte):
    items = []
    for r in rows:
        imp = pfloat(r.get("importo_complessivo_gara") or r.get("importo") or "0")
        if imp <= 0: continue
        nome = r.get("oggetto") or "Bando PNRR"
        items.append({
            "nome": "🇪🇺 " + nome,
            "citta": r.get("provincia") or "—",
            "regione": r.get("regione") or "",
            "valore": imp, "stato": "attivo",
            "tipo": "Lavori PNRR", "tipoIntervento": "PNRR",
            "inizio": r.get("data_pubblicazione") or "—",
            "fine_prevista": r.get("data_scadenza") or "—",
            "fonte": fonte["nome"], "ente": fonte["ente"],
            "cig": r.get("cig") or "—", "cup": r.get("cup") or "—",
            "rup": r.get("rup") or "—",
            "stazione": r.get("denominazione_amministrazione_appaltante") or "—",
            "tipoProcedura": r.get("scelta_contraente") or "—",
            "url": None, "lat": None, "lng": None,
        })
    return items

PARSERS = {"mit_bandi": parse_mit_bandi, "anac_cig": parse_anac_cig, "anac_pnrr": parse_anac_pnrr}

def main():
    log.info("=== CantierTrack Fetch avviato ===")
    all_cantieri = []
    results = []

    for fonte in FONTI:
        log.info(f"Scarico {fonte['id']}...")
        try:
            resp = requests.get(fonte["url"], headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            for enc in ["utf-8", "latin-1"]:
                try: text = resp.content.decode(enc); break
                except: continue
            rows = read_csv(text)
            items = PARSERS[fonte["parser"]](rows, fonte)
            for item in items:
                item["id"] = len(all_cantieri) + 1
            all_cantieri.extend(items)
            results.append({"id": fonte["id"], "nome": fonte["nome"], "count": len(items), "ok": True})
            log.info(f"  OK: {len(items)} cantieri")
        except Exception as e:
            log.error(f"  ERRORE: {e}")
            results.append({"id": fonte["id"], "nome": fonte["nome"], "count": 0, "ok": False})

    output = {
        "aggiornato": datetime.now(timezone.utc).isoformat(),
        "totale": len(all_cantieri),
        "fonti": results,
        "cantieri": all_cantieri,
    }

    out_path = DATA_DIR / "cantieri.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    log.info(f"=== Salvati {len(all_cantieri)} cantieri in {out_path} ===")

    if not any(r["ok"] for r in results):
        log.error("Nessuna fonte ha funzionato!")
        sys.exit(1)

if __name__ == "__main__":
    main()
