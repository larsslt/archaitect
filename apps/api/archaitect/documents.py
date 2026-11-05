"""Phase-2 document intake: PDF text, hash and page-index provenance.

Offline deterministic baseline. Uploaded bytes are DATA: they never unlock
tools, change system rules, contact remotes or request secrets. Scanned pages
without extractable text take the explicit 'not yet supported' path.
Meta-assisted extraction is a later, separately gated adapter; this module
is the deterministic extractor it will be measured against.
"""
import base64
import binascii
import hashlib
import io
import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from pydantic import BaseModel, Field

from .models import EvidenceStatus
from .scenario import EvidenceRecord, ScenarioCondition

MAX_PDF_BYTES = 5_000_000
MAX_PAGES = 20

GERMAN_NUMBERS = {
    'eins': 1, 'eine': 1, 'einem': 1, 'einen': 1,
    'zwei': 2, 'drei': 3, 'vier': 4, 'fünf': 5,
    'sechs': 6, 'sieben': 7, 'acht': 8, 'neun': 9, 'zehn': 10,
}

# Sentence-level patterns for the supported condition kinds. Deliberately
# narrow: anything that does not match is reported as skipped, never guessed.
_PATTERNS: dict[str, list[str]] = {
    'MAX_STOREYS': [
        r'(?:maximal|höchstens|max\.?)\s+(\d+|[a-zäöü]+)\s+(?:voll)?\s*geschosse?',
    ],
    'MAX_FOOTPRINT': [
        r'(?:maximale|max\.?)?\s*(?:grundfläche|überbaubare fläche|bebauung)\s*(?:von|bis zu|höchstens|maximal)?\s*(\d+[.,]?\d*)\s*m',
    ],
    'MAX_HEIGHT': [
        r'(?:firsthöhe|gebäudehöhe|traufhöhe|bauhöhe)\s*(?:von|bis zu|höchstens|maximal)?\s*(\d+[.,]?\d*)\s*m',
    ],
    'ROOF_PITCH': [
        r'dachneigung\s*(?:von|bis zu|von bis)?\s*(\d+[.,]?\d*)\s*°?',
    ],
}

# Kinds we recognize but explicitly do NOT support in the foundation slice.
# They must be rejected visibly, never aliased onto supported kinds.
_UNSUPPORTED_HINTS: dict[str, str] = {
    'GRZ': 'GRZ is a site-coverage ratio, not an absolute MAX_FOOTPRINT',
    'GFZ': 'GFZ is a floor-space ratio, not a MAX_STOREYS count',
    'BAUGRENZE': 'Baugrenze needs georeferenced envelope geometry',
    'ABSTANDSFLÄCHE': 'Abstandsfläche needs georeferenced envelope geometry',
    'GESCHOSSZAHL': 'ambiguous without Vollgeschoss definition',
}

# Markers that flag instructional content inside documents. Flagged pages
# stay usable as DATA but require human review before adoption.
_INSTRUCTION_MARKERS = (
    'ignore previous', 'ignore all previous', 'ignoriere',
    'du bist jetzt', 'als system', 'system:',
    'reveal your', 'zeige deine', 'prompt injection',
    'override', 'jailbreak', 'weise an',
)


class DocumentTooLarge(Exception):
    pass


class DocumentInvalid(Exception):
    pass


class DocumentNeedsOcr(Exception):
    """Scanned pages without extractable text: explicit unsupported path."""


class HashConflict(Exception):
    pass


class ProvenanceFailure(Exception):
    pass


class PageText(BaseModel):
    page_index: int = Field(ge=0)
    text: str = ''
    has_text: bool = False
    instruction_markers: bool = False


class DocumentRecord(BaseModel):
    document_id: str
    filename: str
    sha256: str
    page_count: int = Field(ge=1)
    pages: list[PageText]
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)


class SkippedPassage(BaseModel):
    page_index: int
    snippet: str
    reason: str


class ExtractionResult(BaseModel):
    candidates: list[EvidenceRecord] = Field(default_factory=list)
    skipped: list[SkippedPassage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DocumentRegistry:
    """Foundation in-memory registry. SQLite persistence is a later slice."""

    def __init__(self) -> None:
        self.documents: dict[str, DocumentRecord] = {}
        self.raw: dict[str, bytes] = {}
        self.conditions: list[ScenarioCondition] = []
        self.condition_sources: dict[str, str] = {}
        self.scenario_version: int = 0

    def clear(self) -> None:
        self.documents.clear()
        self.raw.clear()
        self.conditions.clear()
        self.condition_sources.clear()
        self.scenario_version = 0

    def note_adoption(self) -> int:
        self.scenario_version += 1
        return self.scenario_version


def _parse_number(token: str) -> float | None:
    token = token.strip().lower().replace(',', '.')
    try:
        return float(token)
    except ValueError:
        pass
    if token in GERMAN_NUMBERS:
        return float(GERMAN_NUMBERS[token])
    return None


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]


def _normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip().lower()


def decode_upload(content_base64: str) -> bytes:
    try:
        return base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise DocumentInvalid('upload is not valid base64') from exc


def intake_pdf(data: bytes, filename: str) -> DocumentRecord:
    """Validate, parse and fingerprint one small PDF with extractable text."""
    if len(data) > MAX_PDF_BYTES:
        raise DocumentTooLarge(f'PDF exceeds {MAX_PDF_BYTES} bytes')
    if not data.startswith(b'%PDF'):
        raise DocumentInvalid('not a PDF file: magic bytes missing')
    try:
        reader = PdfReader(io.BytesIO(data))
        raw_pages = list(reader.pages)
    except (PdfReadError, ValueError, IndexError) as exc:
        raise DocumentInvalid(f'unreadable PDF: {exc}') from exc
    if len(raw_pages) > MAX_PAGES:
        raise DocumentInvalid(f'PDF has {len(raw_pages)} pages, limit is {MAX_PAGES}')
    digest = hashlib.sha256(data).hexdigest()
    pages: list[PageText] = []
    reasons: list[str] = []
    for index, page in enumerate(raw_pages):
        try:
            text = page.extract_text() or ''
        except (ValueError, TypeError):
            text = ''
        text = text.strip()
        markers = _normalize(text) and any(m in _normalize(text) for m in _INSTRUCTION_MARKERS)
        pages.append(PageText(page_index=index, text=text,
                              has_text=bool(text), instruction_markers=bool(markers)))
    if not any(p.has_text for p in pages):
        raise DocumentNeedsOcr('no extractable text: scanned documents are not yet supported')
    for page in pages:
        if not page.has_text:
            reasons.append(f'page {page.page_index + 1}: scanned or empty, excluded from extraction')
        if page.instruction_markers:
            reasons.append(f'page {page.page_index + 1}: instructional markers found, treated as data pending review')
    return DocumentRecord(
        document_id=f'doc-{digest[:12]}',
        filename=filename,
        sha256=digest,
        page_count=len(pages),
        pages=pages,
        needs_review=bool(reasons),
        review_reasons=reasons,
    )


def extract_candidates(doc: DocumentRecord) -> ExtractionResult:
    """Deterministic baseline extractor: supported kinds with page provenance.

    Returns candidates (status EXTRACTED), visibly skipped passages and
    warnings. Never invents values for unmappable rules.
    """
    result = ExtractionResult()
    for page in doc.pages:
        if not page.has_text:
            continue
        for sentence in _sentences(page.text):
            lowered = sentence.lower()
            matched = False
            for kind, patterns in _PATTERNS.items():
                for pattern in patterns:
                    found = re.search(pattern, lowered)
                    if not found:
                        continue
                    value = _parse_number(found.group(1))
                    if value is None:
                        continue
                    matched = True
                    unit = {'MAX_STOREYS': 'storeys', 'MAX_FOOTPRINT': 'm2',
                            'MAX_HEIGHT': 'm', 'ROOF_PITCH': 'deg'}[kind]
                    result.candidates.append(EvidenceRecord(
                        document_id=doc.document_id,
                        document_sha256=doc.sha256,
                        page_index=page.page_index,
                        quote=sentence.strip(),
                        kind=kind,
                        value=value,
                        unit=unit,
                        status=EvidenceStatus.EXTRACTED,
                    ))
                    break
                if matched:
                    break
            if not matched:
                for hint, reason in _UNSUPPORTED_HINTS.items():
                    if hint.lower() in lowered:
                        result.skipped.append(SkippedPassage(
                            page_index=page.page_index,
                            snippet=sentence.strip()[:200],
                            reason=reason,
                        ))
                        break
        if page.instruction_markers:
            result.warnings.append(
                f'page {page.page_index + 1}: instructional markers treated as data, '
                'no instruction executed; review before adoption')
    return result


def verify_quote(doc: DocumentRecord, page_index: int, quote: str) -> bool:
    """Check the quote against the actually extracted page text."""
    if not quote.strip():
        return False
    if page_index < 0 or page_index >= len(doc.pages):
        return False
    return _normalize(quote) in _normalize(doc.pages[page_index].text)


def adopt_condition(registry: DocumentRegistry, evidence: EvidenceRecord,
                    rule_id: str) -> ScenarioCondition:
    """Adopt one verified-quote candidate into the investigated scenario.

    Adoption is an explicit user act and never upgrades provenance:
    the condition references EXTRACTED evidence, never VERIFIED.
    """
    doc = registry.documents.get(evidence.document_id)
    if doc is None:
        raise ProvenanceFailure('unknown document')
    if evidence.document_sha256 != doc.sha256:
        raise HashConflict('document changed since extraction: re-extract before adoption')
    if not verify_quote(doc, evidence.page_index, evidence.quote):
        raise ProvenanceFailure('quote not found on the cited page')
    if evidence.kind not in ('MAX_STOREYS', 'MAX_FOOTPRINT', 'MAX_HEIGHT', 'ROOF_PITCH'):
        raise ProvenanceFailure(f'unsupported rule kind: {evidence.kind}')
    if evidence.value is None:
        raise ProvenanceFailure('no value: refusing silent default')
    condition = ScenarioCondition(
        rule_id=rule_id,
        kind=evidence.kind,
        value=evidence.value,
        unit=evidence.unit,
        evidence_id=f'{doc.document_id}#p{evidence.page_index + 1}',
        adopted=True,
    )
    registry.conditions.append(condition)
    registry.condition_sources[rule_id] = evidence.document_sha256
    registry.note_adoption()
    return condition
