export type Page = "sources" | "profile" | "ask" | "history" | "settings";

export type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
  };
};

export type HealthStatus = {
  status: "ok";
  environment: string;
  model: string;
};

export type ColumnProfile = {
  name: string;
  dtype: string;
  non_null_count: number;
  null_count: number;
  null_rate: number;
  unique_count: number;
  sample_values: unknown[];
  summary: Record<string, unknown>;
};

export type DatasetProfile = {
  dataset_id: string;
  source_name: string;
  source_type: string;
  row_count: number;
  column_count: number;
  duplicate_rows: number;
  columns: ColumnProfile[];
  anomalies: string[];
  created_at: string;
};

export type DatasetInfo = {
  dataset_id: string;
  source_name: string;
  source_type: string;
  row_count: number;
  column_count: number;
  profile: DatasetProfile;
};

export type DatasetPreview = {
  dataset_id: string;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  returned_rows: number;
};

export type AnalysisPlan = {
  operation: string;
  objective: string;
  required_columns: string[];
  assumptions: string[];
  chart_type: string;
};

export type ChartSpec = {
  chart_type: "bar" | "line" | "scatter" | "heatmap" | "distribution" | "table";
  title: string;
  x?: string | null;
  y?: string | null;
  color?: string | null;
  caption: string;
};

export type ExecutionResult = {
  success: boolean;
  result_columns: string[];
  result_rows: Record<string, unknown>[];
  chart_spec: ChartSpec | null;
  stdout: string;
  error: string | null;
  attempts: number;
};

export type Narrative = {
  key_finding: string;
  business_meaning: string;
  limitations: string[];
  follow_up_questions: string[];
};

export type AnalysisResponse = {
  session_id: string;
  dataset_id: string;
  question: string;
  plan: AnalysisPlan;
  generated_code: string;
  execution: ExecutionResult;
  narrative: Narrative;
  created_at: string;
};

export type SessionRecord = {
  record_id: string;
  session_id: string;
  dataset_id: string;
  question: string;
  response: AnalysisResponse;
  created_at: string;
};

export class ApiClientError extends Error {
  code: string;
  details?: unknown;
  status?: number;

  constructor(code: string, message: string, details?: unknown, status?: number) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.details = details;
    this.status = status;
  }
}
