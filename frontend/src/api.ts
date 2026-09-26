export type JobStatus = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed" | string;
  repository_name: string;
  original_filename?: string;
  current_stage?: string;
  stage_status?: Record<string, string>;
  statistics?: Record<string, any>;
  results?: Record<string, any>;
  logs?: string[];
  error?: string | null;
  progress?: Record<string, number>;
  stage_titles?: Record<string,string>;
};

const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");

export async function startMigration(file: File): Promise<JobStatus> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`${API_BASE}/api/migrate`, { method:"POST", body });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Migration request failed (${response.status})`);
  }
  return response.json();
}

export async function getJob(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${API_BASE}/api/jobs/${encodeURIComponent(jobId)}`);
  if (!response.ok) throw new Error(`Could not load job (${response.status})`);
  return response.json();
}

export async function downloadMigratedRepo(jobId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/jobs/${encodeURIComponent(jobId)}/download`);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Download failed (${response.status})`);
  }
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/i);
  const filename = match?.[1] || "codemigrate_migrated_repository.zip";
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
