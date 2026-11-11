"""Intake, preprocessing, field mapping, caching, and safety guards for uploads."""

import hashlib
import io
import json
import logging
import re
from pathlib import Path
from typing import Any
from PIL import Image, ImageOps
import fitz  # PyMuPDF

from config.settings import settings
from agent.schemas import FormField, FormTemplateDraft, UploadAnalysis, SchemeSummary

logger = logging.getLogger(__name__)

# Prompt injection patterns to detect and neutralize
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    re.compile(r"disregard\s+the\s+above", re.IGNORECASE),
    re.compile(r"override\s+system\s+prompt", re.IGNORECASE),
]

# Field label alias dictionary for deterministic mapping
FIELD_LABEL_ALIASES: dict[str, str] = {
    # Name
    "नाम": "profile.name",
    "आवेदक का नाम": "profile.name",
    "applicant name": "profile.name",
    "full name": "profile.name",
    "name of applicant": "profile.name",
    # Demographics
    "उम्र": "profile.age",
    "आयु": "profile.age",
    "age": "profile.age",
    "लिंग": "profile.gender",
    "gender": "profile.gender",
    "वार्षिक आय": "profile.annual_income",
    "income": "profile.annual_income",
    "annual income": "profile.annual_income",
    "family income": "profile.annual_income",
    # Location
    "राज्य": "profile.state",
    "state": "profile.state",
    "जिला": "profile.district",
    "district": "profile.district",
    "गाँव": "profile.village_or_city",
    "ग्राम": "profile.village_or_city",
    "शहर": "profile.village_or_city",
    "village": "profile.village_or_city",
    "city": "profile.village_or_city",
    # Documents & Bank
    "आधार": "documents.aadhaar.id_number",
    "आधार नंबर": "documents.aadhaar.id_number",
    "aadhaar": "documents.aadhaar.id_number",
    "aadhaar number": "documents.aadhaar.id_number",
    "aadhaar no": "documents.aadhaar.id_number",
    "खाता संख्या": "documents.bank_passbook.id_number",
    "बैंक खाता": "documents.bank_passbook.id_number",
    "bank account": "documents.bank_passbook.id_number",
    "account number": "documents.bank_passbook.id_number",
    "ifsc": "documents.bank_passbook.ifsc",
    "ifsc code": "documents.bank_passbook.ifsc",
    # Land & Agriculture
    "भूमि": "profile.land_holding",
    "जमीन": "profile.land_holding",
    "कृषि भूमि": "profile.land_holding",
    "land area": "profile.land_holding",
    "land holding": "profile.land_holding",
    "khasra": "documents.land_records.id_number",
    "खतौनी": "documents.land_records.id_number",
}


def sanitize_extracted_text(text: str) -> str:
    """Neutralize prompt injection text inside document uploads."""
    sanitized = text
    for pattern in INJECTION_PATTERNS:
        if pattern.search(sanitized):
            logger.warning("Detected potential prompt injection in uploaded document text. Neutralizing.")
            sanitized = pattern.sub("[REDACTED_USER_TEXT]", sanitized)
    return sanitized


def compute_content_hash(file_bytes: bytes) -> str:
    """Calculate SHA256 hex digest of file content for draft_id and caching."""
    return hashlib.sha256(file_bytes).hexdigest()[:16]


def get_drafts_dir() -> Path:
    """Return path to form templates draft directory."""
    drafts_dir = settings.TEMPLATES_DIR / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    return drafts_dir


def check_cached_template(draft_id: str) -> FormTemplateDraft | None:
    """Check if template exists in drafts or approved templates."""
    # Check approved templates
    approved_path = settings.TEMPLATES_DIR / f"{draft_id}.json"
    if approved_path.exists():
        with open(approved_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return FormTemplateDraft.model_validate(data)

    # Check drafts
    draft_path = get_drafts_dir() / f"{draft_id}.json"
    if draft_path.exists():
        with open(draft_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return FormTemplateDraft.model_validate(data)

    return None


def save_draft_template(draft: FormTemplateDraft) -> Path:
    """Save template draft into forms/templates/drafts/<draft_id>.json."""
    draft_path = get_drafts_dir() / f"{draft.draft_id}.json"
    with open(draft_path, "w", encoding="utf-8") as f:
        f.write(draft.model_dump_json(indent=2))
    return draft_path


def map_field_to_profile(label: str) -> str | None:
    """Match form label against dictionary aliases."""
    clean = label.strip().lower()
    clean = re.sub(r"[:\-_/]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()

    if clean in FIELD_LABEL_ALIASES:
        return FIELD_LABEL_ALIASES[clean]

    for alias, hint in FIELD_LABEL_ALIASES.items():
        if alias in clean:
            return hint
    return None


def normalize_and_map_fields(fields: list[FormField]) -> tuple[list[FormField], float]:
    """Ensure unique snake_case keys, assign profile hints, and compute mapping coverage."""
    seen_keys: set[str] = set()
    mapped_count = 0
    total_required = sum(1 for f in fields if f.required)

    normalized: list[FormField] = []
    for f in fields:
        # Profile hint mapping first
        hint = f.profile_hint or map_field_to_profile(f.label_original) or map_field_to_profile(f.label_simple)

        # Generate clean ASCII snake_case key
        if hint:
            derived_key = hint.replace("profile.", "").replace("documents.", "").replace(".id_number", "").replace(".", "_")
        else:
            derived_key = f.key

        raw_key = re.sub(r"[^a-zA-Z0-9_\s]", "", derived_key.lower())
        clean_key = re.sub(r"\s+", "_", raw_key).strip("_") or "field"

        # Deduplicate
        final_key = clean_key
        counter = 1
        while final_key in seen_keys:
            final_key = f"{clean_key}_{counter}"
            counter += 1
        seen_keys.add(final_key)

        updated_field = FormField(
            key=final_key,
            label_original=f.label_original,
            label_simple=f.label_simple,
            type=f.type,
            required=f.required,
            options=f.options,
            section=f.section,
            profile_hint=hint,
            confidence=f.confidence,
        )
        normalized.append(updated_field)
        if updated_field.required and hint:
            mapped_count += 1

    coverage = round(mapped_count / total_required, 3) if total_required > 0 else 1.0
    return normalized, coverage


def process_upload_bytes(file_bytes: bytes, filename: str) -> tuple[str, list[Path]]:
    """Process uploaded PDF, Image, or text document into normalized image or reference paths."""
    draft_id = compute_content_hash(file_bytes)
    temp_dir = settings.BASE_DIR / "uploads" / draft_id
    temp_dir.mkdir(parents=True, exist_ok=True)

    image_paths: list[Path] = []
    lower_name = filename.lower()

    if lower_name.endswith(".pdf"):
        # Split PDF pages
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            pix = page.get_pixmap(dpi=150)
            page_path = temp_dir / f"page_{page_idx + 1}.png"
            pix.save(str(page_path))
            image_paths.append(page_path)
        doc.close()
    elif any(lower_name.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")):
        # Image processing: auto-rotate via EXIF and resize to max 2000px
        image = Image.open(io.BytesIO(file_bytes))
        image = ImageOps.exif_transpose(image)
        max_dim = 2000
        if max(image.size) > max_dim:
            image.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        out_path = temp_dir / "image.png"
        image.save(out_path, format="PNG")
        image_paths.append(out_path)
    else:
        # Text/document file: save as source reference
        out_path = temp_dir / filename
        out_path.write_bytes(file_bytes)
        image_paths.append(out_path)

    return draft_id, image_paths
