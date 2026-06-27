# FlowInvoice PaddleOCR Backend

FastAPI service that processes documents uploaded from the client portal using **PaddleOCR**.

## Supported formats

| Format | Processing |
|--------|------------|
| PDF (text & scanned) | Rendered to images → PaddleOCR |
| Images (JPG, PNG, etc.) | PaddleOCR (includes handwritten scans) |
| Excel (.xlsx) | Direct cell extraction |
| Word (.docx) | Direct text extraction |
| Text (.txt, .md, .csv) | Direct read |
| Email (.eml) | Body + attachment OCR |

## Setup

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

First run downloads PaddleOCR models (~100MB).

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/documents/upload` | Upload document (multipart) |
| GET | `/api/documents` | List all documents (admin inbox) |
| GET | `/api/documents/{id}` | Document detail + OCR results |
| GET | `/api/documents/{id}/status` | Pipeline status (client polling) |
| GET | `/api/documents/{id}/file` | Download original file |
| PATCH | `/api/documents/{id}/fields` | Admin field corrections |
| POST | `/api/documents/{id}/reprocess` | Re-run PaddleOCR |
| GET | `/api/health` | Health check |

## Frontend

```bash
cd hackdelhi
npm run dev
```

- **Client**: `/portal/upload` — upload documents
- **Admin**: `/workspace/inbox` — view uploaded docs → Open → OCR review

Login: `user@client.com` / `user123` (client) or `admin@flowinvoice.ai` / `admin123` (admin)
