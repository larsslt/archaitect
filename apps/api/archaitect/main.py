"""Strict versioned API. No legal approvals and no fabricated cadastral information."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from .solar import SolarRequest, SolarResponse, solar_position
from .models import CommitRequest, PreviewRequest, Project, ValidationResponse
from .constraints import validate
from . import store
from .commands import DesignCommand, apply_command
from .geodata import GeoJSONParcelInput, parse_parcel
from .agent import AgentRequest, AgentUnavailable, AgentInvalidOutput, propose_meta
from . import documents
from .documents import (
    DocumentRecord, DocumentRegistry, ExtractionResult, adopt_condition,
    decode_upload, extract_candidates, intake_pdf,
)
from .scenario import EvidenceRecord, GoalSpec, RunRecord, ScenarioCondition, VariantCandidate
from .search import SearchSpace, run_search
from .models import BuildingDesign
from pydantic import BaseModel, Field
import uuid

from .siteintel.router import router as siteintel_router
registry = DocumentRegistry()

app = FastAPI(title='ArchAItect API', version='0.5.0', description='Research/demo prototype. Not a construction permit or legal assessment.')
app.add_middleware(GZipMiddleware, minimum_size=2000)   # the 360° mesh JSON is several MB
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3000','http://127.0.0.1:3000'], allow_methods=['GET','POST','PUT','DELETE'], allow_headers=['*'])
app.include_router(siteintel_router)

@app.get('/health')
def health(): return {'status':'ok', 'version':'0.5.0'}

@app.get('/projects/{project_id}', response_model=Project)
def get_project(project_id: str):
    item=store.read(project_id)
    if item is None: raise HTTPException(404, 'Project not found')
    return item

@app.post('/projects/{project_id}/validate', response_model=ValidationResponse)
def check_project(project_id: str, preview: PreviewRequest):
    original=get_project(project_id)
    return validate(original.model_copy(update={'design':preview.design}))

@app.post('/projects/{project_id}/commands/commit', response_model=Project)
def commit(project_id: str, request: CommitRequest):
    original=get_project(project_id)
    if request.design.id != original.design.id:
        raise HTTPException(422,'Design identity mismatch')
    if request.expected_version != original.design.version or request.design.version != original.design.version:
        raise HTTPException(409,'Stale revision: reload project')
    candidate=original.model_copy(update={'design':request.design})
    # The commit preserves revisioned exploratory drafts, even when they have FAIL/UNKNOWN rules.
    # A saved draft must never be presented as a legal approval.
    outcome=store.commit(project_id,candidate,request.expected_version)
    if outcome is None: raise HTTPException(409,'Concurrent update: reload project')
    return outcome

@app.post('/projects/{project_id}/commands/undo', response_model=Project)
def undo(project_id: str, request: CommitRequest):
    original=get_project(project_id)
    if request.expected_version != original.design.version:
        raise HTTPException(409,'Stale revision: reload project')
    outcome=store.undo(project_id,request.expected_version)
    if outcome is None: raise HTTPException(409,'No previous revision or concurrent update')
    return outcome

@app.get('/projects/{project_id}/report')
def report(project_id: str):
    project=get_project(project_id)
    result=validate(project)
    return {
      'project_id':project.id,
      'design_version':project.design.version,
      'disclaimer':'Exploratory concept, not planning permission or a professional legal determination.',
      'geometry_status':project.parcel.geometry_status,
      'coordinate_system':project.parcel.coordinate_system,
      'results':result.model_dump(mode='json'),
      'rules':[r.model_dump(mode='json') for r in project.rules],
      'source_url':project.parcel.source_url,
    }


class CommandPreviewRequest(PreviewRequest):
    command: DesignCommand

@app.post('/projects/{project_id}/commands/preview')
def preview_command(project_id: str, request: CommandPreviewRequest):
    project=get_project(project_id)
    if request.design.version!=project.design.version:
        raise HTTPException(409,'Stale revision: reload project')
    if request.design.id!=project.design.id:
        raise HTTPException(422,'Design identity mismatch')
    proposal=apply_command(request.design, request.command)
    return {'proposed_design': proposal, 'validation':validate(project.model_copy(update={'design':proposal})),
            'disclaimer':'Preview only. Not a statement of building-law compliance.'}

@app.get('/projects/{project_id}/revisions')
def revisions(project_id: str):
    get_project(project_id)
    return {'versions':store.history(project_id)}

@app.post('/geodata/validate')
def validate_geodata(payload: GeoJSONParcelInput):
    try:
        parcel=parse_parcel(payload)
    except (ValueError,KeyError,TypeError) as exc:
        raise HTTPException(422,str(exc)) from exc
    return {'parcel':parcel,'verified':False,
            'warning':'Not attached to any project. Proof of parcel identity and zoning applicability is required.'}


@app.post('/projects/{project_id}/agent/preview')
def preview_meta_agent(project_id: str, request: AgentRequest):
    project = get_project(project_id)
    if request.design.id != project.design.id:
        raise HTTPException(422, 'Design identity mismatch')
    if request.design.version != project.design.version:
        raise HTTPException(409, 'Stale revision: reload project')
    # LLM gets only whitelisted scalar building dimensions, not documents or secrets.
    try:
        suggestion = propose_meta(request)
    except AgentUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except AgentInvalidOutput as exc:
        raise HTTPException(422, str(exc)) from exc
    proposed = apply_command(request.design, suggestion.command)
    return {
        'command': suggestion.command,
        'proposed_design': proposed,
        'validation': validate(project.model_copy(update={'design': proposed})),
        'provider': suggestion.provider,
        'model': suggestion.model,
        'usage': {'input_tokens': suggestion.input_tokens, 'output_tokens': suggestion.output_tokens},
        'disclaimer': 'Preview only. No legal assessment; nothing saved.'
    }

@app.post('/simulation/solar', response_model=SolarResponse)
def simulate_solar(request: SolarRequest):
    if not request.is_timezone_aware:
        raise HTTPException(422, 'timestamp requires a timezone offset')
    return solar_position(request)


class IntakeRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    content_base64: str = Field(min_length=1)


class AdoptRequest(BaseModel):
    evidence: EvidenceRecord
    rule_id: str = Field(min_length=1, max_length=80)


@app.post('/documents/intake', response_model=DocumentRecord)
def upload_document(request: IntakeRequest):
    # Early size guard on the encoded payload, before decoding.
    if len(request.content_base64) > 7_000_000:
        raise HTTPException(413, 'Document exceeds size limit')
    try:
        data = decode_upload(request.content_base64)
    except documents.DocumentInvalid as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        record = intake_pdf(data, request.filename)
    except documents.DocumentTooLarge as exc:
        raise HTTPException(413, str(exc)) from exc
    except documents.DocumentNeedsOcr as exc:
        raise HTTPException(422, str(exc)) from exc
    except documents.DocumentInvalid as exc:
        raise HTTPException(422, str(exc)) from exc
    registry.documents[record.document_id] = record
    registry.raw[record.document_id] = data
    return record


@app.get('/documents')
def list_documents():
    return [{'document_id': d.document_id, 'filename': d.filename, 'sha256': d.sha256,
             'page_count': d.page_count, 'needs_review': d.needs_review}
            for d in registry.documents.values()]


@app.get('/documents/{document_id}', response_model=DocumentRecord)
def get_document(document_id: str):
    record = registry.documents.get(document_id)
    if record is None:
        raise HTTPException(404, 'Document not found')
    return record


@app.post('/documents/{document_id}/extract', response_model=ExtractionResult)
def extract_document(document_id: str):
    record = registry.documents.get(document_id)
    if record is None:
        raise HTTPException(404, 'Document not found')
    return extract_candidates(record)


@app.post('/scenarios/conditions/adopt', response_model=ScenarioCondition)
def adopt_evidence(request: AdoptRequest):
    try:
        return adopt_condition(registry, request.evidence, request.rule_id)
    except documents.HashConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except documents.ProvenanceFailure as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get('/scenarios/conditions', response_model=list[ScenarioCondition])
def list_conditions():
    return registry.conditions


class RunRequest(BaseModel):
    design: BuildingDesign
    goal: GoalSpec = Field(default_factory=lambda: GoalSpec(objective='balanced'))
    space: SearchSpace = Field(default_factory=SearchSpace)
    rule_ids: list[str] = Field(default_factory=list)


class StoredRun(BaseModel):
    run: RunRecord
    variants: list[VariantCandidate]
    project_id: str
    design_version: int
    scenario_version: int
    conditions: list[ScenarioCondition] = Field(default_factory=list)


runs: dict[str, StoredRun] = {}


def _resolve_conditions(rule_ids: list[str]) -> list[ScenarioCondition]:
    resolved: list[ScenarioCondition] = []
    for rule_id in rule_ids:
        match = next((c for c in registry.conditions if c.rule_id == rule_id), None)
        if match is None:
            raise HTTPException(422, f'Unknown adopted condition: {rule_id}')
        doc_id = match.evidence_id.split('#p')[0]
        stored = registry.documents.get(doc_id)
        seen = registry.condition_sources.get(rule_id)
        if stored is None or seen != stored.sha256:
            raise HTTPException(409, 'Scenario changed since adoption: re-extract and re-adopt')
        resolved.append(match)
    return resolved


@app.post('/projects/{project_id}/runs', response_model=StoredRun)
def start_run(project_id: str, request: RunRequest):
    project = get_project(project_id)
    if request.design.id != project.design.id:
        raise HTTPException(422, 'Design identity mismatch')
    if request.design.version != project.design.version:
        raise HTTPException(409, 'Stale revision: reload project')
    conditions = _resolve_conditions(request.rule_ids)
    scenario_version = max(registry.scenario_version, 1)
    record = RunRecord(run_id=f'run-{uuid.uuid4().hex[:8]}', project_id=project_id,
                       design_version=request.design.version,
                       scenario_version=scenario_version, goal=request.goal)
    try:
        record, variants = run_search(project.parcel, request.design, conditions,
                                      request.goal, request.space, record,
                                      evidence_ids=[c.evidence_id for c in conditions])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    stored = StoredRun(run=record, variants=variants, project_id=project_id,
                       design_version=request.design.version,
                       scenario_version=scenario_version,
                       conditions=conditions)
    runs[record.run_id] = stored
    return stored


@app.get('/projects/{project_id}/runs')
def list_runs(project_id: str):
    get_project(project_id)
    return [{'run_id': s.run.run_id, 'state': s.run.state,
             'design_version': s.design_version,
             'scenario_version': s.scenario_version,
             'variant_count': len(s.variants)} for s in runs.values()
            if s.project_id == project_id]


@app.get('/projects/{project_id}/runs/{run_id}', response_model=StoredRun)
def get_run(project_id: str, run_id: str):
    stored = runs.get(run_id)
    if stored is None or stored.project_id != project_id:
        raise HTTPException(404, 'Run not found')
    return stored


@app.get('/projects/{project_id}/runs/{run_id}/report')
def run_report(project_id: str, run_id: str):
    stored = runs.get(run_id)
    if stored is None or stored.project_id != project_id:
        raise HTTPException(404, 'Run not found')
    return {
        'project_id': stored.project_id,
        'design_version': stored.design_version,
        'scenario_version': stored.scenario_version,
        'disclaimer': ('Exploratory concept, not planning permission or a professional '
                       'legal determination. Sampled best only, not a proven global optimum.'),
        'goal': stored.run.goal.model_dump(mode='json'),
        'model_calls': stored.run.model_calls,
        'model_note': 'No model calls were used; search and repair ran deterministically offline.',
        'conditions': [c.model_dump(mode='json') for c in stored.conditions],
        'variants': [
            {'metrics': v.metrics.model_dump(mode='json'),
             'feasible': v.feasible,
             'violations': [x.model_dump(mode='json') for x in v.violations],
             'evidence_ids': v.evidence_ids,
             'design': v.design.model_dump(mode='json')}
            for v in stored.variants
        ],
        'run_log': stored.run.log,
        'outcome': stored.run.state,
    }
