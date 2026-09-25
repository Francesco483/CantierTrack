#!/usr/bin/env python3
import csv, io, json, logging, sys
from datetime import datetime, timezone
from pathlib import Path
import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CantierTrack/1.0; academic project)"}
TIMEOUT = 45
MAX_ROWS = 10000

FONTI = [
    {"id": "mit_bandi", "nome": "MIT SCP — Bandi attivi", "ente": "MIT",
     "url": "https://dati.mit.gov.it/scp/v_od_bandi.csv", "parser": "mit_bandi"},
    {"id": "mit_atti_2023", "nome": "MIT SCP — Atti 2023", "ente": "MIT",
     "url": "https://dati.mit.gov.it/scp/v_od_atti_2023.csv", "parser": "mit_atti"},
]

def read_csv(text):
    text = text.strip()
    if not text: return [], []
    first = text.split("\n")[0]
    delim = ";" if first.count(";") >= first.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    rows = []
    headers = []
    for i, row in enumerate(reader):
        if i == 0: headers = list(row.keys())
        if i >= MAX_ROWS: break
        rows.append({k.strip(): (v or "").strip() for k, v in row.items()})
    return rows, headers

def pfloat(v):
    try: return float(str(v).replace(",", ".").replace(" ", "").strip())
    except: return 0.0

def find_col(row, *candidates):
    for c in candidates:
        if c in row and row[c] and row[c] != "—": return row[c]
    return "—"

def parse_mit_bandi(rows, fonte):
    items = []
    for r in rows:
        imp = pfloat(find_col(r, "importo_gara", "importo"))
        if imp <= 0: continue
        items.append({
            "nome": find_col(r, "oggetto_della_gara", "oggetto"),
            "citta": "—", "regione": "",
            "valore": imp, "stato": "attivo",
            "tipo": find_col(r, "modalita_realizzazione", "settore"),
            "tipoIntervento": find_col(r, "settore", "modalita_realizzazione"),
            "inizio": "—", "fine_prevista": "—",
            "fonte": fonte["nome"], "ente": fonte["ente"],
            "cig": find_col(r, "numero_gara_anac", "id_gara"),
            "cup": "—",
            "rup": find_col(r, "rup"),
            "stazione": find_col(r, "denominazione_stazione_appaltante"),
            "tipoProcedura": find_col(r, "modalita_realizzazione"),
            "url": None, "lat": None, "lng": None,
        })
    return items

def parse_mit_atti(rows, fonte):
    items = []
    for r in rows:
        imp = pfloat(find_col(r, "importo_gara", "imp_lotto", "importo"))
        if imp <= 0: continue
        items.append({
            "nome": find_col(r, "oggetto_della_gara", "oggetto_lotto", "oggetto"),
            "citta": find_col(r, "luogo_istat", "luogo_esecuzione_istat", "comune"),
            "regione": find_col(r, "regione", "provincia"),
            "valore": imp, "stato": "completato",
            "tipo": find_col(r, "modalita_realizzazione", "settore"),
            "tipoIntervento": find_col(r, "settore", "modalita_realizzazione"),
            "inizio": find_col(r, "data_pubblicazione", "dt_upd"),
            "fine_prevista": find_col(r, "data_scadenza"),
            "fonte": fonte["nome"], "ente": fonte["ente"],
            "cig": find_col(r, "numero_gara_anac", "cig", "id_gara"),
            "cup": find_col(r, "cup"),
            "rup": find_col(r, "rup"),
            "stazione": find_col(r, "denominazione_stazione_appaltante"),
            "tipoProcedura": find_col(r, "modalita_realizzazione"),
            "url": None, "lat": None, "lng": None,
        })
    return items

PARSERS = {"mit_bandi": parse_mit_bandi, "mit_atti": parse_mit_atti}

def main():
    log.info("=== CantierTrack Fetch avviato ===")
    all_cantieri = []
    results = []

    for fonte in FONTI:
        log.info(f"Scarico {fonte['id']}...")
        try:
            resp = requests.get(fonte["url"], headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            for enc in ["utf-8", "latin-1", "iso-8859-1"]:
                try: text = resp.content.decode(enc); break
                except: continue
            rows, headers = read_csv(text)
            log.info(f"  Colonne: {headers[:8]}")
            items = PARSERS[fonte["parser"]](rows, fonte)
            # ID univoci progressivi
            for i, item in enumerate(items):
                item["id"] = len(all_cantieri) + i + 1
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

    log.info(f"=== Salvati {len(all_cantieri)} cantieri ===")
    if len(all_cantieri) == 0:
        log.error("0 cantieri!")
        sys.exit(1)

if __name__ == "__main__":
    main()
