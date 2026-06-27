import random
import string
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Document
from ..schemas import (
    DocumentDetailSchema,
    DocumentSummarySchema,
    StatusResponseSchema,
    UpdateFieldsSchema,
    UploadResponseSchema,
    build_pipeline_stages,
    document_to_detail,
    document_to_summary,
)
from ..services.ocr_service import process_document, save_upload

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _generate_intake_id(db: Session) -> str:
    for _ in range(10):
        num = random.randint(4000, 9999)
        intake_id = f"INT-{num}"
        if not db.query(Document).filter(Document.intake_id == intake_id).first():
            return intake_id
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"INT-{suffix}"


def _run_ocr_pipeline(document_id: str):
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return

        time.sleep(0.5)
        doc.pipeline_stage = "OCR Complete"
        doc.status = "Processing"
        db.commit()

        result = process_document(doc.storage_path, doc.mime_type, doc.filename)

        doc.raw_text = result["raw_text"]
        doc.ocr_result = result["ocr_result"]
        doc.extracted_fields = result["extracted_fields"]
        doc.confidence_overall = result["ocr_result"].get("confidence_overall", 0)

        avg_conf = doc.confidence_overall or 0

        for stage in ["Employee Validation", "Business Validation", "AI Review"]:
            time.sleep(0.8)
            doc.pipeline_stage = stage
            doc.status = "Processing"
            db.commit()

        time.sleep(0.5)
        doc.pipeline_stage = "Invoice Generated"
        doc.status = "Completed" if avg_conf >= 0.85 else "Pending Review"
        db.commit()

    except Exception as exc:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.status = "Failed Extraction"
            doc.pipeline_stage = "OCR Complete"
            doc.error_message = str(exc)
            db.commit()
    finally:
        db.close()


@router.post("/upload", response_model=UploadResponseSchema)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    client_name: str = Form(default="Client Portal"),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    storage_path, mime_type, file_size = save_upload(file_bytes, file.filename)

    doc = Document(
        intake_id=_generate_intake_id(db),
        filename=file.filename,
        mime_type=mime_type,
        file_size=file_size,
        storage_path=storage_path,
        client_name=client_name,
        source="Portal Upload",
        status="Processing",
        pipeline_stage="Document Received",
        priority="Medium",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(_run_ocr_pipeline, doc.id)

    return UploadResponseSchema(
        id=doc.id,
        intake_id=doc.intake_id,
        filename=doc.filename,
        status=doc.status,
        message="Document uploaded. OCR processing started.",
    )


@router.get("", response_model=list[DocumentSummarySchema])
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    return [document_to_summary(doc) for doc in docs]


@router.get("/{document_id}", response_model=DocumentDetailSchema)
def get_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return document_to_detail(doc)


@router.get("/{document_id}/status", response_model=StatusResponseSchema)
def get_document_status(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return StatusResponseSchema(
        id=doc.id,
        intake_id=doc.intake_id,
        filename=doc.filename,
        status=doc.status,
        pipeline_stage=doc.pipeline_stage,
        stages=build_pipeline_stages(doc.pipeline_stage, doc.status),
        confidence_overall=doc.confidence_overall,
        error_message=doc.error_message,
    )


@router.get("/{document_id}/file")
def get_document_file(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    path = Path(doc.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(path, media_type=doc.mime_type, filename=doc.filename)


@router.patch("/{document_id}/fields", response_model=DocumentDetailSchema)
def update_fields(document_id: str, payload: UpdateFieldsSchema, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    fields = dict(doc.extracted_fields or {})
    for key, value in payload.fields.items():
        existing = fields.get(key, {"value": "", "confidence": 0})
        fields[key] = {"value": value, "confidence": 100}

    doc.extracted_fields = fields
    db.commit()
    db.refresh(doc)
    return document_to_detail(doc)


@router.post("/{document_id}/reprocess", response_model=UploadResponseSchema)
def reprocess_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.status = "Processing"
    doc.pipeline_stage = "Document Received"
    doc.error_message = None
    db.commit()

    background_tasks.add_task(_run_ocr_pipeline, doc.id)

    return UploadResponseSchema(
        id=doc.id,
        intake_id=doc.intake_id,
        filename=doc.filename,
        status=doc.status,
        message="Re-processing started.",
    )
