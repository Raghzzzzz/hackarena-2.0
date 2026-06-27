from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routes.documents import router as documents_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FlowInvoice OCR API",
    description="PaddleOCR-powered document processing for FlowInvoice AI",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "engine": "paddleocr"}
