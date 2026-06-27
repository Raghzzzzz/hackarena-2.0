import re
from typing import Any


def _avg_confidence(entities: list[dict]) -> float:
    if not entities:
        return 0.0
    return round(sum(e.get("conf", 0) for e in entities) / len(entities), 4)


def _strip_label(text: str, labels: list[str]) -> str:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*[:\-]?\s*(.+)", text, re.I)
        if match:
            return match.group(1).strip()
    return text.strip()


def extract_fields_from_text(text: str, entities: list[dict]) -> dict[str, dict[str, Any]]:
    """Heuristic field extraction from OCR text for timesheet documents."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    joined = "\n".join(lines)

    def find_entity(entity_type: str, fallback: str = "") -> tuple[str, float]:
        matches = [e for e in entities if e.get("type") == entity_type]
        if matches:
            best = max(matches, key=lambda x: x.get("conf", 0))
            return best["text"], round(best.get("conf", 0) * 100)
        return fallback, 0

    employee_name, name_conf = find_entity("PERSON")
    employee_id, id_conf = find_entity("ID")
    client_name, client_conf = find_entity("ORG")
    period, period_conf = find_entity("DATE_RANGE")
    regular_hours, reg_conf = find_entity("HOURS_REGULAR")
    overtime_hours, ot_conf = find_entity("HOURS_OVERTIME")
    signature, sig_conf = find_entity("SIGNATURE")

    if not employee_name:
        name_match = re.search(
            r"(?:employee\s*name|name|contractor)\s*[:\-]?\s*([A-Za-z][A-Za-z\s\.\-']{1,40}?)(?:\s*$|\s*(?:employee|emp|id|client|billing|regular|overtime|manager))",
            joined,
            re.I | re.M,
        )
        if name_match:
            employee_name = name_match.group(1).strip()
            name_conf = 88

    if not employee_id:
        id_match = re.search(r"(?:employee\s*id|emp\s*id|id)\s*[:\-]?\s*([A-Z0-9\-]{3,20})", joined, re.I)
        if id_match:
            employee_id = id_match.group(1).strip()
            id_conf = 90
        else:
            emp_match = re.search(r"\b(EMP[\-\s]?\d+)\b", joined, re.I)
            if emp_match:
                employee_id = emp_match.group(1).upper().replace(" ", "-")
                id_conf = 85

    if not client_name:
        client_match = re.search(
            r"(?:client|company|organization)\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\s\.\,&\-]{2,50})",
            joined,
            re.I,
        )
        if client_match:
            client_name = client_match.group(1).strip()
            client_conf = 86

    if not period:
        period_match = re.search(
            r"(?:billing\s*period|period|date\s*range)?\s*[:\-]?\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:\s*[-–to]+\s*\d{1,2})?,?\s*\d{4})",
            joined,
            re.I,
        )
        if period_match:
            period = period_match.group(1).strip()
            period_conf = 84
        else:
            date_range = re.search(r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\s*[-–to]+\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})", joined)
            if date_range:
                period = date_range.group(1)
                period_conf = 82

    if not regular_hours:
        reg_match = re.search(r"(?:regular|standard|normal)\s*(?:hours|hrs)?\s*[:\-]?\s*(\d+(?:\.\d+)?)", joined, re.I)
        if reg_match:
            regular_hours = reg_match.group(1)
            reg_conf = 92

    if not overtime_hours:
        ot_match = re.search(r"(?:overtime|ot)\s*(?:hours|hrs)?\s*[:\-]?\s*(\d+(?:\.\d+)?)", joined, re.I)
        if ot_match:
            overtime_hours = ot_match.group(1)
            ot_conf = 78

    if not signature:
        sig_match = re.search(r"(?:signature|signed|approved)\s*[:\-]?\s*(present|yes|signed|[A-Za-z\.\s]{2,30})", joined, re.I)
        if sig_match:
            signature = sig_match.group(1).strip()
            sig_conf = 88
        elif re.search(r"(?:signature|signed|approved)", joined, re.I):
            signature = "Present"
            sig_conf = 75

    employee_name = _strip_label(employee_name, ["employee name", "name", "contractor"]) if employee_name else ""
    employee_id = _strip_label(employee_id, ["employee id", "emp id", "id"]) if employee_id else ""
    client_name = _strip_label(client_name, ["client", "company", "organization"]) if client_name else ""
    period = _strip_label(period, ["billing period", "period", "date range"]) if period else ""
    regular_hours = _strip_label(regular_hours, ["regular hours", "regular hrs", "regular"]) if regular_hours else ""
    overtime_hours = _strip_label(overtime_hours, ["overtime hours", "overtime hrs", "overtime", "ot"]) if overtime_hours else ""
    signature = _strip_label(signature, ["manager signature", "signature", "signed", "approved"]) if signature else ""

    return {
        "employeeName": {"value": employee_name or "—", "confidence": name_conf or 70},
        "employeeId": {"value": employee_id or "—", "confidence": id_conf or 70},
        "clientName": {"value": client_name or "—", "confidence": client_conf or 70},
        "period": {"value": period or "—", "confidence": period_conf or 70},
        "regularHours": {"value": regular_hours or "—", "confidence": reg_conf or 70},
        "overtimeHours": {"value": overtime_hours or "—", "confidence": ot_conf or 70},
        "managerSignature": {"value": signature or "—", "confidence": sig_conf or 70},
    }


def classify_entities(text: str, bbox: list[float], conf: float) -> str:
    """Assign semantic entity types from OCR line text."""
    lower = text.lower()
    if re.search(r"\bemp[\-\s]?\d+\b", text, re.I):
        return "ID"
    if re.search(r"(?:regular|standard)\s*(?:hours|hrs)?", lower):
        return "HOURS_REGULAR"
    if re.search(r"(?:overtime|ot)\s*(?:hours|hrs)?", lower):
        return "HOURS_OVERTIME"
    if re.search(r"(?:signature|signed|approved)", lower):
        return "SIGNATURE"
    if re.search(
        r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}[\/\-]\d{1,2})",
        lower,
    ):
        return "DATE_RANGE"
    if re.search(r"(?:ltd|inc|corp|company|infosys|tcs|wipro|cognizant)", lower):
        return "ORG"
    if re.match(r"^[A-Z][a-z]+(?:\s[A-Z][a-z]+)+$", text.strip()):
        return "PERSON"
    if re.search(r"\d+\.?\d*", text) and len(text.strip()) <= 6:
        return "NUMBER"
    return "TEXT"


def build_ocr_result(raw_text: str, entities: list[dict]) -> dict[str, Any]:
    return {
        "document_type": "timesheet",
        "confidence_overall": _avg_confidence(entities),
        "entities": entities,
        "full_text": raw_text,
    }
