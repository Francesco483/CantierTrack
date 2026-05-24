# CantierTrack 🏗

Dashboard per monitorare cantieri e appalti pubblici italiani.
I dati vengono aggiornati **ogni giorno alle 08:00** in modo completamente automatico da fonti istituzionali (MIT, ANAC).

## Come funziona

```
Ogni giorno alle 08:00
       ↓
GitHub Actions esegue scripts/fetch_cantieri.py
       ↓
Scarica CSV da MIT SCP + ANAC (senza CORS, lato server)
       ↓
Converte in JSON → salva in data/cantieri.json
       ↓
Il frontend legge raw.githubusercontent.com (CORS libero ✅)
```

## Struttura del repository

```
CantierTrack/
├── cantiertrack.html            ← App frontend (unico file)
├── data/
│   ├── cantieri.json            ← Dati aggiornati da GitHub Actions
│   └── manifest.json           ← Statistiche ultimo aggiornamento
├── scripts/
│   └── fetch_cantieri.py        ← Script di fetch dati
└── .github/workflows/
    └── aggiorna-dati.yml        ← Workflow automatico quotidiano
```

## Fonti dati

| Fonte | Ente | Contenuto | Frequenza |
|---|---|---|---|
| SCP v_od_bandi.csv | MIT | Bandi attivi | Quotidiana |
| SCP v_od_atti_2024.csv | MIT | Tutti gli atti 2024 | Annuale |
| SCP v_od_atti_2023.csv | MIT | Tutti gli atti 2023 | Archivio |
| cig_csv_2025_*.csv | ANAC | Gare >40k€ mensili | Mensile |
| pnrr_csv.csv | ANAC | Gare PNRR | Mensile |

Tutti i dati provengono da portali open data governativi italiani, liberamente accessibili a chiunque.

## Aggiornamento manuale

Puoi forzare un aggiornamento in qualsiasi momento da GitHub:
**Actions → Aggiorna dati cantieri → Run workflow**

Oppure in locale:
```bash
pip install requests
python scripts/fetch_cantieri.py
```

## Pubblicazione su GitHub Pages

1. Vai su **Settings → Pages**
2. Source: **Deploy from branch** → `main` → `/ (root)` → **Save**
3. L'app sarà disponibile su `https://Francesco483.github.io/CantierTrack/cantiertrack.html`
