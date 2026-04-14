"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import api, { toUserFacingError } from "@/lib/api";
import { useBeaconConfig } from "@/lib/beaconConfig";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

/* ── Icons ─────────────────────────────────────────────────────── */
function IconArrowLeft({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="19" y1="12" x2="5" y2="12" />
      <polyline points="12 19 5 12 12 5" />
    </svg>
  );
}
function IconScan({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 7V5a2 2 0 0 1 2-2h2" />
      <path d="M17 3h2a2 2 0 0 1 2 2v2" />
      <path d="M21 17v2a2 2 0 0 1-2 2h-2" />
      <path d="M7 21H5a2 2 0 0 1-2-2v-2" />
      <line x1="7" y1="12" x2="17" y2="12" />
    </svg>
  );
}
function IconChevron({ className, up }: { className?: string; up?: boolean }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {up ? (
        <polyline points="18 15 12 9 6 15" />
      ) : (
        <polyline points="6 9 12 15 18 9" />
      )}
    </svg>
  );
}
function IconSparkle({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2l2.12 6.88L21 12l-6.88 2.12L12 21l-2.12-6.88L3 12l6.88-2.12z" />
    </svg>
  );
}
function IconCode({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="16 18 22 12 16 6" />
      <polyline points="8 6 2 12 8 18" />
    </svg>
  );
}

/* ── Constants ─────────────────────────────────────────────────── */
const SEVERITY_COLORS: Record<string, string> = {
  critical: "#E84855",
  serious: "#E87D3E",
  moderate: "#E8A838",
  minor: "#3BD16F",
};

const TOOLTIP_STYLE = {
  background: "var(--beacon-card-bg)",
  border: "1px solid var(--beacon-border)",
  borderRadius: 4,
  color: "var(--beacon-text)",
  fontSize: 12,
  fontWeight: 600,
  boxShadow: "var(--beacon-card-shadow)",
};

/* ── Main Component ────────────────────────────────────────────── */
export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { aiEnabled } = useBeaconConfig();
  const [project, setProject] = useState<any>(null);
  const [scans, setScans] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<{
    message: string;
    retryable: boolean;
  } | null>(null);
  const [tab, setTab] = useState<"overview" | "issues" | "priority">(
    "overview",
  );
  const [scanning, setScanning] = useState(false);
  const [scanStatus, setScanStatus] = useState<
    "idle" | "scanning" | "completed" | "failed"
  >("idle");
  const [scanMode, setScanMode] = useState("fast");
  const [scanModeTouched, setScanModeTouched] = useState(false);
  const [expandedIssue, setExpandedIssue] = useState<string | null>(null);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const pollRef = useRef<NodeJS.Timeout | null>(null);
  const [pollErrorCount, setPollErrorCount] = useState(0);

  // Deduplicate scans: hide scans that are consecutive matches
  const uniqueScans = (scans || []).reduce((acc: any[], current: any) => {
    const prev = acc[acc.length - 1];
    const isDup =
      prev &&
      current.status === "completed" &&
      prev.status === "completed" &&
      current.score === prev.score &&
      current.total_issues === prev.total_issues &&
      current.scan_mode === prev.scan_mode;
    if (!isDup) {
      acc.push(current);
    }
    return acc;
  }, []);

  const latestScan: any =
    uniqueScans.find((s: any) => s.status === "completed") || null;
  const latestFailedScan: any =
    uniqueScans.find((s: any) => s.status === "failed") || null;

  // Load project + scans
  const loadData = useCallback(
    async (scanOutcome: "completed" | "failed" | null = null) => {
      try {
        const [proj, scanList] = await Promise.all([
          api.getProject(projectId),
          api.getScans(projectId),
        ]);
        setProject(proj);
        setScans(scanList);
        setApiError(null);

        if (scanOutcome) {
          setScanStatus(scanOutcome);
          setTimeout(() => setScanStatus("idle"), 5000);
        }
      } catch (e) {
        console.error(e);
        setApiError(toUserFacingError(e));
      } finally {
        setLoading(false);
      }
    },
    [projectId],
  );

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Keep scan mode selector aligned with latest scan mode until user changes it.
  useEffect(() => {
    if (scanModeTouched) {
      return;
    }

    const recentMode = uniqueScans.find(
      (scan) =>
        scan &&
        typeof scan.scan_mode === "string" &&
        ["fast", "deep", "max"].includes(scan.scan_mode),
    )?.scan_mode;

    if (recentMode && recentMode !== scanMode) {
      setScanMode(recentMode);
    }
  }, [scanModeTouched, scanMode, uniqueScans]);

  // Polling for active scans
  useEffect(() => {
    const activeScan = scans.find((s) => s.status === "scanning");
    if (activeScan) {
      setScanning(true);
      setScanStatus("scanning");
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const progress = await api.getScanProgress(projectId, activeScan.id);
          setPollErrorCount(0); // reset on success
          if (progress.status === "completed" || progress.status === "failed") {
            setScanning(false);
            if (pollRef.current) clearInterval(pollRef.current);
            await loadData(
              progress.status === "failed" ? "failed" : "completed",
            );
          }
        } catch (err) {
          console.error("Polling error:", err);
          setApiError(toUserFacingError(err));
          // If we fail 10 times in a row, auto-stop to prevent hanging
          setPollErrorCount((prev) => {
            const next = prev + 1;
            if (next >= 10) {
              setScanning(false);
              setScanStatus("failed");
              if (pollRef.current) clearInterval(pollRef.current);
            }
            return next;
          });
        }
      }, 2000);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [scans, projectId, loadData]);

  // Start a new scan
  async function startScan() {
    setScanning(true);
    setScanStatus("scanning");
    try {
      await api.startScan({ project_id: projectId, scan_mode: scanMode });

      // Fetch latest state aggressively
      const [proj, scanList] = await Promise.all([
        api.getProject(projectId),
        api.getScans(projectId),
      ]);
      setProject(proj);
      setScans(scanList);
      setApiError(null);

      const hasActive = scanList.some((s: any) => s.status === "scanning");
      if (!hasActive) {
        setScanning(false);
        const latestResult = scanList[0];
        const outcome =
          latestResult?.status === "failed" ? "failed" : "completed";
        setScanStatus(outcome);
        setTimeout(() => setScanStatus("idle"), 5000);
      }
    } catch (e) {
      console.error(e);
      setApiError(toUserFacingError(e));
      setScanning(false);
      setScanStatus("failed");
    }
  }

  const issues: any[] = latestScan?.issues || [];
  const score = latestScan?.score ?? null;
  const issueTypesCount = Number(
    latestScan?.issue_types_count || issues.length || 0,
  );
  const failingElementsCount = Number(
    latestScan?.failing_elements_count || latestScan?.total_issues || 0,
  );
  const pagesScanned = Number(latestScan?.pages_scanned || 1);
  const severityCounts = {
    critical:
      latestScan?.critical_issues ||
      issues.filter((i: any) => i.severity === "critical").length,
    serious:
      latestScan?.serious_issues ||
      issues.filter((i: any) => i.severity === "serious").length,
    moderate:
      latestScan?.moderate_issues ||
      issues.filter((i: any) => i.severity === "moderate").length,
    minor:
      latestScan?.minor_issues ||
      issues.filter((i: any) => i.severity === "minor").length,
  };

  const trust = latestScan?.trust || {};
  const trustWarnings: string[] = Array.isArray(trust.calibration_warnings)
    ? trust.calibration_warnings
    : [];
  const lowTrustRules: string[] = Array.isArray(trust.low_trust_rules_present)
    ? trust.low_trust_rules_present
    : [];
  const enginesCoverage =
    trust.engines_coverage && typeof trust.engines_coverage === "object"
      ? trust.engines_coverage
      : {};
  const confidenceAvg =
    typeof trust.confidence_avg === "number"
      ? trust.confidence_avg
      : latestScan?.issues?.length
        ? latestScan.issues.reduce(
            (sum: number, issue: any) => sum + (Number(issue?.confidence) || 0),
            0,
          ) / latestScan.issues.length
        : 0;
  const suppressionRate =
    typeof trust.suppression_rate === "number" ? trust.suppression_rate : 0;
  const trustDataQuality =
    typeof trust.data_quality === "string" && trust.data_quality
      ? trust.data_quality
      : "unknown";
  const trustCompleteness =
    typeof trust.audit_completeness === "string" && trust.audit_completeness
      ? trust.audit_completeness
      : latestScan?.degraded_mode
        ? "partial"
        : "full";
  const trustIntegrityCaps: any[] = Array.isArray(
    trust.score_integrity?.caps_applied,
  )
    ? trust.score_integrity.caps_applied
    : [];

  const pieData = Object.entries(severityCounts)
    .filter(([, v]) => v > 0)
    .map(([sev, count]) => ({
      name: sev,
      value: count,
      fill: SEVERITY_COLORS[sev],
    }));

  // Score history from UNIQUE completed scans prevents chart spam
  const scoreHistory = uniqueScans
    .filter((s: any) => s.status === "completed" && s.score != null)
    .reverse()
    .map((s: any, i: number) => ({
      scan: `Scan ${i + 1}`,
      score: Math.round(s.score),
      date: s.completed_at ? new Date(s.completed_at).toLocaleDateString() : "",
    }));

  function scoreColor(s: number | null): string {
    if (s === null) return "var(--beacon-text-muted)";
    if (s >= 80) return "var(--beacon-success)";
    if (s >= 50) return "var(--beacon-warning)";
    return "var(--beacon-error)";
  }

  if (loading) {
    return (
      <div className="flex justify-center py-32">
        <div className="w-10 h-10 border-4 border-[var(--beacon-primary)] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="glass-card p-20 text-center max-w-2xl mx-auto mt-20">
        <h2 className="text-2xl font-extrabold mb-4">Project not found</h2>
        <Link href="/dashboard" className="btn-primary inline-block">
          ← Back to Projects
        </Link>
      </div>
    );
  }

  const TABS = [
    { key: "overview" as const, label: "Overview" },
    { key: "issues" as const, label: "Issues", count: issueTypesCount },
    { key: "priority" as const, label: "Fix Priority" },
  ];

  return (
    <div className="animate-fade-in w-full pb-20">
      {/* ── Header ────────────────────────────────────────────── */}
      <div className="mb-8 pb-6 border-b border-[var(--beacon-border)]/60">
        <Link
          href="/dashboard"
          className="text-xs text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] transition-colors mb-4 flex items-center gap-2 font-bold uppercase tracking-[0.15em]"
        >
          <IconArrowLeft className="w-4 h-4" /> Back to Projects
        </Link>
        <div className="flex items-start justify-between sm:items-center flex-col sm:flex-row gap-4">
          <div>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight uppercase">
              {project.name}
            </h1>
            <p className="text-sm font-medium text-[var(--beacon-text-muted)] mt-1 ml-1">
              {project.url}
            </p>
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto">
            <div className="flex flex-col gap-1">
              <select
                value={scanMode}
                onChange={(e) => {
                  setScanModeTouched(true);
                  setScanMode(e.target.value);
                }}
                disabled={scanning}
                className="beacon-input text-xs font-bold uppercase tracking-widest cursor-pointer disabled:opacity-50"
              >
                <option value="fast">Fast Scan</option>
                <option value="deep">Deep Scan</option>
                <option value="max">Max Scan</option>
              </select>
              <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-[var(--beacon-text-muted)]">
                {scanMode === "fast"
                  ? "Fast: entry-page audit"
                  : "Deep/Max: multi-page domain audit"}
              </p>
            </div>
            <div className="flex items-center gap-2 w-full sm:w-auto">
              <button
                onClick={startScan}
                disabled={scanning}
                className={`btn-primary py-3 px-5 sm:flex-1 shrink-0 transition-all ${scanning ? "bg-[var(--beacon-primary)]/40 border-[var(--beacon-primary)]/20 cursor-not-allowed" : ""}`}
              >
                {scanning ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-inherit border-t-transparent rounded-full animate-spin" />
                    <span>Scanning Hub...</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <IconScan className="w-[18px] h-[18px]" />{" "}
                    <span>Initiate Scan</span>
                  </div>
                )}
              </button>

              {scanning && (
                <button
                  onClick={() => {
                    setScanning(false);
                    setScanStatus("idle");
                    if (pollRef.current) clearInterval(pollRef.current);
                  }}
                  className="px-3 py-3 border-2 border-[var(--beacon-error)] text-[var(--beacon-error)] rounded-lg hover:bg-[var(--beacon-error)]/10 transition-colors uppercase text-[10px] font-black tracking-widest shadow-[3px_3px_0px_#000] active:shadow-none active:translate-x-0.5 active:translate-y-0.5"
                  title="Force Stop Scan"
                >
                  STOP
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {apiError && (
        <div className="glass-card p-4 mb-6 border-l-[6px] border-l-[var(--beacon-error)]">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <p className="text-sm font-semibold text-[var(--beacon-text)]">
              {apiError.message}
            </p>
            {apiError.retryable && (
              <button
                onClick={() => void loadData()}
                className="btn-secondary text-xs"
              >
                Retry
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── Notifications ───────────────────────────────────── */}
      {scanStatus === "completed" && (
        <div className="fixed bottom-8 right-8 z-50 animate-slide-in">
          <div className="bg-[var(--beacon-success)] text-black py-4 px-5 rounded-lg font-bold flex items-center justify-between gap-6 shadow-[6px_6px_0px_#000] border-[3px] border-black">
            <div className="flex items-center gap-3">
              <span className="text-2xl">✅</span>
              <span className="tracking-wide">
                Scan successful! Results synchronized.
              </span>
            </div>
            <button
              onClick={() => setScanStatus("idle")}
              className="text-xs uppercase tracking-tighter opacity-80 hover:opacity-100 font-extrabold pb-0.5 border-b-2 border-black/30 hover:border-black transition-colors"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {scanStatus === "failed" && (
        <div className="fixed bottom-8 right-8 z-50 animate-slide-in">
          <div className="bg-[var(--beacon-error)] text-white py-4 px-5 rounded-lg font-bold flex items-center justify-between gap-6 shadow-[6px_6px_0px_#000] border-[3px] border-black max-w-[680px]">
            <div className="flex items-center gap-3">
              <span className="text-2xl">⚠️</span>
              <span className="tracking-wide">
                {latestFailedScan?.summary ||
                  "Scan failed. Please verify the target URL and retry."}
              </span>
            </div>
            <button
              onClick={() => setScanStatus("idle")}
              className="text-xs uppercase tracking-tighter opacity-80 hover:opacity-100 font-extrabold pb-0.5 border-b-2 border-white/40 hover:border-white transition-colors"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* ── Score Strip (Neo-brutalism layout) ────────────────── */}
      {latestScan && (
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4 mb-8">
          {[
            {
              label: "Accessibility Score",
              value: score !== null ? Math.round(score) : "—",
              color: scoreColor(score),
              suffix: "/100",
            },
            {
              label: "Failing Elements",
              value: failingElementsCount,
              color: "var(--beacon-warning)",
              suffix: "",
            },
            {
              label: "Issue Types",
              value: issueTypesCount,
              color: "var(--beacon-text)",
              suffix: "",
            },
            {
              label: "Pages Scanned",
              value: pagesScanned,
              color: "var(--beacon-primary)",
              suffix: "",
            },
            {
              label: "Scan Time",
              value: `${(latestScan.scan_time_seconds || 0).toFixed(1)}s`,
              color: "var(--beacon-text)",
              suffix: "",
            },
            {
              label: "Engines Used",
              value: (latestScan.engines_used || []).length,
              color: "var(--beacon-primary)",
              suffix: "",
            },
          ].map(({ label, value, color, suffix }) => (
            <div
              key={label}
              className="stat-card p-6 flex flex-col items-center justify-center relative overflow-hidden group"
            >
              <p
                className="text-4xl md:text-5xl font-cabinet font-extrabold tabular-nums tracking-tighter"
                style={{ color }}
              >
                {value}
                <span className="text-lg md:text-xl font-bold text-[var(--beacon-text-muted)] opacity-50">
                  {suffix}
                </span>
              </p>
              <p className="text-xs font-bold text-[var(--beacon-text-muted)] mt-2 uppercase tracking-[0.1em]">
                {label}
              </p>
              {label === "Engines Used" && latestScan.engines_used && (
                <div className="flex gap-1.5 mt-3">
                  {latestScan.engines_used.map((e: string) => (
                    <div
                      key={e}
                      className="w-1.5 h-1.5 rounded-full bg-[var(--beacon-primary)] shadow-[0_0_8px_var(--beacon-primary)]"
                      title={e}
                    />
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── Tabs ──────────────────────────────────────────────── */}
      <div className="flex gap-1 bg-[var(--beacon-surface)] border border-[var(--beacon-border)] p-1.5 rounded-lg w-full overflow-x-auto mb-8 shadow-sm">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-5 py-2.5 text-xs font-bold uppercase tracking-[0.1em] rounded-md transition-all whitespace-nowrap flex items-center gap-2 ${
              tab === t.key
                ? "bg-[var(--beacon-primary)] text-black shadow-[2px_2px_0px_#000]"
                : "text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] hover:bg-[var(--beacon-surface)]"
            }`}
          >
            {t.label}
            {t.count !== undefined && (
              <span
                className={`px-1.5 py-0.5 text-[10px] rounded ${tab === t.key ? "bg-black/10" : "bg-[var(--beacon-border)]/50"}`}
              >
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── No Scan State ─────────────────────────────────────── */}
      {!latestScan && !scanning && latestFailedScan && (
        <div className="glass-card p-24 text-center border-l-[6px] border-l-[var(--beacon-error)]">
          <p className="text-5xl mb-4">⚠️</p>
          <h2 className="text-3xl font-extrabold mb-3">Latest scan failed</h2>
          <p className="text-base text-[var(--beacon-text-muted)] font-medium mb-3 max-w-3xl mx-auto">
            {latestFailedScan.summary || "The scan could not complete."}
          </p>
          <p className="text-sm text-[var(--beacon-text-muted)] font-medium max-w-3xl mx-auto">
            Verify the site is reachable and allows automated requests, then run
            a new scan.
          </p>
        </div>
      )}

      {!latestScan && !scanning && !latestFailedScan && (
        <div className="glass-card p-24 text-center">
          <IconScan className="w-16 h-16 mx-auto mb-6 text-[var(--beacon-text-muted)]" />
          <h2 className="text-3xl font-extrabold mb-3">No scan results</h2>
          <p className="text-base text-[var(--beacon-text-muted)] font-medium mb-8 max-w-md mx-auto">
            Trigger your first scan using the top right controls to map the
            accessibility domain.
          </p>
        </div>
      )}

      {/* Scanning State */}
      {scanning && !latestScan && (
        <div className="glass-card p-24 text-center">
          <div className="w-16 h-16 mx-auto mb-6 border-4 border-[var(--beacon-primary)] border-t-transparent rounded-full animate-spin" />
          <h2 className="text-3xl font-extrabold mb-3">Scanning in progress</h2>
          <p className="text-base font-medium text-[var(--beacon-text-muted)]">
            Analyzing document routes, assessing WCAG 2.2 rules, and running AI
            confidence checks on{" "}
            <span className="font-bold text-[var(--beacon-primary)]">
              {project.url}
            </span>
            .
          </p>
        </div>
      )}

      {/* ── OVERVIEW TAB ──────────────────────────────────────── */}
      {tab === "overview" && latestScan && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Severity Breakdown */}
            <div className="glass-card p-8 flex flex-col">
              <h3 className="text-sm font-bold mb-8 uppercase tracking-[0.15em] text-[var(--beacon-text-muted)]">
                Issue Severity Distribution
              </h3>
              {pieData.length > 0 ? (
                <div className="flex flex-col sm:flex-row items-center justify-center gap-10 flex-1">
                  <div className="w-[200px] h-[200px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={pieData}
                          cx="50%"
                          cy="50%"
                          innerRadius={65}
                          outerRadius={95}
                          paddingAngle={4}
                          dataKey="value"
                          stroke="var(--beacon-card-bg)"
                          strokeWidth={2}
                        >
                          {pieData.map((entry, i) => (
                            <Cell key={i} fill={entry.fill} />
                          ))}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="space-y-3.5">
                    {Object.entries(severityCounts).map(([sev, count]) => (
                      <div key={sev} className="flex items-center gap-3">
                        <div
                          className="w-4 h-4 rounded-sm shadow-sm"
                          style={{ background: SEVERITY_COLORS[sev] }}
                        />
                        <span className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--beacon-text)] w-[88px]">
                          {sev}
                        </span>
                        <span className="text-lg font-extrabold tabular-nums bg-[var(--beacon-surface)] border border-[var(--beacon-border)] px-3 py-0.5 rounded shadow-[1px_1px_0px_var(--beacon-border)]">
                          {count}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center">
                  <p className="text-5xl mb-4">🎉</p>
                  <p className="text-[var(--beacon-text-muted)] text-base font-bold text-center">
                    Perfect score! No issues identified.
                  </p>
                </div>
              )}
            </div>

            {/* Score History */}
            <div className="glass-card p-8 flex flex-col">
              <h3 className="text-sm font-bold mb-8 uppercase tracking-[0.15em] text-[var(--beacon-text-muted)]">
                Score History
              </h3>
              {scoreHistory.length > 1 ? (
                <div className="h-[200px] w-full flex-1">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={scoreHistory}>
                      <CartesianGrid
                        strokeDasharray="4 4"
                        stroke="var(--beacon-border)"
                        vertical={false}
                      />
                      <XAxis
                        dataKey="scan"
                        stroke="var(--beacon-text-muted)"
                        fontSize={11}
                        fontWeight="bold"
                        tickMargin={10}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        domain={[0, 100]}
                        stroke="var(--beacon-text-muted)"
                        fontSize={11}
                        fontWeight="bold"
                        axisLine={false}
                        tickLine={false}
                        tickMargin={10}
                      />
                      <Tooltip
                        contentStyle={TOOLTIP_STYLE}
                        cursor={{ fill: "var(--beacon-surface)" }}
                      />
                      <Bar dataKey="score" radius={[6, 6, 0, 0]}>
                        {scoreHistory.map((entry, i) => (
                          <Cell
                            key={i}
                            fill={
                              entry.score >= 80
                                ? "var(--beacon-success)"
                                : entry.score >= 50
                                  ? "var(--beacon-warning)"
                                  : "var(--beacon-error)"
                            }
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : scoreHistory.length === 1 ? (
                <div className="flex-1 flex flex-col items-center justify-center bg-[var(--beacon-surface)] border border-[var(--beacon-border)] border-dashed rounded-lg">
                  <p
                    className="text-7xl font-cabinet font-extrabold"
                    style={{ color: scoreColor(scoreHistory[0].score) }}
                  >
                    {scoreHistory[0].score}
                  </p>
                  <p className="text-xs font-bold uppercase tracking-[0.1em] text-[var(--beacon-text-muted)] mt-2">
                    Run more scans to track progress
                  </p>
                </div>
              ) : (
                <p className="text-[var(--beacon-text-muted)] text-sm m-auto">
                  No score data yet.
                </p>
              )}
            </div>
          </div>

          {/* AI Analysis spanning full width below */}
          {(latestScan.ai_analysis || latestScan.summary) && (
            <div
              className={`glass-card p-8 relative overflow-hidden transition-all border-l-[6px] ${
                latestScan.ai_analysis?.includes("[AI ERROR]")
                  ? "border-l-[var(--beacon-error)] bg-[var(--beacon-error)]/5"
                  : latestScan.ai_analysis?.includes("generating")
                    ? "border-l-[var(--beacon-warning)] bg-[var(--beacon-warning)]/5"
                    : "border-l-[var(--beacon-primary)]"
              }`}
            >
              <div className="absolute -right-10 -top-10 text-[var(--beacon-primary)]/5">
                <IconSparkle className="w-48 h-48" />
              </div>
              <div className="relative z-10">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2.5">
                    <IconSparkle
                      className={`w-5 h-5 ${latestScan.ai_analysis?.includes("[AI ERROR]") ? "text-[var(--beacon-error)]" : "text-[var(--beacon-primary)]"}`}
                    />
                    <h3 className="text-sm font-bold uppercase tracking-[0.15em] text-[var(--beacon-text)]">
                      AI Engine Analysis
                    </h3>
                  </div>

                  {latestScan.ai_analysis?.includes("[AI ERROR]") && (
                    <button
                      onClick={() =>
                        setShowTechnicalDetails(!showTechnicalDetails)
                      }
                      className="text-[10px] font-black uppercase tracking-widest text-[var(--beacon-error)] border-b border-[var(--beacon-error)]/30 hover:border-[var(--beacon-error)] transition-all"
                    >
                      {showTechnicalDetails
                        ? "Hide Logs"
                        : "Show Technical Details"}
                    </button>
                  )}
                </div>

                <div
                  className={`text-sm md:text-base font-medium leading-relaxed whitespace-pre-wrap max-w-4xl transition-colors ${
                    latestScan.ai_analysis?.includes("[AI ERROR]")
                      ? "text-[var(--beacon-error)]"
                      : "text-[var(--beacon-text-soft)]"
                  }`}
                >
                  {latestScan.ai_analysis || latestScan.summary}
                </div>

                {showTechnicalDetails &&
                  latestScan.ai_analysis?.includes("[AI ERROR]") && (
                    <div className="mt-6 p-4 bg-black/40 rounded border border-[var(--beacon-error)]/20 font-mono text-[11px] text-[var(--beacon-error)]/80 leading-loose animate-fade-in">
                      <div className="flex items-center gap-2 mb-2 text-[var(--beacon-error)] font-bold uppercase tracking-wider">
                        <span>&gt; DEBUG_TRACE:</span>
                      </div>
                      {latestScan.ai_analysis}
                    </div>
                  )}
              </div>
            </div>
          )}

          {/* Trust Observability */}
          <div className="glass-card p-6 border-l-[6px] border-l-[var(--beacon-primary)]">
            <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
              <h3 className="text-sm font-bold uppercase tracking-[0.15em] text-[var(--beacon-text)]">
                Trust Observability
              </h3>
              <div className="flex items-center gap-2 text-[10px] font-extrabold uppercase tracking-[0.1em]">
                <span className="bg-[var(--beacon-surface)] border border-[var(--beacon-border)] px-2 py-1 rounded">
                  Data Quality: {trustDataQuality}
                </span>
                <span className="bg-[var(--beacon-surface)] border border-[var(--beacon-border)] px-2 py-1 rounded">
                  Completeness: {trustCompleteness}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <div className="bg-[var(--beacon-surface)] border border-[var(--beacon-border)] rounded-md p-3">
                <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--beacon-text-muted)]">
                  Avg Confidence
                </p>
                <p className="text-xl font-extrabold text-[var(--beacon-text)] mt-1">
                  {(confidenceAvg * 100).toFixed(1)}%
                </p>
              </div>
              <div className="bg-[var(--beacon-surface)] border border-[var(--beacon-border)] rounded-md p-3">
                <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--beacon-text-muted)]">
                  Suppression Rate
                </p>
                <p className="text-xl font-extrabold text-[var(--beacon-text)] mt-1">
                  {(suppressionRate * 100).toFixed(1)}%
                </p>
              </div>
              <div className="bg-[var(--beacon-surface)] border border-[var(--beacon-border)] rounded-md p-3">
                <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--beacon-text-muted)]">
                  Low-Trust Rules
                </p>
                <p className="text-xl font-extrabold text-[var(--beacon-text)] mt-1">
                  {lowTrustRules.length}
                </p>
              </div>
              <div className="bg-[var(--beacon-surface)] border border-[var(--beacon-border)] rounded-md p-3">
                <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--beacon-text-muted)]">
                  Integrity Caps
                </p>
                <p className="text-xl font-extrabold text-[var(--beacon-text)] mt-1">
                  {trustIntegrityCaps.length}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 mb-3">
              {[
                ["Static", !!enginesCoverage.static],
                ["Browser", !!enginesCoverage.browser],
                ["Axe", !!enginesCoverage.axe],
                ["Heuristic", !!enginesCoverage.heuristic],
              ].map(([label, enabled]) => (
                <span
                  key={String(label)}
                  className={`text-[10px] font-extrabold uppercase tracking-[0.1em] px-2 py-1 rounded border ${
                    enabled
                      ? "bg-[var(--beacon-success)]/15 text-[var(--beacon-success)] border-[var(--beacon-success)]/40"
                      : "bg-[var(--beacon-surface)] text-[var(--beacon-text-muted)] border-[var(--beacon-border)]"
                  }`}
                >
                  {label}: {enabled ? "on" : "off"}
                </span>
              ))}
            </div>

            {lowTrustRules.length > 0 && (
              <div className="mb-3 text-xs font-medium text-[var(--beacon-text-soft)]">
                <span className="font-bold text-[var(--beacon-text)] uppercase tracking-[0.08em] text-[10px]">
                  Low-Trust Rules:
                </span>{" "}
                {lowTrustRules.join(", ")}
              </div>
            )}

            {trustWarnings.length > 0 && (
              <div className="space-y-2">
                {trustWarnings.slice(0, 4).map((warning, idx) => (
                  <p
                    key={`${warning}-${idx}`}
                    className="text-xs font-medium text-[var(--beacon-warning)] bg-[var(--beacon-warning)]/10 border border-[var(--beacon-warning)]/30 rounded px-3 py-2"
                  >
                    {warning}
                  </p>
                ))}
              </div>
            )}
          </div>

          {/* Engines & Meta */}
          <div className="glass-card p-5 px-6 flex flex-wrap items-center justify-between gap-6 text-xs text-[var(--beacon-text-muted)] font-bold">
            <div className="flex items-center gap-2">
              <span className="uppercase tracking-[0.1em] opacity-80">
                Engines:{" "}
              </span>
              <div className="flex flex-wrap gap-1.5">
                {(latestScan.engines_used || []).map((e: string) => (
                  <span
                    key={e}
                    className="inline-flex items-center bg-[var(--beacon-surface)] border border-[var(--beacon-border)] px-2.5 py-1 rounded-full text-[var(--beacon-primary)] shadow-[1px_1px_0px_#000] uppercase text-[10px] tracking-wider"
                  >
                    {e}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-6 uppercase tracking-[0.05em]">
              <div className="flex items-center gap-1.5">
                <span className="opacity-70">Duration:</span>
                <span className="text-[var(--beacon-text)] bg-[var(--beacon-surface)] px-2 py-0.5 rounded shadow-[1px_1px_0px_#000] border border-[var(--beacon-border)]">
                  {(latestScan.scan_time_seconds || 0).toFixed(1)}s
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="opacity-70">Mode:</span>
                <span className="text-[var(--beacon-text)] bg-[var(--beacon-surface)] px-2 py-0.5 rounded shadow-[1px_1px_0px_#000] border border-[var(--beacon-border)]">
                  {latestScan.scan_mode || "fast"}
                </span>
              </div>
              {latestScan.completed_at && (
                <div className="opacity-60">
                  {new Date(latestScan.completed_at).toLocaleString()}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── ISSUES TAB ────────────────────────────────────────── */}
      {tab === "issues" && latestScan && (
        <div className="space-y-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-bold uppercase tracking-[0.15em] text-[var(--beacon-text-muted)]">
              Discovered Vulnerabilities by Type
            </h3>
            <span className="text-xs font-bold bg-[var(--beacon-surface)] border border-[var(--beacon-border)] px-3 py-1 rounded shadow-sm">
              {issueTypesCount} types • {failingElementsCount} elements
            </span>
          </div>

          {issues.length === 0 ? (
            <div className="glass-card p-20 text-center">
              <p className="text-5xl mb-4">🏆</p>
              <h2 className="text-2xl font-extrabold mb-2">
                Zero Compliance Violations
              </h2>
              <p className="text-base text-[var(--beacon-text-muted)] font-medium">
                Your site passed all checks successfully.
              </p>
            </div>
          ) : (
            issues.map((issue: any, idx: number) => {
              const isExpanded =
                expandedIssue === (issue.issue_id || idx.toString());
              return (
                <div
                  key={issue.issue_id || idx}
                  className={`glass-card overflow-hidden transition-all duration-300 ${isExpanded ? "ring-2 ring-[var(--beacon-primary)] ring-offset-2 ring-offset-[var(--beacon-bg)]" : ""}`}
                >
                  <button
                    className="w-full p-5 sm:p-6 flex items-start sm:items-center gap-4 text-left hover:bg-[var(--beacon-surface)] transition-colors focus:outline-none"
                    onClick={() =>
                      setExpandedIssue(
                        isExpanded ? null : issue.issue_id || idx.toString(),
                      )
                    }
                  >
                    <span
                      className={`severity-badge severity-${issue.severity} shrink-0 w-24 justify-center py-1 mt-1 sm:mt-0 shadow-sm`}
                    >
                      {issue.severity}
                    </span>
                    <div className="flex-1 min-w-0 pr-4">
                      <p className="text-base font-bold text-[var(--beacon-text)] leading-snug">
                        {issue.description || issue.rule_id}
                      </p>

                      <div className="flex items-center gap-3 mt-2 flex-wrap">
                        {issue.wcag_criterion && (
                          <span className="text-[10px] text-[var(--beacon-primary)] uppercase font-extrabold tracking-[0.1em] bg-[var(--beacon-primary)]/10 px-2 py-0.5 rounded border border-[var(--beacon-primary)]/20">
                            WCAG {issue.wcag_criterion}
                          </span>
                        )}
                        {issue.confidence != null && issue.confidence < 1 && (
                          <span className="text-[10px] font-bold text-[var(--beacon-text-muted)] uppercase tracking-wider">
                            Confidence{" "}
                            <span className="text-[var(--beacon-text)]">
                              {Math.round(issue.confidence * 100)}%
                            </span>
                          </span>
                        )}
                      </div>
                    </div>
                    <IconChevron
                      className={`w-5 h-5 text-[var(--beacon-text-muted)] shrink-0 transition-transform duration-300 ${isExpanded ? "rotate-180" : ""}`}
                    />
                  </button>

                  {isExpanded && (
                    <div className="p-6 pt-0 bg-[var(--beacon-surface)] border-t border-[var(--beacon-border)]">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                        <div className="space-y-6">
                          {/* HTML Snippet */}
                          {issue.html_snippet && (
                            <div>
                              <h4 className="text-[10px] font-bold uppercase tracking-[0.15em] text-[var(--beacon-text-muted)] mb-3 flex items-center gap-2">
                                <IconCode className="w-3.5 h-3.5" /> Failing
                                Element
                              </h4>
                              <div className="bg-[var(--beacon-bg)] p-4 rounded-md border border-[var(--beacon-border)] shadow-[inset_1px_1px_4px_rgba(0,0,0,0.1)]">
                                <pre className="text-[11px] font-mono text-[var(--beacon-text)] whitespace-pre-wrap leading-relaxed overflow-x-auto">
                                  {issue.html_snippet}
                                </pre>
                              </div>
                            </div>
                          )}

                          {/* Impact */}
                          {issue.impact_summary && (
                            <div>
                              <h4 className="text-[10px] font-bold uppercase tracking-[0.15em] text-[var(--beacon-text-muted)] mb-2">
                                User Impact
                              </h4>
                              <p className="text-sm text-[var(--beacon-text-soft)] font-medium leading-relaxed">
                                {issue.impact_summary}
                              </p>
                            </div>
                          )}
                        </div>

                        <div className="space-y-6">
                          {/* Suggested Fix */}
                          {aiEnabled && issue.suggested_fix && (
                            <div>
                              <h4 className="text-[10px] font-bold uppercase tracking-[0.15em] text-[var(--beacon-primary)] mb-2 flex items-center gap-1.5">
                                <IconSparkle className="w-3.5 h-3.5" />{" "}
                                Generative Fix Suggestion
                              </h4>
                              <div className="bg-[var(--beacon-primary)]/5 p-4 rounded-md border border-[var(--beacon-primary)]/20">
                                <p className="text-sm text-[var(--beacon-text)] font-medium leading-relaxed">
                                  {issue.suggested_fix}
                                </p>
                              </div>
                            </div>
                          )}

                          {aiEnabled && !issue.suggested_fix && (
                            <div>
                              <h4 className="text-[10px] font-bold uppercase tracking-[0.15em] text-[var(--beacon-primary)] mb-2 flex items-center gap-1.5">
                                <IconSparkle className="w-3.5 h-3.5" />{" "}
                                Generative Fix Suggestion
                              </h4>
                              <div className="bg-[var(--beacon-primary)]/5 p-4 rounded-md border border-[var(--beacon-primary)]/20">
                                <p className="text-sm text-[var(--beacon-text)] font-medium leading-relaxed">
                                  Fix suggestion unavailable
                                </p>
                              </div>
                            </div>
                          )}

                          {/* Code Fix */}
                          {aiEnabled && issue.code_fix && (
                            <div>
                              <h4 className="text-[10px] font-bold uppercase tracking-[0.15em] text-[var(--beacon-success)] mb-2 flex items-center gap-1.5">
                                <IconCode className="w-3.5 h-3.5" /> Remediated
                                Code
                              </h4>
                              <div className="bg-[#171e19] dark:bg-[var(--beacon-bg)] p-4 rounded-md border border-[var(--beacon-success)]/30 shadow-[inset_1px_1px_4px_rgba(0,0,0,0.2)]">
                                <pre className="text-[11px] font-mono text-[var(--beacon-success)] whitespace-pre-wrap leading-relaxed overflow-x-auto">
                                  {issue.code_fix}
                                </pre>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Meta context block bottom */}
                      {issue.confidence_sources?.length > 0 && (
                        <div className="mt-8 pt-4 border-t border-[var(--beacon-border)] flex items-center gap-3">
                          <span className="text-[10px] font-bold text-[var(--beacon-text-muted)] uppercase tracking-[0.1em]">
                            Trigger Engines:
                          </span>
                          <div className="flex gap-2">
                            {issue.confidence_sources.map((src: string) => (
                              <span
                                key={src}
                                className="text-[9px] bg-[var(--beacon-bg)] border border-[var(--beacon-border)] px-2 py-0.5 rounded shadow-[1px_1px_0px_#000] font-extrabold uppercase text-[var(--beacon-text)]"
                              >
                                {src}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* ── PRIORITY TAB ──────────────────────────────────────── */}
      {tab === "priority" && latestScan && (
        <div className="space-y-6">
          <div className="glass-card p-8 bg-[var(--beacon-primary)]/5 border-[var(--beacon-primary)]/30">
            <h3 className="text-base font-extrabold uppercase tracking-[0.1em] text-[var(--beacon-primary)] flex items-center gap-2">
              <IconSparkle className="w-5 h-5" /> Orchestrated Fix Priority
            </h3>
            <p className="text-sm font-medium text-[var(--beacon-text-soft)] mt-2 max-w-3xl">
              Issues algorithmically ranked by severe impact and highest
              occurrence globally across pages. Remediate these clusters to
              dramatically elevate overall compliance.
            </p>
          </div>

          {(latestScan.priority_ranking || []).length > 0 ? (
            <div className="space-y-4">
              {(latestScan.priority_ranking || []).map(
                (item: any, i: number) => (
                  <div key={i} className="glass-card flex overflow-hidden">
                    <div className="bg-[var(--beacon-surface)] w-16 sm:w-20 border-r border-[var(--beacon-border)] flex flex-col items-center justify-center shrink-0">
                      <span className="text-[10px] font-bold text-[var(--beacon-text-muted)] uppercase tracking-wider mb-1">
                        Rank
                      </span>
                      <span className="text-3xl font-cabinet font-extrabold text-[var(--beacon-text)]">
                        #{i + 1}
                      </span>
                    </div>

                    <div className="p-6 flex-1 bg-[var(--beacon-card-bg)]">
                      <div className="flex items-center gap-3 mb-2 flex-wrap">
                        {item.severity && (
                          <span
                            className={`severity-badge severity-${item.severity} shadow-sm`}
                          >
                            {item.severity}
                          </span>
                        )}
                        {item.wcag_criterion && (
                          <span className="text-[10px] text-black bg-[var(--beacon-primary)] px-2 py-1 rounded font-extrabold uppercase tracking-[0.15em] shadow-[1px_1px_0px_#000000]">
                            WCAG {item.wcag_criterion}
                          </span>
                        )}
                      </div>
                      <p className="text-lg font-bold text-[var(--beacon-text)] mt-2">
                        {item.rule_family || item.description || item.rule_id}
                      </p>

                      <div className="flex items-center gap-4 mt-3">
                        {item.frequency && (
                          <p className="text-xs font-bold text-[var(--beacon-text-muted)] uppercase tracking-wider flex items-center gap-1.5">
                            <span className="w-2 h-2 rounded-full bg-[var(--beacon-warning)] inline-block"></span>
                            {item.frequency} Incident
                            {item.frequency !== 1 ? "s" : ""}
                          </p>
                        )}
                        {item.priority_score && (
                          <p className="text-xs font-bold text-[var(--beacon-text-muted)] uppercase tracking-wider flex items-center gap-1.5">
                            <span className="italic">
                              Impact Weight: {item.priority_score.toFixed(1)}
                            </span>
                          </p>
                        )}
                      </div>

                      {item.fix_suggestion && (
                        <details className="mt-5 group">
                          <summary className="text-xs font-bold text-[var(--beacon-primary)] cursor-pointer flex items-center gap-1.5 uppercase tracking-[0.1em] hover:text-[var(--beacon-text)] transition-colors w-fit select-none outline-none">
                            <IconChevron className="w-4 h-4 transition-transform group-open:rotate-180" />{" "}
                            View Resolution Strategy
                          </summary>
                          <div className="mt-3 bg-[var(--beacon-surface)] p-4 border border-[var(--beacon-border)] rounded-md shadow-[inset_1px_1px_4px_rgba(0,0,0,0.05)]">
                            <pre className="text-[11px] font-mono text-[var(--beacon-text)] whitespace-pre-wrap leading-relaxed max-w-full overflow-x-auto">
                              {item.fix_suggestion}
                            </pre>
                          </div>
                        </details>
                      )}
                    </div>
                  </div>
                ),
              )}
            </div>
          ) : (
            <div className="glass-card p-20 text-center">
              <p className="text-base font-bold text-[var(--beacon-text-muted)]">
                {issues.length === 0
                  ? "No issues exist to be prioritized."
                  : "Priority calculation pending for this scan."}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
