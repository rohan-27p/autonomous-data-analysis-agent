import {
  AnalysisResponse,
  ApiClientError,
  ApiErrorPayload,
  DatasetInfo,
  DatasetPreview,
  DatasetProfile,
  HealthStatus,
  SessionRecord,
} from "./types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export class AutodataApi {
  readonly baseUrl: string;

  constructor(baseUrl = import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  private url(path: string) {
    return `${this.baseUrl}/api/v1${path}`;
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    let response: Response;
    try {
      response = await fetch(this.url(path), init);
    } catch (error) {
      throw new ApiClientError(
        "backend_unreachable",
        "Could not connect to the backend API.",
        error,
      );
    }

    if (!response.ok) {
      let payload: ApiErrorPayload = {};
      try {
        payload = (await response.json()) as ApiErrorPayload;
      } catch {
        throw new ApiClientError("api_error", response.statusText, undefined, response.status);
      }
      const apiError = payload.error ?? {};
      throw new ApiClientError(
        apiError.code ?? "api_error",
        apiError.message ?? "Backend request failed.",
        apiError.details,
        response.status,
      );
    }

    if (response.status === 204) {
      return {} as T;
    }
    return (await response.json()) as T;
  }

  health() {
    return this.request<HealthStatus>("/health");
  }

  uploadDataset(file: File) {
    const formData = new FormData();
    formData.append("file", file);
    return this.request<DatasetInfo>("/datasets/upload", {
      method: "POST",
      body: formData,
    });
  }

  ingestSql(connectionUri: string, query: string, sourceName: string) {
    const payload: {
      connection_uri: string;
      query: string;
      source_name?: string;
    } = {
      connection_uri: connectionUri,
      query,
    };
    if (sourceName.trim()) {
      payload.source_name = sourceName.trim();
    }

    return this.request<DatasetInfo>("/datasets/sql", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  profile(datasetId: string) {
    return this.request<DatasetProfile>(`/datasets/${datasetId}/profile`);
  }

  preview(datasetId: string, limit = 20) {
    return this.request<DatasetPreview>(`/datasets/${datasetId}/preview?limit=${limit}`);
  }

  analyze(datasetId: string, question: string, sessionId?: string | null) {
    return this.request<AnalysisResponse>("/analysis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataset_id: datasetId,
        question,
        ...(sessionId ? { session_id: sessionId } : {}),
      }),
    });
  }

  history(sessionId: string) {
    return this.request<SessionRecord[]>(`/sessions/${sessionId}/history`);
  }
}
