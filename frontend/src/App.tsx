import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  BrainCircuit,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Circle,
  Code2,
  Copy,
  Database,
  FileCode2,
  FolderGit2,
  GitBranch,
  Layers3,
  LoaderCircle,
  Moon,
  Network,
  RefreshCw,
  ScanSearch,
  Search,
  ShieldCheck,
  Sparkles,
  Sun,
  TerminalSquare,
  Upload as UploadIcon,
  XCircle,
  Zap,
} from "lucide-react";
import { downloadMigratedRepo, getJob, startMigration, type JobStatus } from "./api";
import "./App.css";

type Status = "pending" | "running" | "completed" | "failed";

type Stage = {
  id: string;
  name: string;
  group: "Analysis" | "Migration" | "Verification" | "Intelligence" | "Report";
  description: string;
  resultKey: string;
  icon: React.ElementType;
};

const STAGES: Stage[] = [
  { id: "scan", name: "Repository Scan", group: "Analysis", resultKey: "scan", description: "Repository structure, files and source inventory.", icon: ScanSearch },
  { id: "version", name: "Version Detection", group: "Analysis", resultKey: "version", description: "Detected source and target language versions.", icon: GitBranch },
  { id: "selection", name: "Migration Selection", group: "Analysis", resultKey: "selection", description: "Files selected for migration and preserved files.", icon: Search },
  { id: "extraction", name: "Code Extraction", group: "Analysis", resultKey: "extraction", description: "Functions and static code features extracted from candidates.", icon: FileCode2 },
  { id: "embeddings", name: "CodeBERT Embeddings", group: "Analysis", resultKey: "embeddings", description: "Semantic representations generated from the extracted code.", icon: BrainCircuit },
  { id: "dependency", name: "Dependency Graph", group: "Analysis", resultKey: "dependency", description: "Import and local code relationships.", icon: Network },
  { id: "planning", name: "Migration Planning", group: "Analysis", resultKey: "planning", description: "Migration order and transformation plan.", icon: GitBranch },
  { id: "context", name: "Repository Context", group: "Analysis", resultKey: "context", description: "Structured context assembled for migration.", icon: Database },
  { id: "rag", name: "RAG Retrieval", group: "Migration", resultKey: "rag", description: "Historical migration examples retrieved for the current code.", icon: Search },
  { id: "prompt", name: "Prompt Construction", group: "Migration", resultKey: "prompt", description: "Migration prompts assembled from repository intelligence.", icon: Sparkles },
  { id: "llm", name: "LLM Migration", group: "Migration", resultKey: "llm", description: "Modern Python code generated from the legacy implementation.", icon: BrainCircuit },
  { id: "assembly", name: "Repository Assembly", group: "Migration", resultKey: "assembly", description: "Migrated and preserved files assembled into the output repository.", icon: FolderGit2 },
  { id: "syntax", name: "Syntax Verification", group: "Verification", resultKey: "syntax", description: "Migrated Python files checked for valid syntax.", icon: ShieldCheck },
  { id: "dependency_verification", name: "Dependency Verification", group: "Verification", resultKey: "dependency_verification", description: "Imports and local dependency checks.", icon: Network },
  { id: "test_generation", name: "Test Generation", group: "Verification", resultKey: "test_generation", description: "Behavioral test inputs generated for migrated callables.", icon: Zap },
  { id: "differential_testing", name: "Differential Testing", group: "Verification", resultKey: "differential_testing", description: "Original and migrated implementations compared on identical inputs.", icon: RefreshCw },
  { id: "behavioral_verification", name: "Behavioral Verification", group: "Verification", resultKey: "behavioral_verification", description: "Behavioral cases and observed equivalence summarized.", icon: CheckCircle2 },
  { id: "semantic_equivalence", name: "Semantic Equivalence", group: "Intelligence", resultKey: "semantic_equivalence", description: "Semantic verification evidence and differences.", icon: BrainCircuit },
  { id: "risk_analysis", name: "Risk Analysis", group: "Intelligence", resultKey: "risk_analysis", description: "File-level migration risk from structural and behavioral evidence.", icon: ShieldCheck },
  { id: "explainability", name: "Explainability", group: "Intelligence", resultKey: "explainability", description: "Human-readable reasons and evidence behind the migration assessment.", icon: Sparkles },
  { id: "final_report", name: "Final Migration Report", group: "Report", resultKey: "final_report", description: "Consolidated migration, verification and risk summary.", icon: Layers3 },
];

const GROUP_ORDER = ["Analysis", "Migration", "Verification", "Intelligence", "Report"] as const;

function isObj(v: unknown): v is Record<string, any> {
  return !!v && typeof v === "object" && !Array.isArray(v);
}
function arr(v: any): any[] {
  return Array.isArray(v) ? v : [];
}

function unwrapStageData(data: any, stageId: string): any {
  if (!isObj(data)) return data;

  const aliases: Record<string, string[]> = {
    scan: ["scan"],
    version: ["version", "version_manifest"],
    selection: ["selection", "migration_selection"],
    extraction: ["features", "extraction"],
    embeddings: ["embeddings", "embedded_features"],
    dependency: ["dependency", "dependency_graph"],
    planning: ["planning", "migration_plan"],
    context: ["context", "migration_context"],
    rag: ["rag", "rag_results"],
    prompt: ["prompt", "llm_prompts"],
    llm: ["llm", "migration_results"],
    assembly: ["assembly", "assembly_manifest"],
    syntax: ["syntax", "syntax_verification"],
    dependency_verification: ["dependency_verification"],
  };

  for (const key of aliases[stageId] || []) {
    if (data[key] !== undefined && data[key] !== null) {
      return data[key];
    }
  }

  if (data.result !== undefined && data.result !== null) return data.result;
  if (data.data !== undefined && data.data !== null) return data.data;

  return data;
}

function logMatches(logs: string[] | undefined, pattern: RegExp): string[] {
  return (logs || []).filter(line => pattern.test(line));
}

function logNumber(logs: string[] | undefined, pattern: RegExp): number | undefined {
  const line = logMatches(logs, pattern)[0];
  if (!line) return undefined;
  const match = line.match(pattern);
  return match?.[1] ? Number(match[1]) : undefined;
}
function num(obj: any, keys: string[]): number | undefined {
  if (!isObj(obj)) return undefined;
  for (const key of keys) {
    if (typeof obj[key] === "number") return obj[key];
    if (typeof obj[key] === "string" && obj[key] !== "" && !Number.isNaN(Number(obj[key]))) return Number(obj[key]);
  }
  return undefined;
}
function text(v: any, fallback = "—"): string {
  if (v === null || v === undefined || v === "") return fallback;
  if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") return String(v);
  return fallback;
}
function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}
function fileName(v: any): string {
  if (typeof v === "string") return v;
  if (!isObj(v)) return "—";
  return text(v.file ?? v.path ?? v.filename ?? v.file_path ?? v.name, "—");
}
function formatValue(v: any): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") return String(v);
  if (Array.isArray(v)) return `${v.length} item${v.length === 1 ? "" : "s"}`;
  return "Available";
}
function pct(v: any): string {
  if (typeof v !== "number") return text(v);
  return `${(v * 100).toFixed(1)}%`;
}

function statusLabel(status: Status) {
  if (status === "completed") return "Completed";
  if (status === "running") return "Processing";
  if (status === "failed") return "Failed";
  return "Pending";
}

function StatusIcon({ status }: { status: Status }) {
  if (status === "completed") return <span className="status-dot-icon done"><Check size={13} /></span>;
  if (status === "running") return <span className="status-dot-icon running"><LoaderCircle size={14} className="spin" /></span>;
  if (status === "failed") return <span className="status-dot-icon failed"><XCircle size={13} /></span>;
  return <span className="status-dot-icon pending"><Circle size={8} /></span>;
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return (
    <div className="metric-card">
      <div className="metric-icon">{icon}</div>
      <div><span>{label}</span><strong>{value}</strong></div>
    </div>
  );
}

function Section({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section className="content-card">
      <div className="card-heading"><h3>{title}</h3>{action}</div>
      {children}
    </section>
  );
}

function KeyValueGrid({ items }: { items: Array<[string, any]> }) {
  return (
    <div className="kv-grid">
      {items.filter(([, v]) => v !== undefined && v !== null).map(([k, v]) => (
        <div className="kv" key={k}><span>{k}</span><strong>{formatValue(v)}</strong></div>
      ))}
    </div>
  );
}

function List({ items, empty = "No items were returned." }: { items: any[]; empty?: string }) {
  if (!items.length) return <div className="empty-inline">{empty}</div>;
  return (
    <div className="readable-list">
      {items.slice(0, 100).map((item, i) => (
        <div className="readable-row" key={i}>
          <span className="row-index">{i + 1}</span>
          <span>{readableItem(item)}</span>
        </div>
      ))}
      {items.length > 100 && <div className="muted">Showing first 100 of {items.length} items.</div>}
    </div>
  );
}

function readableItem(item: any): string {
  if (typeof item === "string") return item;
  if (!isObj(item)) return String(item);
  const bits: string[] = [];
  const f = item.file ?? item.path ?? item.filename;
  const fn = item.function ?? item.function_name ?? item.symbol;
  const status = item.status ?? item.outcome ?? item.result;
  const reason = item.reason ?? item.message;
  if (f) bits.push(String(f));
  if (fn) bits.push(String(fn));
  if (status) bits.push(String(status));
  if (reason) bits.push(String(reason));
  if (!bits.length) {
    Object.entries(item).slice(0, 5).forEach(([k, v]) => {
      if (!isObj(v) && !Array.isArray(v)) bits.push(`${titleCase(k)}: ${String(v)}`);
    });
  }
  return bits.join(" · ") || "Recorded item";
}

function RawArtifact({ value }: { value: any }) {
  return (
    <details className="raw-details">
      <summary>View raw artifact</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

function UploadScreen({ onStart, error, theme, setTheme }: {
  onStart: (file: File) => void;
  error: string | null;
  theme: "dark" | "light";
  setTheme: React.Dispatch<React.SetStateAction<"dark" | "light">>;
}) {
  const [selected, setSelected] = useState<File | null>(null);
  const pick = (file?: File) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".zip")) return;
    setSelected(file);
  };
  return (
    <main className="upload-page">
      <header className="upload-topbar">
        <div className="brand">
          <div className="brand-mark"><Zap size={19} /></div>
          <div><div className="brand-title">CODEMIGRATE</div><div className="brand-subtitle">Migration intelligence</div></div>
        </div>
        <button className="theme-button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
          {theme === "dark" ? <Sun size={15}/> : <Moon size={15}/>} {theme === "dark" ? "Light" : "Dark"}
        </button>
      </header>
      <div className="upload-shell">
        <div className="upload-copy">
          <div className="eyebrow">AI-POWERED LEGACY MODERNIZATION</div>
          <h1>Turn legacy code into<br />a verified migration.</h1>
          <p>Upload a Python legacy repository and trace analysis, migration, verification and risk from one workspace.</p>
        </div>
        <label className="drop-card">
          <UploadIcon size={28}/>
          <strong>{selected ? selected.name : "Drop repository ZIP here"}</strong>
          <span>or click to browse · ZIP supported by the current API</span>
          <input type="file" accept=".zip" onChange={e => pick(e.target.files?.[0])}/>
        </label>
        <div className="upload-side-note">
          <ShieldCheck size={16}/>
          <span>Results are read from the pipeline artifacts through the FastAPI bridge.</span>
        </div>
      </div>
      {selected && <div className="upload-action"><button className="primary-button" onClick={() => onStart(selected)}><ArrowRight size={17}/> Start migration</button></div>}
      {error && <div className="error-banner">{error}</div>}
    </main>
  );
}

function Overview({ job, onOpen }: { job: JobStatus; onOpen: (id: string) => void }) {
  const stats = job.statistics || {};
  const scan = unwrapStageData(job.results?.scan, "scan");
  const selection = unwrapStageData(job.results?.selection, "selection");
  const semantic = isObj(job.results?.semantic_equivalence) ? job.results.semantic_equivalence : {};
  const summary = isObj(semantic.summary) ? semantic.summary : {};
  const risk = isObj(job.results?.risk_analysis) ? job.results.risk_analysis : {};
  const riskFiles = isObj(risk.files) ? Object.entries(risk.files) : [];
  const completed = STAGES.filter(s => job.stage_status?.[s.id] === "completed").length;
  const behaviorCases = num(summary, ["behavioral_cases", "behavioral_cases_total"]);
  const equivalent = num(summary, ["behavioral_equivalent", "behaviorally_equivalent"]);
  const differences = num(summary, ["behavioral_semantic_differences", "semantic_differences"]);

  return (
    <>
      <div className="page-header">
        <div><div className="eyebrow">MIGRATION OVERVIEW</div><h1>{job.repository_name || "Legacy repository"}</h1><p>Traceable analysis, migration, verification and risk evidence.</p></div>
        <div className={`status-pill ${job.status}`}><span />{job.status === "completed" ? "COMPLETED" : job.status === "failed" ? "FAILED" : "PROCESSING"}</div>
      </div>

      <div className="metric-grid">
        <Metric icon={<Layers3/>} label="Files" value={stats.files ?? "—"} />
        <Metric icon={<GitBranch/>} label="Candidates" value={stats.candidates ?? "—"} />
        <Metric icon={<Code2/>} label="Functions" value={stats.functions ?? "—"} />
        <Metric icon={<Zap/>} label="Stages complete" value={`${completed}/${STAGES.length}`} />
        <Metric icon={<ShieldCheck/>} label="Behavioral cases" value={behaviorCases ?? "—"} />
        <Metric icon={<CheckCircle2/>} label="Equivalent" value={equivalent ?? "—"} />
      </div>

      {isObj(scan) && (
        <Section title="Repository scan">
          <KeyValueGrid items={[
            ["Repository", scan.repository ?? job.repository_name],
            ["Files discovered", scan.total_files ?? logNumber(job.logs, /Files discovered:\s*(\d+)/)],
            ["Languages", Array.isArray(scan.summary?.languages_detected) ? scan.summary.languages_detected.join(", ") : undefined],
            ["Python files", scan.summary?.language_file_counts?.Python ?? logNumber(job.logs, /Python files analyzed:\s*(\d+)/)],
            ["Migration candidates", isObj(selection?.counts) ? selection.counts.targets : stats.candidates],
          ]}/>
        </Section>
      )}

      <Section title="Pipeline progress" action={<strong>{Math.round(completed / STAGES.length * 100)}%</strong>}>
        <div className="progress-track"><div className="progress-fill" style={{ width: `${completed / STAGES.length * 100}%` }} /></div>
        <div className="progress-meta"><span>Current: {job.current_stage || "waiting"}</span><span>{differences ?? 0} semantic differences</span></div>
      </Section>

      <div className="two-column">
        <Section title="Pipeline map" action={<span className="muted">{STAGES.length} stages</span>}>
          <div className="pipeline-map">
            {STAGES.map((stage, i) => {
              const status = (job.stage_status?.[stage.id] || "pending") as Status;
              return (
                <button className="pipeline-row" key={stage.id} onClick={() => onOpen(stage.id)}>
                  <StatusIcon status={status} />
                  <span className="stage-number">{String(i + 1).padStart(2, "0")}</span>
                  <span className="pipeline-row-name">{stage.name}</span>
                  <span className="pipeline-row-group">{stage.group}</span>
                </button>
              );
            })}
          </div>
        </Section>

        <Section title="Job logs" action={<span className="muted">{job.logs?.length || 0} lines</span>}>
          <div className="terminal">
            {(job.logs || []).slice(-100).map((line, i) => <div key={i}>{line}</div>)}
          </div>
        </Section>
      </div>

      {riskFiles.length > 0 && (
        <Section title="Risk snapshot">
          <div className="risk-grid">
            {riskFiles.map(([file, value]: [string, any]) => (
              <div className="risk-card" key={file}>
                <div><strong>{file}</strong><span className={`risk-badge ${String(value?.risk || "unknown").toLowerCase()}`}>{value?.risk || "UNKNOWN"}</span></div>
                <p>{arr(value?.reasons).join(" ") || "No explanation was returned for this file."}</p>
              </div>
            ))}
          </div>
        </Section>
      )}
    </>
  );
}

function StageContent({ stage, job }: { stage: Stage; job: JobStatus }) {
  const result = unwrapStageData(job.results?.[stage.resultKey], stage.id);
  if (stage.id === "explainability") return <ExplainabilityView job={job} />;
  if (stage.id === "final_report") return <FinalReportView job={job} />;
  if (stage.id === "test_generation") return <TestGenerationView data={result} job={job} />;
  if (stage.id === "differential_testing") return <DifferentialView data={result} job={job} />;
  if (stage.id === "behavioral_verification") return <BehavioralView data={result} />;
  if (stage.id === "semantic_equivalence") return <SemanticView data={result} job={job} />;
  if (stage.id === "risk_analysis") return <RiskView data={result} />;
  if (stage.id === "llm") return <MigrationView data={result} />;
  if (stage.id === "selection") return <SelectionView data={result} job={job} />;
  if (stage.id === "scan") return <ScanOverview data={result} />;
  if (stage.id === "version") return <VersionView data={result} job={job} />;
  if (stage.id === "extraction") return <ExtractionView data={result} />;
  if (stage.id === "embeddings") return <EmbeddingView data={result} job={job} />;
  if (stage.id === "dependency") return <DependencyGraphView data={result} />;
  if (stage.id === "planning") return <PlanningView data={result} />;
  if (stage.id === "context") return <ContextView data={result} />;
  if (stage.id === "rag") return <RagView data={result} job={job} />;
  if (stage.id === "prompt") return <PromptView data={result} />;
  if (stage.id === "assembly") return <AssemblyView data={result} />;
  if (stage.id === "syntax") return <VerificationView title="Syntax verification" data={result} />;
  if (stage.id === "dependency_verification") return <VerificationView title="Dependency verification" data={result} />;
  return <GenericStage title={stage.name} data={result} />;
}

function StagePage({ stage, job }: { stage: Stage; job: JobStatus }) {
  const status = (job.stage_status?.[stage.id] || "pending") as Status;
  return (
    <>
      <div className="page-header">
        <div><div className="eyebrow">{stage.group.toUpperCase()}</div><h1>{stage.name}</h1><p>{stage.description}</p></div>
        <div className={`status-pill ${status}`}><StatusIcon status={status}/>{statusLabel(status).toUpperCase()}</div>
      </div>
      {status === "failed" && <div className="error-banner"><XCircle size={17}/>{job.error || "This stage failed. See the job logs for details."}</div>}
      {status === "running" && <div className="info-banner"><LoaderCircle size={17} className="spin"/> This stage is currently being processed. Live output is available in the job logs.</div>}
      {status === "pending" && <div className="info-banner"><Circle size={12}/> This stage has not produced output yet.</div>}
      {status === "completed" && <StageContent stage={stage} job={job} />}
    </>
  );
}

function GenericStage({ title, data }: { title: string; data: any }) {
  if (!data) {
    return <Section title={title}><div className="empty-inline">The pipeline did not return a result object for this stage.</div></Section>;
  }

  if (Array.isArray(data)) {
    return (
      <>
        <Section title={`${title} · ${data.length}`}>
          <List items={data} empty={`No ${title.toLowerCase()} records were returned.`} />
        </Section>
        <RawArtifact value={data}/>
      </>
    );
  }

  const entries = isObj(data) ? Object.entries(data) : [];
  const arrays = entries.filter(([,v]) => Array.isArray(v));
  const scalars = entries.filter(([,v]) => !Array.isArray(v) && !isObj(v));

  return (
    <>
      {scalars.length > 0 && (
        <Section title="Summary">
          <KeyValueGrid items={scalars.map(([k,v]) => [titleCase(k), v])} />
        </Section>
      )}
      {arrays.map(([key, value]) => (
        <Section title={titleCase(key)} key={key}>
          <List items={value as any[]} />
        </Section>
      ))}
      <RawArtifact value={data}/>
    </>
  );
}


function ExtractionView({ data }: { data: any }) {
  const records = arr(data);

  const byFile = new Map<string, any[]>();
  for (const item of records) {
    const file = fileName(item);
    if (!byFile.has(file)) byFile.set(file, []);
    byFile.get(file)!.push(item);
  }

  return (
    <>
      <Section title="Extraction summary">
        <KeyValueGrid items={[
          ["Extracted functions", records.length],
          ["Files with extracted code", byFile.size],
        ]}/>
      </Section>

      <Section title="Extracted functions">
        {records.length === 0 ? (
          <div className="empty-inline">No extracted function records were returned.</div>
        ) : (
          <div className="readable-list">
            {records.map((item: any, index: number) => (
              <div className="readable-row" key={`${fileName(item)}-${index}`}>
                <span className="row-index">{index + 1}</span>
                <span>
                  <strong>
                    {item?.function_full_name ??
                     item?.function_name ??
                     item?.name ??
                     item?.function ??
                     "Extracted function"}
                  </strong>
                  <span className="row-secondary">
                    {fileName(item)}
                    {item?.language_version ? ` · Python ${item.language_version}` : ""}
                  </span>
                </span>
              </div>
            ))}
          </div>
        )}
      </Section>

      <RawArtifact value={data}/>
    </>
  );
}

function SelectionView({ data, job }: { data: any; job: JobStatus }) {
  const selectedFromArtifact = arr(
    data?.targets ??
    data?.selected ??
    data?.selected_for_migration ??
    data?.candidates
  );

  const selectedFromLogs = logMatches(
    job.logs,
    /\[SELECTED\]\s+(.+)$/i
  ).map(line => ({ path: line.replace(/^.*\[SELECTED\]\s+/i, "").trim() }));

  const selected = selectedFromArtifact.length
    ? selectedFromArtifact
    : selectedFromLogs;

  const skipped = arr(
    data?.skipped ??
    data?.preserved ??
    data?.preserved_files
  );

  const review = arr(data?.needs_review ?? data?.review);

  const counts = isObj(data?.counts) ? data.counts : {};

  return (
    <>
      <Section title="Migration scope">
        <KeyValueGrid items={[
          ["Target files", counts.targets ?? selected.length],
          ["Needs review", counts.needs_review ?? review.length],
          ["Skipped / preserved", counts.skipped ?? skipped.length],
          ["Source language", data?.job_spec?.language],
          ["From version", data?.job_spec?.from_version],
          ["Target version", data?.job_spec?.to_version],
          ["Minimum confidence", data?.job_spec?.min_confidence],
        ]}/>
      </Section>

      <div className="two-column">
        <Section title={`Selected for migration · ${selected.length}`}>
          <List items={selected} empty="No migration targets were returned." />
        </Section>

        <Section title={`Preserved / skipped · ${skipped.length}`}>
          <List items={skipped} empty="No preserved or skipped files were returned." />
        </Section>
      </div>

      {review.length > 0 && (
        <Section title={`Needs review · ${review.length}`}>
          <List items={review} />
        </Section>
      )}
    </>
  );
}

function ScanOverview({ data }: { data: any }) {
  const scanData = unwrapStageData(data, "scan");
  const files = Array.isArray(scanData)
    ? scanData
    : arr(scanData?.files ?? scanData?.entries ?? scanData?.discovered_files);

  const summary = isObj(scanData?.summary) ? scanData.summary : {};
  const languageCounts = isObj(summary?.language_file_counts)
    ? summary.language_file_counts
    : {};

  return (
    <>
      <Section title="Repository inventory">
        <KeyValueGrid items={[
          ["Repository", scanData?.repository],
          ["Scanned at", scanData?.scanned_at],
          ["Total files", scanData?.total_files ?? files.length],
          ["Python files", languageCounts.Python ?? files.filter((f: any) => f?.language === "Python").length],
          ["Languages detected", Array.isArray(summary?.languages_detected) ? summary.languages_detected.join(", ") : undefined],
        ]}/>
      </Section>

      <Section title={`Discovered files · ${files.length}`}>
        <div className="readable-list">
          {files.map((item: any, i: number) => (
            <div className="readable-row" key={item?.path || i}>
              <span className="row-index">{i + 1}</span>
              <span>
                <strong>{item?.path ?? item?.file ?? "Unknown file"}</strong>
                <span className="row-secondary">
                  {item?.language ?? "Unknown"} · {item?.category ?? "unknown"}
                </span>
              </span>
            </div>
          ))}
        </div>
      </Section>

      <RawArtifact value={scanData}/>
    </>
  );
}

function VersionView({ data, job }: { data: any; job: JobStatus }) {
  const versionData = unwrapStageData(data, "version");
  const files = Array.isArray(versionData)
    ? versionData
    : arr(versionData?.files ?? versionData?.entries ?? versionData?.version_files);

  const fallbackPythonCount = logNumber(job.logs, /Python files analyzed:\s*(\d+)/);

  const pythonFiles = files.filter((f: any) =>
    String(f?.language ?? "").toLowerCase() === "python"
  );

  const py2 = pythonFiles.filter((f: any) =>
    String(f?.version_detection?.version ?? f?.version ?? "").includes("2")
  );

  const unknown = pythonFiles.filter((f: any) => {
    const v = f?.version_detection?.version ?? f?.version;
    return v === undefined || v === null || String(v).toLowerCase() === "unknown";
  });

  return (
    <>
      <Section title="Version detection summary">
        <KeyValueGrid items={[
          ["Total files", versionData?.total_files ?? (files.length || logNumber(job.logs, /Files discovered:\s*(\d+)/))],
          ["Python files", pythonFiles.length || fallbackPythonCount],
          ["Python 2 detected", py2.length],
          ["Python version unknown", unknown.length],
        ]}/>
      </Section>

      <Section title={`Detected files · ${files.length}`}>
        {files.length === 0 ? (
          <div className="empty-inline">No version-detection file records were returned.</div>
        ) : (
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Language</th>
                  <th>Detected version</th>
                  <th>Confidence</th>
                  <th>Detection method</th>
                </tr>
              </thead>
              <tbody>
                {files.map((item: any, index: number) => {
                  const detection = item?.version_detection ?? {};
                  return (
                    <tr key={`${item?.path || item?.file || index}`}>
                      <td>{item?.path ?? item?.file ?? "—"}</td>
                      <td>{item?.language ?? "—"}</td>
                      <td>{detection?.version ?? item?.version ?? "Not detected"}</td>
                      <td>{detection?.confidence ?? item?.confidence ?? "—"}</td>
                      <td>{detection?.method ?? item?.detection_method ?? "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <RawArtifact value={data}/>
    </>
  );
}

function EmbeddingView({ data, job }: { data: any; job: JobStatus }) {
  const embeddingData = unwrapStageData(data, "embeddings");
  const extracted = Array.isArray(job.results?.extraction)
    ? job.results.extraction
    : [];

  const logEmbeddingCount = logNumber(job.logs, /Embeddings generated:\s*(\d+)/);

  const recordCount =
    typeof embeddingData?.records === "number" && embeddingData.records > 0
      ? embeddingData.records
      : typeof embeddingData?.count === "number" && embeddingData.count > 0
      ? embeddingData.count
      : Array.isArray(embeddingData?.embeddings) && embeddingData.embeddings.length > 0
      ? embeddingData.embeddings.length
      : Array.isArray(embeddingData?.items) && embeddingData.items.length > 0
      ? embeddingData.items.length
      : logEmbeddingCount ?? extracted.length;

  const embeddedUnits = extracted.slice(0, recordCount).map((item: any, index: number) => ({
    file: item?.file_path ?? item?.source_file ?? item?.file ?? item?.path,
    function: item?.function_full_name ?? item?.function_name ?? item?.function,
    chunk_id: item?.chunk_id,
  }));

  return (
    <>
      <Section title="Embedding configuration">
        <KeyValueGrid items={[
          ["Model", embeddingData?.model ?? "microsoft/codebert-base"],
          ["Vector dimension", embeddingData?.dimension ?? 768],
          ["Embedded units", recordCount],
          ["Device", embeddingData?.device],
        ]}/>
      </Section>

      <Section title={`Embedded code units · ${recordCount}`}>
        {embeddedUnits.length > 0 ? (
          <div className="readable-list">
            {embeddedUnits.map((item: any, i: number) => (
              <div className="readable-row" key={item.chunk_id || i}>
                <span className="row-index">{i + 1}</span>
                <span>
                  <strong>{item.function || "Code unit"}</strong>
                  {item.file && <span className="row-secondary">{item.file}</span>}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-inline">
            {recordCount > 0
              ? `${recordCount} embedding vectors were generated. Function metadata is not included in the embedding artifact.`
              : "No embedding records were returned."}
          </div>
        )}
      </Section>

      <RawArtifact value={embeddingData}/>
    </>
  );
}

function RAGExampleCard({ item, index }: { item: any; index: number }) {
  const obj = isObj(item) ? item : { value: item };
  const fn = obj.function || obj.function_name || obj.query_function || obj.callable || obj.target_function;
  const file = obj.file || obj.source_file || obj.target_file;
  const examples = arr(obj.examples || obj.results || obj.matches || obj.retrieved || obj.candidates);
  const score = obj.score ?? obj.similarity ?? obj.distance;
  return <div className="rag-card">
    <div className="rag-head"><span className="row-index">{index + 1}</span><div><strong>{file || "Migration query"}</strong>{fn && <span>{String(fn)}</span>}</div>{score !== undefined && <span className="confidence-chip">{typeof score === "number" ? score.toFixed(3) : String(score)}</span>}</div>
    {examples.length ? <div className="rag-examples">{examples.slice(0, 5).map((ex:any,j:number)=><div className="rag-example" key={j}><span>#{j+1}</span><pre>{typeof ex === "string" ? ex : JSON.stringify(ex, null, 2)}</pre></div>)}</div> : <pre className="compact-json">{JSON.stringify(obj, null, 2)}</pre>}
  </div>;
}

function DependencyGraphView({ data }: { data: any }) {
  const raw = data;

  /*
   * Actual dependency artifact shape:
   *
   * {
   *   "billing.py": {
   *     "config.py": {
   *       "types": ["from_import", "function_call"],
   *       "details": [
   *         {
   *           "module": "config",
   *           "name": "get_config",
   *           "alias": null,
   *           "line": 4
   *         }
   *       ]
   *     }
   *   }
   * }
   */

  const graph =
    isObj(raw?.dependencies)
      ? raw.dependencies
      : isObj(raw?.graph)
        ? raw.graph
        : raw;

  const relationships: Array<{
    source: string;
    target: string;
    type: string;
    details: any[];
  }> = [];

  if (isObj(graph)) {
    Object.entries(graph).forEach(([source, targets]) => {
      if (!isObj(targets)) return;

      Object.entries(targets).forEach(([target, relationship]) => {
        if (!isObj(relationship)) return;

        const types = Array.isArray(relationship.types)
          ? relationship.types
          : [];

        const details = Array.isArray(relationship.details)
          ? relationship.details
          : [];

        if (types.length > 0) {
          types.forEach((type) => {
            relationships.push({
              source,
              target,
              type: String(type),
              details,
            });
          });
        } else {
          relationships.push({
            source,
            target,
            type: "dependency",
            details,
          });
        }
      });
    });
  }

  /*
   * Also support a normal edge-based graph if the backend
   * ever returns one.
   */
  const edgeList =
    Array.isArray(raw?.edges)
      ? raw.edges
      : Array.isArray(graph?.edges)
        ? graph.edges
        : [];

  edgeList.forEach((edge: any) => {
    if (!isObj(edge)) return;

    const source =
      edge.source ??
      edge.from ??
      edge.file ??
      edge.source_file;

    const target =
      edge.target ??
      edge.to ??
      edge.dependency ??
      edge.target_file;

    if (!source || !target) return;

    relationships.push({
      source: String(source),
      target: String(target),
      type: String(
        edge.type ??
        edge.relationship ??
        "dependency"
      ),
      details: Array.isArray(edge.details)
        ? edge.details
        : [],
    });
  });

  /*
   * Remove duplicate relationships.
   */
  const uniqueRelationships = relationships.filter(
    (item, index, arr) =>
      arr.findIndex(
        (x) =>
          x.source === item.source &&
          x.target === item.target &&
          x.type === item.type
      ) === index
  );

  const pythonFiles = Array.isArray(raw?.python_files)
    ? raw.python_files
    : Array.from(
        new Set(
          uniqueRelationships.flatMap((r) => [
            r.source,
            r.target,
          ])
        )
      );

  const edgeCount =
    raw?.edge_count ??
    uniqueRelationships.length;

  const importEdgeCount =
    raw?.import_edge_count ??
    uniqueRelationships.filter((r) =>
      r.type.toLowerCase().includes("import")
    ).length;

  const fromImportEdgeCount =
    raw?.from_import_edge_count ??
    uniqueRelationships.filter((r) =>
      r.type.toLowerCase().includes("from_import")
    ).length;

  const functionCallEdgeCount =
    raw?.function_call_edge_count ??
    uniqueRelationships.filter((r) =>
      r.type.toLowerCase().includes("function_call")
    ).length;

  const inheritanceEdgeCount =
    raw?.inheritance_edge_count ??
    uniqueRelationships.filter((r) =>
      r.type.toLowerCase().includes("inheritance")
    ).length;

  return (
    <div className="stage-stack">

      {/* SUMMARY */}
      <section className="panel">
        <h3>Dependency graph summary</h3>

        <div className="metric-grid dependency-metrics">

          <div className="metric-card">
            <span className="metric-label">
              PYTHON FILES
            </span>
            <strong>
              {pythonFiles.length}
            </strong>
          </div>

          <div className="metric-card">
            <span className="metric-label">
              TOTAL EDGES
            </span>
            <strong>
              {edgeCount}
            </strong>
          </div>

          <div className="metric-card">
            <span className="metric-label">
              IMPORT EDGES
            </span>
            <strong>
              {importEdgeCount}
            </strong>
          </div>

          <div className="metric-card">
            <span className="metric-label">
              FROM-IMPORT
            </span>
            <strong>
              {fromImportEdgeCount}
            </strong>
          </div>

          <div className="metric-card">
            <span className="metric-label">
              FUNCTION CALLS
            </span>
            <strong>
              {functionCallEdgeCount}
            </strong>
          </div>

          <div className="metric-card">
            <span className="metric-label">
              INHERITANCE
            </span>
            <strong>
              {inheritanceEdgeCount}
            </strong>
          </div>

        </div>
      </section>


      {/* RELATIONSHIP TABLE */}
      <section className="panel">
        <div className="panel-heading-row">
          <div>
            <h3>
              Dependency relationships
            </h3>

            <p className="panel-subtitle">
              File-to-file imports and function relationships discovered during static analysis.
            </p>
          </div>

          <span className="count-badge">
            {uniqueRelationships.length} relationships
          </span>
        </div>

        {uniqueRelationships.length === 0 ? (

          <div className="empty-state">
            No structured dependency relationships were returned.
          </div>

        ) : (

          <div className="table-wrap dependency-table-wrap">

            <table className="data-table dependency-table">

              <thead>
                <tr>
                  <th>Source file</th>
                  <th>Dependency</th>
                  <th>Relationship</th>
                  <th>Details</th>
                </tr>
              </thead>

              <tbody>

                {uniqueRelationships.map(
                  (relationship, index) => {

                    const detailText =
                      relationship.details
                        .map((detail: any) => {
                          if (!isObj(detail)) {
                            return String(detail);
                          }

                          const name =
                            detail.name ??
                            detail.function ??
                            "";

                          const module =
                            detail.module ??
                            "";

                          const line =
                            detail.line ??
                            "";

                          const alias =
                            detail.alias ??
                            "";

                          const parts = [
                            module,
                            name,
                            line
                              ? `line ${line}`
                              : "",
                            alias
                              ? `alias: ${alias}`
                              : "",
                          ].filter(Boolean);

                          return parts.join(" · ");
                        })
                        .filter(Boolean)
                        .join("; ");

                    return (
                      <tr key={`${relationship.source}-${relationship.target}-${relationship.type}-${index}`}>

                        <td>
                          <code className="dependency-file">
                            {relationship.source}
                          </code>
                        </td>

                        <td>
                          <code className="dependency-file">
                            {relationship.target}
                          </code>
                        </td>

                        <td>
                          <span className="relationship-badge">
                            {relationship.type}
                          </span>
                        </td>

                        <td className="dependency-detail-cell">
                          {detailText || "—"}
                        </td>

                      </tr>
                    );
                  }
                )}

              </tbody>

            </table>

          </div>
        )}

      </section>


      {/* FILE RELATIONSHIPS */}
      <section className="panel">

        <div className="panel-heading-row">
          <div>
            <h3>Repository dependency map</h3>

            <p className="panel-subtitle">
              Direct relationships between files in the analyzed repository.
            </p>
          </div>
        </div>

        <div className="dependency-map">

          {Array.from(
            new Set(
              uniqueRelationships.map(
                (r) => r.source
              )
            )
          ).map((source) => {

            const outgoing =
              uniqueRelationships.filter(
                (r) => r.source === source
              );

            return (
              <div
                className="dependency-source"
                key={source}
              >

                <div className="dependency-node source-node">
                  <span className="node-type">
                    SOURCE
                  </span>

                  <strong>
                    {source}
                  </strong>
                </div>

                <div className="dependency-arrows">

                  {outgoing.map(
                    (relationship, index) => (

                      <div
                        className="dependency-link"
                        key={`${relationship.target}-${relationship.type}-${index}`}
                      >

                        <span className="arrow">
                          →
                        </span>

                        <div className="dependency-node target-node">

                          <span className="node-type">
                            DEPENDENCY
                          </span>

                          <strong>
                            {relationship.target}
                          </strong>

                          <span className="node-relation">
                            {relationship.type}
                          </span>

                        </div>

                      </div>

                    )
                  )}

                </div>

              </div>
            );
          })}

        </div>

      </section>


      {/* RAW ARTIFACT */}
      <details className="raw-artifact">

        <summary>
          View raw artifact
        </summary>

        <pre>
          {JSON.stringify(raw, null, 2)}
        </pre>

      </details>

    </div>
  );
}

function PlanningView({ data }: { data: any }) {
  const plan = isObj(data) ? data : {};

  const units = Array.isArray(plan.migration_units)
    ? plan.migration_units
    : Array.isArray(plan.units)
      ? plan.units
      : [];

  const strategy =
    plan.strategy ??
    plan.migration_strategy ??
    "dependency first";

  const target =
    plan.target ??
    plan.target_version ??
    "Python 3";

  const migrationOrder =
    Array.isArray(plan.migration_order)
      ? plan.migration_order
      : units;

  const getFileName = (unit: any) => {
    if (typeof unit === "string") return unit;

    return (
      unit?.file ??
      unit?.path ??
      unit?.file_path ??
      unit?.name ??
      "Unknown file"
    );
  };

  const getDependencies = (unit: any): string[] => {
    const deps =
      unit?.dependencies ??
      unit?.depends_on ??
      unit?.dependency_files ??
      unit?.prerequisites ??
      [];

    if (Array.isArray(deps)) {
      return deps.map((d) =>
        typeof d === "string"
          ? d
          : d?.file ?? d?.path ?? d?.name ?? String(d)
      );
    }

    return [];
  };

  const getReason = (unit: any) =>
    unit?.reason ??
    unit?.rationale ??
    unit?.description ??
    unit?.explanation ??
    "Migration order determined from repository dependency analysis.";

  const getPriority = (unit: any) =>
    unit?.priority ??
    unit?.order ??
    unit?.sequence ??
    null;

  const getRisk = (unit: any) =>
    unit?.risk ??
    unit?.risk_level ??
    unit?.migration_risk ??
    null;

  const getSymbols = (unit: any) =>
    unit?.symbols ??
    unit?.functions ??
    unit?.targets ??
    [];

  const getComplexity = (unit: any) =>
    unit?.complexity ??
    unit?.metrics ??
    null;

  return (
    <div className="stage-stack">

      {/* =====================================================
          PLAN SUMMARY
          ===================================================== */}

      <section className="panel">

        <h3>Migration plan summary</h3>

        <div className="metric-grid">

          <div className="metric-card">
            <span className="metric-label">
              MIGRATION UNITS
            </span>

            <strong>
              {units.length}
            </strong>
          </div>

          <div className="metric-card">
            <span className="metric-label">
              STRATEGY
            </span>

            <strong>
              {String(strategy)}
            </strong>
          </div>

          <div className="metric-card">
            <span className="metric-label">
              TARGET
            </span>

            <strong>
              {String(target)}
            </strong>
          </div>

        </div>

      </section>


      {/* =====================================================
          MIGRATION ORDER
          ===================================================== */}

      <section className="panel">

        <div className="panel-heading-row">

          <div>
            <h3>
              Migration order
            </h3>

            <p className="panel-subtitle">
              Files are ordered according to the dependency-aware
              migration plan.
            </p>
          </div>

          <span className="count-badge">
            {migrationOrder.length} steps
          </span>

        </div>


        <div className="migration-order-list">

          {migrationOrder.map(
            (unit: any, index: number) => {

              const file = getFileName(unit);

              const dependencies =
                getDependencies(unit);

              const priority =
                getPriority(unit);

              return (
                <div
                  className="migration-order-item"
                  key={`${file}-${index}`}
                >

                  <div className="migration-order-number">
                    {index + 1}
                  </div>

                  <div className="migration-order-content">

                    <div className="migration-order-header">

                      <code>
                        {file}
                      </code>

                      {priority !== null && (
                        <span className="count-badge">
                          Priority {priority}
                        </span>
                      )}

                    </div>


                    {dependencies.length > 0 && (

                      <div className="migration-dependencies">

                        <span className="migration-detail-label">
                          DEPENDS ON
                        </span>

                        <div className="migration-chip-list">

                          {dependencies.map(
                            (dependency, depIndex) => (

                              <span
                                className="migration-chip"
                                key={`${dependency}-${depIndex}`}
                              >
                                {dependency}
                              </span>

                            )
                          )}

                        </div>

                      </div>

                    )}

                  </div>

                </div>
              );
            }
          )}

        </div>

      </section>


      {/* =====================================================
          MIGRATION UNITS
          ===================================================== */}

      <section className="panel">

        <div className="panel-heading-row">

          <div>
            <h3>
              Planned migration units
            </h3>

            <p className="panel-subtitle">
              Detailed transformation units produced by the
              migration planner.
            </p>
          </div>

        </div>


        <div className="migration-unit-list">

          {units.map(
            (unit: any, index: number) => {

              const file =
                getFileName(unit);

              const dependencies =
                getDependencies(unit);

              const reason =
                getReason(unit);

              const priority =
                getPriority(unit);

              const risk =
                getRisk(unit);

              const symbols =
                getSymbols(unit);

              const complexity =
                getComplexity(unit);

              return (

                <details
                  className="migration-unit-card"
                  key={`${file}-${index}`}
                >

                  <summary>

                    <div className="migration-summary-left">

                      <span className="migration-index">
                        {index + 1}
                      </span>

                      <div>

                        <strong>
                          {file}
                        </strong>

                        <span className="migration-summary-subtitle">
                          Migration unit
                        </span>

                      </div>

                    </div>

                    <span className="migration-expand">
                      View details
                    </span>

                  </summary>


                  <div className="migration-unit-details">

                    {/* FILE */}

                    <div className="detail-section">

                      <h4>
                        File
                      </h4>

                      <code className="migration-file-code">
                        {file}
                      </code>

                    </div>


                    {/* ORDER / PRIORITY */}

                    <div className="detail-grid">

                      <div className="detail-box">

                        <span>
                          MIGRATION ORDER
                        </span>

                        <strong>
                          {index + 1}
                        </strong>

                      </div>

                      {priority !== null && (

                        <div className="detail-box">

                          <span>
                            PRIORITY
                          </span>

                          <strong>
                            {String(priority)}
                          </strong>

                        </div>

                      )}

                      {risk !== null && (

                        <div className="detail-box">

                          <span>
                            RISK
                          </span>

                          <strong>
                            {String(risk)}
                          </strong>

                        </div>

                      )}

                    </div>


                    {/* DEPENDENCIES */}

                    {dependencies.length > 0 && (

                      <div className="detail-section">

                        <h4>
                          Dependencies
                        </h4>

                        <div className="migration-chip-list">

                          {dependencies.map(
                            (dependency, depIndex) => (

                              <span
                                className="migration-chip"
                                key={`${dependency}-${depIndex}`}
                              >
                                {dependency}
                              </span>

                            )
                          )}

                        </div>

                      </div>

                    )}


                    {/* SYMBOLS / FUNCTIONS */}

                    {Array.isArray(symbols) &&
                      symbols.length > 0 && (

                        <div className="detail-section">

                          <h4>
                            Functions / symbols
                          </h4>

                          <div className="migration-symbol-list">

                            {symbols.map(
                              (symbol: any, symbolIndex: number) => (

                                <div
                                  className="migration-symbol"
                                  key={symbolIndex}
                                >
                                  {typeof symbol === "string"
                                    ? symbol
                                    : symbol?.name ??
                                      symbol?.function ??
                                      JSON.stringify(symbol)}
                                </div>

                              )
                            )}

                          </div>

                        </div>

                    )}


                    {/* COMPLEXITY / METRICS */}

                    {complexity && (

                      <div className="detail-section">

                        <h4>
                          Code metrics
                        </h4>

                        <div className="detail-grid">

                          {isObj(complexity) &&
                            Object.entries(complexity)
                              .slice(0, 8)
                              .map(([key, value]) => (

                                <div
                                  className="detail-box"
                                  key={key}
                                >

                                  <span>
                                    {titleCase(
                                      key.replace(
                                        /_/g,
                                        " "
                                      )
                                    )}
                                  </span>

                                  <strong>
                                    {formatValue(value)}
                                  </strong>

                                </div>

                              ))}

                        </div>

                      </div>

                    )}


                    {/* REASON */}

                    <div className="detail-section">

                      <h4>
                        Migration rationale
                      </h4>

                      <p className="migration-reason">
                        {reason}
                      </p>

                    </div>

                  </div>

                </details>

              );
            }
          )}

        </div>

      </section>


      {/* =====================================================
          RAW ARTIFACT
          ===================================================== */}

      <details className="raw-artifact">

        <summary>
          View raw artifact
        </summary>

        <pre>
          {JSON.stringify(data, null, 2)}
        </pre>

      </details>

    </div>
  );
}

function ContextView({ data }: { data:any }) {
  const items = Array.isArray(data) ? data : arr(data?.contexts ?? data?.items ?? data?.records);
  return <><div className="info-banner"><Database size={17}/><div><strong>What is Repository Context?</strong><span>A structured bundle of the target file's source code, symbols, dependencies, migration plan and related repository information. It is assembled before the LLM prompt so the model receives repository-level context instead of only the individual function.</span></div></div><Section title={`Migration contexts · ${items.length}`}>{items.length ? <div className="context-grid">{items.map((x:any,i:number)=>{const o=isObj(x)?x:{}; return <div className="context-card" key={i}><div className="context-head"><strong>{o?.target?.file ?? o?.file ?? fileName(x)}</strong><span>{o?.target?.version ?? o?.version ?? "Python 2 → Python 3"}</span></div><div className="context-chips"><span>{arr(o?.symbols).length} symbols</span><span>{arr(o?.dependencies ?? o?.imports).length} dependencies</span><span>{o?.source_code ? "source included":"structured context"}</span></div><pre className="compact-json">{JSON.stringify(o,null,2)}</pre></div>})}</div>:<div className="empty-inline">No structured repository contexts were returned.</div>}</Section><RawArtifact value={data}/></>;
}

function PromptView({ data }: { data:any }) {
  const prompts = Array.isArray(data) ? data : arr(data?.prompts ?? data?.items ?? data?.records);
  return <><Section title="Prompt construction"><KeyValueGrid items={[["Prompts",prompts.length || data?.count],["Purpose","Provide repository intelligence + migration instructions to the LLM"]]}/></Section><Section title={`Constructed prompts · ${prompts.length}`}>{prompts.length ? <div className="prompt-list">{prompts.map((p:any,i:number)=>{const file=p?.file ?? p?.target_file ?? p?.filename ?? `Prompt ${i+1}`; const body=p?.prompt ?? p?.text ?? p?.content ?? p?.llm_prompt ?? JSON.stringify(p,null,2); return <details className="prompt-card" key={i}><summary><span className="row-index">{i+1}</span><strong>{file}</strong><span>View prompt</span></summary><pre className="prompt-code">{body}</pre></details>})}</div>:<div className="empty-inline">No prompt records were returned.</div>}</Section><RawArtifact value={data}/></>;
}

function AssemblyView({ data }: { data:any }) {
  const files = arr(data?.files ?? data?.manifest ?? data?.entries);
  return <><Section title="Repository assembly summary"><KeyValueGrid items={[["Status",data?.status],["Original files",data?.original_files],["Migrated files",data?.migrated_files],["Preserved files",data?.preserved_files],["Skipped files",data?.skipped_files],["Assembly errors",data?.assembly_errors]]}/></Section><Section title={`Final repository manifest · ${files.length}`}>{files.length ? <div className="data-table-wrap"><table className="data-table"><thead><tr><th>File</th><th>Action</th><th>Status</th></tr></thead><tbody>{files.map((x:any,i:number)=><tr key={i}><td>{fileName(x)}</td><td>{x?.action ?? x?.operation ?? x?.status ?? "—"}</td><td>{x?.status ?? "—"}</td></tr>)}</tbody></table></div>:<div className="empty-inline">Assembly summary is available, but no manifest rows were returned.</div>}</Section><RawArtifact value={data}/></>;
}

function RagView({ data, job }: { data: any; job: JobStatus }) {
  const raw = data;
  const records = Array.isArray(raw) ? raw : arr(raw?.records ?? raw?.results ?? raw?.queries ?? raw?.items ?? raw?.retrievals);
  const queryCount = num(raw, ["query_count","queries_count","queries_completed","count"]) ?? logNumber(job.logs, /RAG queries completed:\s*(\d+)/) ?? records.length;
  const successful = num(raw, ["successful_queries","successful_rag_queries"]) ?? logNumber(job.logs, /Successful RAG queries:\s*(\d+)/);
  const logQueries = logMatches(job.logs, /\[RAG\]\s+(.+?)\s+→\s+(\d+)\s+examples/i);
  return <>
    <Section title="Retrieval summary"><KeyValueGrid items={[["Queries",queryCount],["Successful queries",successful ?? "—"],["Retrieved records",records.length],["Top-k shown",5]]}/></Section>
    {logQueries.length > 0 && <Section title="Retrieval activity from pipeline log"><div className="data-table-wrap"><table className="data-table"><thead><tr><th>Function</th><th>Retrieved examples</th></tr></thead><tbody>{logQueries.map((line,i)=>{const m=line.match(/\[RAG\]\s+(.+?)\s+→\s+(\d+)/i);return <tr key={i}><td>{m?.[1]||line}</td><td>{m?.[2]||"—"}</td></tr>})}</tbody></table></div></Section>}
    <Section title={`Retrieved migration examples · ${records.length}`}>
      {records.length ? <div className="rag-list">{records.map((x:any,i:number)=><RAGExampleCard item={x} index={i} key={i}/>)}</div> : <div className="empty-inline">No RAG records were returned by the current artifact. If the log shows successful queries, the raw artifact below should be inspected for its exact structure.</div>}
    </Section>
    <RawArtifact value={raw}/>
  </>;
}


function VerificationView({ title, data }: { title: string; data: any }) {
  const pass = data?.status === "PASS" || data?.status === "SUCCESS" || data?.passed === true || data?.success === true;
  const files = isObj(data?.files) ? Object.entries(data.files) : arr(data?.files ?? data?.results ?? data?.checks ?? data?.records);
  const entries = files as any[];
  return <>
    <div className={`result-banner ${pass ? "good" : "neutral"}`}><CheckCircle2 size={20}/><div><strong>{pass ? `${title} passed` : text(data?.status, `${title} completed`)}</strong><span>The result below is read from the actual pipeline verification artifact.</span></div></div>
    <Section title="Verification summary"><KeyValueGrid items={[["Status",data?.status],["Files checked",isObj(data?.files) ? Object.keys(data.files).length : Array.isArray(data?.files) ? data.files.length : undefined],["Source",data?.source]]}/></Section>
    <Section title="Checked files">
      {entries.length ? <div className="data-table-wrap"><table className="data-table"><thead><tr><th>File</th><th>Status</th><th>Details</th></tr></thead><tbody>{entries.map((entry:any,i:number)=>{const key=Array.isArray(entry)?entry[0]:fileName(entry);const value=Array.isArray(entry)?entry[1]:entry;const status = value?.status ?? value?.result ?? (value?.success === true ? "PASS" : value?.success === false ? "FAIL" : (pass ? "PASS" : "—"));return <tr key={i}><td>{String(key)}</td><td><span className={`status-text ${String(status).toLowerCase()}`}>{String(status)}</span></td><td>{isObj(value) ? (value.message ?? value.error ?? value.details ?? value.reason ?? "Verified") : formatValue(value)}</td></tr>})}</tbody></table></div> : <div className="empty-inline">The artifact contains a stage-level result but no per-file records.</div>}
    </Section>
    <RawArtifact value={data}/>
  </>;
}


function TestGenerationView({ data, job }: { data: any; job: JobStatus }) {
  const semantic = isObj(job.results?.semantic_equivalence) ? job.results.semantic_equivalence : {};
  const summary = isObj(semantic.summary) ? semantic.summary : {};
  const cases = num(summary, ["behavioral_cases", "behavioral_cases_total"]) ?? num(data, ["behavioral_cases", "count", "total"]) ?? 0;
  const files = isObj(semantic.files) ? Object.entries(semantic.files) : [];
  return (
    <>
      <div className="metric-grid compact">
        <Metric icon={<Zap/>} label="Behavioral cases" value={cases} />
        <Metric icon={<ShieldCheck/>} label="Source" value="Semantic verification" />
      </div>
      <Section title="Generated test inputs"><div className="info-banner"><Zap size={16}/> {cases} behavioral test cases were produced for differential verification.</div><div className="muted small">Per-file counts are shown below when the verification report provides them.</div><div className="risk-grid">{files.map(([file, v]: [string, any]) => <div className="risk-card" key={file}><strong>{file}</strong><span>{v?.behavioral_cases ?? v?.cases ?? "—"} cases</span></div>)}</div></Section>
      {data && <RawArtifact value={data}/>}
    </>
  );
}

function DifferentialView({ data, job }: { data: any; job: JobStatus }) {
  const semantic = isObj(job.results?.semantic_equivalence) ? job.results.semantic_equivalence : {};
  const summary = isObj(semantic.summary) ? semantic.summary : {};
  const cases = num(summary, ["behavioral_cases", "behavioral_cases_total"]) ?? 0;
  const equivalent = num(summary, ["behavioral_equivalent", "behaviorally_equivalent"]) ?? 0;
  const differences = num(summary, ["behavioral_semantic_differences", "semantic_differences"]) ?? 0;
  return (
    <>
      <div className="metric-grid compact">
        <Metric icon={<Zap/>} label="Comparisons" value={cases}/>
        <Metric icon={<CheckCircle2/>} label="Equivalent" value={equivalent}/>
        <Metric icon={<AlertCircle/>} label="Differences" value={differences}/>
      </div>
      <Section title="Differential testing result">
        <div className={`result-banner ${differences === 0 ? "good" : "warn"}`}>
          {differences === 0 ? <CheckCircle2 size={20}/> : <AlertCircle size={20}/>}
          <div><strong>{differences === 0 ? "All observed behaviours matched" : "Behavioural differences were detected"}</strong><span>{equivalent} of {cases} behavioural cases were equivalent.</span></div>
        </div>
      </Section>
      {data && <RawArtifact value={data}/>}
    </>
  );
}

function BehavioralView({ data }: { data: any }) {
  const summary = isObj(data?.summary) ? data.summary : data;
  const cases = num(summary, ["behavioral_cases", "behavioral_cases_total"]) ?? 0;
  const equivalent = num(summary, ["behavioral_equivalent", "behaviorally_equivalent"]) ?? 0;
  const differences = num(summary, ["behavioral_semantic_differences", "semantic_differences"]) ?? 0;
  return (
    <>
      <div className="metric-grid compact">
        <Metric icon={<Zap/>} label="Behavioral cases" value={cases}/>
        <Metric icon={<CheckCircle2/>} label="Equivalent" value={equivalent}/>
        <Metric icon={<AlertCircle/>} label="Semantic differences" value={differences}/>
      </div>
      <Section title="Interpretation">
        <p className="explanation">{differences === 0 ? `All ${equivalent} observed behavioral cases matched between the original and migrated implementations.` : `${differences} behavioral cases showed semantic differences and should be reviewed.`}</p>
      </Section>
      <RawArtifact value={data}/>
    </>
  );
}

function SemanticView({ data, job }: { data: any; job: JobStatus }) {
  const summary = isObj(data?.summary) ? data.summary : {};
  const semanticDiff = num(summary,["behavioral_semantic_differences","semantic_differences"]) ?? 0;
  const cases = num(summary,["behavioral_cases","behavioral_cases_total"]) ?? 0;
  const llm = Array.isArray(job.results?.llm) ? job.results.llm : [];
  const pairs = llm.map((item:any) => {
    const eq = item?.semantic_equivalence || item?.semantic_result || item?.equivalence || {};
    const prediction = eq?.prediction ?? eq?.classification ?? eq?.label ?? item?.prediction;
    const confidence = eq?.confidence ?? eq?.confidence_score ?? item?.confidence;
    return { file:item?.file || item?.target_file || item?.path, classification:prediction, confidence };
  }).filter((x:any)=>x.file);
  return <>
    <div className={`result-banner ${semanticDiff===0 ? "good" : "warn"}`}><CheckCircle2 size={20}/><div><strong>{semanticDiff===0 ? "No runtime semantic differences reported" : "Runtime semantic differences reported"}</strong><span>{cases} behavioral cases were evaluated by the differential verifier.</span></div></div>
    <Section title="File-pair semantic classification">
      {pairs.length ? <div className="data-table-wrap"><table className="data-table semantic-table"><thead><tr><th>Original file</th><th>Migrated file</th><th>Classification</th><th>Confidence</th></tr></thead><tbody>{pairs.map((p:any,i:number)=>{const raw=String(p.classification??"—"); const equivalent=/equivalent/i.test(raw)&&!/not|non/i.test(raw); return <tr key={i}><td>{p.file}</td><td>{p.file}</td><td><span className={`classification ${equivalent ? "equivalent":"not-equivalent"}`}>{raw}</span></td><td>{typeof p.confidence === "number" ? `${(p.confidence <= 1 ? p.confidence*100 : p.confidence).toFixed(2)}%` : text(p.confidence)}</td></tr>})}</tbody></table></div> : <div className="empty-inline">The current migration artifact does not expose per-file classifier predictions in a structured field. The runtime semantic evidence is shown below.</div>}
    </Section>
    <Section title="Runtime semantic verification"><KeyValueGrid items={[["Existing tests equivalent",summary.existing_tests_equivalent],["Behavioral cases",cases],["Behaviorally equivalent",summary.behavioral_equivalent],["Semantic differences",semanticDiff]]}/></Section>
    <RawArtifact value={data}/>
  </>;
}


function RiskView({ data }: { data: any }) {
  const files = isObj(data?.files) ? Object.entries(data.files) : [];
  return (
    <>
      <Section title="Risk model"><KeyValueGrid items={[
        ["Model", data?.model],
        ["Source", data?.source],
        ["Files assessed", files.length],
      ]}/></Section>
      <div className="risk-grid">
        {files.map(([file, value]: [string, any]) => (
          <div className="risk-card" key={file}>
            <div className="risk-file-head"><strong>{file}</strong><span className={`risk-badge ${String(value?.risk || "").toLowerCase()}`}>{value?.risk || "UNKNOWN"}</span></div>
            <div className="risk-feature-grid">
              <span>Functions <b>{value?.features?.function_count ?? "—"}</b></span>
              <span>Classes <b>{value?.features?.class_count ?? "—"}</b></span>
              <span>Cases <b>{value?.features?.behavioral_cases ?? "—"}</b></span>
              <span>Differences <b>{value?.features?.semantic_differences ?? "—"}</b></span>
              <span>Difference rate <b>{pct(value?.features?.semantic_difference_rate)}</b></span>
            </div>
            <p>{arr(value?.reasons).join(" ") || "No reason was returned."}</p>
          </div>
        ))}
      </div>
      <RawArtifact value={data}/>
    </>
  );
}

function ExplainabilityView({ job }: { job: JobStatus }) {
  const semantic = isObj(job.results?.semantic_equivalence) ? job.results.semantic_equivalence : {};
  const summary = isObj(semantic.summary) ? semantic.summary : {};
  const risk = isObj(job.results?.risk_analysis) ? job.results.risk_analysis : {};
  const riskFiles = isObj(risk.files) ? Object.entries(risk.files) : [];
  const syntax = isObj(job.results?.syntax) ? job.results.syntax : {};
  const dependency = isObj(job.results?.dependency_verification) ? job.results.dependency_verification : {};
  const diff = num(summary, ["behavioral_semantic_differences", "semantic_differences"]) ?? 0;
  const cases = num(summary, ["behavioral_cases", "behavioral_cases_total"]) ?? 0;
  const equivalent = num(summary, ["behavioral_equivalent", "behaviorally_equivalent"]) ?? 0;

  return (
    <>
      <div className="explain-hero">
        <div className="explain-icon"><Sparkles/></div>
        <div><h2>Why the migration received its current assessment</h2><p>This explanation is assembled from the actual verification and risk-analysis outputs. It does not invent a model decision.</p></div>
      </div>

      <Section title="Evidence chain">
        <div className="evidence-list">
          <Evidence title="Syntax verification" ok={syntax?.status === "PASS" || syntax?.success === true} detail="The migrated Python files were checked for syntactic validity." />
          <Evidence title="Dependency verification" ok={dependency?.status === "PASS" || dependency?.success === true} detail="Imports and local dependency relationships were checked." />
          <Evidence title="Differential behaviour" ok={diff === 0 && cases > 0} detail={`${equivalent} of ${cases} behavioral cases were equivalent.`} />
          <Evidence title="Risk analysis" ok={riskFiles.length > 0 && riskFiles.every(([,v]: [string,any]) => String(v?.risk).toUpperCase() === "LOW")} detail={`${riskFiles.length} migrated files received a risk assessment.`} />
        </div>
      </Section>

      <Section title="File-level explanation">
        <div className="risk-grid">
          {riskFiles.map(([file, value]: [string, any]) => (
            <div className="risk-card" key={file}>
              <div className="risk-file-head"><strong>{file}</strong><span className={`risk-badge ${String(value?.risk || "").toLowerCase()}`}>{value?.risk || "UNKNOWN"}</span></div>
              <p>{arr(value?.reasons).join(" ") || "No explicit reason was returned by the risk model."}</p>
              <div className="risk-feature-grid">
                <span>Behavioral cases <b>{value?.features?.behavioral_cases ?? "—"}</b></span>
                <span>Differences <b>{value?.features?.semantic_differences ?? "—"}</b></span>
                <span>Difference rate <b>{pct(value?.features?.semantic_difference_rate)}</b></span>
                <span>Test failed <b>{value?.features?.existing_test_failed ?? "—"}</b></span>
              </div>
            </div>
          ))}
        </div>
      </Section>
    </>
  );
}

function Evidence({ title, ok, detail }: { title: string; ok: boolean; detail: string }) {
  return <div className="evidence-row"><span className={ok ? "evidence-check" : "evidence-warn"}>{ok ? <Check size={14}/> : <AlertCircle size={14}/>}</span><div><strong>{title}</strong><p>{detail}</p></div></div>;
}

function MigrationView({ data }: { data: any }) {
  const records = Array.isArray(data) ? data : arr(data?.files ?? data?.results ?? data?.migrations ?? data?.items);
  return <>
    <Section title="Migration engine"><KeyValueGrid items={[["Migration units",records.length || data?.count],["Provider",data?.provider],["Model",data?.model]]}/></Section>
    <Section title="Original → migrated source">
      {records.length ? <div className="migration-table-list">{records.map((item:any,i:number)=>{const file=item?.file || item?.target_file || item?.path || `Migration ${i+1}`; const original=item?.source_code ?? item?.original_code ?? item?.legacy_code ?? ""; const migrated=item?.migrated_code ?? item?.generated_code ?? item?.code ?? item?.modern_code ?? ""; return <div className="migration-file-card" key={i}><div className="migration-file-head"><strong>{file}</strong><span className="success-chip">Migrated</span></div><div className="code-compare"><div><div className="code-label">Original · Python 2</div><pre className="code-block">{original || "Source code was not embedded in this result."}</pre></div><div><div className="code-label">Migrated · Python 3</div><pre className="code-block">{migrated || "Generated code was not embedded in this result."}</pre></div></div></div>})}</div> : <div className="empty-inline">No structured migration records were returned.</div>}
    </Section>
    <RawArtifact value={data}/>
  </>;
}


function FinalReportView({ job }: { job: JobStatus }) {
  const stats = job.statistics || {};
  const semantic = isObj(job.results?.semantic_equivalence) ? job.results.semantic_equivalence : {};
  const summary = isObj(semantic.summary) ? semantic.summary : {};
  const risk = isObj(job.results?.risk_analysis) ? job.results.risk_analysis : {};
  const riskFiles = isObj(risk.files) ? Object.entries(risk.files) : [];
  const completed = STAGES.filter(s => job.stage_status?.[s.id] === "completed").length;
  const cases = num(summary, ["behavioral_cases", "behavioral_cases_total"]) ?? 0;
  const equivalent = num(summary, ["behavioral_equivalent", "behaviorally_equivalent"]) ?? 0;
  const differences = num(summary, ["behavioral_semantic_differences", "semantic_differences"]) ?? 0;
  const syntax = isObj(job.results?.syntax) ? job.results.syntax : {};
  const dependency = isObj(job.results?.dependency_verification) ? job.results.dependency_verification : {};

  return (
    <>
      <Section title="Migration summary">
        <KeyValueGrid items={[
          ["Repository", job.repository_name],
          ["Pipeline status", job.status],
          ["Files", stats.files],
          ["Migration candidates", stats.candidates],
          ["Extracted functions", stats.functions],
          ["RAG queries", stats.rag_queries],
          ["Stages completed", `${completed}/${STAGES.length}`],
        ]}/>
      </Section>

      <Section title="Verification summary">
        <KeyValueGrid items={[
          ["Syntax verification", syntax?.status || (syntax?.success ? "PASS" : undefined)],
          ["Dependency verification", dependency?.status || (dependency?.success ? "PASS" : undefined)],
          ["Behavioral cases", cases],
          ["Equivalent cases", equivalent],
          ["Semantic differences", differences],
        ]}/>
        <div className={`result-banner ${differences === 0 ? "good" : "warn"}`}>
          {differences === 0 ? <CheckCircle2 size={20}/> : <AlertCircle size={20}/>}
          <div><strong>{differences === 0 ? "No behavioral semantic differences were reported." : "Behavioral differences require review."}</strong><span>{equivalent} of {cases} cases were equivalent.</span></div>
        </div>
      </Section>

      <Section title="Risk summary">
        <div className="risk-grid">
          {riskFiles.map(([file, value]: [string, any]) => (
            <div className="risk-card" key={file}>
              <div className="risk-file-head"><strong>{file}</strong><span className={`risk-badge ${String(value?.risk || "").toLowerCase()}`}>{value?.risk || "UNKNOWN"}</span></div>
              <p>{arr(value?.reasons).join(" ")}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Completed pipeline stages">
        <div className="completed-list">
          {STAGES.map(stage => {
            const status = (job.stage_status?.[stage.id] || "pending") as Status;
            return <div key={stage.id}><StatusIcon status={status}/><span>{stage.name}</span><small>{statusLabel(status)}</small></div>;
          })}
        </div>
      </Section>

      <Section title="What this means">
        <p className="explanation">
          The report consolidates the data returned by the migration pipeline. It shows what was analyzed, what was migrated, what verification executed, and what the risk model reported. It should be read together with the individual stage views for detailed evidence.
        </p>
      </Section>
    </>
  );
}

function App() {
  const [theme, setTheme] = useState<"dark" | "light">(() => localStorage.getItem("codemigrate-theme") === "light" ? "light" : "dark");
  const [job, setJob] = useState<JobStatus | null>(null);
  const [activeStage, setActiveStage] = useState("overview");
  const [file, setFile] = useState<File | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => localStorage.setItem("codemigrate-theme", theme), [theme]);

  useEffect(() => {
    const saved = localStorage.getItem("codemigrate-job-id");
    if (!saved) return;
    getJob(saved).then(j => setJob(j)).catch(() => localStorage.removeItem("codemigrate-job-id"));
  }, []);

  useEffect(() => {
    if (!job?.job_id || job.status === "completed" || job.status === "failed") return;
    const timer = window.setInterval(async () => {
      try {
        const updated = await getJob(job.job_id);
        setJob(updated);
        if (updated.current_stage && activeStage === "overview") setActiveStage(updated.current_stage);
      } catch (e) {
        console.error(e);
      }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [job?.job_id, job?.status, activeStage]);

  const completed = useMemo(() => STAGES.filter(s => job?.stage_status?.[s.id] === "completed").length, [job]);
  const active = STAGES.find(s => s.id === activeStage);

  const start = async (f: File) => {
    setStarting(true); setError(null);
    try {
      const newJob = await startMigration(f);
      setJob(newJob);
      localStorage.setItem("codemigrate-job-id", newJob.job_id);
      setActiveStage("overview");
    } catch (e: any) {
      setError(e?.message || "Failed to start migration.");
    } finally {
      setStarting(false);
    }
  };

  const reset = () => {
    localStorage.removeItem("codemigrate-job-id");
    setJob(null); setFile(null); setError(null); setActiveStage("overview");
  };

  if (!job) {
    return (
      <div className={`app ${theme}-theme`}>
        <UploadScreen onStart={start} error={error} theme={theme} setTheme={setTheme}/>
      </div>
    );
  }

  return (
    <div className={`app ${theme}-theme`}>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Zap size={19}/></div>
          <div><div className="brand-title">CODEMIGRATE</div><div className="brand-subtitle">Migration intelligence</div></div>
        </div>

        <div className="job-card">
          <span>JOB</span><strong>{job.job_id}</strong><p>{job.repository_name}</p>
        </div>

        <nav className="sidebar-nav">
          <button className={`nav-overview ${activeStage === "overview" ? "selected" : ""}`} onClick={() => setActiveStage("overview")}><Layers3 size={16}/>Migration Overview</button>
          {GROUP_ORDER.map(group => (
            <div key={group} className="nav-group">
              <div className="nav-group-title">{group}<span>{group === "Analysis" ? "Repository intelligence" : group === "Migration" ? "Code transformation" : group === "Verification" ? "Correctness checks" : group === "Intelligence" ? "AI safety analysis" : "Delivery"}</span></div>
              {STAGES.filter(s => s.group === group).map(stage => {
                const status = (job.stage_status?.[stage.id] || "pending") as Status;
                return (
                  <button key={stage.id} className={`nav-stage ${activeStage === stage.id ? "selected" : ""}`} onClick={() => setActiveStage(stage.id)}>
                    <StatusIcon status={status}/><span>{stage.name}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <button className="theme-button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? <Sun size={15}/> : <Moon size={15}/>} {theme === "dark" ? "Light mode" : "Dark mode"}</button>
          <div className="footer-progress"><div className="progress-track"><div className="progress-fill" style={{width: `${completed / STAGES.length * 100}%`}}/></div><span>{completed}/{STAGES.length} complete</span></div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div><div className="eyebrow">LEGACY CODE MODERNIZATION</div><div className="topbar-title">{activeStage === "overview" ? "Migration Intelligence" : active?.name}</div><p>{job.repository_name}</p></div>
          <div className="topbar-actions">
            <div className={`top-status ${job.status}`}><span/>{job.status === "completed" ? "COMPLETED" : job.status === "failed" ? "FAILED" : "PROCESSING"} <small>· {job.current_stage || "pipeline"}</small></div>
            <>{job.status === "completed" && <button className="download-button" onClick={() => downloadMigratedRepo(job.job_id)}><FolderGit2 size={15}/> Download migrated repo</button>}<button className="new-job-button" onClick={reset}>New job</button></>
          </div>
        </header>

        <div className="main-scroll">
          {error && <div className="error-banner">{error}</div>}
          {activeStage === "overview" ? <Overview job={job} onOpen={setActiveStage}/> : active ? <StagePage stage={active} job={job}/> : null}
        </div>
      </main>
    </div>
  );
}

export default App;
