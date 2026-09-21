"use client";
import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import api, { toUserFacingError } from "@/lib/api";
import Link from "next/link";

function IconPlus({ className }: { className?: string }) {
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
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
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
      strokeWidth="1.5"
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
function IconGlobe({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  );
}
function IconTrash({ className }: { className?: string }) {
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
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
    </svg>
  );
}
function IconShield({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
function IconAlertTriangle({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}
function IconCheckCircle({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}
function IconX({ className }: { className?: string }) {
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
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}


export default function AllProjectsPage() {
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<{
    message: string;
    retryable: boolean;
  } | null>(null);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [creating, setCreating] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const successTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    loadProjects();
  }, []);

  useEffect(() => {
    return () => {
      if (successTimerRef.current) {
        clearTimeout(successTimerRef.current);
      }
    };
  }, []);

  function showSuccessMessage(message: string) {
    setSuccessMessage(message);
    if (successTimerRef.current) {
      clearTimeout(successTimerRef.current);
    }
    successTimerRef.current = setTimeout(() => {
      setSuccessMessage(null);
    }, 60_000);
  }

  /* ── apiError auto-dismiss: 60 seconds ───────────────────────── */
  useEffect(() => {
    if (!apiError) return;
    const t = setTimeout(() => setApiError(null), 60_000);
    return () => clearTimeout(t);
  }, [apiError]);

  async function loadProjects() {
    try {
      const data = await api.getProjects();
      setProjects(data);
      setApiError(null);
    } catch (e) {
      console.error(e);
      setApiError(toUserFacingError(e));
    } finally {
      setLoading(false);
    }
  }

  function normalizeUrl(raw: string): string {
    const trimmed = raw.trim();
    if (!trimmed) return "";
    if (/^https?:\/\//i.test(trimmed)) {
      return trimmed;
    }
    return `https://${trimmed}`;
  }

  function isValidUrl(urlString: string): boolean {
    const trimmed = urlString.trim();
    if (!trimmed) return false;
    try {
      const normalized = normalizeUrl(trimmed);
      const url = new URL(normalized);
      const isHttp = url.protocol === "http:" || url.protocol === "https:";
      const hasHost = url.hostname.length > 0 && (url.hostname.includes(".") || url.hostname === "localhost");
      return isHttp && hasHost;
    } catch {
      return false;
    }
  }

  async function createProject() {
    if (!newName.trim() || !newUrl.trim()) return;
    
    const normalizedUrl = normalizeUrl(newUrl.trim());
    if (!isValidUrl(normalizedUrl)) {
      setApiError({
        message: "Please enter a valid website domain or URL (e.g. sai-folio.vercel.app or https://example.com)",
        retryable: false
      });
      return;
    }
    
    const name = newName.trim();
    setCreating(true);
    try {
      const created = await api.createProject({ name, url: normalizedUrl });
      const optimisticProject = {
        id: created?.id || `local-${Date.now()}`,
        name: created?.name || name,
        url: created?.url || normalizedUrl,
        latest_score: created?.latest_score ?? null,
        total_issues: created?.total_issues ?? 0,
        last_scan_at: created?.last_scan_at ?? null,
        ...created,
      };

      setProjects((prev) => {
        const withoutDuplicate = prev.filter(
          (project) => project.id !== optimisticProject.id,
        );
        return [optimisticProject, ...withoutDuplicate];
      });

      setNewName("");
      setNewUrl("");
      setShowNewForm(false);
      setApiError(null);
      showSuccessMessage(`Project \"${optimisticProject.name}\" created.`);
      void loadProjects();
    } catch (e) {
      console.error(e);
      setApiError(toUserFacingError(e));
    } finally {
      setCreating(false);
    }
  }

  async function deleteProject(pid: string) {
    const projectName =
      projects.find((project) => project.id === pid)?.name || "Project";
    if (
      !confirm(
        "Are you absolutely sure you want to delete this project? All historic scans will be erased forever.",
      )
    )
      return;

    const previousProjects = projects;
    setProjects((prev) => prev.filter((project) => project.id !== pid));

    try {
      await api.deleteProject(pid);
      setApiError(null);
      showSuccessMessage(`Deleted \"${projectName}\".`);
      void loadProjects();
    } catch (e) {
      console.error(e);
      setProjects(previousProjects);
      setApiError(toUserFacingError(e));
    }
  }

  function scoreColor(score: number | null): string {
    if (score === null || score === undefined)
      return "var(--beacon-text-muted)";
    if (score >= 80) return "var(--beacon-success)";
    if (score >= 50) return "var(--beacon-warning)";
    return "var(--beacon-error)";
  }

  if (loading) {
    return (
      <div className="flex justify-center py-32">
        <div className="w-10 h-10 border-4 border-[var(--beacon-primary)] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="animate-fade-in w-full pb-20">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 pb-4 border-b border-[var(--beacon-border)]/50">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">
            All Projects
          </h1>
          <p className="text-[var(--beacon-text-muted)] mt-1.5 font-medium">
            {projects.length} project{projects.length !== 1 ? "s" : ""}{" "}
            registered in the system
          </p>
        </div>
        <button
          onClick={() => setShowNewForm(!showNewForm)}
          className="btn-primary"
          data-testid="new-project-btn"
        >
          <IconPlus className="w-4 h-4" /> New Project
        </button>
      </div>

      {/* ── Floating Toast Portal ──────────────────────────────── */}
      {mounted && createPortal(
        <aside
          aria-label="Notifications"
          style={{ position: "fixed", bottom: "24px", right: "24px", zIndex: 99999, display: "flex", flexDirection: "column", gap: "12px", maxWidth: "420px", width: "calc(100vw - 3rem)", pointerEvents: "none" }}
        >
          {successMessage && (
            <div
              role="status"
              aria-live="polite"
              className="pointer-events-auto w-full bg-[var(--beacon-surface)] text-[var(--beacon-text)] p-4 rounded-xl border-2 border-[var(--beacon-border)] shadow-[5px_5px_0px_#000] animate-slide-in-right flex items-start justify-between gap-3 border-l-8 border-l-[var(--beacon-success)]"
            >
              <div className="flex items-start gap-3 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-[var(--beacon-success)]/15 border border-[var(--beacon-success)]/30 flex items-center justify-center shrink-0 text-[var(--beacon-success)] mt-0.5">
                  <IconCheckCircle className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <h4 className="text-xs font-black uppercase tracking-wider text-[var(--beacon-success)]">
                    Success
                  </h4>
                  <p className="text-xs font-bold text-[var(--beacon-text)] mt-0.5 leading-snug">
                    {successMessage}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSuccessMessage(null)}
                aria-label="Close notification"
                className="w-7 h-7 rounded-md border border-[var(--beacon-border)] flex items-center justify-center text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] hover:bg-[var(--beacon-bg)] transition-colors shrink-0"
              >
                <IconX className="w-4 h-4" />
              </button>
            </div>
          )}

          {apiError && !showNewForm && (
            <div
              role="alert"
              aria-live="assertive"
              className="pointer-events-auto w-full bg-[var(--beacon-surface)] text-[var(--beacon-text)] p-4 rounded-xl border-2 border-[var(--beacon-border)] shadow-[5px_5px_0px_#000] animate-slide-in-right flex items-start justify-between gap-3 border-l-8 border-l-[var(--beacon-error)]"
            >
              <div className="flex items-start gap-3 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-red-500/15 border border-red-500/30 flex items-center justify-center shrink-0 text-[var(--beacon-error)] mt-0.5">
                  <IconAlertTriangle className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <h4 className="text-xs font-black uppercase tracking-wider text-[var(--beacon-error)]">
                    API Error
                  </h4>
                  <p className="text-xs font-bold text-[var(--beacon-text)] mt-0.5 leading-snug break-words">
                    {apiError.message}
                  </p>
                  {apiError.retryable && (
                    <button
                      onClick={loadProjects}
                      className="mt-2 text-xs font-black uppercase tracking-wider px-2.5 py-1 rounded bg-[var(--beacon-bg)] border border-[var(--beacon-border)] hover:bg-[var(--beacon-card-bg)] text-[var(--beacon-text)] transition-colors inline-block"
                    >
                      Retry
                    </button>
                  )}
                </div>
              </div>
              <button
                onClick={() => setApiError(null)}
                aria-label="Close notification"
                className="w-7 h-7 rounded-md border border-[var(--beacon-border)] flex items-center justify-center text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] hover:bg-[var(--beacon-bg)] transition-colors shrink-0"
              >
                <IconX className="w-4 h-4" />
              </button>
            </div>
          )}
        </aside>,
        document.body
      )}

      {/* New Project Form */}
      {showNewForm && (
        <div className="glass-card p-6 mb-8 animate-fade-in border-2 border-[var(--beacon-border)] shadow-[4px_4px_0px_#000]" data-testid="new-project-form">
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-sm font-bold uppercase tracking-[0.15em]">
              Create New Project
            </h3>
            <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--beacon-primary)] bg-[var(--beacon-primary)]/10 px-2 py-0.5 rounded">
              Ready to Audit
            </span>
          </div>

          {/* Form-scoped error card */}
          {apiError && (
            <div className="mb-5 p-3.5 rounded-lg border-2 border-[var(--beacon-error)] bg-red-500/10 text-red-700 dark:text-red-300 text-xs font-semibold flex items-center justify-between gap-4 shadow-[2px_2px_0px_#000]">
              <div className="flex items-center gap-2.5">
                <IconAlertTriangle className="w-4 h-4 shrink-0 text-[var(--beacon-error)]" />
                <span>{apiError.message}</span>
              </div>
              <button
                onClick={() => setApiError(null)}
                aria-label="Close alert"
                className="w-6 h-6 rounded border border-[var(--beacon-error)]/40 flex items-center justify-center text-[var(--beacon-error)] hover:bg-red-500/20 transition-colors shrink-0"
              >
                <IconX className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">
            <div>
              <label className="text-xs text-[var(--beacon-text-muted)] font-bold uppercase tracking-[0.1em] block mb-2">
                Project Name
              </label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Product Landing Page"
                className="beacon-input w-full font-medium"
                data-testid="project-name-input"
                autoFocus
              />
            </div>
            <div>
              <label className="text-xs text-[var(--beacon-text-muted)] font-bold uppercase tracking-[0.1em] block mb-2">
                Website URL
              </label>
              <input
                type="text"
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
                placeholder="https://example.com"
                className="beacon-input w-full font-medium"
                data-testid="project-url-input"
              />
              {newUrl.trim() && (
                <p className="text-[11px] font-medium text-[var(--beacon-text-muted)] mt-1.5 flex items-center gap-1.5">
                  <IconGlobe className="w-3.5 h-3.5 text-[var(--beacon-primary)] shrink-0" />
                  Will be scanned as: <span className="font-mono text-[var(--beacon-text)] font-bold">{normalizeUrl(newUrl)}</span>
                </p>
              )}
            </div>
          </div>

          {/* 3-Tier Anti-Bot & Headless Browser Automation Notice */}
          <div className="p-4 rounded-lg border-2 border-emerald-500/60 bg-emerald-50 dark:bg-emerald-950/30 text-xs mb-5 flex items-start gap-3 shadow-[2px_2px_0px_#000]">
            <IconShield className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <span className="font-black uppercase tracking-wider text-emerald-950 dark:text-emerald-300 block text-[11px] flex items-center gap-2">
                Stealth Anti-Bot &amp; Headless Automation
                <span className="text-[9px] bg-emerald-600 text-white px-1.5 py-0.2 rounded font-black tracking-wider uppercase">v3.0</span>
              </span>
              <p className="text-emerald-900 dark:text-emerald-100 font-medium leading-relaxed text-xs">
                BEACON v3.0 features a 3-tier resilient browser pipeline (Patchright C++ patched Chromium, Camoufox, and Playwright fallback). Sites protected by Cloudflare Turnstile or challenge walls are automatically evaluated with stealth evasion and graceful fallback telemetry.
              </p>
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={createProject}
              disabled={creating || !newName.trim() || !isValidUrl(newUrl)}
              className="btn-primary"
              data-testid="create-project-submit-btn"
            >
              {creating ? "Launching..." : "Launch Project"}
            </button>
            <button
              onClick={() => {
                setShowNewForm(false);
                setApiError(null);
              }}
              className="btn-secondary"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Empty State */}
      {projects.length === 0 && !showNewForm && (
        <div className="glass-card flex flex-col items-center justify-center p-20 text-center mt-10">
          <div className="w-20 h-20 bg-[var(--beacon-primary-dim)] text-[var(--beacon-primary)] rounded-full flex items-center justify-center mb-6">
            <IconGlobe className="w-10 h-10" />
          </div>
          <h2 className="text-2xl font-extrabold mb-3">No projects yet</h2>
          <p className="text-[var(--beacon-text-muted)] font-medium mb-8 max-w-sm mx-auto">
            Create your first project to start running heavy accessibility and
            semantic UI diagnostics.
          </p>
          <button
            onClick={() => setShowNewForm(true)}
            className="btn-primary py-3 px-6 text-sm"
            data-testid="create-first-project-btn"
          >
            <IconPlus className="w-[18px] h-[18px]" /> Create First Project
          </button>
        </div>
      )}

      {/* Project Grid */}
      {projects.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6" data-testid="project-grid">
          {projects.map((project) => (
            <Link
              key={project.id}
              href={`/dashboard/${project.id}`}
              className="glass-card flex flex-col hover:-translate-y-1 transition-all duration-200 group"
              data-testid="project-card"
            >
              <div className="p-6 flex-1 flex flex-col">
                {/* Score & Name header */}
                <div className="flex justify-between items-start mb-6">
                  <div className="flex-1 min-w-0 pr-4">
                    <h3 className="text-lg font-bold truncate group-hover:text-[var(--beacon-primary)] transition-colors">
                      {project.name}
                    </h3>
                    <p className="text-sm font-medium text-[var(--beacon-text-muted)] truncate mt-1">
                      {project.url}
                    </p>
                  </div>
                  {project.latest_score !== null &&
                  project.latest_score !== undefined ? (
                    <div className="text-right shrink-0">
                      <span
                        className="text-3xl font-extrabold tracking-tight tabular-nums"
                        style={{ color: scoreColor(project.latest_score) }}
                      >
                        {Math.round(project.latest_score)}
                      </span>
                      <span className="text-sm font-bold text-[var(--beacon-text-muted)]">
                        /100
                      </span>
                    </div>
                  ) : (
                    <span className="text-xs font-bold uppercase tracking-wider text-[var(--beacon-text-muted)] bg-[var(--beacon-surface)] border border-[var(--beacon-border)] px-2.5 py-1.5 rounded-full shrink-0 shadow-[2px_2px_0px_#000]">
                      No scans
                    </span>
                  )}
                </div>

                {/* Stats / Indicators */}
                <div className="mt-auto pt-4 border-t border-[var(--beacon-border)]/50 flex flex-wrap items-center justify-between gap-y-2">
                  <div className="flex items-center gap-4 text-xs font-semibold uppercase tracking-[0.05em] text-[var(--beacon-text-muted)]">
                    {project.total_issues > 0 ? (
                      <span className="flex items-center gap-1.5 bg-[var(--beacon-error)]/10 text-[var(--beacon-error)] px-2 py-0.5 rounded border border-[var(--beacon-error)]/20 shadow-[1px_1px_0px_var(--beacon-error)]">
                        <span className="w-1.5 h-1.5 rounded-full bg-[var(--beacon-error)]" />
                        {project.total_issues} issues
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-[var(--beacon-border)]" />
                        No Issues Found
                      </span>
                    )}
                  </div>
                  {project.last_scan_at && (
                    <span className="text-xs font-medium text-[var(--beacon-text-muted)]">
                      {new Date(project.last_scan_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>

              {/* Actions / Footer area */}
              <div className="px-6 py-3 border-t border-[var(--beacon-border)] bg-[var(--beacon-surface)] flex items-center justify-between rounded-b-[7px]">
                <span className="text-xs text-[var(--beacon-text)] font-extrabold uppercase tracking-[0.1em] opacity-70 group-hover:opacity-100 group-hover:text-[var(--beacon-primary)] transition-colors">
                  View Project &rarr;
                </span>

                <button
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    deleteProject(project.id);
                  }}
                  className="p-1.5 text-[var(--beacon-text-muted)] hover:text-[#E84855] hover:bg-[#E84855]/10 rounded transition-colors"
                  title="Delete project permanently"
                >
                  <IconTrash className="w-4 h-4" />
                </button>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
