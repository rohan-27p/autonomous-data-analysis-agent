import {
  AlertTriangle,
  BarChart3,
  Bot,
  CheckCircle2,
  ChevronRight,
  Cloud,
  Code2,
  Database,
  FileJson,
  FileSpreadsheet,
  History,
  LineChart,
  ListChecks,
  Loader2,
  PanelLeft,
  Play,
  Plus,
  RefreshCw,
  Send,
  Settings,
  Sparkles,
  Table2,
  UploadCloud,
  UserCircle,
  X,
} from "lucide-react";
import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";

import { AutodataApi } from "./api";
import {
  AnalysisResponse,
  ApiClientError,
  ChartSpec,
  ColumnProfile,
  DatasetInfo,
  DatasetPreview,
  HealthStatus,
  Page,
  SessionRecord,
} from "./types";

const api = new AutodataApi();

type Notice = { type: "success" | "error" | "info"; title: string; body?: string };

type ChatTurn = {
  id: string;
  question: string;
  createdAt: string;
  status: "pending" | "complete" | "error";
  analysis?: AnalysisResponse;
  error?: string;
};

function formatNumber(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
  }
  return String(value ?? "");
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function summarizeColumn(column: ColumnProfile) {
  const topValues = column.summary.top_values;
  if (Array.isArray(topValues)) {
    return topValues
      .slice(0, 3)
      .map((item) => {
        if (typeof item === "object" && item && "value" in item && "count" in item) {
          return `${String(item.value)} (${String(item.count)})`;
        }
        return String(item);
      })
      .join(", ");
  }
  if ("mean" in column.summary) {
    return `min=${formatNumber(column.summary.min)}, mean=${formatNumber(
      column.summary.mean,
    )}, max=${formatNumber(column.summary.max)}`;
  }
  if (column.sample_values.length) return column.sample_values.slice(0, 3).join(", ");
  return "-";
}

function classifyFile(name: string) {
  if (name.endsWith(".json")) return <FileJson size={18} />;
  return <FileSpreadsheet size={18} />;
}

export function App() {
  const [page, setPage] = useState<Page>("sources");
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [dataset, setDataset] = useState<DatasetInfo | null>(null);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [chatTurns, setChatTurns] = useState<ChatTurn[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [history, setHistory] = useState<SessionRecord[]>([]);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const activeDatasetName = dataset?.source_name ?? "No dataset selected";

  useEffect(() => {
    void refreshHealth();
  }, []);

  useEffect(() => {
    if (!dataset) {
      setPreview(null);
      return;
    }
    void api.preview(dataset.dataset_id, 20).then(setPreview).catch(() => setPreview(null));
  }, [dataset]);

  async function refreshHealth() {
    try {
      const response = await api.health();
      setHealth(response);
      setHealthError(null);
    } catch (error) {
      setHealth(null);
      setHealthError(error instanceof Error ? error.message : "Backend unavailable.");
    }
  }

  async function loadHistory(nextSessionId = sessionId) {
    if (!nextSessionId) return;
    try {
      setHistory(await api.history(nextSessionId));
    } catch {
      setHistory([]);
    }
  }

  async function handleUpload(file: File) {
    setBusy("upload");
    setNotice(null);
    try {
      const response = await api.uploadDataset(file);
      setDataset(response);
      setAnalysis(null);
      setChatTurns([]);
      setSessionId(null);
      setHistory([]);
      setPage("profile");
      setNotice({
        type: "success",
        title: "Dataset ready",
        body: `${response.source_name} was profiled successfully.`,
      });
    } catch (error) {
      showApiError("Upload failed", error);
    } finally {
      setBusy(null);
    }
  }

  async function handleSqlSubmit(connectionUri: string, query: string, sourceName: string) {
    setBusy("sql");
    setNotice(null);
    try {
      const response = await api.ingestSql(connectionUri, query, sourceName);
      setDataset(response);
      setAnalysis(null);
      setChatTurns([]);
      setSessionId(null);
      setHistory([]);
      setPage("profile");
      setNotice({
        type: "success",
        title: "SQL dataset loaded",
        body: `${response.source_name} returned ${formatNumber(response.row_count)} rows.`,
      });
    } catch (error) {
      showApiError("SQL ingestion failed", error);
    } finally {
      setBusy(null);
    }
  }

  async function handleAnalyze(question: string) {
    if (!dataset) {
      setNotice({
        type: "error",
        title: "No dataset selected",
        body: "Upload a dataset or connect SQL before asking the agent.",
      });
      setPage("sources");
      return;
    }

    setBusy("analysis");
    setNotice(null);
    const turnId = `turn-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const createdAt = new Date().toISOString();
    setChatTurns((current) => [
      ...current,
      { id: turnId, question, createdAt, status: "pending" },
    ]);
    setPage("ask");
    try {
      const response = await api.analyze(dataset.dataset_id, question, sessionId);
      setAnalysis(response);
      setChatTurns((current) =>
        current.map((turn) =>
          turn.id === turnId
            ? { ...turn, status: "complete", analysis: response, createdAt: response.created_at }
            : turn,
        ),
      );
      setSessionId(response.session_id);
      setPage("ask");
      await loadHistory(response.session_id);
    } catch (error) {
      const message = error instanceof Error ? error.message : "The agent could not complete this request.";
      setChatTurns((current) =>
        current.map((turn) =>
          turn.id === turnId ? { ...turn, status: "error", error: message } : turn,
        ),
      );
      showApiError("Analysis failed", error);
    } finally {
      setBusy(null);
    }
  }

  function showApiError(title: string, error: unknown) {
    if (error instanceof ApiClientError) {
      setNotice({ type: "error", title, body: `${error.message} (${error.code})` });
      return;
    }
    setNotice({ type: "error", title, body: error instanceof Error ? error.message : undefined });
  }

  return (
    <div className="app-shell">
      <Sidebar
        activePage={page}
        health={health}
        history={history}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNewAnalysis={() => {
          setAnalysis(null);
          setChatTurns([]);
          setPage(dataset ? "ask" : "sources");
        }}
        onPageChange={(nextPage) => {
          setPage(nextPage);
          setSidebarOpen(false);
        }}
      />
      <div className="workspace">
        <TopBar
          activeDatasetName={activeDatasetName}
          onMenu={() => setSidebarOpen(true)}
          onRefreshHealth={refreshHealth}
        />
        <main className="workspace-main">
          {notice && <NoticeBanner notice={notice} onDismiss={() => setNotice(null)} />}
          {healthError && (
            <NoticeBanner
              notice={{ type: "error", title: "Backend unavailable", body: healthError }}
              onDismiss={() => setHealthError(null)}
            />
          )}
          {page === "sources" && (
            <DataSourcesView
              busy={busy}
              dataset={dataset}
              onSqlSubmit={handleSqlSubmit}
              onUpload={handleUpload}
            />
          )}
          {page === "profile" && (
            <ProfileView dataset={dataset} preview={preview} onGoToSources={() => setPage("sources")} />
          )}
          {page === "ask" && (
            <AskAgentView
              busy={busy}
              dataset={dataset}
              chatTurns={chatTurns}
              onAsk={handleAnalyze}
              onNeedDataset={() => setPage("sources")}
            />
          )}
          {page === "history" && (
            <ResultHistoryView
              analysis={analysis}
              history={history}
              onAsk={handleAnalyze}
              onSelectAnalysis={setAnalysis}
              onRefreshHistory={() => loadHistory()}
            />
          )}
          {page === "settings" && (
            <SettingsView
              apiBaseUrl={api.baseUrl}
              health={health}
              onRefreshHealth={refreshHealth}
            />
          )}
        </main>
      </div>
    </div>
  );
}

function Sidebar({
  activePage,
  health,
  history,
  isOpen,
  onClose,
  onNewAnalysis,
  onPageChange,
}: {
  activePage: Page;
  health: HealthStatus | null;
  history: SessionRecord[];
  isOpen: boolean;
  onClose: () => void;
  onNewAnalysis: () => void;
  onPageChange: (page: Page) => void;
}) {
  const items: Array<{ page: Page; label: string; icon: React.ReactNode }> = [
    { page: "sources", label: "Data Sources", icon: <Database size={22} /> },
    { page: "profile", label: "Profile", icon: <UserCircle size={22} /> },
    { page: "ask", label: "Ask Agent", icon: <Bot size={22} /> },
    { page: "history", label: "Analysis History", icon: <History size={22} /> },
    { page: "settings", label: "Settings", icon: <Settings size={22} /> },
  ];

  return (
    <>
      <aside className={`sidebar ${isOpen ? "is-open" : ""}`}>
        <div className="sidebar-brand">
          <div className="brand-mark"><Bot size={24} /></div>
          <div>
            <h1>Autonomous Data</h1>
            <p>Analysis Agent</p>
          </div>
          <button className="icon-button sidebar-close" onClick={onClose} aria-label="Close menu">
            <X size={18} />
          </button>
        </div>
        <button className="primary-button sidebar-new" onClick={onNewAnalysis}>
          <Plus size={18} />
          New Analysis
        </button>
        <nav className="sidebar-nav" aria-label="Main navigation">
          {items.map((item) => (
            <button
              key={item.page}
              className={`nav-item ${activePage === item.page ? "active" : ""}`}
              onClick={() => onPageChange(item.page)}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </nav>
        <div className="session-mini">
          <p>Session History</p>
          {history.length ? (
            history.slice(0, 3).map((record) => (
              <button key={record.record_id} onClick={() => onPageChange("history")}>
                {record.question}
              </button>
            ))
          ) : <span>No API history yet</span>}
        </div>
        <div className="sidebar-status">
          <span><Cloud size={15} /> {health?.model ?? "Backend model pending"}</span>
          <span><CheckCircle2 size={15} /> Status: {health ? "Online" : "Offline"}</span>
        </div>
      </aside>
      {isOpen && <button className="sidebar-backdrop" onClick={onClose} aria-label="Close menu" />}
    </>
  );
}

function TopBar({
  activeDatasetName,
  onMenu,
  onRefreshHealth,
}: {
  activeDatasetName: string;
  onMenu: () => void;
  onRefreshHealth: () => void;
}) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="icon-button mobile-menu" onClick={onMenu} aria-label="Open menu">
          <PanelLeft size={20} />
        </button>
        <strong>Autonomous Data Analysis Agent</strong>
        <span className="topbar-divider" />
        <span className="breadcrumb">Dashboard</span>
        <ChevronRight size={16} className="breadcrumb-icon" />
        <span className="dataset-crumb"><Table2 size={16} /> Dataset: {activeDatasetName}</span>
      </div>
      <div className="topbar-actions">
        <button className="icon-button" aria-label="Refresh backend" onClick={onRefreshHealth}>
          <RefreshCw size={19} />
        </button>
        <div className="avatar">AD</div>
      </div>
    </header>
  );
}

function NoticeBanner({ notice, onDismiss }: { notice: Notice; onDismiss: () => void }) {
  return (
    <section className={`notice ${notice.type}`}>
      <div>
        <strong>{notice.title}</strong>
        {notice.body && <p>{notice.body}</p>}
      </div>
      <button className="icon-button" onClick={onDismiss} aria-label="Dismiss notice">
        <X size={16} />
      </button>
    </section>
  );
}

function DataSourcesView({
  busy,
  dataset,
  onSqlSubmit,
  onUpload,
}: {
  busy: string | null;
  dataset: DatasetInfo | null;
  onSqlSubmit: (connectionUri: string, query: string, sourceName: string) => void;
  onUpload: (file: File) => void;
}) {
  const [sourceName, setSourceName] = useState("");
  const [connectionUri, setConnectionUri] = useState("");
  const [query, setQuery] = useState("");

  function submitSql(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSqlSubmit(connectionUri.trim(), query.trim(), sourceName.trim());
  }

  function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    if (file) onUpload(file);
    event.currentTarget.value = "";
  }

  return (
    <section className="page-grid sources-grid">
      <div className="page-copy">
        <div className="crumb-line"><Database size={18} /> Data Sources <ChevronRight size={16} /> Connect</div>
        <h2>Connect Data</h2>
        <p>Upload static files or connect to an external SQL database for analysis.</p>
      </div>

      <div className="panel source-panel">
        <PanelHeader icon={<UploadCloud size={22} />} title="File Upload" />
        <label className={`dropzone ${busy === "upload" ? "loading" : ""}`}>
          <input
            type="file"
            accept=".csv,.xlsx,.xls,.json"
            onChange={upload}
            disabled={busy === "upload"}
          />
          <span className="drop-icon"><UploadCloud size={34} /></span>
          <strong>{busy === "upload" ? "Uploading and profiling..." : "Drag and drop files here"}</strong>
          <small>Supported formats: CSV, Excel (.xlsx, .xls), JSON</small>
          <span className="secondary-button">Browse Files</span>
        </label>
      </div>

      <form className="panel source-panel" onSubmit={submitSql}>
        <PanelHeader icon={<Database size={22} />} title="SQL Connection" />
        <div className="form-grid">
          <label>
            Source Name
            <input
              value={sourceName}
              onChange={(event) => setSourceName(event.target.value)}
              placeholder="Optional source name"
            />
          </label>
          <label>
            Connection URI
            <input
              value={connectionUri}
              onChange={(event) => setConnectionUri(event.target.value)}
              placeholder="postgresql://user:pass@host:5432/db"
              required
            />
          </label>
        </div>
        <label>
          <span className="label-row">
            Query (SELECT only)
            <small>Limits apply to prevent full table scans</small>
          </span>
          <textarea
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="SELECT * FROM your_table LIMIT 1000"
            required
          />
        </label>
        <div className="form-actions">
          <button className="primary-button" disabled={busy === "sql"}>
            {busy === "sql" ? <Loader2 className="spin" size={17} /> : <Play size={17} />}
            Test & Connect
          </button>
        </div>
      </form>

      <aside className="panel ingestion-panel">
        <PanelHeader
          icon={<RefreshCw size={21} />}
          title="Ingestion Status"
        />
        {busy === "upload" && (
          <StatusItem
            icon={<UploadCloud size={18} />}
            title="Uploaded file"
            meta="Profiling dataset through API..."
            status="PROCESSING"
            progress
          />
        )}
        {busy === "sql" && (
          <StatusItem
            icon={<Database size={18} />}
            title="SQL source"
            meta="Loading records through API..."
            status="PROCESSING"
            progress
          />
        )}
        {dataset ? (
          <StatusItem
            icon={classifyFile(dataset.source_name)}
            title={dataset.source_name}
            meta={`${formatNumber(dataset.row_count)} rows • ${formatNumber(
              dataset.column_count,
            )} columns • ${dataset.source_type.toUpperCase()}`}
            status="READY"
          />
        ) : (
          <div className="empty-source-state">
            <Database size={24} />
            <strong>No connected data sources</strong>
            <p>Upload a file or connect SQL to populate this panel from the API.</p>
          </div>
        )}
      </aside>
    </section>
  );
}

function StatusItem({
  icon,
  title,
  meta,
  status,
  progress,
  errorText,
}: {
  icon: React.ReactNode;
  title: string;
  meta: string;
  status: "READY" | "PROCESSING" | "FAILED";
  progress?: boolean;
  errorText?: string;
}) {
  return (
    <div className={`status-item ${status.toLowerCase()}`}>
      <div className="status-icon">{icon}</div>
      <div className="status-copy">
        <div className="status-title">
          <strong>{title}</strong>
          <span>{status}</span>
        </div>
        <p>{meta}</p>
        {progress && <div className="progress"><i /></div>}
        {errorText && <p className="error-text">{errorText}</p>}
      </div>
    </div>
  );
}

function ProfileView({
  dataset,
  preview,
  onGoToSources,
}: {
  dataset: DatasetInfo | null;
  preview: DatasetPreview | null;
  onGoToSources: () => void;
}) {
  if (!dataset) {
    return <EmptyDataset onGoToSources={onGoToSources} />;
  }

  const profile = dataset.profile;

  return (
    <section className="profile-layout">
      <div className="page-copy">
        <div className="crumb-line"><UserCircle size={18} /> Profile <ChevronRight size={16} /> {profile.source_name}</div>
        <h2>Dataset Profile</h2>
        <p>Review schema, quality signals, anomalies, and sample rows before asking the agent.</p>
      </div>

      <div className="metric-row">
        <Metric label="Rows" value={formatNumber(profile.row_count)} />
        <Metric label="Columns" value={formatNumber(profile.column_count)} />
        <Metric label="Duplicate rows" value={formatNumber(profile.duplicate_rows)} />
        <Metric label="Source type" value={profile.source_type.toUpperCase()} />
      </div>

      <div className="panel">
        <PanelHeader icon={<ListChecks size={21} />} title="Column Profile" />
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Column</th>
                <th>Type</th>
                <th>Null %</th>
                <th>Unique</th>
                <th>Summary</th>
              </tr>
            </thead>
            <tbody>
              {profile.columns.map((column) => (
                <tr key={column.name}>
                  <td className="linkish">{column.name}</td>
                  <td><code>{column.dtype}</code></td>
                  <td>{formatPercent(column.null_rate)}</td>
                  <td>{formatNumber(column.unique_count)}</td>
                  <td>{summarizeColumn(column)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="two-col">
        <div className="panel">
          <PanelHeader icon={<AlertTriangle size={21} />} title="Anomaly Hints" />
          {profile.anomalies.length ? (
            <ul className="check-list warning-list">
              {profile.anomalies.map((anomaly) => <li key={anomaly}>{anomaly}</li>)}
            </ul>
          ) : (
            <p className="empty-line">No anomaly hints detected in the automatic profile.</p>
          )}
        </div>
        <div className="panel">
          <PanelHeader icon={<Table2 size={21} />} title="Data Preview" />
          <div className="table-wrap compact">
            {preview ? <PreviewTable preview={preview} /> : <p className="empty-line">Loading preview...</p>}
          </div>
        </div>
      </div>
    </section>
  );
}

function PreviewTable({ preview }: { preview: DatasetPreview }) {
  return (
    <table>
      <thead>
        <tr>{preview.columns.slice(0, 6).map((column) => <th key={column}>{column}</th>)}</tr>
      </thead>
      <tbody>
        {preview.rows.slice(0, 8).map((row, index) => (
          <tr key={index}>
            {preview.columns.slice(0, 6).map((column) => (
              <td key={column}>{formatNumber(row[column])}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AskAgentView({
  busy,
  dataset,
  chatTurns,
  onAsk,
  onNeedDataset,
}: {
  busy: string | null;
  dataset: DatasetInfo | null;
  chatTurns: ChatTurn[];
  onAsk: (question: string) => void;
  onNeedDataset: () => void;
}) {
  const [question, setQuestion] = useState("");
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chatTurns, busy]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim()) return;
    onAsk(question.trim());
    setQuestion("");
  }

  if (!dataset) {
    return <EmptyDataset onGoToSources={onNeedDataset} />;
  }

  return (
    <section className="ask-layout">
      <DatasetContext dataset={dataset} />
      {chatTurns.length === 0 ? (
        <div className="agent-intro">
          <div className="agent-icon"><Bot size={34} /></div>
          <h2>How can I help you analyze this data?</h2>
          <p>
            Ask a question in plain English. The response will be generated from the
            active dataset through the backend API.
          </p>
        </div>
      ) : (
        <div className="chat-transcript" aria-live="polite">
          {chatTurns.map((turn) => (
            <ChatTurnView key={turn.id} turn={turn} onAsk={onAsk} />
          ))}
          <div ref={transcriptEndRef} />
        </div>
      )}
      <form className="agent-composer" onSubmit={submit}>
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask a question about the dataset... (e.g., 'Show me revenue by region for last month')"
        />
        <div className="composer-footer">
          <span className="composer-context">{dataset.source_name}</span>
          <button className="primary-button" disabled={busy === "analysis" || !question.trim()}>
            {busy === "analysis" ? <Loader2 className="spin" size={17} /> : <Send size={17} />}
            Ask Agent
          </button>
        </div>
      </form>
      <p className="fine-print">AI-generated analysis may be inaccurate. Verify critical business insights.</p>
    </section>
  );
}

function ChatTurnView({ turn, onAsk }: { turn: ChatTurn; onAsk: (question: string) => void }) {
  return (
    <article className="chat-turn">
      <div className="chat-message user-message">
        <div className="message-bubble">
          <p>{turn.question}</p>
          <span>{new Date(turn.createdAt).toLocaleString()}</span>
        </div>
        <div className="message-avatar user-avatar">AD</div>
      </div>

      <div className="chat-message ai-message">
        <div className="message-avatar ai-avatar"><Bot size={20} /></div>
        <div className="message-bubble ai-bubble">
          {turn.status === "pending" && (
            <div className="thinking-state">
              <Loader2 className="spin" size={18} />
              <span>Analyzing the dataset...</span>
            </div>
          )}
          {turn.status === "error" && (
            <div className="error-state">
              <AlertTriangle size={18} />
              <span>{turn.error ?? "Analysis failed."}</span>
            </div>
          )}
          {turn.status === "complete" && turn.analysis && (
            <ResultView analysis={turn.analysis} onAsk={onAsk} mode="chat" />
          )}
        </div>
      </div>
    </article>
  );
}

function DatasetContext({ dataset }: { dataset: DatasetInfo }) {
  return (
    <section className="dataset-context">
      <div className="context-icon"><BarChart3 size={24} /></div>
      <div>
        <h2>{dataset.source_name.replace(/\.[^.]+$/, "")} Analysis</h2>
        <p>
          Analyzing {formatNumber(dataset.row_count)} rows from {dataset.source_name}. The agent is ready
          to process complex queries, generate visualizations, and identify trends.
        </p>
        <div className="context-tags">
          <span><Database size={14} /> {dataset.source_type.toUpperCase()}</span>
          <span><Table2 size={14} /> {formatNumber(dataset.column_count)} Columns</span>
        </div>
      </div>
    </section>
  );
}

function ResultHistoryView({
  analysis,
  history,
  onAsk,
  onRefreshHistory,
  onSelectAnalysis,
}: {
  analysis: AnalysisResponse | null;
  history: SessionRecord[];
  onAsk: (question: string) => void;
  onRefreshHistory: () => void;
  onSelectAnalysis: (analysis: AnalysisResponse) => void;
}) {
  const activeAnalysis = analysis ?? history[0]?.response ?? null;

  if (!activeAnalysis) {
    return (
      <section className="panel centered-panel">
        <Bot size={34} />
        <h2>No analysis yet</h2>
        <p>Run an agent question to see plans, code, tables, charts, and history.</p>
      </section>
    );
  }

  return (
    <section className="result-layout">
      <ResultView analysis={activeAnalysis} onAsk={onAsk} />
      <aside className="panel history-panel">
        <PanelHeader
          icon={<History size={21} />}
          title="Analysis History"
          trailing={<button className="icon-button" onClick={onRefreshHistory}><RefreshCw size={16} /></button>}
        />
        {history.length ? (
          history.map((record) => (
            <button
              className={`history-item ${
                record.response.created_at === activeAnalysis.created_at ? "active" : ""
              }`}
              key={record.record_id}
              onClick={() => onSelectAnalysis(record.response)}
            >
              <strong>{record.question}</strong>
              <span>{new Date(record.created_at).toLocaleString()}</span>
            </button>
          ))
        ) : (
          <p className="empty-line">No saved records for this session yet.</p>
        )}
      </aside>
    </section>
  );
}

function ResultView({
  analysis,
  onAsk,
  mode = "standalone",
}: {
  analysis: AnalysisResponse;
  onAsk: (question: string) => void;
  mode?: "standalone" | "chat";
}) {
  const rows = analysis.execution.result_rows;
  const chartSpec = analysis.execution.chart_spec;

  return (
    <div className={`result-view ${mode === "chat" ? "chat-result" : ""}`}>
      <section className="result-question">
        <div className="agent-small"><Bot size={24} /></div>
        <div>
          <h2>{mode === "chat" ? "Analysis result" : analysis.question}</h2>
          <p>
            <Table2 size={16} /> Dataset {analysis.dataset_id.slice(0, 8)}
            <span /> {new Date(analysis.created_at).toLocaleString()}
          </p>
        </div>
      </section>
      <div className="result-grid">
        <div className="result-left">
          <div className="panel">
            <PanelHeader icon={<ListChecks size={20} />} title="Analysis Plan" />
            <ul className="check-list">
              <li>{analysis.plan.objective}</li>
              <li>Operation: {analysis.plan.operation.replace(/_/g, " ")}</li>
              <li>Required columns: {analysis.plan.required_columns.join(", ") || "Auto-detected"}</li>
              <li>Chart type: {analysis.plan.chart_type}</li>
            </ul>
          </div>
          <CodePanel code={analysis.generated_code} attempts={analysis.execution.attempts} />
        </div>
        <div className="result-right">
          <NarrativePanel analysis={analysis} />
          <div className="two-col result-cards">
            <DataTable rows={rows} />
            <ChartPanel chartSpec={chartSpec} rows={rows} />
          </div>
          <div className="followups">
            <span>Suggested Follow-ups</span>
            {analysis.narrative.follow_up_questions.map((question) => (
              <button key={question} onClick={() => onAsk(question)}>
                <LineChart size={16} />
                {question}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function CodePanel({ code, attempts }: { code: string; attempts: number }) {
  return (
    <section className="code-panel">
      <header>
        <span><Code2 size={17} /> Execution Script</span>
        <strong><CheckCircle2 size={14} /> Success after {attempts} attempt{attempts === 1 ? "" : "s"}</strong>
      </header>
      <pre>{code}</pre>
    </section>
  );
}

function NarrativePanel({ analysis }: { analysis: AnalysisResponse }) {
  return (
    <section className="narrative-panel">
      <Sparkles size={24} />
      <div>
        <span>Key Finding</span>
        <p>{analysis.narrative.key_finding}</p>
        <div className="narrative-grid">
          <div>
            <strong>Business Meaning</strong>
            <p>{analysis.narrative.business_meaning}</p>
          </div>
          <div>
            <strong>Limitations</strong>
            <p>{analysis.narrative.limitations.join(" ") || "No limitations returned."}</p>
          </div>
        </div>
      </div>
    </section>
  );
}

function DataTable({ rows }: { rows: Record<string, unknown>[] }) {
  const columns = Object.keys(rows[0] ?? {}).slice(0, 6);
  return (
    <section className="panel data-card">
      <PanelHeader icon={<Table2 size={20} />} title="Data Table" />
      <div className="table-wrap compact">
        {columns.length ? (
          <table>
            <thead>
              <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
            </thead>
            <tbody>
              {rows.slice(0, 8).map((row, index) => (
                <tr key={index}>
                  {columns.map((column) => <td key={column}>{formatNumber(row[column])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="empty-line">No result rows returned.</p>
        )}
      </div>
    </section>
  );
}

function ChartPanel({ chartSpec, rows }: { chartSpec: ChartSpec | null; rows: Record<string, unknown>[] }) {
  return (
    <section className="panel chart-card">
      <PanelHeader icon={<BarChart3 size={20} />} title="Visualization" />
      {chartSpec && rows.length ? (
        <>
          <SimpleChart chartSpec={chartSpec} rows={rows} />
          <p className="chart-caption">{chartSpec.caption}</p>
        </>
      ) : (
        <p className="empty-line">No chart specification returned.</p>
      )}
    </section>
  );
}

function SimpleChart({ chartSpec, rows }: { chartSpec: ChartSpec; rows: Record<string, unknown>[] }) {
  const xKey = chartSpec.x ?? Object.keys(rows[0] ?? {})[0];
  const yKey = chartSpec.y ?? Object.keys(rows[0] ?? {}).find((key) => typeof rows[0]?.[key] === "number");
  const values = rows
    .slice(0, 8)
    .map((row) => ({ label: String(row[xKey] ?? ""), value: Number(row[yKey ?? ""] ?? 0) }))
    .filter((item) => Number.isFinite(item.value));
  const maxValue = Math.max(...values.map((item) => item.value), 1);

  if (!values.length || chartSpec.chart_type === "table") {
    return <p className="empty-line">Chart data is not numeric.</p>;
  }

  return (
    <div className={`simple-chart ${chartSpec.chart_type}`}>
      <div className="bars">
        {values.map((item, index) => (
          <div className="bar-slot" key={`${item.label}-${index}`}>
            <i style={{ height: `${Math.max((item.value / maxValue) * 100, 6)}%` }} />
            <span>{item.label.slice(0, 8)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SettingsView({
  apiBaseUrl,
  health,
  onRefreshHealth,
}: {
  apiBaseUrl: string;
  health: HealthStatus | null;
  onRefreshHealth: () => void;
}) {
  return (
    <section className="settings-layout">
      <div className="page-copy">
        <div className="crumb-line"><Settings size={18} /> Settings <ChevronRight size={16} /> Repair Status</div>
        <h2>Settings & Repair Status</h2>
        <p>Review backend connectivity, model configuration, and autonomous repair behavior.</p>
      </div>
      <div className="two-col">
        <div className="panel">
          <PanelHeader icon={<Cloud size={21} />} title="Backend" />
          <dl className="definition-list">
            <dt>API base URL</dt>
            <dd><code>{apiBaseUrl}</code></dd>
            <dt>Environment</dt>
            <dd>{health?.environment ?? "Unavailable"}</dd>
            <dt>Model</dt>
            <dd>{health?.model ?? "Unavailable"}</dd>
          </dl>
          <button className="primary-button" onClick={onRefreshHealth}>
            <RefreshCw size={17} />
            Check backend health
          </button>
        </div>
        <div className="panel">
          <PanelHeader icon={<CheckCircle2 size={21} />} title="Autonomous Repair" />
          <ol className="timeline">
            <li><CheckCircle2 size={16} /> Generate analysis contract</li>
            <li><CheckCircle2 size={16} /> Execute controlled pandas code</li>
            <li><CheckCircle2 size={16} /> Repair failed code with model feedback</li>
            <li><CheckCircle2 size={16} /> Validate chart and narrative response</li>
          </ol>
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function PanelHeader({
  icon,
  title,
  trailing,
}: {
  icon: React.ReactNode;
  title: string;
  trailing?: React.ReactNode;
}) {
  return (
    <header className="panel-header">
      <span>{icon}{title}</span>
      {trailing}
    </header>
  );
}

function EmptyDataset({ onGoToSources }: { onGoToSources: () => void }) {
  return (
    <section className="panel centered-panel">
      <Database size={34} />
      <h2>No dataset connected</h2>
      <p>Upload a CSV, Excel, JSON file, or connect a SELECT-only SQL source.</p>
      <button className="primary-button" onClick={onGoToSources}>
        <Plus size={17} />
        Connect Data
      </button>
    </section>
  );
}
