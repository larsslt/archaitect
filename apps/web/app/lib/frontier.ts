// Frontier DTOs. Mirror the FastAPI documents/scenario/search/run contracts.
export type EvidenceStatus = 'VERIFIED' | 'EXTRACTED' | 'DEMO_ASSUMPTION';

export interface Design {
  id: string; version: number; center_x: number; center_y: number;
  width_m: number; depth_m: number; rotation_deg: number; storeys: number;
  eave_height_m: number; ridge_height_m: number;
  roof_type: 'gable' | 'flat'; roof_pitch_deg: number;
}

export interface EvidenceRecord {
  document_id: string;
  document_sha256: string;
  page_index: number; // 0-based; UI shows page_index + 1
  quote: string;
  kind: string;
  value: number | null;
  unit: string | null;
  status: EvidenceStatus;
}

export interface PageText {
  page_index: number;
  text: string;
  has_text: boolean;
  instruction_markers: boolean;
}

export interface DocumentRecord {
  document_id: string;
  filename: string;
  sha256: string;
  page_count: number;
  pages: PageText[];
  needs_review: boolean;
  review_reasons: string[];
}

export interface SkippedPassage {
  page_index: number;
  snippet: string;
  reason: string;
}

export interface ExtractionResult {
  candidates: EvidenceRecord[];
  skipped: SkippedPassage[];
  warnings: string[];
}

export interface ScenarioCondition {
  rule_id: string;
  kind: string;
  value: number;
  unit: string | null;
  evidence_id: string;
  adopted: boolean;
}

export interface CounterExample {
  condition_id: string;
  observed: number;
  limit: number;
  design_param: string;
}

export interface VariantMetrics {
  footprint_m2: number;
  gross_floor_area_m2: number;
  ridge_height_m: number;
  storeys: number;
}

export interface VariantCandidate {
  design: Design;
  metrics: VariantMetrics;
  violations: CounterExample[];
  evidence_ids: string[];
}

export type RunState =
  | 'queued' | 'planning' | 'searching' | 'verifying'
  | 'repairing' | 'ready' | 'cancelled' | 'failed' | 'no_solution';

export interface RunRecord {
  run_id: string;
  project_id: string;
  design_version: number;
  scenario_version: number;
  goal: { objective: string; max_variants: number; note: string };
  state: RunState;
  model_calls: number;
  repairs: number;
  log: string[];
}

export interface StoredRun {
  run: RunRecord;
  variants: VariantCandidate[];
  project_id: string;
  design_version: number;
  scenario_version: number;
  conditions: ScenarioCondition[];
}
