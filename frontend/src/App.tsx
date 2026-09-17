import { useEffect, useMemo, useState } from "react";
import {
  Upload,
  FolderGit2,
  ScanSearch,
  GitBranch,
  Database,
  BrainCircuit,
  FileCode2,
  CheckCircle2,
  Clock3,
  AlertCircle,
  ArrowRight,
  Sparkles,
  LoaderCircle,
  XCircle,
  ChevronDown,
  ChevronRight,
  Search,
  Layers3,
  Network,
  ListChecks,
  TerminalSquare,
  Copy,
  Check,
  Code2,
  FileSearch,
  GitMerge,
  CircleDot,
  Sun,
  Moon
} from "lucide-react";

import "./App.css";
import {
  getJob,
  startMigration,
  type JobStatus,
} from "./api";


/* =========================================================
   TYPES
   ========================================================= */

type Stage = {
  id: string;
  name: string;
  description: string;
  icon: React.ElementType;
};

type JsonObject = Record<string, any>;


/* =========================================================
   PIPELINE
   ========================================================= */

const stages: Stage[] = [
  {
    id: "scan",
    name: "Repository Scan",
    description: "Discover files and repository structure",
    icon: ScanSearch,
  },
  {
    id: "version",
    name: "Version Detection",
    description: "Identify legacy language versions",
    icon: GitBranch,
  },
  {
    id: "extraction",
    name: "Code Extraction",
    description: "Extract functions and migration candidates",
    icon: FileCode2,
  },
  {
    id: "embeddings",
    name: "Semantic Embeddings",
    description: "Generate CodeBERT representations",
    icon: BrainCircuit,
  },
  {
    id: "dependency",
    name: "Dependency Analysis",
    description: "Map imports and code relationships",
    icon: GitBranch,
  },
  {
    id: "planning",
    name: "Migration Planning",
    description: "Determine migration order and scope",
    icon: Sparkles,
  },
  {
    id: "context",
    name: "Repository Context",
    description: "Build contextual migration knowledge",
    icon: Database,
  },
  {
    id: "rag",
    name: "RAG Retrieval",
    description: "Retrieve historical migration examples",
    icon: Database,
  },
  {
    id: "prompt",
    name: "Prompt Construction",
    description: "Build context-aware migration prompts",
    icon: FileCode2,
  },
  {
    id: "llm",
    name: "LLM Migration",
    description: "Generate migrated source code",
    icon: BrainCircuit,
  },
];


const futureModules = [
  "Syntax Verification",
  "Differential Testing",
  "Semantic Equivalence",
  "Migration Risk",
  "Explainability",
  "Developer Feedback",
];


/* =========================================================
   GENERIC HELPERS
   These make the UI resilient to slightly different
   JSON structures coming from your existing pipeline.
   ========================================================= */

function isObject(value: any): value is JsonObject {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value)
  );
}


function asArray(value: any): any[] {
  if (Array.isArray(value)) {
    return value;
  }

  if (value === undefined || value === null) {
    return [];
  }

  return [value];
}


function firstDefined(
  obj: any,
  keys: string[],
  fallback: any = undefined,
): any {
  if (!isObject(obj)) {
    return fallback;
  }

  for (const key of keys) {
    if (
      obj[key] !== undefined &&
      obj[key] !== null
    ) {
      return obj[key];
    }
  }

  return fallback;
}


function asString(
  value: any,
  fallback = "—",
): string {
  if (
    value === undefined ||
    value === null ||
    value === ""
  ) {
    return fallback;
  }

  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return String(value);
  }

  return fallback;
}


function getFileName(
  item: any,
  fallback = "Unknown file",
): string {
  return asString(
    firstDefined(item, [
      "file",
      "file_path",
      "filepath",
      "path",
      "source_file",
      "filename",
      "name",
    ]),
    fallback,
  );
}


function getFunctionName(
  item: any,
  fallback = "Unknown function",
): string {
  return asString(
    firstDefined(item, [
      "function",
      "function_name",
      "functionName",
      "symbol",
      "symbol_name",
      "name",
    ]),
    fallback,
  );
}


function findArrays(
  value: any,
  matchingKeys: string[],
): any[][] {
  const results: any[][] = [];

  if (!isObject(value)) {
    return results;
  }

  for (const [key, child] of Object.entries(value)) {
    const normalized = key.toLowerCase();

    if (
      Array.isArray(child) &&
      matchingKeys.some((k) =>
        normalized.includes(k.toLowerCase()),
      )
    ) {
      results.push(child);
    }

    if (isObject(child)) {
      results.push(
        ...findArrays(
          child,
          matchingKeys,
        ),
      );
    }
  }

  return results;
}


function findObjectsWithKeys(
  value: any,
  keys: string[],
): any[] {
  const results: any[] = [];

  if (Array.isArray(value)) {
    for (const item of value) {
      results.push(
        ...findObjectsWithKeys(
          item,
          keys,
        ),
      );
    }

    return results;
  }

  if (!isObject(value)) {
    return results;
  }

  const normalizedKeys = Object.keys(value).map(
    (key) => key.toLowerCase(),
  );

  const matches = keys.some((key) =>
    normalizedKeys.includes(
      key.toLowerCase(),
    ),
  );

  if (matches) {
    results.push(value);
  }

  for (const child of Object.values(value)) {
    if (isObject(child) || Array.isArray(child)) {
      results.push(
        ...findObjectsWithKeys(
          child,
          keys,
        ),
      );
    }
  }

  return results;
}


function collectStrings(
  value: any,
  depth = 0,
): string[] {
  if (depth > 4) {
    return [];
  }

  if (typeof value === "string") {
    return [value];
  }

  if (Array.isArray(value)) {
    return value.flatMap((item) =>
      collectStrings(item, depth + 1),
    );
  }

  if (isObject(value)) {
    return Object.values(value).flatMap(
      (item) =>
        collectStrings(
          item,
          depth + 1,
        ),
    );
  }

  return [];
}


function formatJson(value: any): string {
  try {
    return JSON.stringify(
      value,
      null,
      2,
    );
  } catch {
    return String(value);
  }
}


/* =========================================================
   SMALL UI COMPONENTS
   ========================================================= */

function SectionTitle({
  eyebrow,
  title,
  description,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
}) {
  return (
    <div className="view-section-title">
      {eyebrow && (
        <div className="view-eyebrow">
          {eyebrow}
        </div>
      )}

      <h3>{title}</h3>

      {description && (
        <p>{description}</p>
      )}
    </div>
  );
}


function Metric({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: any;
  icon?: React.ElementType;
}) {
  return (
    <div className="stage-metric">
      <div className="stage-metric-top">
        {Icon && (
          <div className="stage-metric-icon">
            <Icon size={16} />
          </div>
        )}

        <span>{label}</span>
      </div>

      <strong>
        {asString(value)}
      </strong>
    </div>
  );
}


function StatusPill({
  status,
}: {
  status: string;
}) {
  const normalized =
    status.toLowerCase();

  const positive =
    normalized.includes("success") ||
    normalized.includes("complete") ||
    normalized === "completed" ||
    normalized === "true" ||
    normalized === "yes";

  const negative =
    normalized.includes("fail") ||
    normalized.includes("error") ||
    normalized === "false" ||
    normalized === "no";

  return (
    <span
      className={`data-pill ${
        positive
          ? "positive"
          : negative
          ? "negative"
          : ""
      }`}
    >
      {positive && (
        <CheckCircle2 size={13} />
      )}

      {negative && (
        <XCircle size={13} />
      )}

      {!positive && !negative && (
        <CircleDot size={13} />
      )}

      {status}
    </span>
  );
}


function RawData({
  data,
}: {
  data: any;
}) {
  const [open, setOpen] =
    useState(false);

  return (
    <div className="raw-data">
      <button
        className="raw-toggle"
        onClick={() =>
          setOpen(!open)
        }
      >
        {open ? (
          <ChevronDown size={15} />
        ) : (
          <ChevronRight size={15} />
        )}

        <TerminalSquare size={15} />

        Raw pipeline data
      </button>

      {open && (
        <pre className="raw-data-content">
          {formatJson(data)}
        </pre>
      )}
    </div>
  );
}


function EmptyStage({
  title,
  description,
  icon: Icon = Clock3,
}: {
  title: string;
  description: string;
  icon?: React.ElementType;
}) {
  return (
    <div className="stage-empty">
      <div className="stage-empty-icon">
        <Icon size={25} />
      </div>

      <h3>{title}</h3>

      <p>{description}</p>
    </div>
  );
}


/* =========================================================
   REPOSITORY SCAN VIEW
   ========================================================= */

function ScanView({
  data,
}: {
  data: any;
}) {
  const files = useMemo(() => {
    const arrays =
      findArrays(data, [
        "files",
        "file_list",
        "discovered",
        "entries",
      ]);

    const first =
      arrays.find(
        (arr) =>
          arr.length > 0,
      );

    return first ?? [];
  }, [data]);


  const pythonFiles =
    files.filter((file) => {
      const name =
        typeof file === "string"
          ? file
          : getFileName(file, "");

      return name
        .toLowerCase()
        .endsWith(".py");
    });


  const candidateArrays =
    findArrays(data, [
      "candidate",
      "migration",
      "selected",
      "target",
    ]);

  const candidates =
    candidateArrays
      .flat()
      .filter(
        (item, index, arr) =>
          arr.indexOf(item) ===
          index,
      );


  const skippedArrays =
    findArrays(data, [
      "skip",
      "ignored",
      "excluded",
      "ignore",
    ]);

  const skipped =
    skippedArrays.flat();


  const languages = new Map<
    string,
    number
  >();

  files.forEach((file) => {
    const name =
      typeof file === "string"
        ? file
        : getFileName(file, "");

    const extension =
      name.includes(".")
        ? name
            .split(".")
            .pop()
            ?.toLowerCase()
        : "";

    if (!extension) {
      return;
    }

    const language =
      extension === "py"
        ? "Python"
        : extension === "js" ||
          extension === "jsx"
        ? "JavaScript"
        : extension === "ts" ||
          extension === "tsx"
        ? "TypeScript"
        : extension === "json"
        ? "JSON"
        : extension === "md"
        ? "Markdown"
        : extension.toUpperCase();

    languages.set(
      language,
      (languages.get(language) ?? 0) +
        1,
    );
  });


  const totalFiles =
    firstDefined(data, [
      "total_files",
      "file_count",
      "files_count",
      "num_files",
    ]) ??
    files.length;


  const candidateCount =
    firstDefined(data, [
      "migration_candidates",
      "candidate_count",
      "candidates_count",
    ]) ??
    candidates.length;


  return (
    <div className="stage-view">

      <div className="stage-overview-grid">
        <Metric
          label="Total files"
          value={totalFiles}
          icon={FolderGit2}
        />

        <Metric
          label="Python files"
          value={
            firstDefined(data, [
              "python_files",
              "python_file_count",
            ]) ??
            pythonFiles.length
          }
          icon={FileCode2}
        />

        <Metric
          label="Migration candidates"
          value={candidateCount}
          icon={Search}
        />

        <Metric
          label="Skipped / ignored"
          value={
            firstDefined(data, [
              "skipped_files",
              "ignored_files",
              "excluded_files",
            ]) ??
            skipped.length
          }
          icon={XCircle}
        />
      </div>


      {languages.size > 0 && (
        <div className="stage-section">
          <SectionTitle
            eyebrow="REPOSITORY"
            title="Languages detected"
            description="File types discovered during repository scanning."
          />

          <div className="language-grid">
            {Array.from(
              languages.entries(),
            ).map(
              ([language, count]) => (
                <div
                  className="language-card"
                  key={language}
                >
                  <div className="language-icon">
                    <Code2 size={17} />
                  </div>

                  <div>
                    <strong>
                      {language}
                    </strong>

                    <span>
                      {count}{" "}
                      {count === 1
                        ? "file"
                        : "files"}
                    </span>
                  </div>
                </div>
              ),
            )}
          </div>
        </div>
      )}


      {candidates.length > 0 && (
        <div className="stage-section">
          <SectionTitle
            eyebrow="MIGRATION TARGETS"
            title="Files selected for migration"
          />

          <div className="file-list">
            {candidates.map(
              (candidate, index) => {
                const name =
                  typeof candidate ===
                  "string"
                    ? candidate
                    : getFileName(
                        candidate,
                        `Candidate ${index + 1}`,
                      );

                return (
                  <div
                    className="file-row"
                    key={`${name}-${index}`}
                  >
                    <FileCode2
                      size={17}
                    />

                    <span>
                      {name}
                    </span>

                    <StatusPill status="Migration candidate" />
                  </div>
                );
              },
            )}
          </div>
        </div>
      )}


      {skipped.length > 0 && (
        <div className="stage-section">
          <SectionTitle
            eyebrow="FILTERED"
            title="Skipped or ignored files"
          />

          <div className="file-list muted-list">
            {skipped
              .slice(0, 50)
              .map(
                (item, index) => {
                  const name =
                    typeof item ===
                    "string"
                      ? item
                      : getFileName(
                          item,
                          `Item ${index + 1}`,
                        );

                  return (
                    <div
                      className="file-row"
                      key={`${name}-${index}`}
                    >
                      <CircleDot
                        size={15}
                      />

                      <span>
                        {name}
                      </span>
                    </div>
                  );
                },
              )}
          </div>
        </div>
      )}

      <RawData data={data} />
    </div>
  );
}


/* =========================================================
   VERSION DETECTION VIEW
   ========================================================= */

function VersionView({
  data,
}: {
  data: any;
}) {
  const language =
    asString(
      firstDefined(data, [
        "language",
        "detected_language",
        "primary_language",
      ]),
      "Python",
    );

  const sourceVersion =
    asString(
      firstDefined(data, [
        "source_version",
        "legacy_version",
        "from_version",
        "detected_version",
        "version",
      ]),
      "Detected from repository",
    );

  const targetVersion =
    asString(
      firstDefined(data, [
        "target_version",
        "to_version",
        "migration_target",
      ]),
      "Python 3",
    );


  const migrationRequired =
    firstDefined(data, [
      "migration_required",
      "requires_migration",
      "needs_migration",
    ]);


  const candidates =
    findArrays(data, [
      "candidate",
      "migration",
      "selected",
      "target",
    ])
      .flat();


  const constructs =
    findArrays(data, [
      "construct",
      "feature",
      "issue",
      "pattern",
      "legacy",
    ])
      .flat();


  return (
    <div className="stage-view">

      <div className="version-banner">
        <div className="version-banner-icon">
          <GitBranch size={23} />
        </div>

        <div>
          <span>Detected migration path</span>

          <strong>
            {language}{" "}
            <ArrowRight size={16} />{" "}
            {targetVersion}
          </strong>
        </div>

        {migrationRequired !==
          undefined && (
          <StatusPill
            status={
              migrationRequired
                ? "Migration required"
                : "No migration required"
            }
          />
        )}
      </div>


      <div className="stage-overview-grid">

        <Metric
          label="Language"
          value={language}
          icon={Code2}
        />

        <Metric
          label="Legacy version"
          value={sourceVersion}
          icon={GitBranch}
        />

        <Metric
          label="Target version"
          value={targetVersion}
          icon={ArrowRight}
        />

        <Metric
          label="Migration required"
          value={
            migrationRequired ===
            undefined
              ? "Detected"
              : migrationRequired
              ? "YES"
              : "NO"
          }
          icon={AlertCircle}
        />

      </div>


      {candidates.length > 0 && (
        <div className="stage-section">

          <SectionTitle
            eyebrow="MIGRATION SCOPE"
            title="Files requiring migration"
          />

          <div className="file-list">
            {candidates.map(
              (item, index) => (
                <div
                  className="file-row"
                  key={index}
                >
                  <FileCode2
                    size={17}
                  />

                  <span>
                    {getFileName(
                      item,
                      typeof item ===
                        "string"
                        ? item
                        : `Migration target ${
                            index + 1
                          }`,
                    )}
                  </span>

                  <span className="path-arrow">
                    {sourceVersion}
                    {" → "}
                    {targetVersion}
                  </span>
                </div>
              ),
            )}
          </div>

        </div>
      )}


      {constructs.length > 0 && (
        <div className="stage-section">

          <SectionTitle
            eyebrow="LEGACY PATTERNS"
            title="Detected migration constructs"
            description="Patterns identified by the version-analysis stage."
          />

          <div className="tag-list">
            {constructs
              .slice(0, 40)
              .map(
                (item, index) => (
                  <span
                    className="feature-tag"
                    key={index}
                  >
                    {typeof item ===
                    "string"
                      ? item
                      : asString(
                          firstDefined(
                            item,
                            [
                              "feature",
                              "name",
                              "pattern",
                              "type",
                              "construct",
                            ],
                          ),
                          `Pattern ${
                            index + 1
                          }`,
                        )}
                  </span>
                ),
              )}
          </div>

        </div>
      )}

      <RawData data={data} />
    </div>
  );
}


/* =========================================================
   CODE EXTRACTION VIEW
   ========================================================= */

function ExtractionView({
  data,
}: {
  data: any;
}) {
  const units =
    findArrays(data, [
      "functions",
      "migration_units",
      "units",
      "features",
      "symbols",
    ])
      .flat()
      .filter(
        (item, index, arr) =>
          arr.indexOf(item) ===
          index,
      );


  const uniqueUnits =
    units.length > 0
      ? units
      : findObjectsWithKeys(
          data,
          [
            "function_name",
            "function",
            "symbol",
          ],
        );


  const candidateCount =
    firstDefined(data, [
      "migration_candidates",
      "candidate_count",
      "candidates",
    ]);


  return (
    <div className="stage-view">

      <div className="stage-overview-grid">

        <Metric
          label="Extracted units"
          value={
            firstDefined(data, [
              "total_functions",
              "function_count",
              "units_count",
            ]) ??
            uniqueUnits.length
          }
          icon={Layers3}
        />

        <Metric
          label="Migration candidates"
          value={
            typeof candidateCount ===
            "number"
              ? candidateCount
              : candidateCount
              ? asArray(
                  candidateCount,
                ).length
              : "—"
          }
          icon={Search}
        />

        <Metric
          label="Analysis"
          value="Static code features"
          icon={FileSearch}
        />

      </div>


      {uniqueUnits.length > 0 ? (
        <div className="stage-section">

          <SectionTitle
            eyebrow="EXTRACTED CODE"
            title="Functions & migration units"
            description="Code units identified for downstream embedding, retrieval and migration."
          />

          <div className="unit-grid">

            {uniqueUnits.map(
              (item, index) => {

                const file =
                  typeof item ===
                  "string"
                    ? ""
                    : getFileName(
                        item,
                        "",
                      );

                const fn =
                  typeof item ===
                  "string"
                    ? item
                    : getFunctionName(
                        item,
                        `Code unit ${index + 1}`,
                      );

                const candidate =
                  firstDefined(item, [
                    "migration_candidate",
                    "is_candidate",
                    "selected",
                    "requires_migration",
                  ]);

                const features =
                  firstDefined(item, [
                    "features",
                    "migration_features",
                    "issues",
                    "patterns",
                  ]);


                return (
                  <div
                    className="unit-card"
                    key={index}
                  >

                    <div className="unit-card-header">

                      <div className="unit-icon">
                        <FileCode2
                          size={17}
                        />
                      </div>

                      <div className="unit-title">

                        <strong>
                          {fn}
                        </strong>

                        {file && (
                          <span>
                            {file}
                          </span>
                        )}

                      </div>

                      {candidate !==
                        undefined && (
                        <StatusPill
                          status={
                            candidate
                              ? "Candidate"
                              : "Reviewed"
                          }
                        />
                      )}

                    </div>


                    {Array.isArray(
                      features,
                    ) &&
                      features.length >
                        0 && (
                        <div className="unit-features">

                          {features
                            .slice(
                              0,
                              8,
                            )
                            .map(
                              (
                                feature,
                                featureIndex,
                              ) => (
                                <span
                                  className="feature-tag"
                                  key={
                                    featureIndex
                                  }
                                >
                                  {typeof feature ===
                                  "string"
                                    ? feature
                                    : asString(
                                        firstDefined(
                                          feature,
                                          [
                                            "name",
                                            "type",
                                            "feature",
                                          ],
                                        ),
                                        "Feature",
                                      )}
                                </span>
                              ),
                            )}

                        </div>
                      )}

                  </div>
                );
              },
            )}

          </div>

        </div>
      ) : (
        <EmptyStage
          title="Code units extracted"
          description="The extraction stage completed. Expand Raw pipeline data below to inspect the detailed feature structure."
          icon={FileSearch}
        />
      )}

      <RawData data={data} />
    </div>
  );
}


/* =========================================================
   EMBEDDING VIEW
   ========================================================= */

function EmbeddingView({
  data,
}: {
  data: any;
}) {
  const records =
    firstDefined(data, [
      "records",
      "count",
      "embedding_count",
    ]);

  const dimension =
    firstDefined(data, [
      "dimension",
      "embedding_dimension",
      "vector_dimension",
    ]);

  const model =
    firstDefined(data, [
      "model",
      "model_name",
      "embedding_model",
    ]);


  return (
    <div className="stage-view">

      <div className="embedding-hero">

        <div className="embedding-icon">
          <BrainCircuit size={30} />
        </div>

        <div>
          <div className="view-eyebrow">
            SEMANTIC REPRESENTATION
          </div>

          <h3>
            CodeBERT Embeddings
          </h3>

          <p>
            Legacy code is converted into
            semantic representations for
            migration-example retrieval and
            downstream intelligence.
          </p>
        </div>

      </div>


      <div className="stage-overview-grid">

        <Metric
          label="Model"
          value={
            model ??
            "microsoft/codebert-base"
          }
          icon={BrainCircuit}
        />

        <Metric
          label="Embedded units"
          value={records ?? "—"}
          icon={Layers3}
        />

        <Metric
          label="Vector dimension"
          value={dimension ?? "—"}
          icon={Database}
        />

      </div>


      <div className="embedding-status">

        <div className="embedding-status-header">

          <div>
            <strong>
              Embedding pipeline
            </strong>

            <span>
              Semantic representations
              generated successfully
            </span>
          </div>

          <CheckCircle2
            size={21}
          />

        </div>

        <div className="progress-track">
          <div
            className="progress-fill"
            style={{
              width: "100%",
            }}
          />
        </div>

        <div className="progress-label">
          <span>
            Complete
          </span>

          <span>
            {records ?? "—"} records
          </span>
        </div>

      </div>


      <RawData data={data} />
    </div>
  );
}


/* =========================================================
   DEPENDENCY VIEW
   ========================================================= */

function DependencyView({
  data,
}: {
  data: any;
}) {
  const edges =
    findArrays(data, [
      "edges",
      "dependencies",
      "relationships",
      "imports",
      "calls",
    ])
      .flat()
      .filter(
        (item, index, arr) =>
          arr.indexOf(item) ===
          index,
      );


  const pythonFiles =
    firstDefined(data, [
      "python_files",
      "python_file_count",
      "num_python_files",
    ]);


  const edgeCount =
    firstDefined(data, [
      "dependency_edges",
      "edge_count",
      "total_edges",
      "relationships_count",
    ]) ??
    edges.length;


  const importCount =
    firstDefined(data, [
      "import_edges",
      "imports_count",
      "import_count",
    ]);


  const callCount =
    firstDefined(data, [
      "function_calls",
      "function_call_edges",
      "call_edges",
      "calls_count",
    ]);


  const getSource = (
    edge: any,
  ) =>
    asString(
      firstDefined(edge, [
        "source",
        "from",
        "caller",
        "parent",
        "source_file",
      ]),
      typeof edge === "string"
        ? edge
        : "Unknown",
    );


  const getTarget = (
    edge: any,
  ) =>
    asString(
      firstDefined(edge, [
        "target",
        "to",
        "callee",
        "child",
        "target_file",
      ]),
      "Unknown",
    );


  return (
    <div className="stage-view">

      <div className="stage-overview-grid">

        <Metric
          label="Python files"
          value={
            pythonFiles ??
            "—"
          }
          icon={FileCode2}
        />

        <Metric
          label="Dependency relationships"
          value={edgeCount}
          icon={Network}
        />

        <Metric
          label="Import relationships"
          value={
            importCount ??
            "—"
          }
          icon={GitMerge}
        />

        <Metric
          label="Function calls"
          value={
            callCount ??
            "—"
          }
          icon={ArrowRight}
        />

      </div>


      <div className="stage-section">

        <SectionTitle
          eyebrow="REPOSITORY GRAPH"
          title="Dependency relationships"
          description="Source-to-target relationships extracted from the repository."
        />

        {edges.length > 0 ? (

          <div className="dependency-list">

            {edges
              .slice(0, 100)
              .map(
                (edge, index) => (
                  <div
                    className="dependency-row"
                    key={index}
                  >

                    <div className="dependency-node">
                      <FileCode2
                        size={15}
                      />

                      <span>
                        {getSource(
                          edge,
                        )}
                      </span>
                    </div>

                    <ArrowRight
                      size={17}
                      className="dependency-arrow"
                    />

                    <div className="dependency-node target">
                      <FileCode2
                        size={15}
                      />

                      <span>
                        {getTarget(
                          edge,
                        )}
                      </span>
                    </div>

                  </div>
                ),
              )}

          </div>

        ) : (

          <div className="dependency-empty">
            <Network size={25} />

            <p>
              Dependency data is available
              from the pipeline. Expand Raw
              pipeline data if the current
              schema does not expose individual
              relationships.
            </p>
          </div>

        )}

      </div>


      <RawData data={data} />
    </div>
  );
}


/* =========================================================
   MIGRATION PLANNING VIEW
   ========================================================= */

function PlanningView({
  data,
}: {
  data: any;
}) {
  const plan =
    findArrays(data, [
      "migration_order",
      "order",
      "sequence",
      "plan",
      "units",
      "steps",
    ])
      .flat();


  const uniquePlan =
    plan.filter(
      (item, index, arr) =>
        arr.indexOf(item) ===
        index,
    );


  const order =
    uniquePlan.length > 0
      ? uniquePlan
      : findObjectsWithKeys(
          data,
          [
            "file",
            "migration_order",
            "order",
          ],
        );


  const rationale =
    firstDefined(data, [
      "rationale",
      "reason",
      "strategy",
      "planning_rationale",
      "description",
    ]);


  return (
    <div className="stage-view">

      <div className="planning-hero">

        <div className="planning-icon">
          <ListChecks size={27} />
        </div>

        <div>
          <div className="view-eyebrow">
            REPOSITORY-LEVEL STRATEGY
          </div>

          <h3>
            Recommended Migration Order
          </h3>

          <p>
            Dependencies are considered so
            lower-level components can be
            migrated before their dependents.
          </p>
        </div>

      </div>


      {order.length > 0 ? (

        <div className="plan-list">

          {order.map(
            (item, index) => {

              const file =
                typeof item ===
                "string"
                  ? item
                  : getFileName(
                      item,
                      `Migration step ${
                        index + 1
                      }`,
                    );


              const reason =
                typeof item ===
                "string"
                  ? ""
                  : asString(
                      firstDefined(
                        item,
                        [
                          "reason",
                          "rationale",
                          "why",
                          "description",
                        ],
                      ),
                      "",
                    );


              const dependencies =
                typeof item ===
                "string"
                  ? []
                  : asArray(
                      firstDefined(
                        item,
                        [
                          "dependencies",
                          "depends_on",
                          "requires",
                        ],
                      ),
                    );


              return (
                <div
                  className="plan-step"
                  key={index}
                >

                  <div className="plan-number">
                    {String(
                      index + 1,
                    ).padStart(
                      2,
                      "0",
                    )}
                  </div>

                  <div className="plan-line" />

                  <div className="plan-content">

                    <div className="plan-file">
                      <FileCode2
                        size={18}
                      />

                      <strong>
                        {file}
                      </strong>
                    </div>

                    {reason && (
                      <p>
                        {reason}
                      </p>
                    )}

                    {dependencies.length >
                      0 && (
                      <div className="plan-dependencies">
                        <span>
                          Depends on
                        </span>

                        {dependencies
                          .slice(
                            0,
                            8,
                          )
                          .map(
                            (
                              dep,
                              depIndex,
                            ) => (
                              <span
                                className="dependency-chip"
                                key={
                                  depIndex
                                }
                              >
                                {typeof dep ===
                                "string"
                                  ? dep
                                  : getFileName(
                                      dep,
                                      "Dependency",
                                    )}
                              </span>
                            ),
                          )}
                      </div>
                    )}

                  </div>

                </div>
              );
            },
          )}

        </div>

      ) : (

        <EmptyStage
          title="Migration plan generated"
          description="The planner completed. The detailed plan can be inspected through the raw pipeline data if its structure is not directly exposed."
          icon={ListChecks}
        />

      )}


      {rationale && (
        <div className="rationale-card">

          <div className="rationale-icon">
            <Sparkles size={18} />
          </div>

          <div>
            <strong>
              Planning rationale
            </strong>

            <p>
              {asString(
                rationale,
              )}
            </p>
          </div>

        </div>
      )}


      <RawData data={data} />
    </div>
  );
}


/* =========================================================
   REPOSITORY CONTEXT VIEW
   ========================================================= */

function ContextView({
  data,
}: {
  data: any;
}) {
  const tree =
    firstDefined(data, [
      "repository_tree",
      "tree",
      "structure",
      "files",
    ]);


  const contextItems =
    findArrays(data, [
      "context",
      "components",
      "sources",
      "files",
      "dependencies",
    ])
      .flat()
      .filter(
        (item, index, arr) =>
          arr.indexOf(item) ===
          index,
      );


  return (
    <div className="stage-view">

      <div className="context-hero">

        <div className="context-icon">
          <Database size={27} />
        </div>

        <div>

          <div className="view-eyebrow">
            CONTEXT BUILDING
          </div>

          <h3>
            Repository-aware migration context
          </h3>

          <p>
            The migration process combines
            repository structure, dependencies,
            migration planning and related code
            to provide broader context to the LLM.
          </p>

        </div>

      </div>


      {tree && (
        <div className="stage-section">

          <SectionTitle
            eyebrow="STRUCTURE"
            title="Repository structure"
          />

          <pre className="tree-view">
            {typeof tree ===
            "string"
              ? tree
              : formatJson(tree)}
          </pre>

        </div>
      )}


      {contextItems.length >
        0 && (
        <div className="stage-section">

          <SectionTitle
            eyebrow="CONTEXT SOURCES"
            title="Information included"
          />

          <div className="context-grid">

            {contextItems
              .slice(0, 40)
              .map(
                (item, index) => {

                  const label =
                    typeof item ===
                    "string"
                      ? item
                      : getFileName(
                          item,
                          asString(
                            firstDefined(
                              item,
                              [
                                "name",
                                "type",
                                "source",
                                "component",
                              ],
                            ),
                            `Context ${index + 1}`,
                          ),
                        );

                  return (
                    <div
                      className="context-chip-card"
                      key={index}
                    >
                      <CheckCircle2
                        size={16}
                      />

                      <span>
                        {label}
                      </span>
                    </div>
                  );
                },
              )}

          </div>

        </div>
      )}


      <RawData data={data} />
    </div>
  );
}


/* =========================================================
   RAG VIEW
   ========================================================= */

function RagView({
  data,
}: {
  data: any;
}) {
  const queries =
    findArrays(data, [
      "queries",
      "rag_queries",
      "searches",
    ])
      .flat();


  const examples =
    findArrays(data, [
      "results",
      "examples",
      "matches",
      "retrieved",
      "documents",
    ])
      .flat();


  const uniqueExamples =
    examples.filter(
      (item, index, arr) =>
        arr.indexOf(item) ===
        index,
    );


  const queryCount =
    firstDefined(data, [
      "query_count",
      "queries_count",
      "rag_queries",
      "total_queries",
    ]) ??
    queries.length;


  const successful =
    firstDefined(data, [
      "successful_queries",
      "successful",
      "success_count",
    ]);


  const exampleCount =
    firstDefined(data, [
      "examples_retrieved",
      "retrieved_examples",
      "result_count",
      "results_count",
    ]) ??
    uniqueExamples.length;


  return (
    <div className="stage-view">

      <div className="stage-overview-grid">

        <Metric
          label="RAG queries"
          value={queryCount}
          icon={Search}
        />

        <Metric
          label="Successful queries"
          value={
            successful ??
            "—"
          }
          icon={CheckCircle2}
        />

        <Metric
          label="Retrieved examples"
          value={exampleCount}
          icon={Database}
        />

      </div>


      <div className="rag-explainer">

        <div className="rag-explainer-icon">
          <Sparkles size={21} />
        </div>

        <div>
          <strong>
            Historical migration intelligence
          </strong>

          <p>
            Similar legacy-to-modern code
            transformations are retrieved to
            give the LLM concrete migration
            examples.
          </p>
        </div>

      </div>


      {uniqueExamples.length >
      0 ? (

        <div className="stage-section">

          <SectionTitle
            eyebrow="RETRIEVED KNOWLEDGE"
            title="Migration examples"
            description="Examples retrieved by semantic similarity."
          />

          <div className="rag-grid">

            {uniqueExamples
              .slice(0, 60)
              .map(
                (
                  example,
                  index,
                ) => {

                  const file =
                    getFileName(
                      example,
                      `Example ${index + 1}`,
                    );

                  const fn =
                    getFunctionName(
                      example,
                      "",
                    );

                  const similarity =
                    firstDefined(
                      example,
                      [
                        "similarity",
                        "score",
                        "similarity_score",
                        "distance",
                      ],
                    );


                  const source =
                    firstDefined(
                      example,
                      [
                        "repository",
                        "repo",
                        "source",
                        "source_repo",
                      ],
                    );


                  const legacyCode =
                    firstDefined(
                      example,
                      [
                        "legacy_code",
                        "source_code",
                        "old_code",
                        "before",
                        "original_code",
                      ],
                    );


                  const migratedCode =
                    firstDefined(
                      example,
                      [
                        "migrated_code",
                        "target_code",
                        "new_code",
                        "after",
                        "modern_code",
                      ],
                    );


                  return (
                    <div
                      className="rag-card"
                      key={index}
                    >

                      <div className="rag-card-header">

                        <div className="rag-title">

                          <FileCode2
                            size={17}
                          />

                          <div>
                            <strong>
                              {file}
                            </strong>

                            {fn && (
                              <span>
                                {fn}
                              </span>
                            )}
                          </div>

                        </div>

                        {similarity !==
                          undefined && (
                          <span className="similarity-badge">
                            {formatSimilarity(
                              similarity,
                            )}
                          </span>
                        )}

                      </div>


                      {source && (
                        <div className="rag-source">
                          Source:{" "}
                          {asString(
                            source,
                          )}
                        </div>
                      )}


                      {(legacyCode ||
                        migratedCode) && (
                        <div className="rag-code-grid">

                          <div>
                            <span>
                              Legacy
                            </span>

                            <pre>
                              {typeof legacyCode ===
                              "string"
                                ? legacyCode
                                : formatJson(
                                    legacyCode,
                                  )}
                            </pre>
                          </div>

                          <div>
                            <span>
                              Migrated
                            </span>

                            <pre>
                              {typeof migratedCode ===
                              "string"
                                ? migratedCode
                                : formatJson(
                                    migratedCode,
                                  )}
                            </pre>
                          </div>

                        </div>
                      )}

                    </div>
                  );
                },
              )}

          </div>

        </div>

      ) : (

        <EmptyStage
          title="RAG retrieval completed"
          description="The retrieval stage completed successfully. The detailed examples are available in the raw pipeline result."
          icon={Database}
        />

      )}


      <RawData data={data} />
    </div>
  );
}


/* =========================================================
   SIMILARITY FORMAT
   ========================================================= */

function formatSimilarity(
  value: any,
): string {
  const numeric =
    Number(value);

  if (
    Number.isNaN(numeric)
  ) {
    return String(value);
  }

  if (
    numeric >= 0 &&
    numeric <= 1
  ) {
    return `${(
      numeric * 100
    ).toFixed(1)}%`;
  }

  return numeric.toFixed(3);
}


/* =========================================================
   PROMPT VIEW
   ========================================================= */

function PromptView({
  data,
}: {
  data: any;
}) {
  const prompts = useMemo(() => {

    if (Array.isArray(data)) {
      return data;
    }

    const arrays =
      findArrays(data, [
        "prompts",
        "items",
        "requests",
      ]);

    const found =
      arrays
        .flat()
        .filter(
          (item, index, arr) =>
            arr.indexOf(item) ===
            index,
        );

    return found.length > 0
      ? found
      : [data];

  }, [data]);


  const [selected, setSelected] =
    useState(0);

  const [copied, setCopied] =
    useState(false);


  useEffect(() => {
    if (
      selected >=
      prompts.length
    ) {
      setSelected(0);
    }
  }, [
    prompts.length,
    selected,
  ]);


  const current =
    prompts[selected] ??
    prompts[0];


  const promptText =
    typeof current ===
    "string"
      ? current
      : asString(
          firstDefined(
            current,
            [
              "prompt",
              "content",
              "text",
              "final_prompt",
              "llm_prompt",
            ],
          ),
          formatJson(current),
        );


  const file =
    typeof current ===
    "string"
      ? ""
      : getFileName(
          current,
          "",
        );


  const copyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(
        promptText,
      );

      setCopied(true);

      window.setTimeout(
        () => {
          setCopied(false);
        },
        1500,
      );
    } catch {
      // Clipboard can be unavailable in some environments.
    }
  };


  return (
    <div className="stage-view">

      <div className="prompt-hero">

        <div className="prompt-icon">
          <TerminalSquare
            size={27}
          />
        </div>

        <div>

          <div className="view-eyebrow">
            LLM INPUT
          </div>

          <h3>
            Context-aware migration prompt
          </h3>

          <p>
            This is the actual prompt generated
            by the migration pipeline for the
            language model.
          </p>

        </div>

        <button
          className="secondary-button"
          onClick={copyPrompt}
        >
          {copied ? (
            <>
              <Check size={15} />
              Copied
            </>
          ) : (
            <>
              <Copy size={15} />
              Copy prompt
            </>
          )}
        </button>

      </div>


      {prompts.length > 1 && (
        <div className="prompt-tabs">

          {prompts.map(
            (item, index) => {

              const name =
                typeof item ===
                "string"
                  ? `Prompt ${
                      index + 1
                    }`
                  : getFileName(
                      item,
                      `Prompt ${
                        index + 1
                      }`,
                    );

              return (
                <button
                  key={index}
                  className={
                    selected ===
                    index
                      ? "active"
                      : ""
                  }
                  onClick={() =>
                    setSelected(
                      index,
                    )
                  }
                >
                  <FileCode2
                    size={14}
                  />

                  {name}
                </button>
              );
            },
          )}

        </div>
      )}


      <div className="prompt-meta">

        <div>
          <span>
            Target
          </span>

          <strong>
            {file ||
              "Migration prompt"}
          </strong>
        </div>

        <div>
          <span>
            Prompt length
          </span>

          <strong>
            {promptText.length.toLocaleString()}{" "}
            characters
          </strong>
        </div>

      </div>


      <div className="prompt-container">

        <div className="prompt-header">

          <div>
            <TerminalSquare
              size={16}
            />

            Generated LLM prompt
          </div>

          <span>
            Read-only
          </span>

        </div>

        <pre className="prompt-content">
          {promptText}
        </pre>

      </div>


      <RawData data={data} />
    </div>
  );
}


/* =========================================================
   MIGRATION RESULT
   ========================================================= */

function MigrationResult({
  data,
}: {
  data: any;
}) {
  const items = Array.isArray(data)
    ? data
    : findArrays(data, [
        "results",
        "migrations",
        "files",
        "items",
      ])
        .flat();


  if (
    items.length ===
    0
  ) {
    return (
      <div className="stage-view">
        <EmptyStage
          title="Migration completed"
          description="The LLM migration stage completed, but no file-level migration records were exposed in the current response."
          icon={CheckCircle2}
        />

        <RawData data={data} />
      </div>
    );
  }


  const successful =
    items.filter(
      (item) =>
        String(
          firstDefined(
            item,
            [
              "status",
              "state",
            ],
            "",
          ),
        )
          .toLowerCase()
          .includes("success"),
    ).length;


  return (
    <div className="stage-view">

      <div className="stage-overview-grid">

        <Metric
          label="Migrated files"
          value={items.length}
          icon={FileCode2}
        />

        <Metric
          label="Successful"
          value={
            successful > 0
              ? successful
              : "Completed"
          }
          icon={CheckCircle2}
        />

        <Metric
          label="Provider"
          value="Gemini"
          icon={BrainCircuit}
        />

      </div>


      <div className="migration-results">

        {items.map(
          (
            item: any,
            index: number,
          ) => {

            const source =
              firstDefined(
                item,
                [
                  "source_code",
                  "original_code",
                  "legacy_code",
                  "before",
                ],
              );


            const migrated =
              firstDefined(
                item,
                [
                  "migrated_code",
                  "code",
                  "target_code",
                  "new_code",
                  "after",
                ],
              );


            const status =
              asString(
                firstDefined(
                  item,
                  [
                    "status",
                    "state",
                  ],
                  "completed",
                ),
                "completed",
              );


            return (
              <div
                className="migration-item"
                key={index}
              >

                <div className="migration-file">

                  <div className="migration-file-left">

                    <div className="migration-file-icon">
                      <FileCode2
                        size={16}
                      />
                    </div>

                    <div>

                      <strong>
                        {getFileName(
                          item,
                          `Migration ${
                            index + 1
                          }`,
                        )}
                      </strong>

                      <span>
                        Source → migrated
                      </span>

                    </div>

                  </div>

                  <StatusPill
                    status={status}
                  />

                </div>


                <div className="code-grid">

                  <CodePanel
                    title="Original"
                    code={
                      typeof source ===
                      "string"
                        ? source
                        : source
                        ? formatJson(
                            source,
                          )
                        : "Source code unavailable"
                    }
                  />


                  <CodePanel
                    title="Migrated"
                    code={
                      typeof migrated ===
                      "string"
                        ? migrated
                        : migrated
                        ? formatJson(
                            migrated,
                          )
                        : "Migrated code unavailable"
                    }
                    migrated
                  />

                </div>

              </div>
            );
          },
        )}

      </div>


      <RawData data={data} />
    </div>
  );
}


/* =========================================================
   CODE PANEL
   ========================================================= */

function CodePanel({
  title,
  code,
  migrated = false,
}: {
  title: string;
  code: string;
  migrated?: boolean;
}) {
  const [copied, setCopied] =
    useState(false);


  const copy = async () => {
    try {
      await navigator.clipboard.writeText(
        code,
      );

      setCopied(true);

      window.setTimeout(
        () => {
          setCopied(false);
        },
        1200,
      );
    } catch {
      // Clipboard may be unavailable.
    }
  };


  return (
    <div className="code-panel">

      <div className="code-header">

        <div>
          <Code2 size={14} />

          {title}

          {migrated && (
            <span className="modern-badge">
              Python 3
            </span>
          )}
        </div>

        <button
          className="code-copy"
          onClick={copy}
          title="Copy code"
        >
          {copied ? (
            <Check size={14} />
          ) : (
            <Copy size={14} />
          )}
        </button>

      </div>

      <pre>
        {code}
      </pre>

    </div>
  );
}


/* =========================================================
   MAIN STAGE RESULT ROUTER
   ========================================================= */

function StageResult({
  stage,
  job,
}: {
  stage: string;
  job: JobStatus;
}) {
  const result =
    job.results?.[stage];


  const status =
    job.stage_status?.[stage] ??
    "pending";


  if (
    status ===
    "pending"
  ) {
    return (
      <EmptyStage
        title="Waiting for this stage"
        description="This stage has not started yet. Select it when the pipeline reaches this step."
        icon={Clock3}
      />
    );
  }


  if (
    status ===
    "running"
  ) {
    return (
      <EmptyStage
        title="Processing"
        description="The migration pipeline is currently processing this stage."
        icon={LoaderCircle}
      />
    );
  }


  if (
    status ===
    "failed"
  ) {
    return (
      <EmptyStage
        title="Stage failed"
        description={
          job.error ??
          "An error occurred during this stage."
        }
        icon={XCircle}
      />
    );
  }


  if (
    !result
  ) {
    return (
      <EmptyStage
        title="No result available"
        description="The stage completed but did not return displayable result data."
        icon={AlertCircle}
      />
    );
  }


  switch (
    stage
  ) {

    case "scan":
      return (
        <ScanView
          data={result}
        />
      );

    case "version":
      return (
        <VersionView
          data={result}
        />
      );

    case "extraction":
      return (
        <ExtractionView
          data={result}
        />
      );

    case "embeddings":
      return (
        <EmbeddingView
          data={result}
        />
      );

    case "dependency":
      return (
        <DependencyView
          data={result}
        />
      );

    case "planning":
      return (
        <PlanningView
          data={result}
        />
      );

    case "context":
      return (
        <ContextView
          data={result}
        />
      );

    case "rag":
      return (
        <RagView
          data={result}
        />
      );

    case "prompt":
      return (
        <PromptView
          data={result}
        />
      );

    case "llm":
      return (
        <MigrationResult
          data={result}
        />
      );

    default:
      return (
        <RawData
          data={result}
        />
      );
  }
}


/* =========================================================
   APP
   ========================================================= */

function App() {

  const [theme, setTheme] = useState<"dark" | "light">(() => {
    const savedTheme = localStorage.getItem("codemigrate-theme");

    return savedTheme === "light" ? "light" : "dark";
  });

  useEffect(() => {
    localStorage.setItem("codemigrate-theme", theme);
  }, [theme]);

  const [file, setFile] =
    useState<File | null>(
      null,
    );


  const [job, setJob] =
    useState<JobStatus | null>(
      null,
    );


  const [activeStage, setActiveStage] =
    useState("scan");


  const [starting, setStarting] =
    useState(false);


  const [error, setError] =
    useState<string | null>(
      null,
    );


  /* =======================================================
     POLL BACKEND
     ======================================================= */

  useEffect(() => {

    if (
      !job?.job_id
    ) {
      return;
    }


    if (
      job.status ===
        "completed" ||
      job.status ===
        "failed"
    ) {
      return;
    }


    const interval =
      window.setInterval(
        async () => {

          try {

            const updated =
              await getJob(
                job.job_id,
              );


            setJob(
              updated,
            );


            if (
              updated.current_stage
            ) {
              setActiveStage(
                updated.current_stage,
              );
            }

          } catch (
            err
          ) {
            console.error(
              err,
            );
          }

        },
        1200,
      );


    return () => {
      window.clearInterval(
        interval,
      );
    };

  }, [
    job?.job_id,
    job?.status,
  ]);


  /* =======================================================
     FILE
     ======================================================= */

  const handleFile = (
    selectedFile:
      | File
      | undefined,
  ) => {

    if (
      !selectedFile
    ) {
      return;
    }


    if (
      !selectedFile.name
        .toLowerCase()
        .endsWith(".zip")
    ) {

      setError(
        "Please upload a ZIP repository.",
      );

      return;
    }


    setError(
      null,
    );

    setFile(
      selectedFile,
    );
  };


  /* =======================================================
     START MIGRATION
     ======================================================= */

  const handleStartMigration =
    async () => {

      if (!file) {
        return;
      }


      try {

        setStarting(
          true,
        );

        setError(
          null,
        );


        const newJob =
          await startMigration(
            file,
          );


        setJob(
          newJob,
        );

        setActiveStage(
          "scan",
        );

      } catch (
        err
      ) {

        setError(
          err instanceof
            Error
            ? err.message
            : "Failed to start migration.",
        );

      } finally {

        setStarting(
          false,
        );

      }
    };


  /* =======================================================
     RESET
     ======================================================= */

  const reset = () => {

    setFile(
      null,
    );

    setJob(
      null,
    );

    setError(
      null,
    );

    setActiveStage(
      "scan",
    );
  };


  /* =======================================================
     STAGE HELPERS
     ======================================================= */

  const getStageStatus = (
    stageId: string,
  ) => {

    return (
      job?.stage_status?.[
        stageId
      ] ??
      "pending"
    );
  };


  const selectedStage =
    stages.find(
      (stage) =>
        stage.id ===
        activeStage,
    );


  /* =======================================================
     RENDER
     ======================================================= */

  return (
    
    <div className={`app ${theme}-theme`}>

      {/* ===================================================
          SIDEBAR
          =================================================== */}

      <aside className="sidebar">

        <div className="brand">

          <div className="brand-mark">
            <Sparkles size={19} />
          </div>

          <div>

            <div className="brand-title">
              CodeMigrate
            </div>

            <div className="brand-subtitle">
              Migration Intelligence
            </div>

          </div>

        </div>


        <div className="sidebar-section">

          <div className="sidebar-label">
            PIPELINE
          </div>


          <div className="stage-list">

            {stages.map(
              (
                stage,
              ) => {

                const Icon =
                  stage.icon;

                const status =
                  getStageStatus(
                    stage.id,
                  );


                return (
                  <button
                    key={
                      stage.id
                    }
                    className={`stage-item ${
                      activeStage ===
                      stage.id
                        ? "selected"
                        : ""
                    }`}
                    onClick={() =>
                      setActiveStage(
                        stage.id,
                      )
                    }
                  >

                    <div
                      className={`stage-icon ${status}`}
                    >

                      {status ===
                      "completed" ? (
                        <CheckCircle2
                          size={
                            16
                          }
                        />
                      ) : status ===
                        "running" ? (
                        <LoaderCircle
                          size={
                            16
                          }
                          className="spin"
                        />
                      ) : status ===
                        "failed" ? (
                        <XCircle
                          size={
                            16
                          }
                        />
                      ) : (
                        <Icon
                          size={
                            16
                          }
                        />
                      )}

                    </div>


                    <div className="stage-info">

                      <div className="stage-name">
                        {
                          stage.name
                        }
                      </div>

                      <div className="stage-description">
                        {
                          stage.description
                        }
                      </div>

                    </div>

                  </button>
                );
              },
            )}

          </div>

        </div>


        <div className="sidebar-footer">

          <div className="system-status">

            <span className="status-dot" />

            {job?.status ===
            "completed"
              ? "Migration complete"
              : job?.status ===
                "failed"
              ? "Pipeline error"
              : job
              ? "Pipeline running"
              : "Pipeline ready"}

          </div>


          <div className="version">
            Review 1 • MVP
          </div>

        </div>

      </aside>


      {/* ===================================================
          MAIN
          =================================================== */}

      <main className="main">

        <header className="topbar">

          <div>

            <div className="eyebrow">
              LEGACY CODE MODERNIZATION
            </div>

            <h1>
              Migration Intelligence
            </h1>

            <p>
              Analyze, understand and migrate
              legacy repositories with
              AI-assisted intelligence.
            </p>

          </div>


          <div className="topbar-actions">

            {/* Theme Toggle */}
            <button
              className="theme-toggle"
              onClick={() =>
                setTheme(
                  theme === "dark"
                    ? "light"
                    : "dark"
                )
              }
              title={
                theme === "dark"
                  ? "Switch to light mode"
                  : "Switch to dark mode"
              }
            >

              {theme === "dark" ? (
                <Sun size={15} />
              ) : (
                <Moon size={15} />
              )}

              <span>
                {theme === "dark"
                  ? "Light"
                  : "Dark"}
              </span>

            </button>


            {/* System / Migration Status */}
            <div className="topbar-badge">

              <span className="status-dot" />

              {job?.status ===
              "completed"
                ? "Completed"
                : job
                ? "Processing"
                : "System Ready"}

            </div>

          </div>

        </header>


        {/* =================================================
            ERROR
            ================================================= */}

        {error && (
          <div className="error-banner">

            <XCircle size={18} />

            <span>
              {error}
            </span>

          </div>
        )}


        {/* =================================================
            UPLOAD SCREEN
            ================================================= */}

        {!job ? (

          <>

            <section className="upload-card">

              <div className="upload-icon">
                <Upload size={26} />
              </div>


              <div className="upload-content">

                <h2>
                  Upload a repository
                </h2>

                <p>
                  Start a migration analysis
                  by uploading your repository
                  as a ZIP file.
                </p>


                <label className="upload-button">

                  <Upload size={17} />

                  Choose ZIP Repository

                  <input
                    type="file"
                    accept=".zip"
                    onChange={(
                      event,
                    ) =>
                      handleFile(
                        event
                          .target
                          .files?.[0],
                      )
                    }
                  />

                </label>


                {file && (

                  <div className="selected-file">

                    <FolderGit2
                      size={17}
                    />

                    <div>

                      <strong>
                        {
                          file.name
                        }
                      </strong>

                      <span>
                        {(
                          file.size /
                          1024 /
                          1024
                        ).toFixed(
                          2,
                        )}{" "}
                        MB
                      </span>

                    </div>

                  </div>

                )}

              </div>

            </section>


            <section className="section">

              <div className="section-header">

                <div>

                  <div className="section-eyebrow">
                    WORKFLOW
                  </div>

                  <h2>
                    Migration Pipeline
                  </h2>

                </div>


                <span className="stage-count">
                  {
                    stages.length
                  }{" "}
                  stages
                </span>

              </div>


              <div className="pipeline-preview">

                {stages.map(
                  (
                    stage,
                    index,
                  ) => {

                    const Icon =
                      stage.icon;


                    return (
                      <div
                        className="pipeline-node"
                        key={
                          stage.id
                        }
                      >

                        <div className="pipeline-icon">
                          <Icon
                            size={
                              18
                            }
                          />
                        </div>

                        <div>

                          <strong>
                            {
                              stage.name
                            }
                          </strong>

                          <span>
                            {
                              stage.description
                            }
                          </span>

                        </div>


                        {index <
                          stages.length -
                            1 && (
                          <ArrowRight
                            className="pipeline-arrow"
                            size={
                              16
                            }
                          />
                        )}

                      </div>
                    );
                  },
                )}

              </div>

            </section>


            <section className="architecture-grid">

              <div className="info-card">

                <BrainCircuit
                  size={
                    21
                  }
                />

                <h3>
                  AI Migration
                </h3>

                <p>
                  Gemini generates the
                  migrated source code using
                  repository context and
                  retrieved migration examples.
                </p>

              </div>


              <div className="info-card">

                <Database
                  size={
                    21
                  }
                />

                <h3>
                  Semantic Intelligence
                </h3>

                <p>
                  CodeBERT embeddings and RAG
                  connect migration with
                  historical code transformations.
                </p>

              </div>


              <div className="info-card">

                <GitBranch
                  size={
                    21
                  }
                />

                <h3>
                  Repository Awareness
                </h3>

                <p>
                  Dependency relationships and
                  migration planning provide
                  repository-level context.
                </p>

              </div>

            </section>


            <button
              className="start-button"
              disabled={
                !file ||
                starting
              }
              onClick={
                handleStartMigration
              }
            >

              {starting ? (
                <>
                  <LoaderCircle
                    size={
                      18
                    }
                    className="spin"
                  />

                  Uploading...
                </>
              ) : (
                <>
                  Start Migration Analysis

                  <ArrowRight
                    size={
                      18
                    }
                  />
                </>
              )}

            </button>

          </>

        ) : (

          /* =================================================
             RUNNING / RESULT SCREEN
             ================================================= */

          <>

            <section className="dashboard-header">

              <div>

                <div className="section-eyebrow">
                  ACTIVE MIGRATION
                </div>

                <h2>
                  {
                    job.repository_name
                  }
                </h2>

                <p>
                  {job.status ===
                  "completed"
                    ? "Migration pipeline completed successfully."
                    : job.status ===
                      "failed"
                    ? "The migration pipeline encountered an error."
                    : `Running ${
                        selectedStage?.name ??
                        "pipeline"
                      }...`}
                </p>

              </div>


              <div
                className={`running-badge ${
                  job.status ===
                  "completed"
                    ? "complete"
                    : job.status ===
                      "failed"
                    ? "failed"
                    : ""
                }`}
              >

                {job.status ===
                "completed" ? (
                  <>
                    <CheckCircle2
                      size={
                        15
                      }
                    />

                    Completed
                  </>
                ) : job.status ===
                  "failed" ? (
                  <>
                    <XCircle
                      size={
                        15
                      }
                    />

                    Failed
                  </>
                ) : (
                  <>
                    <span className="pulse-dot" />

                    Processing
                  </>
                )}

              </div>

            </section>


            {/* STATS */}

            <section className="stats-grid">

              <div className="stat-card">

                <span>
                  FILES
                </span>

                <strong>
                  {
                    job.statistics
                      ?.files ??
                    "—"
                  }
                </strong>

                <small>
                  Repository files
                </small>

              </div>


              <div className="stat-card">

                <span>
                  MIGRATION CANDIDATES
                </span>

                <strong>
                  {
                    job.statistics
                      ?.candidates ??
                    "—"
                  }
                </strong>

                <small>
                  Selected for migration
                </small>

              </div>


              <div className="stat-card">

                <span>
                  FUNCTIONS
                </span>

                <strong>
                  {
                    job.statistics
                      ?.functions ??
                    "—"
                  }
                </strong>

                <small>
                  Extracted features
                </small>

              </div>


              <div className="stat-card">

                <span>
                  RAG QUERIES
                </span>

                <strong>
                  {
                    job.statistics
                      ?.rag_queries ??
                    "—"
                  }
                </strong>

                <small>
                  Knowledge retrieval
                </small>

              </div>

            </section>


            {/* RESULT */}

            <section className="result-card">

              <div className="result-header">

                <div className="result-title">

                  {selectedStage && (
                    <>
                      <div className="result-icon">

                        {(() => {

                          const Icon =
                            selectedStage.icon;

                          return (
                            <Icon
                              size={
                                19
                              }
                            />
                          );

                        })()}

                      </div>


                      <div>

                        <h2>
                          {
                            selectedStage.name
                          }
                        </h2>

                        <p>
                          {
                            selectedStage.description
                          }
                        </p>

                      </div>
                    </>
                  )}

                </div>


                <div className="processing">

                  {getStageStatus(
                    activeStage,
                  ) ===
                  "completed" ? (
                    <>
                      <CheckCircle2
                        size={
                          16
                        }
                      />

                      Completed
                    </>
                  ) : getStageStatus(
                      activeStage,
                    ) ===
                    "failed" ? (
                    <>
                      <XCircle
                        size={
                          16
                        }
                      />

                      Failed
                    </>
                  ) : getStageStatus(
                      activeStage,
                    ) ===
                    "running" ? (
                    <>
                      <LoaderCircle
                        size={
                          16
                        }
                        className="spin"
                      />

                      Processing
                    </>
                  ) : (
                    <>
                      <Clock3
                        size={
                          16
                        }
                      />

                      Pending
                    </>
                  )}

                </div>

              </div>


              <StageResult
                stage={
                  activeStage
                }
                job={job}
              />

            </section>


            {/* LOGS */}

            {job.logs &&
              job.logs.length >
                0 && (

                <section className="logs-card">

                  <div className="logs-header">
                    Pipeline Activity
                  </div>

                  <div className="logs">

                    {job.logs
                      .slice(
                        -12,
                      )
                      .map(
                        (
                          log,
                          index,
                        ) => (
                          <div
                            key={
                              index
                            }
                          >
                            {
                              log
                            }
                          </div>
                        ),
                      )}

                  </div>

                </section>

              )}


            {/* FUTURE MODULES */}

            <section className="future-section">

              <div className="section-eyebrow">
                NEXT MODULES
              </div>

              <h2>
                Verification & Intelligence
              </h2>

              <div className="future-grid">

                {futureModules.map(
                  (
                    item,
                  ) => (

                    <div
                      className="future-card"
                      key={
                        item
                      }
                    >

                      <Clock3
                        size={
                          16
                        }
                      />

                      <span>
                        {
                          item
                        }
                      </span>

                      <small>
                        Coming next
                      </small>

                    </div>

                  ),
                )}

              </div>

            </section>


            <button
              className="reset-button"
              onClick={
                reset
              }
            >
              Start another repository
            </button>

          </>

        )}

      </main>

    </div>
  );
}


export default App;