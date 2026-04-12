# e-Arzuhal – Statistics Service

Sözleşme özellik kullanım istatistikleri ve öneri mikroservisi.

---

## Genel Bakış

Bu FastAPI servisi her sözleşme tipinde hangi özelliklerin (maddeler, alanlar) kullanıldığını takip eder. Yeni bir sözleşme analiz edildiğinde:

1. Sözleşmenin özellik kümesini veritabanına kaydeder
2. Benzer sözleşmelerde yaygın olan özellikleri hesaplar (≥ %30 kullanım)
3. Mevcut sözleşmede eksik olan özellikler için **öneriler** döner

---

## Tech Stack

| Katman | Teknoloji |
|--------|-----------|
| Language | Python 3.11+ |
| Framework | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic 1.14 |
| DB (dev) | SQLite (`statistics.db` — gitignore'da) |
| DB (prod) | PostgreSQL 16 |
| Validation | Pydantic v2 |
| Testing | pytest + httpx |

---

## Kurulum

```bash
cd statistics-server
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8002
```

SQLite veritabanı `./statistics.db` konumunda otomatik oluşturulur.
Bu dosya `.gitignore`'da tanımlıdır — commit edilmez.

---

## API Endpoints

### GET /health

```json
{ "status": "ok", "version": "1.0.0", "service": "e-Arzuhal Statistics Service" }
```

### POST /contracts/analyze

Sözleşme kaydını sakla ve önerileri al.

**İstek:**
```json
{
  "contract_type": "kira_sozlesmesi",
  "features": ["kira_bedeli", "depozito"],
  "fields": { "kira_bedeli": "15000", "adres": "Kadikoy" },
  "completeness_score": 75.0
}
```

**Yanıt:**
```json
{
  "contract_type": "kira_sozlesmesi",
  "record_id": 42,
  "recommendations": [
    {
      "feature_name": "sozlesme_suresi",
      "usage_percentage": 87.5,
      "message": "Bu alan benzer sözleşmelerin %87.5'inde yer alıyor."
    }
  ],
  "stats_summary": {
    "total_contracts": 8,
    "avg_completeness": 82.3
  }
}
```

### GET /stats/{contract_type}

Sözleşme tipi için istatistikleri getir.

---

## Öneri Mantığı

```
usage_percentage = (bu_ozellige_sahip_sozlesmeler / ayni_tipteki_toplam) x 100

Öneri koşulları:
  usage_percentage >= threshold (varsayılan: %30)
  AND özellik mevcut sözleşmede YOK

Azalan usage_percentage'a göre sırala, en fazla N öneri döndür (varsayılan: 5)
```

---

## Ortam Değişkenleri

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `DATABASE_URL` | `sqlite:///./statistics.db` | DB bağlantı dizesi |
| `DEBUG` | `true` | Swagger UI + detaylı log |
| `ALLOWED_ORIGINS` | `http://localhost:8080` | CORS whitelist |
| `INTERNAL_API_KEY` | _(boş)_ | Prod'da main-server ile aynı olmalı |
| `RECOMMENDATION_THRESHOLD` | `30.0` | Öneri eşiği (%) |
| `RECOMMENDATION_TOP_N` | `5` | Maks öneri sayısı |

---

## Güvenlik

- `ALLOWED_ORIGINS` prod'da yalnızca `main-server` adresi olmalı — frontend doğrudan erişemez.
- `INTERNAL_API_KEY` set edilmemişse (dev) kontrol atlanır; set edilmişse `X-Internal-API-Key` header zorunlu.
- `DEBUG=false` (prod): Swagger devre dışı.

---

## Testler

```bash
pytest tests/ -v
```

---

## main-server Entegrasyonu

`main-server`'daki `StatisticsService.java` bu servisi çağırır:

```
POST http://localhost:8002/contracts/analyze
```

NLP + GraphRAG pipeline'ı tamamlandıktan sonra tespit edilen özellikler ve tamamlanma skoru iletilir.

---

## Maintainer

e-Arzuhal Team — Statistics & Recommendation Service
