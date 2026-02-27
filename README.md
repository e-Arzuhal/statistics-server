# e-Arzuhal – Statistics Service

Contract feature usage statistics and recommendation microservice.

---

## Overview

This FastAPI service tracks which features (clauses, fields) appear in contracts of each type. When a new contract is analyzed, it:

1. Stores the contract's feature set in the database
2. Computes which features are commonly present in similar contracts (>= 30% usage)
3. Returns **recommendations** for features the current contract is missing

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Framework | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic 1.14 |
| DB (dev) | SQLite |
| DB (prod) | PostgreSQL 16 |
| Validation | Pydantic v2 |
| Testing | pytest + httpx |

---

## Quick Start (Development)

```bash
cd statistics-server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8002
```

SQLite database is created automatically at `./statistics.db`.

---

## API Endpoints

### `GET /health`
```json
{ "status": "ok", "version": "1.0.0", "service": "e-Arzuhal Statistics Service" }
```

### `POST /contracts/analyze`

Store a contract record and receive feature recommendations.

**Request:**
```json
{
  "contract_type": "kira_sozlesmesi",
  "features": ["kira_bedeli", "depozito"],
  "fields": { "kira_bedeli": "15000", "adres": "Kadikoy" },
  "completeness_score": 75.0
}
```

**Response:**
```json
{
  "contract_type": "kira_sozlesmesi",
  "record_id": 42,
  "recommendations": [
    {
      "feature_name": "sozlesme_suresi",
      "usage_percentage": 87.5,
      "count": 7,
      "total": 8,
      "message": "Bu alan benzer sozlesmelerin %87.5'inde yer aliyor. Eklemeyi dusunebilirsiniz."
    }
  ],
  "stats_summary": {
    "total_contracts": 8,
    "avg_completeness": 82.3
  }
}
```

### `GET /stats/{contract_type}`

Get aggregated statistics for a contract type.

**Response:**
```json
{
  "contract_type": "kira_sozlesmesi",
  "total_contracts": 42,
  "feature_stats": [
    { "feature_name": "kira_bedeli", "count": 42, "usage_percentage": 100.0 },
    { "feature_name": "depozito", "count": 38, "usage_percentage": 90.5 }
  ],
  "avg_completeness": 78.4
}
```

---

## Recommendation Logic

```
usage_percentage = (contracts_with_feature / total_contracts_of_same_type) x 100

Recommend if:
  usage_percentage >= threshold (default: 30%)
  AND feature is NOT already present in the current contract

Sort by usage_percentage descending, return top N (default: 5)
```

Configurable via environment variables:
- `RECOMMENDATION_THRESHOLD` — percentage threshold (default: `30.0`)
- `RECOMMENDATION_TOP_N` — max recommendations returned (default: `5`)

---

## Environment Variables

`.env.example` dosyasindan kopyalayin:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./statistics.db` | DB baglanti dizesi |
| `DEBUG` | `true` | Swagger UI + detayli log |
| `ALLOWED_ORIGINS` | `http://localhost:8080` | CORS whitelist (virgülle ayrilmis) |
| `INTERNAL_API_KEY` | _(bos)_ | Servisler arasi API anahtari |
| `RECOMMENDATION_THRESHOLD` | `30.0` | Oneri esigi (%) |
| `RECOMMENDATION_TOP_N` | `5` | Maks oneri sayisi |

---

## Security

### CORS

`ALLOWED_ORIGINS` environment variable ile izin verilen origin'ler belirlenir.
Production'da yalnizca `main-server` adresini ekleyin — frontend dogrudan bu servise erisemez:

```
ALLOWED_ORIGINS=http://main-server:8080
```

### Internal API Key Middleware

- `INTERNAL_API_KEY` **set edilmemisse** (dev): kontrol atlanir.
- **Set edilmisse** (prod): `X-Internal-API-Key` header'i eslesmeyen istekler `401` alir.
- `/health` endpoint'i her zaman serbest.

`main-server`'in `INTERNAL_API_KEY` degeriyle ayni olmalidir:

```bash
# Uretmek icin:
openssl rand -hex 32
```

### Swagger UI

- `DEBUG=true`: `/docs` erisilebilir.
- `DEBUG=false` (prod): Swagger devre disi.

---

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## Main Server Integration

The main Spring Boot server (`main-server`) calls this service from `StatisticsService.java`:

```
POST http://localhost:8002/contracts/analyze
```

This is triggered after a contract is analyzed by the NLP + GraphRAG pipeline, passing the detected features and completeness score.

---

## Maintainer

e-Arzuhal Team -- Statistics & Recommendation Service
