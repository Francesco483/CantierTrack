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

## Setup (5 minuti)

### 1. Fork o clona questo repository su GitHub

```bash
git clone https://github.com/TUO_USERNAME/building-radar-italia.git
cd building-radar-italia
```

### 2. Aggiorna l'URL nel frontend

Apri `building-radar-italia.html` e cerca questa riga:

```javascript
const GITHUB_DATA_URL = 'https://raw.githubusercontent.com/TUO_USERNAME/building-radar-italia/main/data/cantieri.json';
```

Sostituisci `TUO_USERNAME` con il tuo username GitHub.

### 3. Attiva GitHub Actions

1. Vai su **Settings → Actions → General**
2. Assicurati che "Allow all actions" sia abilitato
3. Vai su **Actions** → seleziona "Aggiorna dati cantieri" → clicca **Run workflow**

Il primo aggiornamento partirà subito. Poi girerà automaticamente ogni giorno.

### 4. (Opzionale) Pubblica su GitHub Pages

1. Vai su **Settings → Pages**
2. Source: **Deploy from a branch** → `main` → `/ (root)`
3. Il tuo sito sarà disponibile su `https://TUO_USERNAME.github.io/building-radar-italia/`

## Struttura del repository

```
building-radar-italia/
├── building-radar-italia.html   ← App frontend (unico file)
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

## Aggiornamento manuale

Puoi forzare un aggiornamento in qualsiasi momento:

```bash
pip install requests
python scripts/fetch_cantieri.py
```

Oppure da GitHub: **Actions → Aggiorna dati cantieri → Run workflow**
