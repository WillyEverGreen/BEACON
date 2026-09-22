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
function IconShield({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
function IconFileText({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
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
        q: "What is BEACON v3.0?",
        a: "BEACON (Benchmarking & Evaluation of Accessibility Compliance Optimization Node) is an enterprise-grade accessibility intelligence platform. Version 3.0 introduces multi-engine consensus (axe-core, IBM Equal Access, Siteimprove Alfa, Guidepup screen reader), 100% W3C ACT Rule Adjudication, Patchright stealth anti-bot automation, and zero-regression AI remediation.",
      },
      {
        q: "How do I run my first scan?",
        a: "1. Click 'New Project' on the dashboard and enter your website URL and project name.\n2. Choose your scan mode: Fast (single-page static audit), Deep (multi-page domain audit), or Max (exhaustive crawl).\n3. Open your project and click 'Initiate Scan'.\n4. Explore the Overview, Issues, Fix Priority Queue, and Telemetry tabs, or click 'Export' for SARIF/EARL reports.",
      },
    ],
  },
  {
    id: "consensus",
    title: "Multi-Engine Consensus",
    icon: IconShield,
    sections: [
      {
        q: "How does the Consensus Engine work?",
        a: "Unlike single-engine linters that suffer from false alarms, BEACON reconciles findings across multiple independent audit engines:\n• axe-core 4.10 (industry baseline standard)\n• IBM Equal Access 3.1 (enterprise rule coverage)\n• Siteimprove Alfa (W3C ACT rule evaluation)\n• Guidepup Screen Reader (dynamic speech synthesis and focus trap detection)\n• BEACON Heuristics & Cognitive COGA\n\nFindings with multi-engine agreement receive boosted calibrated confidence (up to 99%), pinning down genuine barriers with zero noise.",
      },
      {
        q: "What is W3C ACT Rule Adjudication?",
        a: "W3C Accessibility Conformance Testing (ACT) defines unambiguous, vendor-neutral test cases. When an issue matches a verified ACT rule identifier, BEACON flags it as 'ACT Adjudicated', cementing 100% benchmark precision and authoritative compliance grounding.",
      },
    ],
  },
  {
    id: "remediation",
    title: "AI Remediation Sandbox",
    icon: IconWrench,
    sections: [
      {
        q: "How does NVIDIA NIM AI Remediation work?",
        a: "BEACON couples state-of-the-art NVIDIA NIM language models with a contextual RAG knowledge base containing WCAG 2.2, WAI-ARIA APG, and COGA design patterns to synthesize exact, paste-ready HTML and CSS patches.",
      },
      {
        q: "What is the Zero-Regression Remediation Sandbox?",
        a: "Candidate AI fixes are not accepted blindly. Each patch is executed inside an isolated DOM container (`RemediationSandbox`) where a differential audit is performed. Any patch that introduces new violations or contains unsafe scripting (`<script>`, inline `onclick`, unauthorized attributes) is automatically rejected.",
      },
    ],
  },
  {
    id: "exporters",
    title: "SARIF & EARL Exporters",
    icon: IconFileText,
    sections: [
      {
        q: "How do I export to OASIS SARIF 2.1.0?",
        a: "Click 'Export' > 'OASIS SARIF 2.1.0' on any completed project scan. The resulting `.sarif` file can be directly uploaded to GitHub Code Scanning via `github/codeql-action/upload-sarif`, piped into GitLab SAST, or inspected in VS Code.",
      },
      {
        q: "What is W3C EARL 1.0 JSON-LD?",
        a: "The Evaluation and Report Language (EARL) 1.0 is the W3C standard format for recording accessibility test results. The `.jsonld` export generates machine-readable conformance assertion graphs ideal for European Accessibility Act (EAA), Section 508, and official government audits.",
      },
    ],
  },
  {
    id: "topology",
    title: "Topology & Anti-Bot",
    icon: IconSearch,
    sections: [
      {
        q: "What is Native Topology Crawling?",
        a: "BEACON clusters pages by structural DOM tag-tree skeletons stripped of volatile classes and IDs. When subsequent pages in a template cluster (e.g. blog posts or product catalogs) yield no new violation types, the crawler stops early, cutting crawl loops by 66.7% while preserving template diversity.",
      },
      {
        q: "How does 3-Tier Anti-Bot Automation work?",
        a: "Websites with modern bot protections (such as Cloudflare Turnstile or CAPTCHA challenges) are handled via a 3-tier launcher:\n1. Patchright (undetected C++ patched Chromium stripping CDP artifacts)\n2. Camoufox (anti-detect Firefox with WebGL/font spoofing)\n3. Playwright (standard fallback with challenge detection)\n\nIf challenge walls are detected, BEACON logs dedicated observability telemetry instead of crashing.",
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
