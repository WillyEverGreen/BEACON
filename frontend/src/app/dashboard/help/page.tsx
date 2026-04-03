"use client";
import { useState } from "react";

function IconChevron({ className, up }: { className?: string; up?: boolean }) {
  return (<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{up ? <polyline points="18 15 12 9 6 15"/> : <polyline points="6 9 12 15 18 9"/>}</svg>);
}
function IconSearch({ className }: { className?: string }) {
  return (<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>);
}

const DOCS = [
  {
    id: "getting-started",
    title: "Getting Started",
    icon: "🚀",
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
    icon: "🔍",
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
    icon: "🔧",
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
        <span className="text-sm font-medium">{q}</span>
        <IconChevron className="w-4 h-4 text-[var(--beacon-text-muted)] shrink-0" up={open} />
      </button>
      {open && (
        <div className="pb-4 pr-4">
          {a.split("\n").map((line, i) =>
            line.trim() === "" ? <div key={i} className="h-2" /> :
            line.match(/^[A-Z\s/]+:/) || line.endsWith(":") ? (
              <p key={i} className="text-xs font-medium text-[var(--beacon-primary)] uppercase tracking-[0.06em] mt-3 mb-1">{line}</p>
            ) : line.startsWith("•") || line.startsWith("·") ? (
              <p key={i} className="text-xs text-[var(--beacon-text-muted)] leading-relaxed pl-3">{line}</p>
            ) : line.match(/^\s+(GET|POST|WS|DELETE)/) ? (
              <p key={i} className="text-xs font-mono text-[var(--beacon-text-muted)] leading-relaxed pl-4">{line}</p>
            ) : (
              <p key={i} className="text-xs text-[var(--beacon-text-muted)] leading-relaxed">{line}</p>
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
        <h1 className="text-2xl font-medium tracking-[-0.02em]">Help &amp; Documentation</h1>
        <p className="text-[var(--beacon-text-muted)] text-sm mt-1">Everything you need to use BEACON effectively</p>
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
          <div className="w-44 shrink-0">
            <div className="space-y-0.5 sticky top-4">
              {DOCS.map(section => (
                <button
                  key={section.id}
                  onClick={() => {
                    setActiveSection(section.id);
                    document.getElementById(section.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
                  }}
                  className={`w-full text-left px-3 py-2 rounded text-xs flex items-center gap-2 transition ${
                    activeSection === section.id
                      ? "bg-[var(--beacon-primary)]/10 text-[var(--beacon-primary)]"
                      : "text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] hover:bg-[var(--beacon-surface)]"
                  }`}
                >
                  <span>{section.icon}</span>
                  {section.title}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 space-y-5">
          {filtered.map(section => (
            <div key={section.id} id={section.id} className="glass-card p-5">
              <div className="flex items-center gap-3 mb-4">
                <span className="text-xl">{section.icon}</span>
                <h2 className="text-sm font-medium uppercase tracking-[0.1em]">{section.title}</h2>
                <span className="text-xs text-[var(--beacon-text-muted)] ml-auto">{section.sections.length} articles</span>
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
