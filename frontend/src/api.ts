const DEFAULT_API = import.meta.env.VITE_API_URL || "http://localhost:8000";

export type Summary = {
  ASR: number;
  FPR: number;
  n_harmful: number;
  n_harmless: number;
  counts?: Record<string, number>;
  latency_ms_avg?: Record<string, number | null>;
  sample_output?: SampleOutput;
  run_info?: RunInfo;
};

export type JobStatus = {
  status: "running" | "done" | "error" | "stopped";
  processed: number | null;
  total: number | null;
  summary: Summary | null;
  error: string | null;
};

export type SampleOutput = {
  prompt?: string;
  target_output?: string;
  blue_decision?: string;
  model?: string;
  is_harmful?: boolean;
  allowed?: boolean;
  timing_ms?: number | null;
  blocked_reason?: string;
};

export type RunInfo = {
  run_started_at?: string;
  source?: string;
  run_dir?: string;
};

type StartPayload = {
  config: string;
  prompt?: string;
  model_name?: string;
  upload_name?: string;
  upload_content?: string;
};

export async function startRun(
  configPath: string,
  apiBase = DEFAULT_API,
  extra?: { prompt?: string; model_name?: string; upload_name?: string; upload_content?: string },
): Promise<string> {
  const res = await fetch(`${apiBase}/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      config: configPath,
      prompt: extra?.prompt,
      model_name: extra?.model_name,
      upload_name: extra?.upload_name,
      upload_content: extra?.upload_content,
    } satisfies StartPayload),
  });
  if (!res.ok) {
    throw new Error(`Start failed: ${res.status}`);
  }
  const data = await res.json();
  return data.job_id as string;
}

export async function fetchProgress(jobId: string, apiBase = DEFAULT_API): Promise<JobStatus> {
  const res = await fetch(`${apiBase}/progress/${jobId}`);
  if (!res.ok) {
    throw new Error(`Progress fetch failed: ${res.status}`);
  }
  return (await res.json()) as JobStatus;
}

export async function stopRun(jobId: string, apiBase = DEFAULT_API): Promise<void> {
  const res = await fetch(`${apiBase}/stop/${jobId}`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`Stop failed: ${res.status}`);
  }
}

// Fallback sample data for offline use
export const sampleSummary: Summary = {
  ASR: 0.4,
  FPR: 0.02,
  n_harmful: 50,
  n_harmless: 50,
  counts: { TP_block: 48, FN_allow: 2, TN_allow: 49, FP_block: 1 },
  latency_ms_avg: { total: 3200, target: 3000, blue: 200 },
};
