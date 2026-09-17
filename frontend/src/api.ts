export type JobStatus = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  repository_name: string;
  original_filename?: string;
  current_stage?: string;

  stage_status: Record<
    string,
    "pending" | "running" | "completed" | "failed"
  >;

  statistics?: {
    files?: number;
    candidates?: number;
    functions?: number;
    rag_queries?: number;
  };

  results?: Record<string, any>;

  logs?: string[];

  error?: string | null;
};

const API_BASE = "http://localhost:8000";

export async function startMigration(
  file: File,
): Promise<JobStatus> {
  const formData = new FormData();

  formData.append("file", file);

  const response = await fetch(
    `${API_BASE}/api/migrate`,
    {
      method: "POST",
      body: formData,
    },
  );

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || "Failed to start migration");
  }

  return response.json();
}

export async function getJob(
  jobId: string,
): Promise<JobStatus> {
  const response = await fetch(
    `${API_BASE}/api/jobs/${jobId}`,
  );

  if (!response.ok) {
    throw new Error("Unable to retrieve migration job");
  }

  return response.json();
}