"use client";
import { useState } from "react";

function IconChevron({ className, up }: { className?: string; up?: boolean }) {
  return (<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{up ? <polyline points="18 15 12 9 6 15"/> : <polyline points="6 9 12 15 18 9"/>}</svg>);
}
function IconSearch({ className }: { className?: string }) {
  return (<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>);
}
function IconRocket({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z" />
      <path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z" />
      <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0" />
      <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5" />
    </svg>
  );
}
function IconWrench({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
    </svg>
  );
}

const DOCS = [
  {
    id: "getting-started",
    title: "Getting Started",
    icon: IconRocket,
    sections: [
      {
        q: "What is BEACON?",
        a: "BEACON (Benchmarking & Evaluation of Accessibility Compliance Optimization Node) is an AI-powered web accessibility auditing platform. It crawls your website, runs 65+ WCAG 2.2 checks, and utilizes an AI semantic layer for actionable fix suggestions.",
      },
      {
        q: "How do I run my first scan?",
        a: "1. Click 'New Project' on the dashboard and enter your website URL and project name.\n2. Open your project and click 'Run Scan'.\n3. Wait for the engine to complete its analysis.\n4. Explore the Overview, Issues, and Fix Priority Queue tabs.",
      },
    ],
  },
  {
    id: "scanning",
    title: "Scans & Scoring",
    icon: IconSearch,
    sections: [
      {
        q: "What does a scan check?",
        a: "• 65+ WCAG 2.2 checks (images, forms, ARIA, color contrast, keyboard navigation, headings, landmarks)\n• Semantic analysis for complex UI elements\n• Fix generation for discovered violations",
      },
      {
        q: "How are scan scores calculated?",
        a: "Scores range from 0–100:\n• Weighted by WCAG level (AAA=1×, AA=2×, A=3× weight) and severity (critical=4pts, serious=3, moderate=2, minor=1).\n• Automatically grouped and deduped by domain.",
      },
      {
        q: "Why do scans take a few moments?",
        a: "BEACON evaluates your page dynamically with Playwright, checks color contrast of rendered elements, and validates issues with an LLM layer. Typical scan time is 5-25 seconds depending on page size and complexity.",
      },
    ],
  },
  {
    id: "issues",
    title: "Issues & Fixes",
    icon: IconWrench,
    sections: [
      {
        q: "How do I see what's wrong?",
        a: "Go to the Issues tab in your project. Each issue lists the description, exact HTML snippet, and WCAG criteria. You'll see Kimi AI's suggested fixes, which include both an explanation and paste-ready code.",
      },
      {
        q: "What is the Fix Priority Queue?",
        a: "This ranks the issues based on User Impact × Frequency. Start from #1 on this list for maximum immediate UX improvement.",
      },
    ],
  },
];

function AccordionSection({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-[var(--beacon-border)]/60 last:border-0">
      <button
        className="w-full text-left py-3 flex items-center justify-between gap-3 hover:text-[var(--beacon-primary)] transition"
        onClick={() => setOpen(!open)}
      >
        <span className="text-sm font-bold text-[var(--beacon-text)]">{q}</span>
        <IconChevron className="w-4 h-4 text-[var(--beacon-text-muted)] shrink-0" up={open} />
      </button>
      {open && (
        <div className="pb-4 pr-4">
          {a.split("\n").map((line, i) =>
            line.trim() === "" ? <div key={i} className="h-2" /> :
            line.match(/^[A-Z\s/]+:/) || line.endsWith(":") ? (
              <p key={i} className="text-xs font-bold text-[var(--beacon-primary)] uppercase tracking-[0.06em] mt-3 mb-1">{line}</p>
            ) : line.startsWith("•") || line.startsWith("·") ? (
              <p key={i} className="text-xs font-medium text-[var(--beacon-text-soft)] leading-relaxed pl-3">{line}</p>
            ) : line.match(/^\s+(GET|POST|WS|DELETE)/) ? (
              <p key={i} className="text-xs font-mono font-bold text-[var(--beacon-text)] leading-relaxed pl-4">{line}</p>
            ) : (
              <p key={i} className="text-xs font-medium text-[var(--beacon-text-soft)] leading-relaxed">{line}</p>
            )
          )}
        </div>
      )}
    </div>
  );
}

export default function HelpPage() {
  const [search, setSearch] = useState("");
  const [activeSection, setActiveSection] = useState("getting-started");

  const filtered = search.trim()
    ? DOCS.map(section => ({
        ...section,
        sections: section.sections.filter(
          s => s.q.toLowerCase().includes(search.toLowerCase()) || s.a.toLowerCase().includes(search.toLowerCase())
        ),
      })).filter(s => s.sections.length > 0)
    : DOCS;

  return (
    <div className="animate-fade-in max-w-4xl">
      <div className="mb-8">
        <h1 className="text-3xl font-extrabold tracking-[-0.02em] text-[var(--beacon-text)]">Help &amp; Documentation</h1>
        <p className="text-[var(--beacon-text-muted)] font-medium text-sm mt-1">Everything you need to use BEACON effectively</p>
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <IconSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--beacon-text-muted)]" />
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search documentation..."
          className="beacon-input w-full pl-9"
        />
      </div>

      <div className="flex gap-6">
        {/* Sidebar nav */}
        {!search && (
          <div className="w-48 shrink-0">
            <div className="space-y-1 sticky top-4">
              {DOCS.map(section => (
                <button
                  key={section.id}
                  onClick={() => {
                    setActiveSection(section.id);
                    document.getElementById(section.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
                  }}
                  className={`w-full text-left px-3 py-2 rounded-md text-xs font-bold flex items-center gap-2.5 transition ${
                    activeSection === section.id
                      ? "bg-[var(--beacon-primary)] text-black shadow-[2px_2px_0px_#000]"
                      : "text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] hover:bg-[var(--beacon-surface)]"
                  }`}
                >
                  <section.icon className="w-3.5 h-3.5 shrink-0" />
                  <span>{section.title}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 space-y-5">
          {filtered.map(section => (
            <div key={section.id} id={section.id} className="glass-card p-6">
              <div className="flex items-center gap-3 mb-4">
                <section.icon className="w-5 h-5 text-[var(--beacon-primary)] shrink-0" />
                <h2 className="text-sm font-extrabold uppercase tracking-[0.1em] text-[var(--beacon-text)]">{section.title}</h2>
                <span className="text-xs font-bold text-[var(--beacon-text-muted)] ml-auto">{section.sections.length} articles</span>
              </div>
              <div>
                {section.sections.map((s, i) => (
                  <AccordionSection key={i} q={s.q} a={s.a} />
                ))}
              </div>
            </div>
          ))}

          {filtered.length === 0 && (
            <div className="glass-card p-12 text-center">
              <p className="text-[var(--beacon-text-muted)] text-sm">No documentation found for &quot;{search}&quot;</p>
            </div>
          )}

          {/* Footer */}
          <div className="glass-card p-4 text-center">
            <p className="text-xs text-[var(--beacon-text-muted)]">
              Can&apos;t find what you need?{" "}
              <a href="https://github.com" target="_blank" rel="noreferrer" className="text-[var(--beacon-primary)] hover:underline">
                Open an issue on GitHub
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
