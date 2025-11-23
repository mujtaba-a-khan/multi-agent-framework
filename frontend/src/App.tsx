import { useState } from "react";
import { startRun, fetchProgress, sampleSummary, Summary } from "./api";

const formatPct = (v: number | undefined) => (typeof v === "number" ? `${(v * 100).toFixed(1)}%` : "—");

export default function App() {
  const [configPath, setConfigPath] = useState("configs/baseline_openai_multi_red_ensemble.yml");
  const [apiBase, setApiBase] = useState<string>(import.meta.env.VITE_API_URL || "http://localhost:8000");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ processed: number; total: number | null }>({ processed: 0, total: null });

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    setProgress({ processed: 0, total: null });
    try {
      const jobId = await startRun(configPath, apiBase);
      const poll = async () => {
        try {
          const status = await fetchProgress(jobId, apiBase);
          if (status.total) {
            setProgress({ processed: status.processed ?? 0, total: status.total });
          }
          if (status.status === "done" && status.summary) {
            setSummary(status.summary);
            setLoading(false);
            return;
          }
          if (status.status === "error") {
            throw new Error(status.error || "Run failed");
          }
          setTimeout(poll, 500);
        } catch (err) {
          setError((err as Error).message);
          setSummary(sampleSummary);
          setLoading(false);
        }
      };
      poll();
    } catch (err) {
      setError((err as Error).message);
      setSummary(sampleSummary);
      setLoading(false);
    }
  };

  return (
    <div style={{ fontFamily: "Inter, sans-serif", padding: "24px", maxWidth: "960px", margin: "0 auto" }}>
      <h1>MADLab Dashboard</h1>
      <div style={{ display: "flex", gap: "12px", marginBottom: "16px" }}>
        <input
          style={{ flex: 1, padding: "8px 12px" }}
          value={configPath}
          onChange={(e) => setConfigPath(e.target.value)}
          placeholder="Config path"
        />
        <input
          style={{ flex: 1, padding: "8px 12px" }}
          value={apiBase}
          onChange={(e) => setApiBase(e.target.value)}
          placeholder="API base URL"
        />
        <button onClick={handleRun} disabled={loading} style={{ padding: "8px 16px" }}>
          {loading ? "Running..." : "Run"}
        </button>
      </div>
      {loading && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-start",
            gap: 8,
            marginBottom: 12,
            color: "#444",
            fontSize: 14,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div className="spinner" style={{ width: 16, height: 16, border: "2px solid #ccc", borderTopColor: "#555", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
            <span>Running... this can take a bit.</span>
          </div>
          <div style={{ position: "relative", width: "100%", maxWidth: 400, height: 6, background: "#eee", borderRadius: 4, overflow: "hidden" }}>
            <div
              style={{
                position: "absolute",
                left: progress.total ? `${Math.max(0, Math.min(100, (progress.processed / progress.total) * 100 - 40))}%` : "-40%",
                top: 0,
                height: "100%",
                width: "40%",
                background: "linear-gradient(90deg, #c8d6ff, #6c8bff)",
                borderRadius: 4,
                animation: progress.total ? "none" : "indeterminate 1.2s ease-in-out infinite",
              }}
            />
          </div>
          {progress.total ? (
            <div style={{ fontSize: 12, color: "#666" }}>
              {progress.processed} / {progress.total} ({((progress.processed / progress.total) * 100).toFixed(0)}%)
            </div>
          ) : null}
        </div>
      )}
      {error && <div style={{ color: "red", marginBottom: "12px" }}>{error} (showing sample data)</div>}
      {summary && (
        <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
          <h2>Summary</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
            <Stat label="ASR" value={formatPct(summary.ASR)} />
            <Stat label="FPR" value={formatPct(summary.FPR)} />
            <Stat label="Harmful" value={summary.n_harmful.toString()} />
            <Stat label="Harmless" value={summary.n_harmless.toString()} />
            <Stat label="Latency (total)" value={`${summary.latency_ms_avg?.total ?? "—"} ms`} />
            <Stat label="Latency (blue)" value={`${summary.latency_ms_avg?.blue ?? "—"} ms`} />
          </div>
          {summary.counts && (
            <div style={{ marginTop: 12 }}>
              <h3>Counts</h3>
              <ul>
                <li>TP_block: {summary.counts.TP_block ?? "—"}</li>
                <li>FN_allow: {summary.counts.FN_allow ?? "—"}</li>
                <li>TN_allow: {summary.counts.TN_allow ?? "—"}</li>
                <li>FP_block: {summary.counts.FP_block ?? "—"}</li>
              </ul>
            </div>
          )}
        </div>
      )}
      {!summary && !loading && <p>Enter a config path and run to see results. If API is unavailable, sample data will display.</p>}
      <style>
        {`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes indeterminate {
          0% { left: -40%; width: 40%; }
          50% { left: 20%; width: 60%; }
          100% { left: 100%; width: 40%; }
        }
        `}
      </style>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ padding: 12, background: "#f8f8f8", borderRadius: 6 }}>
      <div style={{ fontSize: 12, color: "#666" }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 600 }}>{value}</div>
    </div>
  );
}
