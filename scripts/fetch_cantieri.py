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

# Solo MIT SCP che funziona — ANAC blocca con 403
FONTI = [
    {"id": "mit_bandi", "nome": "MIT SCP — Bandi attivi", "ente": "MIT",
     "url": "https://dati.mit.gov.it/scp/v_od_bandi.csv", "parser": "mit_bandi"},
    {"id": "mit_atti_2024", "nome": "MIT SCP — Atti 2024", "ente": "MIT",
     "url": "https://dati.mit.gov.it/scp/v_od_atti_2024.csv", "parser": "mit_atti"},
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
    """Trova la prima colonna disponibile tra i candidati."""
    for c in candidates:
        if c in row and row[c]: return row[c]
    return "—"

def parse_mit_bandi(rows, fonte):
    items = []
    for r in rows:
        # Prova varie combinazioni di nomi colonna
        imp = pfloat(find_col(r, "importo", "IMPORTO", "valore", "VALORE"))
        if imp <= 0: continue
        stato_raw = find_col(r, "stato_bando", "STATO_BANDO", "stato", "STATO").upper()
        stato = "completato" if any(x in stato_raw for x in ["SCAD","CHIUSO","ANNULL"]) else \
                "sospeso" if "SOSP" in stato_raw else "attivo"
        items.append({
            "nome": find_col(r, "oggetto", "OGGETTO", "denominazione"),
            "citta": find_col(r, "luogo_esecuzione", "LUOGO_ESECUZIONE", "comune", "luogo"),
            "regione": find_col(r, "regione", "REGIONE", "provincia"),
            "valore": imp, "stato": stato,
            "tipo": find_col(r, "tipo_bando", "TIPO_BANDO", "tipo"),
            "tipoIntervento": find_col(r, "tipo_intervento", "TIPO_INTERVENTO", "categoria"),
            "inizio": find_col(r, "data_pubb_bando_scp", "DATA_PUBB_BANDO_SCP", "data_pubblicazione", "data"),
            "fine_prevista": find_col(r, "termine_pres_dom_off", "TERMINE_PRES_DOM_OFF", "scadenza"),
            "fonte": fonte["nome"], "ente": fonte["ente"],
            "cig": find_col(r, "cig", "CIG"),
            "cup": find_col(r, "cup", "CUP"),
            "rup": find_col(r, "rup", "RUP"),
            "stazione": find_col(r, "denominazione_stazione_appaltante", "DENOMINAZIONE_STAZIONE_APPALTANTE", "stazione_appaltante"),
            "tipoProcedura": find_col(r, "tipo_procedura", "TIPO_PROCEDURA"),
            "url": r.get("url") or r.get("URL") or None,
            "lat": None, "lng": None,
        })
    return items

def parse_mit_atti(rows, fonte):
    items = []
    for r in rows:
        imp = pfloat(find_col(r, "imp_lotto", "IMP_LOTTO", "importo_gara", "IMPORTO_GARA", "importo", "IMPORTO"))
        if imp <= 0: continue
        items.append({
            "nome": find_col(r, "oggetto_lotto", "OGGETTO_LOTTO", "oggetto_della_gara", "oggetto", "OGGETTO"),
            "citta": find_col(r, "luogo_esecuzione_istat", "LUOGO_ESECUZIONE_ISTAT", "luogo_esecuzione", "comune"),
            "regione": find_col(r, "regione", "REGIONE", "provincia"),
            "valore": imp, "stato": "completato",
            "tipo": find_col(r, "tipo_appalto", "TIPO_APPALTO", "tipo_bando", "tipo"),
            "tipoIntervento": find_col(r, "tipo_appalto", "TIPO_APPALTO", "categoria"),
            "inizio": find_col(r, "data_pubblicazione_bando", "DATA_PUBBLICAZIONE_BANDO", "data_pubblicazione"),
            "fine_prevista": find_col(r, "data_scadenza_bando", "DATA_SCADENZA_BANDO", "scadenza"),
            "fonte": fonte["nome"], "ente": fonte["ente"],
            "cig": find_col(r, "cig", "CIG"),
            "cup": find_col(r, "cup", "CUP"),
            "rup": find_col(r, "rup", "RUP"),
            "stazione": find_col(r, "denominazione_stazione_appaltante", "DENOMINAZIONE_STAZIONE_APPALTANTE"),
            "tipoProcedura": find_col(r, "tipo_procedura", "TIPO_PROCEDURA"),
            "url": r.get("url_documento") or r.get("URL_DOCUMENTO") or None,
            "lat": None, "lng": None,
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
            log.info(f"  Colonne CSV: {headers[:10]}")
            log.info(f"  Righe totali: {len(rows)}")
            items = PARSERS[fonte["parser"]](rows, fonte)
            for item in items:
                item["id"] = len(all_cantieri) + 1
            all_cantieri.extend(items)
            results.append({"id": fonte["id"], "nome": fonte["nome"], "count": len(items), "ok": True})
            log.info(f"  OK: {len(items)} cantieri estratti")
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
        log.error("ATTENZIONE: 0 cantieri salvati!")
        sys.exit(1)

if __name__ == "__main__":
    main()
