"use client";
import { useState, useEffect } from "react";
import api from "@/lib/api";
import Link from "next/link";

function IconPlus({ className }: { className?: string }) {
  return (<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>);
}
function IconScan({ className }: { className?: string }) {
  return (<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><line x1="7" y1="12" x2="17" y2="12"/></svg>);
}
function IconGlobe({ className }: { className?: string }) {
  return (<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>);
}
function IconTrash({ className }: { className?: string }) {
  return (<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>);
}

export default function AllProjectsPage() {
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => { loadProjects(); }, []);

  async function loadProjects() {
    try {
      const data = await api.getProjects();
      setProjects(data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }

  async function createProject() {
    if (!newName.trim() || !newUrl.trim()) return;
    setCreating(true);
    try {
      await api.createProject({ name: newName.trim(), url: newUrl.trim() });
      setNewName("");
      setNewUrl("");
      setShowNewForm(false);
      await loadProjects();
    } catch (e) { console.error(e); }
    finally { setCreating(false); }
  }

  async function deleteProject(pid: string) {
    if (!confirm("Are you absolutely sure you want to delete this project? All historic scans will be erased forever.")) return;
    try {
      await api.deleteProject(pid);
      await loadProjects();
    } catch (e) { console.error(e); }
  }

  function scoreColor(score: number | null): string {
    if (score === null || score === undefined) return "var(--beacon-text-muted)";
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
          <h1 className="text-3xl font-extrabold tracking-tight">All Projects</h1>
          <p className="text-[var(--beacon-text-muted)] mt-1.5 font-medium">
            {projects.length} project{projects.length !== 1 ? "s" : ""} registered in the system
          </p>
        </div>
        <button onClick={() => setShowNewForm(!showNewForm)} className="btn-primary">
          <IconPlus className="w-4 h-4" /> New Project
        </button>
      </div>

      {/* New Project Form */}
      {showNewForm && (
        <div className="glass-card p-6 mb-8 animate-fade-in">
          <h3 className="text-sm font-bold uppercase tracking-[0.15em] mb-5">Create New Project</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">
            <div>
              <label className="text-xs text-[var(--beacon-text-muted)] font-bold uppercase tracking-[0.1em] block mb-2">Project Name</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Product Landing Page"
                className="beacon-input w-full font-medium"
                autoFocus
              />
            </div>
            <div>
              <label className="text-xs text-[var(--beacon-text-muted)] font-bold uppercase tracking-[0.1em] block mb-2">Website URL</label>
              <input
                type="url"
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
                placeholder="https://example.com"
                className="beacon-input w-full font-medium"
              />
            </div>
          </div>
          <div className="flex gap-3">
            <button onClick={createProject} disabled={creating || !newName.trim() || !newUrl.trim()} className="btn-primary">
              {creating ? "Creating..." : "Launch Project"}
            </button>
            <button onClick={() => setShowNewForm(false)} className="btn-secondary">Cancel</button>
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
            Create your first project to start running heavy accessibility and semantic UI diagnostics.
          </p>
          <button onClick={() => setShowNewForm(true)} className="btn-primary py-3 px-6 text-sm">
            <IconPlus className="w-[18px] h-[18px]" /> Create First Project
          </button>
        </div>
      )}

      {/* Project Grid */}
      {projects.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {projects.map((project) => (
            <Link key={project.id} href={`/dashboard/${project.id}`} className="glass-card flex flex-col hover:-translate-y-1 transition-all duration-200 group">
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
                    {project.latest_score !== null && project.latest_score !== undefined ? (
                      <div className="text-right shrink-0">
                        <span className="text-3xl font-extrabold tracking-tight tabular-nums" style={{ color: scoreColor(project.latest_score) }}>
                          {Math.round(project.latest_score)}
                        </span>
                        <span className="text-sm font-bold text-[var(--beacon-text-muted)]">/100</span>
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
                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); deleteProject(project.id); }}
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
