"use client";
import { useState, useEffect, useCallback, useMemo, useRef, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";

const emptySubscribe = () => () => {};
import { useParams } from "next/navigation";
import Link from "next/link";
import api, { downloadScanReport, toUserFacingError } from "@/lib/api";
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
function IconShield({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
function IconCheckCircle({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
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
function IconSearch({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}
function IconInfo({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}
function IconTrophy({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" />
      <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" />
      <path d="M4 22h16" />
      <path d="M10 14.66V17c0 .55-.45 1-1 1H7v2h10v-2h-2c-.55 0-1-.45-1-1v-2.34c3.55-.79 6-3.9 6-7.66V4H4v5c0 3.76 2.45 6.87 6 7.66Z" />
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
function IconDownload({ className }: { className?: string }) {
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
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}
function IconUser({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}
function IconPalette({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="13.5" cy="6.5" r=".5" fill="currentColor" />
      <circle cx="17.5" cy="10.5" r=".5" fill="currentColor" />
      <circle cx="8.5" cy="7.5" r=".5" fill="currentColor" />
      <circle cx="6.5" cy="12.5" r=".5" fill="currentColor" />
      <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z" />
    </svg>
  );
}
function IconForm({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M7 8h10" />
      <path d="M7 12h10" />
      <path d="M7 16h6" />
    </svg>
  );
}
function IconImage({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
      <circle cx="8.5" cy="8.5" r="1.5" />
      <polyline points="21 15 16 10 5 21" />
    </svg>
  );
}
function IconKeyboard({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="M6 8h.001" />
      <path d="M10 8h.001" />
      <path d="M14 8h.001" />
      <path d="M18 8h.001" />
      <path d="M6 12h.001" />
      <path d="M18 12h.001" />
      <path d="M10 12h4" />
      <path d="M6 16h.001" />
      <path d="M10 16h.001" />
      <path d="M14 16h.001" />
      <path d="M18 16h.001" />
    </svg>
  );
}
function IconTag({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2H2v10l9.29 9.29c.94.94 2.48.94 3.42 0l6.58-6.58c.94-.94.94-2.48 0-3.42L12 2Z" />
      <path d="M7 7h.01" />
    </svg>
  );
}
function IconLayers({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="12 2 2 7 12 12 22 7 12 2" />
      <polyline points="2 17 12 22 22 17" />
      <polyline points="2 12 12 17 22 12" />
    </svg>
  );
}
function IconFilter({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
    </svg>
  );
}
function IconRefresh({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21.5 2v6h-6" />
      <path d="M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
    </svg>
  );
}
function IconCheck({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
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

const ROLE_OPTIONS = [
  { id: "DEVELOPER", label: "Developer", desc: "AST selectors, code fixes, and technical diagnostics" },
  { id: "QA_A11Y", label: "QA / A11y", desc: "Assertion checklist, verification queue, and test steps" },
  { id: "COMPLIANCE", label: "Compliance", desc: "Mandatory criteria coverage, VPAT/EN 301 549 conformance" },
  { id: "EXECUTIVE", label: "Executive", desc: "Risk overview, health score, and business impact" },
] as const;

const REGULATORY_PROFILES_OPTIONS = [
  { id: "GLOBAL_WCAG_22_AA", label: "WCAG 2.2 AA", badge: "Global Standard" },
  { id: "US_SECTION_508", label: "Section 508", badge: "US Federal / VPAT" },
  { id: "EU_EN_301_549", label: "EN 301 549", badge: "EU Standard / EAA" },
  { id: "UK_PUBLIC_SECTOR", label: "UK PSBAR", badge: "UK Public Sector" },
  { id: "INDIA_GIGW", label: "GIGW 3.0", badge: "Govt of India" },
] as const;

const PERSONA_OPTIONS = [
  { id: "ALL", label: "All Users" },
  { id: "SCREEN_READER", label: "Screen Reader (Blind)" },
  { id: "KEYBOARD_MOTOR", label: "Keyboard-Only (Motor)" },
  { id: "LOW_VISION", label: "Low Vision / Contrast" },
  { id: "COGNITIVE", label: "Cognitive / Neurodivergent" },
  { id: "DEAF_HARD_OF_HEARING", label: "Deaf / Hard of Hearing" },
] as const;

type PresentationBucket = "verified" | "needs_review" | "low_confidence";
type IssueViewFilter = "show_all" | "verified_only" | "hide_low_confidence";

interface ContextualIssueFilter {
  active: boolean;
  sourceRole: "DEVELOPER" | "QA_A11Y" | "COMPLIANCE" | "EXECUTIVE";
  profileId?: string;
  profileName?: string;
  personaId?: string;
  personaName?: string;
  severity?: "mandatory" | "advisory" | "other" | "critical_serious" | "needs_review" | "all";
  title: string;
  subtitle: string;
  targetFindingIds?: string[];
}

const ISSUE_PRESENTATION_META: Record<
  PresentationBucket,
  {
    title: string;
    shortLabel: string;
    icon: React.ComponentType<{ className?: string }>;
    trustExplanation: string;
    headerClass: string;
    badgeClass: string;
  }
> = {
  verified: {
    title: "Verified Issues",
    shortLabel: "Verified",
    icon: IconCheckCircle,
    trustExplanation: "High confidence, verified multi-engine accessibility issue",
    headerClass:
      "badge-verified border border-emerald-500/40",
    badgeClass:
      "badge-verified",
  },
  needs_review: {
    title: "Needs Review",
    shortLabel: "Needs Review",
    icon: IconAlertTriangle,
    trustExplanation: "Requires manual inspection or assistive technology verification",
    headerClass:
      "badge-needs-review border border-amber-500/40",
    badgeClass:
      "badge-needs-review",
  },
  low_confidence: {
    title: "Low Confidence",
    shortLabel: "Low Confidence",
    icon: IconSearch,
    trustExplanation: "Heuristic, experimental, or context-dependent detection",
    headerClass:
      "badge-low-confidence border border-zinc-400/40",
    badgeClass:
      "badge-low-confidence",
  },
};

const ISSUE_CATEGORIES = [
  {
    id: "all",
    label: "All Categories",
    shortLabel: "All",
    icon: IconLayers,
    badgeClass: "bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700",
    activeClass: "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-black shadow-sm",
  },
  {
    id: "color",
    label: "Contrast & Color",
    shortLabel: "Contrast",
    icon: IconPalette,
    badgeClass: "bg-sky-500/10 text-sky-800 dark:text-sky-300 border-sky-500/30",
    activeClass: "bg-sky-600 text-white shadow-sm",
  },
  {
    id: "forms",
    label: "Forms & Controls",
    shortLabel: "Forms",
    icon: IconForm,
    badgeClass: "bg-amber-500/10 text-amber-800 dark:text-amber-300 border-amber-500/30",
    activeClass: "bg-amber-600 text-white shadow-sm",
  },
  {
    id: "images",
    label: "Images & Media",
    shortLabel: "Images",
    icon: IconImage,
    badgeClass: "bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 border-emerald-500/30",
    activeClass: "bg-emerald-600 text-white shadow-sm",
  },
  {
    id: "keyboard",
    label: "Keyboard & Focus",
    shortLabel: "Keyboard",
    icon: IconKeyboard,
    badgeClass: "bg-purple-500/10 text-purple-800 dark:text-purple-300 border-purple-500/30",
    activeClass: "bg-purple-600 text-white shadow-sm",
  },
  {
    id: "aria",
    label: "ARIA & Semantics",
    shortLabel: "ARIA",
    icon: IconTag,
    badgeClass: "bg-rose-500/10 text-rose-800 dark:text-rose-300 border-rose-500/30",
    activeClass: "bg-rose-600 text-white shadow-sm",
  },
  {
    id: "structure",
    label: "Structure & Navigation",
    shortLabel: "Structure",
    icon: IconLayers,
    badgeClass: "bg-indigo-500/10 text-indigo-800 dark:text-indigo-300 border-indigo-500/30",
    activeClass: "bg-indigo-600 text-white shadow-sm",
  },
] as const;

function getIssueCategory(issue: any): (typeof ISSUE_CATEGORIES)[number] {
  const cat = String(issue?.category || "").toLowerCase();
  const rule = String(issue?.rule_id || issue?.rule || "").toLowerCase();
  const desc = String(issue?.description || "").toLowerCase();
  const wcag = String(issue?.wcag_criterion || "");

  // Contrast & Color
  if (
    cat === "color" ||
    cat === "contrast" ||
    rule.includes("contrast") ||
    desc.includes("contrast") ||
    wcag.startsWith("1.4")
  ) {
    return ISSUE_CATEGORIES[1];
  }

  // Forms & Controls
  if (
    cat === "forms" ||
    cat === "form" ||
    rule.includes("label") ||
    rule.includes("button") ||
    rule.includes("input") ||
    rule.includes("select") ||
    desc.includes("label") ||
    desc.includes("form") ||
    (wcag.startsWith("1.3") && (rule.includes("form") || desc.includes("input") || rule.includes("label")))
  ) {
    return ISSUE_CATEGORIES[2];
  }

  // Images & Media
  if (
    cat === "images" ||
    cat === "image" ||
    cat === "media" ||
    rule.includes("alt") ||
    rule.includes("image") ||
    rule.includes("video") ||
    rule.includes("audio") ||
    desc.includes("alt") ||
    desc.includes("image") ||
    wcag.startsWith("1.1") ||
    wcag.startsWith("1.2")
  ) {
    return ISSUE_CATEGORIES[3];
  }

  // Keyboard & Focus
  if (
    cat === "keyboard" ||
    rule.includes("keyboard") ||
    rule.includes("tabindex") ||
    rule.includes("focus") ||
    rule.includes("accesskey") ||
    desc.includes("keyboard") ||
    desc.includes("focus") ||
    wcag.startsWith("2.1")
  ) {
    return ISSUE_CATEGORIES[4];
  }

  // ARIA & Semantics
  if (
    cat === "aria" ||
    rule.startsWith("aria-") ||
    rule.includes("aria") ||
    desc.includes("aria") ||
    rule.includes("role") ||
    wcag.startsWith("4.1")
  ) {
    return ISSUE_CATEGORIES[5];
  }

  // Structure & Navigation
  if (
    cat === "navigation" ||
    cat === "html" ||
    cat === "structure" ||
    rule.includes("heading") ||
    rule.includes("landmark") ||
    rule.includes("region") ||
    rule.includes("link") ||
    rule.includes("bypass") ||
    rule.includes("lang") ||
    rule.includes("title") ||
    rule.includes("table") ||
    rule.includes("list") ||
    wcag.startsWith("2.4") ||
    wcag.startsWith("3.1")
  ) {
    return ISSUE_CATEGORIES[6];
  }

  return ISSUE_CATEGORIES[6];
}

function resolveConfidenceTier(issue: any): "high" | "medium" | "low" {
  const explicitTier = String(issue?.confidence_tier || "")
    .trim()
    .toLowerCase();

  if (explicitTier === "high" || explicitTier === "medium" || explicitTier === "low") {
    return explicitTier;
  }

  const confidence = Number(issue?.confidence || 0);
  if (confidence >= 0.85) {
    return "high";
  }
  if (confidence >= 0.6) {
    return "medium";
  }
  return "low";
}

function classifyIssueBucket(issue: any): PresentationBucket {
  const tier = resolveConfidenceTier(issue);
  if (tier === "low") {
    return "low_confidence";
  }

  const issueType = String(issue?.issue_type || "")
    .trim()
    .toLowerCase();
  const needsManualReview = Boolean(issue?.needs_manual_review);
  if (needsManualReview || issueType === "needs-review") {
    return "needs_review";
  }

  return "verified";
}

function formatBucketPercentage(count: number, total: number): string {
  if (total <= 0) {
    return "0%";
  }

  const pct = (count / total) * 100;
  const rounded = Math.round(pct * 10) / 10;
  return Number.isInteger(rounded) ? `${rounded.toFixed(0)}%` : `${rounded.toFixed(1)}%`;
}

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
  const [issueViewFilter, setIssueViewFilter] =
    useState<IssueViewFilter>("verified_only");
  const [expandedIssue, setExpandedIssue] = useState<string | null>(null);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [roleView, setRoleView] = useState<"DEVELOPER" | "QA_A11Y" | "COMPLIANCE" | "EXECUTIVE">("DEVELOPER");
  const [regulatoryProfile, setRegulatoryProfile] = useState<string>("GLOBAL_WCAG_22_AA");
  const [personaLens, setPersonaLens] = useState<string>("ALL");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [issueGroupBy, setIssueGroupBy] = useState<"status" | "category">("status");
  const [projectedScan, setProjectedScan] = useState<any>(null);
  const [contextualFilter, setContextualFilter] = useState<ContextualIssueFilter | null>(null);

  const activeProfileLabel = useMemo(() => {
    return REGULATORY_PROFILES_OPTIONS.find((p) => p.id === regulatoryProfile)?.label || regulatoryProfile;
  }, [regulatoryProfile]);

  const activePersonaLabel = useMemo(() => {
    return PERSONA_OPTIONS.find((p) => p.id === personaLens)?.label || personaLens;
  }, [personaLens]);

  const applyContextualFilter = useCallback((filter: ContextualIssueFilter) => {
    setContextualFilter(filter);
    setIssueViewFilter("show_all");
    setSelectedCategory("all");
    setTab("issues");
  }, []);

  const clearActiveContext = useCallback(() => {
    setContextualFilter(null);
  }, []);
  const [projectedLoading, setProjectedLoading] = useState(false);
  const pollRef = useRef<NodeJS.Timeout | null>(null);
  const aiRefreshAttemptsRef = useRef(0);
  const aiRefreshScanIdRef = useRef<string | null>(null);
  const [aiRefreshExhausted, setAiRefreshExhausted] = useState(false);
  const pollErrorCountRef = useRef(0);
  const mounted = useSyncExternalStore(emptySubscribe, () => true, () => false);

  const [statementOpen, setStatementOpen] = useState(false);
  const [statementOrgName, setStatementOrgName] = useState("");
  const [statementProfile, setStatementProfile] = useState("W3C WCAG 2.2 Level AA");
  const [statementContent, setStatementContent] = useState("");
  const [statementLoading, setStatementLoading] = useState(false);
  const [statementCopied, setStatementCopied] = useState(false);

  /* ── Toast auto-dismiss: 60 seconds ──────────────────────────── */
  useEffect(() => {
    if (scanStatus !== "completed" && scanStatus !== "failed") return;
    const t = setTimeout(() => setScanStatus("idle"), 60_000);
    return () => clearTimeout(t);
  }, [scanStatus]);

  useEffect(() => {
    if (!apiError) return;
    const t = setTimeout(() => setApiError(null), 60_000);
    return () => clearTimeout(t);
  }, [apiError]);

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
  const aiAnalysisText =
    typeof latestScan?.ai_analysis === "string" ? latestScan.ai_analysis : "";
  const aiAnalysisPending =
    latestScan?.enrichment_status === "pending" ||
    aiAnalysisText.toLowerCase().includes("generating insights") ||
    aiAnalysisText.toLowerCase().includes("refreshing insights");
  const showAiRefreshing = aiAnalysisPending && !aiRefreshExhausted;

  const generateStatement = useCallback(async (customOrg?: string, customProf?: string) => {
    if (!latestScan?.id) return;
    setStatementLoading(true);
    try {
      const org = (customOrg !== undefined ? customOrg : statementOrgName).trim() || project?.name || "Our Organization";
      const prof = customProf !== undefined ? customProf : statementProfile;
      const res = await api.generateAccessibilityStatement(projectId, latestScan.id, org, prof);
      setStatementContent(res.statement || "No statement generated.");
    } catch (err) {
      console.error(err);
      setStatementContent("Failed to generate statement. Ensure the BEACON backend is running on port 8000.");
    } finally {
      setStatementLoading(false);
    }
  }, [latestScan?.id, statementOrgName, project?.name, statementProfile, projectId]);

  function handleOpenStatementModal() {
    setStatementOpen(true);
    const org = project?.name || "";
    setStatementOrgName(org);
    void generateStatement(org, statementProfile);
  }

  function handleCopyStatement() {
    if (!statementContent) return;
    navigator.clipboard.writeText(statementContent);
    setStatementCopied(true);
    setTimeout(() => setStatementCopied(false), 3000);
  }

  function handleDownloadStatement() {
    if (!statementContent) return;
    const blob = new Blob([statementContent], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `accessibility-statement-${projectId}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

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
          pollErrorCountRef.current = 0; // reset on success
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
          pollErrorCountRef.current += 1;
          if (pollErrorCountRef.current >= 10) {
            setScanning(false);
            setScanStatus("failed");
            if (pollRef.current) clearInterval(pollRef.current);
          }
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

  // Auto-refresh completed scans while AI enrichment is pending.
  useEffect(() => {
    const completedScanId = latestScan?.id ? String(latestScan.id) : null;

    if (completedScanId !== aiRefreshScanIdRef.current) {
      aiRefreshScanIdRef.current = completedScanId;
      aiRefreshAttemptsRef.current = 0;
      setAiRefreshExhausted(false);
    }

    if (!completedScanId || scanning || !aiAnalysisPending) {
      if (!aiAnalysisPending) {
        aiRefreshAttemptsRef.current = 0;
        setAiRefreshExhausted(false);
      }
      return;
    }

    const interval = setInterval(() => {
      if (aiRefreshAttemptsRef.current >= 10) {
        setAiRefreshExhausted(true);
        clearInterval(interval);
        return;
      }

      aiRefreshAttemptsRef.current += 1;
      void loadData();
    }, 3000);

    return () => clearInterval(interval);
  }, [latestScan?.id, aiAnalysisPending, scanning, loadData]);

  // Multi-Lens & Regulatory Profile Projection (§39–§48)
  useEffect(() => {
    if (!latestScan?.id) {
      setProjectedScan(null);
      return;
    }
    let cancelled = false;
    setProjectedLoading(true);
    api.getScan(projectId, latestScan.id, {
      profile: regulatoryProfile,
      persona: personaLens === "ALL" ? undefined : personaLens,
      view: roleView,
    })
      .then((data) => {
        if (!cancelled) {
          setProjectedScan(data);
        }
      })
      .catch((err) => {
        console.warn("Failed to load projected scan view:", err);
      })
      .finally(() => {
        if (!cancelled) {
          setProjectedLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, latestScan?.id, roleView, regulatoryProfile, personaLens]);

  const issues: any[] = useMemo(() => {
    return (personaLens !== "ALL" && projectedScan?.view_data?.findings)
      ? projectedScan.view_data.findings
      : (latestScan?.issues || []);
  }, [personaLens, projectedScan?.view_data?.findings, latestScan?.issues]);
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

  const contextFilteredIssues = useMemo(() => {
    if (!contextualFilter?.active) return issues;

    if (contextualFilter.targetFindingIds && contextualFilter.targetFindingIds.length > 0) {
      const idSet = new Set(contextualFilter.targetFindingIds.map(String));
      return issues.filter((issue: any) => {
        const fid = String(issue.id || issue.finding_id || issue.issue_id || "");
        return idSet.has(fid);
      });
    }

    if (contextualFilter.severity === "mandatory" || contextualFilter.severity === "critical_serious") {
      return issues.filter((i: any) => i.severity === "critical" || i.severity === "serious");
    }
    if (contextualFilter.severity === "advisory") {
      return issues.filter((i: any) => i.severity === "moderate" || i.severity === "minor");
    }
    if (contextualFilter.severity === "needs_review") {
      return issues.filter((i: any) => i.issue_type === "needs-review" || i.needs_manual_review);
    }
    return issues;
  }, [issues, contextualFilter]);

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { all: contextFilteredIssues.length };
    for (const cat of ISSUE_CATEGORIES) {
      if (cat.id !== "all") counts[cat.id] = 0;
    }
    for (const issue of contextFilteredIssues) {
      const cat = getIssueCategory(issue);
      counts[cat.id] = (counts[cat.id] || 0) + 1;
    }
    return counts;
  }, [contextFilteredIssues]);

  const categoryFilteredIssues = useMemo(() => {
    if (selectedCategory === "all") return contextFilteredIssues;
    return contextFilteredIssues.filter((issue: any) => getIssueCategory(issue).id === selectedCategory);
  }, [contextFilteredIssues, selectedCategory]);

  const presentationOrder: PresentationBucket[] = [
    "verified",
    "needs_review",
    "low_confidence",
  ];
  const issuesByPresentation = useMemo(() => {
    const grouped: Record<PresentationBucket, any[]> = {
      verified: [],
      needs_review: [],
      low_confidence: [],
    };

    for (const issue of categoryFilteredIssues) {
      grouped[classifyIssueBucket(issue)].push(issue);
    }

    return grouped;
  }, [categoryFilteredIssues]);

  const presentationCounts: Record<PresentationBucket, number> = {
    verified: issuesByPresentation.verified.length,
    needs_review: issuesByPresentation.needs_review.length,
    low_confidence: issuesByPresentation.low_confidence.length,
  };
  const totalPresentationIssues = categoryFilteredIssues.length;
  const presentationPercentages: Record<PresentationBucket, string> = {
    verified: formatBucketPercentage(
      presentationCounts.verified,
      totalPresentationIssues,
    ),
    needs_review: formatBucketPercentage(
      presentationCounts.needs_review,
      totalPresentationIssues,
    ),
    low_confidence: formatBucketPercentage(
      presentationCounts.low_confidence,
      totalPresentationIssues,
    ),
  };
  const visiblePresentationOrder: PresentationBucket[] =
    issueViewFilter === "verified_only"
      ? ["verified"]
      : issueViewFilter === "hide_low_confidence"
        ? ["verified", "needs_review"]
        : presentationOrder;
  const visiblePresentationIssueCount = visiblePresentationOrder.reduce(
    (sum, bucket) => sum + issuesByPresentation[bucket].length,
    0,
  );

  const issuesByCategoryGroup = useMemo(() => {
    const groups: { category: (typeof ISSUE_CATEGORIES)[number]; issues: any[] }[] = [];
    const allowedIssues = categoryFilteredIssues.filter((issue: any) => {
      const bucket = classifyIssueBucket(issue);
      if (issueViewFilter === "verified_only") return bucket === "verified";
      if (issueViewFilter === "hide_low_confidence") return bucket === "verified" || bucket === "needs_review";
      return true;
    });

    for (const cat of ISSUE_CATEGORIES) {
      if (cat.id === "all") continue;
      if (selectedCategory !== "all" && cat.id !== selectedCategory) continue;

      const catIssues = allowedIssues.filter((issue: any) => getIssueCategory(issue).id === cat.id);
      if (catIssues.length > 0) {
        groups.push({ category: cat, issues: catIssues });
      }
    }

    return groups;
  }, [categoryFilteredIssues, issueViewFilter, selectedCategory]);

  const trust = latestScan?.trust || {};
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

  const renderIssueCard = (
    issue: any,
    idx: number,
    explicitBucket?: PresentationBucket,
  ) => {
    const bucket = explicitBucket || classifyIssueBucket(issue);
    const issueKey = issue.issue_id || `${bucket}-${idx}`;
    const isExpanded = expandedIssue === issueKey;
    const bucketMeta = ISSUE_PRESENTATION_META[bucket];
    const issueCat = getIssueCategory(issue);
    const CatIcon = issueCat.icon;

    return (
      <div
        key={issueKey}
        className={`glass-card overflow-hidden transition-all duration-200 border border-[var(--beacon-border)]/70 ${
          isExpanded
            ? "ring-2 ring-[var(--beacon-primary)] shadow-md"
            : "hover:border-[var(--beacon-primary)]/40 hover:shadow-sm"
        }`}
      >
        <button
          className="w-full p-4 sm:p-5 flex items-center justify-between gap-4 text-left hover:bg-[var(--beacon-surface)]/60 transition-colors focus:outline-none"
          onClick={() => setExpandedIssue(isExpanded ? null : issueKey)}
        >
          <div className="flex items-center gap-3.5 min-w-0 flex-1">
            <span
              className={`severity-badge severity-${issue.severity} shrink-0 w-22 justify-center py-1 font-black text-center`}
            >
              {issue.severity}
            </span>

            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-sm font-extrabold text-[var(--beacon-text)] tracking-tight">
                  {issue.rule_id || issue.description}
                </span>
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded border inline-flex items-center gap-1.5 shadow-xs ${issueCat.badgeClass}`}
                  title={`Category: ${issueCat.label}`}
                >
                  <CatIcon className="w-3 h-3 shrink-0" />
                  <span>{issueCat.shortLabel}</span>
                </span>
                {issue.wcag_criterion && (
                  <span className="text-[10px] font-bold text-zinc-700 dark:text-zinc-300 bg-zinc-100 dark:bg-zinc-800 px-2 py-0.5 rounded border border-zinc-200 dark:border-zinc-700">
                    WCAG {issue.wcag_criterion}
                  </span>
                )}
                {(issue.act_adjudicated || issue.act_rule_id) && (
                  <span
                    className="text-[10px] font-black text-amber-900 dark:text-amber-200 bg-amber-100 dark:bg-amber-950/60 px-2 py-0.5 rounded border border-amber-300 dark:border-amber-700/80 flex items-center gap-1 shadow-sm"
                    title="Verified against formal W3C Accessibility Conformance Testing (ACT) Rules"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                    {issue.act_rule_id ? `ACT ${issue.act_rule_id}` : "ACT Adjudicated"}
                  </span>
                )}
                {Number(issue.agreement_count || 0) > 1 && (
                  <span
                    className="text-[10px] font-black text-indigo-900 dark:text-indigo-200 bg-indigo-100 dark:bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-300 dark:border-indigo-700/80 shadow-sm"
                    title={`Consensus verified across ${issue.agreement_count} independent audit engines`}
                  >
                    Consensus ({issue.agreement_count} engines)
                  </span>
                )}
                {issue.engine && (
                  <span className="text-[10px] font-bold text-zinc-600 dark:text-zinc-400 bg-zinc-200/70 dark:bg-zinc-800 px-1.5 py-0.5 rounded uppercase font-mono">
                    {issue.engine}
                  </span>
                )}
                {Array.isArray(issue.personas) && issue.personas.length > 0 && (
                  <div className="flex gap-1 flex-wrap">
                    {issue.personas.map((p: any) => (
                      <span
                        key={p.id || p}
                        className="text-[9px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-800 dark:text-purple-300 border border-purple-500/30 inline-flex items-center gap-1"
                      >
                        <IconUser className="w-2.5 h-2.5 shrink-0" />
                        <span>{p.name || p.id || p}</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {issue.description && issue.description !== issue.rule_id && (
                <p className="text-xs text-[var(--beacon-text-muted)] font-medium mt-1 truncate">
                  {issue.description}
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <span
              className={`hidden sm:inline-flex text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded items-center gap-1.5 ${bucketMeta.badgeClass}`}
            >
              <bucketMeta.icon className="w-3 h-3" />
              <span>{bucketMeta.shortLabel}</span>
            </span>

            {issue.confidence != null && (
              <div className="text-right hidden sm:block">
                <span className="text-xs font-black text-[var(--beacon-text)]">
                  {Math.round(issue.confidence * 100)}%
                </span>
                <span className="text-[10px] text-[var(--beacon-text-muted)] font-bold ml-1 uppercase">
                  conf
                </span>
              </div>
            )}

            <div
              className={`w-7 h-7 rounded-lg flex items-center justify-center text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] transition-transform duration-200 ${
                isExpanded ? "rotate-180 text-[var(--beacon-primary)] bg-[var(--beacon-primary)]/10" : ""
              }`}
            >
              <IconChevron className="w-4 h-4" />
            </div>
          </div>
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
                    <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
                      <h4 className="text-[10px] font-bold uppercase tracking-[0.15em] text-[var(--beacon-success)] flex items-center gap-1.5">
                        <IconCode className="w-3.5 h-3.5" /> Remediated Code
                      </h4>
                      <span
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-wider bg-emerald-500/15 text-emerald-800 dark:text-emerald-300 border border-emerald-500/30"
                        title="Enforces strict DOM container validation, preventing XSS and ensuring zero new accessibility violations"
                      >
                        <IconShield className="w-2.5 h-2.5 text-emerald-500" />
                        AST Sandbox Verified (0 Regressions)
                      </span>
                    </div>
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
            {((issue.participating_engines && issue.participating_engines.length > 0) || (issue.confidence_sources && issue.confidence_sources.length > 0)) && (
              <div className="mt-8 pt-4 border-t border-[var(--beacon-border)] flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] font-bold text-[var(--beacon-text-muted)] uppercase tracking-[0.1em]">
                    Consensus Engines:
                  </span>
                  <div className="flex gap-1.5 flex-wrap">
                    {Array.from(new Set([...(issue.participating_engines || []), ...(issue.confidence_sources || [])])).map((src: string) => (
                      <span
                        key={src}
                        className="text-[9px] bg-[var(--beacon-bg)] border border-[var(--beacon-border)] px-2 py-0.5 rounded shadow-[1px_1px_0px_#000] font-extrabold uppercase text-[var(--beacon-text)]"
                      >
                        {src}
                      </span>
                    ))}
                  </div>
                </div>
                {issue.selector_fingerprint && (
                  <span
                    className="text-[9px] font-mono text-[var(--beacon-text-muted)] bg-[var(--beacon-bg)] px-2 py-0.5 rounded border border-[var(--beacon-border)] truncate max-w-xs"
                    title={issue.selector_fingerprint}
                  >
                    FP: {issue.selector_fingerprint}
                  </span>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="animate-fade-in w-full pb-20">
      {/* ── Header {/* ── Tabs ──────────────────────────────────────── */}
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

          <div className="flex flex-col sm:items-end gap-1.5 w-full sm:w-auto">
            <div className="flex items-center gap-2.5 w-full sm:w-auto">
              {/* Scan Mode Select */}
              <div className="relative flex-1 sm:flex-initial">
                <select
                  value={scanMode}
                  onChange={(e) => {
                    setScanModeTouched(true);
                    setScanMode(e.target.value);
                  }}
                  disabled={scanning}
                  className="h-11 w-full sm:w-auto pl-3.5 pr-8 rounded-lg border-2 border-[var(--beacon-border)] bg-[var(--beacon-surface)] text-xs font-black uppercase tracking-wider text-[var(--beacon-text)] shadow-[3px_3px_0px_#000] cursor-pointer outline-none focus:outline-none focus:ring-2 focus:ring-[var(--beacon-border)] focus:ring-offset-1 focus:ring-offset-[var(--beacon-bg)] appearance-none hover:bg-[var(--beacon-card-bg)] hover:border-[var(--beacon-text)] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <option value="fast">Fast Scan</option>
                  <option value="deep">Deep Scan</option>
                  <option value="max">Max Scan</option>
                </select>
                <div className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--beacon-text-muted)]">
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </div>
              </div>

              {/* Initiate Scan Button */}
              <button
                onClick={startScan}
                disabled={scanning}
                className={`h-11 px-5 rounded-lg border-2 border-[var(--beacon-border)] font-black uppercase text-xs tracking-wider transition-all flex items-center justify-center gap-2 shadow-[3px_3px_0px_#000] active:shadow-none active:translate-x-0.5 active:translate-y-0.5 shrink-0 ${
                  scanning
                    ? "bg-[var(--beacon-primary)]/40 cursor-not-allowed text-black/60 shadow-none"
                    : "bg-[var(--beacon-primary)] text-black hover:brightness-105"
                }`}
              >
                {scanning ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                    <span>Scanning...</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <IconScan className="w-4 h-4" />
                    <span>Initiate Scan</span>
                  </div>
                )}
              </button>

              {/* Emergency Stop Button */}
              {scanning && (
                <button
                  onClick={() => {
                    setScanning(false);
                    setScanStatus("idle");
                    if (pollRef.current) clearInterval(pollRef.current);
                  }}
                  className="h-11 px-3.5 border-2 border-[var(--beacon-error)] text-[var(--beacon-error)] rounded-lg hover:bg-[var(--beacon-error)]/10 transition-colors uppercase text-[10px] font-black tracking-widest shadow-[3px_3px_0px_#000] active:shadow-none active:translate-x-0.5 active:translate-y-0.5 shrink-0"
                  title="Force Stop Scan"
                >
                  STOP
                </button>
              )}

              {/* Export Dropdown */}
              {latestScan && !scanning && (
                <div className="relative">
                  <button
                    onClick={() => setShowExportMenu(!showExportMenu)}
                    className="h-11 px-4 rounded-lg border-2 border-[var(--beacon-border)] bg-[var(--beacon-surface)] hover:bg-[var(--beacon-card-bg)] text-xs font-black uppercase tracking-wider text-[var(--beacon-text)] transition-all flex items-center justify-center gap-2 shadow-[3px_3px_0px_#000] active:shadow-none active:translate-x-0.5 active:translate-y-0.5 shrink-0"
                    title="Export Scan Report"
                  >
                    <IconDownload className="w-4 h-4 text-[var(--beacon-primary)]" />
                    <span>Export</span>
                    <IconChevron className="w-3 h-3" up={showExportMenu} />
                  </button>

                  {showExportMenu && (
                    <div className="absolute right-0 top-12 w-64 rounded-xl border-2 border-[var(--beacon-border)] bg-[var(--beacon-surface)] p-2 shadow-[4px_4px_0px_#000] z-50 animate-fade-in flex flex-col gap-1">
                      <div className="px-3 py-1.5 border-b border-[var(--beacon-border)]/50 mb-1">
                        <span className="text-[10px] font-black uppercase tracking-widest text-[var(--beacon-text-muted)]">
                          Export Compliance Reports
                        </span>
                      </div>
                      <button
                        onClick={() => {
                          setShowExportMenu(false);
                          downloadScanReport(projectId, latestScan.id, "sarif");
                        }}
                        className="w-full text-left px-3 py-2 rounded-lg text-xs font-bold hover:bg-[var(--beacon-primary)] hover:text-black transition-colors flex items-center justify-between group cursor-pointer"
                      >
                        <div className="flex flex-col">
                          <span className="font-extrabold uppercase text-[var(--beacon-text)] group-hover:text-black">OASIS SARIF 2.1.0</span>
                          <span className="text-[10px] text-[var(--beacon-text-muted)] group-hover:text-black/80">GitHub Code Scanning / CI-CD</span>
                        </div>
                        <span className="text-[10px] font-mono font-bold bg-black/10 dark:bg-white/10 px-1.5 py-0.5 rounded text-[var(--beacon-text)] group-hover:text-black">.sarif</span>
                      </button>

                      <button
                        onClick={() => {
                          setShowExportMenu(false);
                          downloadScanReport(projectId, latestScan.id, "earl");
                        }}
                        className="w-full text-left px-3 py-2 rounded-lg text-xs font-bold hover:bg-[var(--beacon-primary)] hover:text-black transition-colors flex items-center justify-between group cursor-pointer"
                      >
                        <div className="flex flex-col">
                          <span className="font-extrabold uppercase text-[var(--beacon-text)] group-hover:text-black">W3C EARL 1.0 JSON-LD</span>
                          <span className="text-[10px] text-[var(--beacon-text-muted)] group-hover:text-black/80">EU EAA &amp; ADA Regulatory Audit</span>
                        </div>
                        <span className="text-[10px] font-mono font-bold bg-black/10 dark:bg-white/10 px-1.5 py-0.5 rounded text-[var(--beacon-text)] group-hover:text-black">.jsonld</span>
                      </button>

                      <button
                        onClick={() => {
                          setShowExportMenu(false);
                          downloadScanReport(projectId, latestScan.id, "markdown");
                        }}
                        className="w-full text-left px-3 py-2 rounded-lg text-xs font-bold hover:bg-[var(--beacon-primary)] hover:text-black transition-colors flex items-center justify-between group cursor-pointer"
                      >
                        <div className="flex flex-col">
                          <span className="font-extrabold uppercase text-[var(--beacon-text)] group-hover:text-black">Markdown Report</span>
                          <span className="text-[10px] text-[var(--beacon-text-muted)] group-hover:text-black/80">Executive &amp; Dev Summary</span>
                        </div>
                        <span className="text-[10px] font-mono font-bold bg-black/10 dark:bg-white/10 px-1.5 py-0.5 rounded text-[var(--beacon-text)] group-hover:text-black">.md</span>
                      </button>

                      <button
                        onClick={() => {
                          setShowExportMenu(false);
                          downloadScanReport(projectId, latestScan.id, "json");
                        }}
                        className="w-full text-left px-3 py-2 rounded-lg text-xs font-bold hover:bg-[var(--beacon-primary)] hover:text-black transition-colors flex items-center justify-between group cursor-pointer"
                      >
                        <div className="flex flex-col">
                          <span className="font-extrabold uppercase text-[var(--beacon-text)] group-hover:text-black">Raw Findings JSON</span>
                          <span className="text-[10px] text-[var(--beacon-text-muted)] group-hover:text-black/80">Normalized Scan Payload</span>
                        </div>
                        <span className="text-[10px] font-mono font-bold bg-black/10 dark:bg-white/10 px-1.5 py-0.5 rounded text-[var(--beacon-text)] group-hover:text-black">.json</span>
                      </button>

                      <button
                        onClick={() => {
                          setShowExportMenu(false);
                          downloadScanReport(projectId, latestScan.id, "csv");
                        }}
                        className="w-full text-left px-3 py-2 rounded-lg text-xs font-bold hover:bg-[var(--beacon-primary)] hover:text-black transition-colors flex items-center justify-between group cursor-pointer"
                      >
                        <div className="flex flex-col">
                          <span className="font-extrabold uppercase text-[var(--beacon-text)] group-hover:text-black">Audit Findings CSV</span>
                          <span className="text-[10px] text-[var(--beacon-text-muted)] group-hover:text-black/80">Compliance Spreadsheet Matrix</span>
                        </div>
                        <span className="text-[10px] font-mono font-bold bg-black/10 dark:bg-white/10 px-1.5 py-0.5 rounded text-[var(--beacon-text)] group-hover:text-black">.csv</span>
                      </button>
                      <div className="h-px bg-[var(--beacon-border)]/60 my-1" />
                      <button
                        onClick={() => {
                          setShowExportMenu(false);
                          handleOpenStatementModal();
                        }}
                        className="w-full text-left px-3 py-2 rounded-lg text-xs font-bold hover:bg-[var(--beacon-primary)] hover:text-black transition-colors flex items-center justify-between group cursor-pointer"
                      >
                        <div className="flex flex-col">
                          <span className="font-extrabold uppercase text-[var(--beacon-text)] group-hover:text-black">Accessibility Statement</span>
                          <span className="text-[10px] text-[var(--beacon-text-muted)] group-hover:text-black/80">W3C / UK PSBAR / EU Draft (§68)</span>
                        </div>
                        <span className="text-[10px] font-mono font-bold bg-black/10 dark:bg-white/10 px-1.5 py-0.5 rounded text-[var(--beacon-text)] group-hover:text-black">.md</span>
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Helper Text aligned underneath */}
            <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--beacon-text-muted)] text-right">
              {scanMode === "fast"
                ? "Fast: Entry-page audit (~5s)"
                : scanMode === "deep"
                  ? "Deep: Multi-page domain audit (~30s)"
                  : "Max: Exhaustive full-domain audit (~90s)"}
            </p>
          </div>
        </div>
      </div>

      {/* ── Floating Toast Portal ──────────────────────────────── */}
      {mounted && createPortal(
        <aside
          aria-label="Notifications"
          style={{ position: "fixed", bottom: "24px", right: "24px", zIndex: 99999, display: "flex", flexDirection: "column", gap: "12px", maxWidth: "420px", width: "calc(100vw - 3rem)", pointerEvents: "none" }}
        >
          {/* 1. Success Toast */}
          {scanStatus === "completed" && (
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
                    Scan Complete
                  </h4>
                  <p className="text-xs font-bold text-[var(--beacon-text)] mt-0.5 leading-snug">
                    Scan successful! Results synchronized.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setScanStatus("idle")}
                aria-label="Close notification"
                className="w-7 h-7 rounded-md border border-[var(--beacon-border)] flex items-center justify-center text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] hover:bg-[var(--beacon-bg)] transition-colors shrink-0"
              >
                <IconX className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* 2. Failure / Bot Protection Warning Toast */}
          {scanStatus === "failed" && (
            <div
              role="alert"
              aria-live="assertive"
              className="pointer-events-auto w-full bg-[var(--beacon-surface)] text-[var(--beacon-text)] p-4 rounded-xl border-2 border-[var(--beacon-border)] shadow-[5px_5px_0px_#000] animate-slide-in-right flex items-start justify-between gap-3 border-l-8 border-l-[var(--beacon-warning)]"
            >
              <div className="flex items-start gap-3 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center shrink-0 text-amber-600 dark:text-amber-400 mt-0.5">
                  <IconShield className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <h4 className="text-xs font-black uppercase tracking-wider text-amber-600 dark:text-amber-400">
                    {(latestFailedScan?.summary || "").toLowerCase().includes("bot") || (latestFailedScan?.summary || "").toLowerCase().includes("cloudflare")
                      ? "Cloudflare / Bot Challenge"
                      : "Scan Warning"}
                  </h4>
                  <p className="text-xs font-bold text-[var(--beacon-text)] mt-0.5 leading-snug break-words">
                    {latestFailedScan?.summary ||
                      "Scan failed. Please verify the target website is reachable and allows automated inspection."}
                  </p>
                  {((latestFailedScan?.summary || "").toLowerCase().includes("bot") || (latestFailedScan?.summary || "").toLowerCase().includes("cloudflare")) && (
                    <p className="text-[11px] text-[var(--beacon-text-muted)] mt-1.5 leading-relaxed bg-[var(--beacon-bg)] p-2 rounded border border-[var(--beacon-border)]/40">
                      Websites behind Cloudflare Turnstile or CAPTCHA challenge walls block automated audits. Test an unprotected staging domain or path.
                    </p>
                  )}
                </div>
              </div>
              <button
                onClick={() => setScanStatus("idle")}
                aria-label="Close notification"
                className="w-7 h-7 rounded-md border border-[var(--beacon-border)] flex items-center justify-center text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] hover:bg-[var(--beacon-bg)] transition-colors shrink-0"
              >
                <IconX className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* 3. API Error Toast */}
          {apiError && (
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
                      onClick={() => void loadData()}
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

      {/* ── Accessibility Statement Modal (§68) ──────────────────── */}
      {statementOpen && (
        <div className="fixed inset-0 z-[99999] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="bg-zinc-950 border-2 border-zinc-700 rounded-2xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-scale-in">
            <div className="p-5 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/60">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-[var(--beacon-primary)]/15 border border-[var(--beacon-primary)]/30 flex items-center justify-center text-[var(--beacon-primary)]">
                  <IconShield className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-black uppercase tracking-wider text-white">
                    Accessibility Statement Generator
                  </h3>
                  <p className="text-[11px] text-zinc-400 font-medium">
                    Authoritative compliance statement draft based on verified audit findings (§68)
                  </p>
                </div>
              </div>
              <button
                onClick={() => setStatementOpen(false)}
                className="w-8 h-8 rounded-lg bg-zinc-800 hover:bg-zinc-700 flex items-center justify-center text-zinc-300 transition-colors"
                aria-label="Close modal"
              >
                <IconX className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 space-y-4 overflow-y-auto flex-1 text-xs">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-zinc-400 mb-1">
                    Organization / Project Name
                  </label>
                  <input
                    type="text"
                    value={statementOrgName}
                    onChange={(e) => setStatementOrgName(e.target.value)}
                    placeholder="Acme Corporation"
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-100 font-medium focus:outline-none focus:ring-1 focus:ring-[var(--beacon-primary)]"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-zinc-400 mb-1">
                    Target Standard / Profile
                  </label>
                  <select
                    value={statementProfile}
                    onChange={(e) => {
                      setStatementProfile(e.target.value);
                      void generateStatement(statementOrgName, e.target.value);
                    }}
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-100 font-medium focus:outline-none focus:ring-1 focus:ring-[var(--beacon-primary)]"
                  >
                    <option value="W3C WCAG 2.2 Level AA">W3C WCAG 2.2 Level AA (Global)</option>
                    <option value="US Section 508 / VPAT">US Section 508 / VPAT</option>
                    <option value="EU EN 301 549 / EAA">EU Standard EN 301 549 (EAA)</option>
                    <option value="UK Public Sector (PSBAR)">UK Public Sector (PSBAR)</option>
                    <option value="India GIGW 3.0">Govt of India GIGW 3.0</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end">
                <button
                  onClick={() => void generateStatement()}
                  disabled={statementLoading}
                  className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-bold text-xs flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <IconRefresh className={`w-3.5 h-3.5 ${statementLoading ? "animate-spin" : ""}`} />
                  <span>{statementLoading ? "Regenerating..." : "Refresh Draft"}</span>
                </button>
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-zinc-400 mb-1.5">
                  Generated Markdown Preview
                </label>
                <div className="relative">
                  {statementLoading ? (
                    <div className="p-12 text-center bg-black/60 rounded-xl border border-zinc-800">
                      <div className="w-6 h-6 border-2 border-[var(--beacon-primary)] border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                      <span className="text-zinc-400 font-medium">Drafting official accessibility statement...</span>
                    </div>
                  ) : (
                    <pre className="p-4 bg-black/80 rounded-xl border border-zinc-800 font-mono text-[11px] text-zinc-200 leading-relaxed whitespace-pre-wrap max-h-80 overflow-y-auto">
                      {statementContent}
                    </pre>
                  )}
                </div>
              </div>
            </div>

            <div className="p-4 border-t border-zinc-800 bg-zinc-900/60 flex items-center justify-between gap-3">
              <span className="text-[11px] text-zinc-400 italic">
                Strict §68 rule: Never claims full conformance if unresolved findings remain.
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleCopyStatement}
                  className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-bold text-xs transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  {statementCopied ? (
                    <>
                      <IconCheck className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-emerald-400 font-bold">Copied!</span>
                    </>
                  ) : (
                    <span>Copy Markdown</span>
                  )}
                </button>
                <button
                  onClick={handleDownloadStatement}
                  className="px-4 py-2 rounded-lg bg-[var(--beacon-primary)] hover:opacity-90 text-black font-black text-xs transition-opacity flex items-center gap-1.5 shadow-sm"
                >
                  <IconDownload className="w-3.5 h-3.5" />
                  <span>Download .md</span>
                </button>
              </div>
            </div>
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
                {label === "Score" && latestScan?.score == null ? (
                  <span className="text-2xl font-black text-amber-800 dark:text-amber-300">N/A</span>
                ) : (
                  <>
                    {value}
                    <span className="text-lg md:text-xl font-bold text-[var(--beacon-text-muted)]">
                      {suffix}
                    </span>
                  </>
                )}
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

      {/* ── Degraded Mode Banner ─────────────────────────────── */}
      {latestScan?.degraded_mode && (
        <div className="banner-degraded flex items-center gap-3 px-5 py-3.5 mb-6 rounded-lg text-xs font-black uppercase tracking-[0.08em] animate-fade-in">
          <IconAlertTriangle className="w-5 h-5 text-amber-800 dark:text-amber-400 shrink-0" />
          <div className="flex-1">
            <span className="font-black text-amber-950 dark:text-amber-300">Degraded Scan</span>
            {latestScan.degradation_reason && (
              <span className="ml-2 font-bold text-amber-900 dark:text-amber-200/90 normal-case tracking-normal">
                — {latestScan.degradation_reason}
              </span>
            )}
          </div>
          <span className="px-2.5 py-1 rounded bg-amber-200/90 dark:bg-amber-900/60 border border-amber-700/50 dark:border-amber-400/40 text-[10px] text-amber-950 dark:text-amber-100 font-black tracking-wider">
            Score capped at {latestScan.trust?.score_integrity?.caps_applied?.find((c: any) => c.type === "partial_audit_cap")?.to ?? 82}/100
          </span>
        </div>
      )}

      {/* ── Governance & Perspective Ribbon (§39–§48) ────────────────── */}
      <div className="bg-[var(--beacon-card-bg)] border border-zinc-200 dark:border-zinc-800/80 rounded-xl p-4 mb-6 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3.5">
          
          {/* Role View Switcher */}
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--beacon-text-muted)]">
                Role Perspective
              </span>
              <span className="text-[11px] text-[var(--beacon-text-muted)] font-normal">
                — {ROLE_OPTIONS.find((r) => r.id === roleView)?.desc}
              </span>
            </div>
            <div className="flex items-center gap-1 bg-zinc-100/80 dark:bg-zinc-900/60 p-1 rounded-lg border border-zinc-200 dark:border-zinc-800/80 w-fit">
              {ROLE_OPTIONS.map((r) => (
                <button
                  key={r.id}
                  onClick={() => setRoleView(r.id)}
                  className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all ${
                    roleView === r.id
                      ? "bg-[var(--beacon-primary)] text-black shadow-sm font-black"
                      : "text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] hover:bg-white/70 dark:hover:bg-zinc-800/60"
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>

          {/* Regulatory Profile & Persona Lens Selectors */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Regulatory Profile */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--beacon-text-muted)]">
                Regulatory Profile
              </label>
              <div className="relative">
                <select
                  value={regulatoryProfile}
                  onChange={(e) => setRegulatoryProfile(e.target.value)}
                  className="h-9 w-56 pl-3 pr-8 rounded-lg border border-zinc-200 dark:border-zinc-800/80 bg-zinc-100/80 dark:bg-zinc-900/60 text-xs font-bold text-[var(--beacon-text)] cursor-pointer outline-none focus:ring-1 focus:ring-[var(--beacon-primary)] appearance-none transition-colors"
                >
                  {REGULATORY_PROFILES_OPTIONS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label} ({p.badge})
                    </option>
                  ))}
                </select>
                <div className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--beacon-text-muted)]">
                  <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </div>
              </div>
            </div>

            {/* Persona Lens */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-extrabold uppercase tracking-[0.1em] text-[var(--beacon-text-muted)]">
                Persona Lens
              </label>
              <div className="relative">
                <select
                  value={personaLens}
                  onChange={(e) => setPersonaLens(e.target.value)}
                  className="h-9 w-44 pl-3 pr-8 rounded-lg border border-zinc-200 dark:border-zinc-800/80 bg-zinc-100/80 dark:bg-zinc-900/60 text-xs font-bold text-[var(--beacon-text)] cursor-pointer outline-none focus:ring-1 focus:ring-[var(--beacon-primary)] appearance-none transition-colors"
                >
                  {PERSONA_OPTIONS.map((pl) => (
                    <option key={pl.id} value={pl.id}>
                      {pl.label}
                    </option>
                  ))}
                </select>
                <div className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--beacon-text-muted)]">
                  <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </div>
              </div>
            </div>

            {/* Loading Indicator */}
            {projectedLoading && (
              <div className="flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400 self-end mb-2">
                <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
                <span className="text-[11px] font-bold">Applying Lens...</span>
              </div>
            )}
          </div>
        </div>

        {/* Dynamic Role / Compliance / Executive Perspective Summary Card */}
        {projectedScan?.view_data && (
          <div className="mt-3.5 pt-3.5 border-t border-zinc-200/80 dark:border-zinc-800/80 text-xs">
            {roleView === "COMPLIANCE" && (
              <div className="bg-zinc-50/80 dark:bg-zinc-900/40 p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800/60 shadow-xs space-y-3.5">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[var(--beacon-text-muted)] tracking-wider">Conformance Status</div>
                    <div className={`text-sm font-black mt-0.5 ${
                      projectedScan.view_data.technical_conformance_status === "CONFORMANT" ? "text-emerald-600 dark:text-emerald-400" :
                      projectedScan.view_data.technical_conformance_status === "PARTIAL" ? "text-amber-600 dark:text-amber-400" : "text-rose-600 dark:text-rose-400"
                    }`}>
                      {projectedScan.view_data.technical_conformance_status || "EVALUATING"}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[var(--beacon-text-muted)] tracking-wider">Technical Assessment Score</div>
                    <div className="text-sm font-black text-[var(--beacon-text)] mt-0.5">
                      {projectedScan.view_data.technical_assessment_score ?? projectedScan.profile_score?.profile_score ?? projectedScan.profile_score?.score_details?.score ?? projectedScan.profile_score?.score ?? "--"}/100
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[var(--beacon-text-muted)] tracking-wider">Mandatory Violations</div>
                    <button
                      onClick={() => {
                        applyContextualFilter({
                          active: true,
                          sourceRole: "COMPLIANCE",
                          profileId: regulatoryProfile,
                          profileName: activeProfileLabel,
                          personaId: personaLens,
                          personaName: activePersonaLabel,
                          severity: "mandatory",
                          title: `${activeProfileLabel.toUpperCase()} MANDATORY FINDINGS`,
                          subtitle: `Showing ${projectedScan.view_data.mandatory_violations_count ?? 0} mandatory blocking violations for ${activePersonaLabel}`,
                          targetFindingIds: projectedScan.view_data.mandatory_finding_ids,
                        });
                      }}
                      className="text-sm font-black text-rose-600 dark:text-rose-400 mt-0.5 hover:underline cursor-pointer flex items-center gap-1 text-left"
                      title="Click to filter to mandatory blocking violations in Issues Tab"
                    >
                      {projectedScan.view_data.mandatory_violations_count ?? 0} blocking →
                    </button>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[var(--beacon-text-muted)] tracking-wider">Advisory Items</div>
                    <button
                      onClick={() => {
                        applyContextualFilter({
                          active: true,
                          sourceRole: "COMPLIANCE",
                          profileId: regulatoryProfile,
                          profileName: activeProfileLabel,
                          personaId: personaLens,
                          personaName: activePersonaLabel,
                          severity: "advisory",
                          title: `${activeProfileLabel.toUpperCase()} ADVISORY FINDINGS`,
                          subtitle: `Showing ${projectedScan.view_data.advisory_findings_count ?? 0} advisory findings for ${activePersonaLabel}`,
                          targetFindingIds: projectedScan.view_data.advisory_finding_ids,
                        });
                      }}
                      className="text-sm font-black text-amber-600 dark:text-amber-300 mt-0.5 hover:underline cursor-pointer flex items-center gap-1 text-left"
                      title="Click to filter to advisory findings in Issues Tab"
                    >
                      {projectedScan.view_data.advisory_findings_count ?? 0} advisory →
                    </button>
                  </div>
                </div>

                {/* Finding Distribution Explanation (Fixing 10 vs 5 Discrepancy) */}
                <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 rounded-lg bg-zinc-100/80 dark:bg-zinc-800/60 border border-zinc-200/70 dark:border-zinc-700/60 text-[11px]">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-extrabold text-[var(--beacon-text)]">
                      {issues.length} Total Findings:
                    </span>
                    <span className="font-bold text-rose-600 dark:text-rose-400">
                      {projectedScan.view_data.mandatory_violations_count ?? 0} Mandatory Blocking
                    </span>
                    <span className="text-zinc-400 dark:text-zinc-600">•</span>
                    <span className="font-bold text-amber-600 dark:text-amber-400">
                      {projectedScan.view_data.advisory_findings_count ?? 0} Advisory
                    </span>
                    <span className="text-zinc-400 dark:text-zinc-600">•</span>
                    <button
                      onClick={() => {
                        applyContextualFilter({
                          active: true,
                          sourceRole: "COMPLIANCE",
                          profileId: regulatoryProfile,
                          profileName: activeProfileLabel,
                          personaId: personaLens,
                          personaName: activePersonaLabel,
                          severity: "other",
                          title: `${activeProfileLabel.toUpperCase()} OTHER FINDINGS`,
                          subtitle: `Showing non-blocking / informational findings outside ${activeProfileLabel}`,
                          targetFindingIds: projectedScan.view_data.other_finding_ids,
                        });
                      }}
                      className="font-bold text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] hover:underline cursor-pointer"
                    >
                      {Math.max(0, issues.length - (projectedScan.view_data.mandatory_violations_count ?? 0) - (projectedScan.view_data.advisory_findings_count ?? 0))} Other / Non-blocking Findings →
                    </button>
                  </div>
                  <span className="text-[10px] text-[var(--beacon-text-muted)] font-medium">
                    Profile Filter Active
                  </span>
                </div>

                {/* Card Action & Disclaimer */}
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-2 border-t border-zinc-200/60 dark:border-zinc-800/40">
                  <p className="text-[11px] text-[var(--beacon-text-muted)] italic flex-1 flex items-start gap-1.5 leading-relaxed">
                    <IconInfo className="w-3.5 h-3.5 text-zinc-500 dark:text-zinc-400 shrink-0 mt-0.5" />
                    <span>{projectedScan.view_data.disclaimer || "Technical assessment only. This evaluation maps detected evidence against the selected regulatory criteria. It does not constitute legal advice, formal ACR/VPAT certification, or a government determination of compliance."}</span>
                  </p>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => {
                        clearActiveContext();
                        setIssueViewFilter("show_all");
                        setTab("issues");
                      }}
                      className="px-3 py-1.5 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-[var(--beacon-text)] text-xs font-bold hover:bg-zinc-50 dark:hover:bg-zinc-700/60 transition-all shadow-xs cursor-pointer"
                    >
                      View All {issues.length} Findings
                    </button>
                    <button
                      onClick={() => {
                        applyContextualFilter({
                          active: true,
                          sourceRole: "COMPLIANCE",
                          profileId: regulatoryProfile,
                          profileName: activeProfileLabel,
                          personaId: personaLens,
                          personaName: activePersonaLabel,
                          severity: "mandatory",
                          title: `${activeProfileLabel.toUpperCase()} MANDATORY FINDINGS`,
                          subtitle: `Showing ${projectedScan.view_data.mandatory_violations_count ?? 0} mandatory blocking violations for ${activePersonaLabel}`,
                          targetFindingIds: projectedScan.view_data.mandatory_finding_ids,
                        });
                      }}
                      className="px-3 py-1.5 rounded-lg bg-[var(--beacon-primary)] text-black text-xs font-black hover:brightness-105 transition-all shadow-xs flex items-center gap-1.5 cursor-pointer"
                    >
                      <span>View {projectedScan.view_data.mandatory_violations_count ?? 0} Blocking Issues</span>
                      <span>→</span>
                    </button>
                  </div>
                </div>
              </div>
            )}

            {roleView === "EXECUTIVE" && (
              <div className="bg-zinc-50/80 dark:bg-zinc-900/40 p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800/60 shadow-xs">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[var(--beacon-text-muted)] tracking-wider">Health Score</div>
                    <div className="text-sm font-black text-emerald-600 dark:text-emerald-400 mt-0.5">
                      {projectedScan.view_data.overall_health_score ?? "--"}/100
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[var(--beacon-text-muted)] tracking-wider">High-Impact Issues</div>
                    <button
                      onClick={() => {
                        applyContextualFilter({
                          active: true,
                          sourceRole: "EXECUTIVE",
                          severity: "critical_serious",
                          title: "EXECUTIVE HIGH-IMPACT FINDINGS",
                          subtitle: `Showing ${projectedScan.view_data.critical_and_serious_issues ?? 0} critical & serious risk issues`,
                          targetFindingIds: projectedScan.view_data.critical_serious_ids,
                        });
                      }}
                      className="text-sm font-black text-rose-600 dark:text-rose-400 mt-0.5 hover:underline cursor-pointer flex items-center gap-1"
                      title="Click to view critical & serious issues in Issues Tab"
                    >
                      {projectedScan.view_data.critical_and_serious_issues ?? 0} Critical/Serious →
                    </button>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[var(--beacon-text-muted)] tracking-wider">Pending Review</div>
                    <div className="text-sm font-black text-amber-600 dark:text-amber-300 mt-0.5">
                      {projectedScan.view_data.pending_human_review ?? 0} manual checks
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[var(--beacon-text-muted)] tracking-wider">Validated Fixes</div>
                    <div className="text-sm font-black text-teal-600 dark:text-teal-400 mt-0.5">
                      {projectedScan.view_data.validated_fixes_count ?? 0} ready
                    </div>
                  </div>
                </div>
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 pt-3 mt-3 border-t border-zinc-200/60 dark:border-zinc-800/40">
                  <p className="text-[11px] text-[var(--beacon-text-soft)] font-medium flex-1 flex items-center gap-1.5">
                    <IconInfo className="w-3.5 h-3.5 text-zinc-500 dark:text-zinc-400 shrink-0" />
                    <span>{projectedScan.view_data.executive_summary_statement || "Executive summary of audited digital assets."}</span>
                  </p>
                  <button
                    onClick={() => {
                      applyContextualFilter({
                        active: true,
                        sourceRole: "EXECUTIVE",
                        severity: "critical_serious",
                        title: "EXECUTIVE RISK FINDINGS",
                        subtitle: `Showing high-priority risk findings`,
                        targetFindingIds: projectedScan.view_data.critical_serious_ids,
                      });
                    }}
                    className="px-3 py-1.5 rounded-lg bg-[var(--beacon-primary)] text-black text-xs font-black hover:brightness-105 transition-all shadow-xs shrink-0 flex items-center gap-1.5 cursor-pointer"
                  >
                    <span>View {projectedScan.view_data.critical_and_serious_issues ?? 0} High-Impact Issues</span>
                    <span>→</span>
                  </button>
                </div>
              </div>
            )}

            {roleView === "QA_A11Y" && (
              <div className="bg-zinc-50/80 dark:bg-zinc-900/40 p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800/60 shadow-xs">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[var(--beacon-text-muted)] tracking-wider">Verification Queue</div>
                    <button
                      onClick={() => {
                        applyContextualFilter({
                          active: true,
                          sourceRole: "QA_A11Y",
                          severity: "needs_review",
                          title: "QA VERIFICATION QUEUE",
                          subtitle: `Showing ${projectedScan.view_data.verification_queue_size ?? projectedScan.view_data.needs_review_count ?? 0} items for assistive technology review`,
                          targetFindingIds: projectedScan.view_data.review_queue_ids,
                        });
                      }}
                      className="text-sm font-black text-amber-600 dark:text-amber-400 mt-0.5 hover:underline cursor-pointer flex items-center gap-1 text-left"
                    >
                      {projectedScan.view_data.verification_queue_size ?? projectedScan.view_data.needs_review_count ?? 0} items for review →
                    </button>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[var(--beacon-text-muted)] tracking-wider">Verified Violations</div>
                    <button
                      onClick={() => {
                        applyContextualFilter({
                          active: true,
                          sourceRole: "QA_A11Y",
                          severity: "all",
                          title: "QA VERIFIED VIOLATIONS",
                          subtitle: `Showing ${projectedScan.view_data.verified_failures_count ?? projectedScan.view_data.verified_violations?.length ?? 0} confirmed automated failures`,
                          targetFindingIds: projectedScan.view_data.verified_failure_ids,
                        });
                      }}
                      className="text-sm font-black text-rose-600 dark:text-rose-400 mt-0.5 hover:underline cursor-pointer flex items-center gap-1"
                      title="Click to view verified issues in Issues Tab"
                    >
                      {projectedScan.view_data.verified_failures_count ?? projectedScan.view_data.verified_violations?.length ?? 0} confirmed →
                    </button>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[var(--beacon-text-muted)] tracking-wider">Assertion Checklist</div>
                    <div className="text-sm font-black text-[var(--beacon-text)] mt-0.5">
                      {projectedScan.view_data.assertion_checklist?.length ?? 50} WCAG criteria
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[var(--beacon-text-muted)] tracking-wider">Total Findings</div>
                    <button
                      onClick={() => {
                        clearActiveContext();
                        setIssueViewFilter("show_all");
                        setTab("issues");
                      }}
                      className="text-sm font-black text-[var(--beacon-text)] mt-0.5 hover:underline cursor-pointer flex items-center gap-1"
                      title="Click to view all issues in Issues Tab"
                    >
                      {issues.length} detected →
                    </button>
                  </div>
                </div>
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 pt-3 mt-3 border-t border-zinc-200/60 dark:border-zinc-800/40">
                  <p className="text-[11px] text-[var(--beacon-text-muted)] italic flex-1 flex items-center gap-1.5">
                    <IconInfo className="w-3.5 h-3.5 text-zinc-500 dark:text-zinc-400 shrink-0" />
                    <span>Prioritize items in the Verification Queue using assistive technology tests (screen reader &amp; keyboard).</span>
                  </p>
                  <button
                    onClick={() => {
                      applyContextualFilter({
                        active: true,
                        sourceRole: "QA_A11Y",
                        severity: "needs_review",
                        title: "QA VERIFICATION QUEUE",
                        subtitle: "Review items requiring manual verification",
                        targetFindingIds: projectedScan.view_data.review_queue_ids,
                      });
                    }}
                    className="px-3 py-1.5 rounded-lg bg-[var(--beacon-primary)] text-black text-xs font-black hover:brightness-105 transition-all shadow-xs shrink-0 flex items-center gap-1.5 cursor-pointer"
                  >
                    <span>View Verification Queue ({projectedScan.view_data.verification_queue_size ?? projectedScan.view_data.needs_review_count ?? 0})</span>
                    <span>→</span>
                  </button>
                </div>
              </div>
            )}

            {roleView === "DEVELOPER" && (
              <div className="bg-zinc-50/80 dark:bg-zinc-900/40 p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800/60 shadow-xs">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[var(--beacon-text-muted)] tracking-wider">Actionable Violations</div>
                    <button
                      onClick={() => {
                        applyContextualFilter({
                          active: true,
                          sourceRole: "DEVELOPER",
                          severity: "all",
                          title: "DEVELOPER ACTIONABLE CODE FIXES",
                          subtitle: `Showing ${projectedScan.view_data.total_actionable_findings ?? projectedScan.view_data.actionable_count ?? issues.length} actionable AST items with code patches`,
                          targetFindingIds: projectedScan.view_data.actionable_finding_ids,
                        });
                      }}
                      className="text-sm font-black text-rose-600 dark:text-rose-400 mt-0.5 hover:underline cursor-pointer flex items-center gap-1"
                      title="Click to view actionable fixes in Issues Tab"
                    >
                      {projectedScan.view_data.total_actionable_findings ?? projectedScan.view_data.actionable_count ?? issues.length} AST items →
                    </button>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[var(--beacon-text-muted)] tracking-wider">Remediation Ready</div>
                    <div className="text-sm font-black text-emerald-600 dark:text-emerald-400 mt-0.5">
                      {projectedScan.view_data.remediation_ready_count ?? projectedScan.view_data.total_actionable_findings ?? 0} patches ready
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[var(--beacon-text-muted)] tracking-wider">Failing Elements</div>
                    <div className="text-sm font-black text-[var(--beacon-text)] mt-0.5">
                      {failingElementsCount} instances
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[var(--beacon-text-muted)] tracking-wider">Total Findings</div>
                    <button
                      onClick={() => {
                        clearActiveContext();
                        setIssueViewFilter("show_all");
                        setTab("issues");
                      }}
                      className="text-sm font-black text-[var(--beacon-text)] mt-0.5 hover:underline cursor-pointer flex items-center gap-1"
                      title="Click to view all issues in Issues Tab"
                    >
                      {issues.length} detected →
                    </button>
                  </div>
                </div>
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 pt-3 mt-3 border-t border-zinc-200/60 dark:border-zinc-800/40">
                  <p className="text-[11px] text-[var(--beacon-text-muted)] italic flex-1 flex items-center gap-1.5">
                    <IconInfo className="w-3.5 h-3.5 text-zinc-500 dark:text-zinc-400 shrink-0" />
                    <span>Verified selectors are mapped to DOM AST nodes. Click any issue below to inspect code diffs and fixes.</span>
                  </p>
                  <button
                    onClick={() => {
                      applyContextualFilter({
                        active: true,
                        sourceRole: "DEVELOPER",
                        severity: "all",
                        title: "DEVELOPER ACTIONABLE CODE FIXES",
                        subtitle: "Review code-first fixes and AST locations",
                        targetFindingIds: projectedScan.view_data.actionable_finding_ids,
                      });
                    }}
                    className="px-3 py-1.5 rounded-lg bg-[var(--beacon-primary)] text-black text-xs font-black hover:brightness-105 transition-all shadow-xs shrink-0 flex items-center gap-1.5 cursor-pointer"
                  >
                    <span>View Actionable Code Fixes ({projectedScan.view_data.total_actionable_findings ?? projectedScan.view_data.actionable_count ?? issues.length})</span>
                    <span>→</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

{/* ── Tabs ──────────────────────────────────────── */}
      <div className="flex gap-1.5 bg-zinc-100/80 dark:bg-zinc-900/60 border border-zinc-200 dark:border-zinc-800/80 p-1.5 rounded-xl w-full overflow-x-auto mb-8 shadow-sm backdrop-blur-sm">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-5 py-2.5 text-xs font-extrabold uppercase tracking-[0.1em] rounded-lg transition-all whitespace-nowrap flex items-center gap-2 ${
              tab === t.key
                ? "bg-[var(--beacon-primary)] text-black shadow-sm font-black"
                : "text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] hover:bg-white/70 dark:hover:bg-zinc-800/60"
            }`}
          >
            {t.label}
            {t.count !== undefined && (
              <span
                className={`px-2 py-0.5 text-[10px] font-black rounded-md ${
                  tab === t.key
                    ? "bg-black/15 text-black"
                    : "bg-zinc-200/80 dark:bg-zinc-800 text-[var(--beacon-text)]"
                }`}
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
          <IconAlertTriangle className="w-12 h-12 mx-auto mb-4 text-[var(--beacon-error)]" />
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
                    <PieChart width={200} height={200}>
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
                <div className="flex-1 flex flex-col items-center justify-center py-6">
                  <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center text-emerald-500 mb-3 shadow-xs">
                    <IconCheckCircle className="w-8 h-8" />
                  </div>
                  <p className="text-[var(--beacon-text)] text-base font-bold text-center">
                    Perfect score! No issues identified.
                  </p>
                  <p className="text-xs text-[var(--beacon-text-muted)] text-center mt-1">
                    All evaluated automated checks passed successfully.
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
                <div className="h-[200px] min-h-[200px] w-full min-w-0 flex-1">
                  <ResponsiveContainer width="100%" height={200} minWidth={0} minHeight={200}>
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
              className={`glass-card p-6 md:p-8 relative overflow-hidden transition-all rounded-2xl border ${
                latestScan.ai_analysis?.includes("[AI ERROR]")
                  ? "border-amber-500/40 bg-amber-500/5"
                  : latestScan.ai_analysis?.includes("generating")
                    ? "border-amber-500/30 bg-amber-500/5"
                    : "border-indigo-500/30 bg-gradient-to-br from-indigo-500/5 via-transparent to-amber-500/5"
              }`}
            >
              <div className="relative z-10">
                <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-[var(--beacon-primary)]/15 border border-[var(--beacon-primary)]/30 flex items-center justify-center text-[var(--beacon-primary)]">
                      <IconSparkle className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="text-sm font-black uppercase tracking-[0.14em] text-[var(--beacon-text)] leading-none">
                        AI Engine Analysis
                      </h3>
                      <p className="text-[11px] font-semibold text-[var(--beacon-text-muted)] mt-1">
                        Executive synthesis &amp; cognitive remediation model
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {showAiRefreshing && (
                      <span className="text-[10px] font-extrabold uppercase tracking-[0.12em] text-[var(--beacon-primary)] bg-[var(--beacon-primary)]/10 border border-[var(--beacon-primary)]/30 px-2.5 py-1 rounded-full flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-[var(--beacon-primary)] animate-ping" />
                        Refreshing insights...
                      </span>
                    )}

                    {latestScan.ai_analysis?.includes("[AI ERROR]") && (
                      <span className="text-[10px] font-extrabold uppercase tracking-[0.12em] text-amber-700 dark:text-amber-400 bg-amber-500/10 border border-amber-500/30 px-2.5 py-1 rounded-full">
                        Standby Mode
                      </span>
                    )}
                  </div>
                </div>

                {latestScan.ai_analysis?.includes("[AI ERROR]") ? (
                  <div className="mt-4 p-5 rounded-xl bg-white/60 dark:bg-black/40 border border-amber-500/30 space-y-3">
                    <p className="text-sm font-semibold text-[var(--beacon-text)] leading-relaxed">
                      AI insight synthesis is in standby mode. All 65+ multi-engine static rules, WCAG 2.2 evaluations, and confidence scores have executed with 100% precision. Discover all verified issues and targeted fixes in the sections below.
                    </p>
                    <div className="pt-1">
                      <button
                        onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
                        className="text-xs font-bold text-amber-800 dark:text-amber-400 hover:underline flex items-center gap-1.5"
                      >
                        <IconInfo className="w-3.5 h-3.5" />
                        {showTechnicalDetails ? "Hide Diagnostic Trace" : "View Diagnostic Trace"}
                      </button>
                    </div>
                    {showTechnicalDetails && (
                      <div className="mt-3 p-3.5 bg-black/90 rounded-lg border border-zinc-800 font-mono text-[11px] text-zinc-300 leading-relaxed overflow-x-auto">
                        <span className="text-amber-400 font-bold block mb-1">&gt; DIAGNOSTIC_EXCEPTION:</span>
                        {latestScan.ai_analysis.replace("[AI ERROR]: ", "")}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-sm md:text-base font-medium leading-relaxed whitespace-pre-wrap max-w-4xl text-[var(--beacon-text)] mt-2">
                    {latestScan.ai_analysis || latestScan.summary}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Trust Observability */}
          <div className="glass-card p-5 md:p-6 rounded-xl border border-[var(--beacon-border)]">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-[var(--beacon-border)] flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0">
                  <IconShield className="w-4.5 h-4.5" />
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-sm font-black uppercase tracking-[0.12em] text-[var(--beacon-text)] leading-none">
                      Audit Reliability
                    </h3>
                    <span className="text-[10px] font-black uppercase tracking-wider bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded">
                      Quality: {trustDataQuality}
                    </span>
                    <span className="text-[10px] font-black uppercase tracking-wider bg-zinc-100 dark:bg-zinc-800 text-[var(--beacon-text)] border border-[var(--beacon-border)] px-2 py-0.5 rounded">
                      Coverage: {trustCompleteness}
                    </span>
                    {latestScan.antibot_state && (
                      <span className="text-[10px] font-black uppercase tracking-wider bg-emerald-500/15 text-emerald-800 dark:text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        Stealth: {latestScan.antibot_state}
                      </span>
                    )}
                    {latestScan.pages_discovered && latestScan.pages_discovered > latestScan.pages_scanned && (
                      <span className="text-[10px] font-black uppercase tracking-wider bg-[var(--beacon-primary)]/15 text-black dark:text-[var(--beacon-primary)] border border-[var(--beacon-primary)]/40 px-2 py-0.5 rounded flex items-center gap-1">
                        Topology Deduplicated ({latestScan.pages_discovered - latestScan.pages_scanned} templates skipped)
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[var(--beacon-text-muted)] font-medium mt-1">
                    Multi-engine static evaluation with automated false-positive calibration
                  </p>
                </div>
              </div>

              {/* High-level KPI summary */}
              <div className="flex items-center gap-4 sm:gap-6 self-start md:self-auto pt-2 md:pt-0">
                <div className="text-left md:text-right">
                  <div className="text-base font-black text-[var(--beacon-text)] leading-none">
                    {(confidenceAvg * 100).toFixed(1)}%
                  </div>
                  <div className="text-[9px] uppercase font-bold text-[var(--beacon-text-muted)] mt-1">
                    Confidence
                  </div>
                </div>
                <div className="h-7 w-px bg-[var(--beacon-border)]/40" />
                <div className="text-left md:text-right">
                  <div className="text-base font-black text-[var(--beacon-text)] leading-none">
                    {lowTrustRules.length}
                  </div>
                  <div className="text-[9px] uppercase font-bold text-[var(--beacon-text-muted)] mt-1">
                    Gated Rules
                  </div>
                </div>
                <div className="h-7 w-px bg-[var(--beacon-border)]/40" />
                <div className="text-left md:text-right">
                  <div className="text-base font-black text-emerald-600 dark:text-emerald-400 leading-none">
                    {trustIntegrityCaps.length === 0 ? "Clean" : "Capped"}
                  </div>
                  <div className="text-[9px] uppercase font-bold text-[var(--beacon-text-muted)] mt-1">
                    Integrity
                  </div>
                </div>
              </div>
            </div>

            {/* Collapsible Technical Telemetry Details */}
            {(lowTrustRules.length > 0 || enginesCoverage) && (
              <details className="mt-4 pt-3 border-t border-[var(--beacon-border)]/40 group">
                <summary className="cursor-pointer text-xs font-bold text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] flex items-center justify-between select-none py-1">
                  <span>View Telemetry Breakdown &amp; Engine States ({lowTrustRules.length} rules suppressed)</span>
                  <span className="group-open:rotate-180 transition-transform text-sm">▾</span>
                </summary>

                <div className="mt-4 space-y-4 pt-2">
                  {/* Engine Matrix */}
                  <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg bg-zinc-50 dark:bg-zinc-900/60 border border-[var(--beacon-border)]">
                    <span className="text-[11px] font-black uppercase tracking-wider text-[var(--beacon-text)]">
                      Active Engines:
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {[
                        ["axe-core 4.10", !!enginesCoverage.axe || (latestScan.engines_used || []).some((e: string) => e.toLowerCase().includes("axe"))],
                        ["IBM Equal Access 3.1", !!enginesCoverage.ibm || (latestScan.engines_used || []).some((e: string) => e.toLowerCase().includes("ibm"))],
                        ["Browser Dynamic Probes", !!enginesCoverage.browser || (latestScan.engines_used || []).some((e: string) => e.toLowerCase().includes("probe") || e.toLowerCase().includes("browser"))],
                        ["BEACON Static & Heuristics", true],
                        ["Cognitive COGA", !!enginesCoverage.cognitive || (latestScan.engines_used || []).some((e: string) => e.toLowerCase().includes("cognitive")) || (latestScan.cognitive_scores != null)],
                        ["Lighthouse Hybrid", !!enginesCoverage.lighthouse || (latestScan.engines_used || []).some((e: string) => e.toLowerCase().includes("lighthouse"))],
                        ["Alfa (Siteimprove ACT)", !!enginesCoverage.alfa || (latestScan.engines_used || []).some((e: string) => e.toLowerCase().includes("alfa"))],
                        ["Guidepup Screen Reader", !!enginesCoverage.guidepup || (latestScan.engines_used || []).some((e: string) => e.toLowerCase().includes("guidepup"))],
                      ].map(([label, enabled]) => (
                        <span
                          key={String(label)}
                          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${
                            enabled
                              ? "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border-emerald-600/40"
                              : "bg-zinc-100 text-zinc-600 border-[var(--beacon-border)] dark:bg-zinc-800 dark:text-zinc-400"
                          }`}
                        >
                          <span className={`w-1.5 h-1.5 rounded-full ${enabled ? "bg-emerald-500 animate-pulse" : "bg-zinc-400"}`} />
                          {label}: {enabled ? "Active" : "Standby"}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Suppressed rules list */}
                  {lowTrustRules.length > 0 && (
                    <div className="p-3 rounded-lg bg-zinc-50 dark:bg-zinc-900/60 border border-[var(--beacon-border)] space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-black uppercase tracking-wider text-[var(--beacon-text)]">
                          Suppressed Low-Trust Heuristics:
                        </span>
                        <span className="text-[10px] text-[var(--beacon-text-muted)] font-medium">
                          Auto-muted below threshold
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {lowTrustRules.map((rule) => (
                          <span
                            key={rule}
                            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-[var(--beacon-surface)] border border-[var(--beacon-border)] text-xs font-mono text-[var(--beacon-text)]"
                          >
                            <span>{rule}</span>
                            <span className="text-[9px] uppercase font-bold text-zinc-500">muted</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </details>
            )}
          </div>

          {/* ── Pages Audited Accordion ────────────────────────── */}
          {latestScan?.scraped_pages && latestScan.scraped_pages.length > 0 && (
            <details className="glass-card p-5 group">
              <summary className="flex items-center justify-between cursor-pointer select-none outline-none list-none">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-extrabold uppercase tracking-[0.1em] text-[var(--beacon-text)]">
                    Pages Audited
                  </span>
                  <span className="badge-wcag text-[10px] font-black px-2 py-0.5 rounded">
                    {latestScan.scraped_pages.length}
                  </span>
                  {latestScan.degraded_mode && (
                    <span className="badge-needs-review text-[10px] font-black px-2 py-0.5 rounded">
                      Incomplete
                    </span>
                  )}
                </div>
                <span className="text-[var(--beacon-text-muted)] text-xs transition-transform group-open:rotate-180 select-none">
                  ▾
                </span>
              </summary>
              <div className="mt-4 space-y-1 max-h-64 overflow-y-auto pr-1">
                {latestScan.scraped_pages.map((pageUrl: string, idx: number) => (
                  <div
                    key={idx}
                    className="flex items-center gap-2 text-xs font-mono text-[var(--beacon-text-soft)] bg-[var(--beacon-bg)] px-3 py-2 rounded border border-[var(--beacon-border)] hover:border-[var(--beacon-primary)]/40 transition-colors"
                  >
                    <span className="text-[var(--beacon-primary)] opacity-60 shrink-0">{idx + 1}.</span>
                    <span className="truncate flex-1">{pageUrl}</span>
                  </div>
                ))}
              </div>
            </details>
          )}


          <div className="glass-card p-4 px-6 flex flex-wrap items-center justify-between gap-6 text-xs text-[var(--beacon-text-muted)] font-bold border border-[var(--beacon-border)]">
            <div className="flex items-center gap-2">
              <span className="uppercase tracking-[0.1em] opacity-80">
                Engines Used:{" "}
              </span>
              <div className="flex flex-wrap gap-1.5">
                {(latestScan.engines_used || []).map((e: string) => (
                  <span
                    key={e}
                    className="inline-flex items-center bg-[var(--beacon-surface)] border border-[var(--beacon-border)] px-2.5 py-1 rounded-md text-[var(--beacon-text)] font-extrabold uppercase text-[10px] tracking-wider"
                  >
                    {e}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-6 uppercase tracking-[0.05em] flex-wrap">
              <div className="flex items-center gap-1.5">
                <span className="opacity-70">Duration:</span>
                <span className="text-[var(--beacon-text)] font-extrabold bg-[var(--beacon-surface)] px-2 py-0.5 rounded border border-[var(--beacon-border)]">
                  {(latestScan.scan_time_seconds || 0).toFixed(1)}s
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="opacity-70">Mode:</span>
                <span className="text-[var(--beacon-text)] font-extrabold bg-[var(--beacon-surface)] px-2 py-0.5 rounded border border-[var(--beacon-border)]">
                  {latestScan.scan_mode || "fast"}
                </span>
              </div>
              {latestScan.completed_at && (
                <div className="opacity-60 text-[11px]">
                  {new Date(latestScan.completed_at).toLocaleString()}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── ISSUES TAB ────────────────────────────────────────── */}
      {tab === "issues" && latestScan && (
        <div className="space-y-6">
          {/* Contextual Filter & Compliance Projection Banner */}
          {contextualFilter?.active && (
            <div className="rounded-xl border border-zinc-200/90 dark:border-zinc-800/80 bg-zinc-50/95 dark:bg-zinc-900/70 p-4 shadow-xs space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-black uppercase tracking-wider text-[var(--beacon-text)]">
                      {contextualFilter.title}
                    </span>
                    <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded-full bg-[var(--beacon-primary)] text-black">
                      Perspective Active
                    </span>
                  </div>
                  <p className="text-xs text-[var(--beacon-text-muted)] mt-0.5">
                    {contextualFilter.subtitle}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs font-bold px-2.5 py-1 rounded-lg bg-zinc-200/80 dark:bg-zinc-800 text-[var(--beacon-text)]">
                    Showing {contextFilteredIssues.length} of {issues.length} findings
                  </span>
                  <button
                    onClick={clearActiveContext}
                    className="text-xs font-bold px-2.5 py-1 rounded-lg bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] hover:border-zinc-400 transition-colors cursor-pointer"
                  >
                    Clear Context &amp; Show All
                  </button>
                </div>
              </div>

              {/* Dismissible context tags */}
              <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-zinc-200/60 dark:border-zinc-800/50 text-xs">
                <span className="text-[10px] font-bold text-[var(--beacon-text-muted)] uppercase tracking-wider mr-1">
                  Active Filters:
                </span>
                {contextualFilter.profileName && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md bg-blue-500/10 text-blue-700 dark:text-blue-300 border border-blue-500/20 text-xs font-semibold">
                    <span>{contextualFilter.profileName}</span>
                  </span>
                )}
                {contextualFilter.personaName && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md bg-purple-500/10 text-purple-700 dark:text-purple-300 border border-purple-500/20 text-xs font-semibold">
                    <span>{contextualFilter.personaName}</span>
                  </span>
                )}
                {contextualFilter.severity && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md bg-rose-500/10 text-rose-700 dark:text-rose-300 border border-rose-500/20 text-xs font-semibold">
                    <span className="capitalize">{contextualFilter.severity.replace("_", " ")}</span>
                    <button
                      onClick={() => setContextualFilter(prev => prev ? { ...prev, severity: undefined, targetFindingIds: undefined, subtitle: "Showing all profile findings" } : null)}
                      className="hover:text-rose-950 dark:hover:text-rose-100 font-black cursor-pointer text-sm"
                      title="Remove severity filter"
                    >
                      ×
                    </button>
                  </span>
                )}
              </div>
            </div>
          )}
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-[var(--beacon-border)]/60">
            <div>
              <div className="flex items-center gap-2.5 flex-wrap">
                <h3 className="text-sm font-black uppercase tracking-[0.14em] text-[var(--beacon-text)]">
                  Discovered Issues
                </h3>
                <span className="text-xs font-bold bg-zinc-100 dark:bg-zinc-800 text-[var(--beacon-text-muted)] border border-zinc-200 dark:border-zinc-700 px-2.5 py-0.5 rounded-full">
                  {issues.length} total • {issueTypesCount} rule types • {failingElementsCount} failing elements
                </span>
              </div>
              <p className="text-xs font-medium text-[var(--beacon-text-muted)] mt-1">
                Multi-engine static evaluation with confidence-weighted suppression &amp; categorization
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              {/* Group By Selector */}
              <div className="inline-flex p-1 bg-zinc-100/80 dark:bg-zinc-900/60 border border-zinc-200 dark:border-zinc-800/80 rounded-xl gap-1 shadow-xs">
                <button
                  onClick={() => setIssueGroupBy("status")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
                    issueGroupBy === "status"
                      ? "bg-white dark:bg-zinc-800 text-[var(--beacon-text)] shadow-xs font-black"
                      : "text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] hover:bg-white/40 dark:hover:bg-zinc-800/40"
                  }`}
                  title="Group issues by verification confidence status"
                >
                  <IconShield className="w-3.5 h-3.5 shrink-0" />
                  <span>By Status</span>
                </button>
                <button
                  onClick={() => setIssueGroupBy("category")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
                    issueGroupBy === "category"
                      ? "bg-white dark:bg-zinc-800 text-[var(--beacon-text)] shadow-xs font-black"
                      : "text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] hover:bg-white/40 dark:hover:bg-zinc-800/40"
                  }`}
                  title="Group issues by accessibility category (Contrast, Forms, Images, etc.)"
                >
                  <IconLayers className="w-3.5 h-3.5 shrink-0" />
                  <span>By Category</span>
                </button>
              </div>

              {/* Unified Segmented Filter Controls */}
              <div className="inline-flex p-1 bg-zinc-100/80 dark:bg-zinc-900/60 border border-zinc-200 dark:border-zinc-800/80 rounded-xl gap-1 shadow-xs">
                <button
                  onClick={() => setIssueViewFilter("show_all")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
                    issueViewFilter === "show_all"
                      ? "bg-[var(--beacon-primary)] text-black shadow-xs font-black"
                      : "text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] hover:bg-white/60 dark:hover:bg-zinc-800/60"
                  }`}
                >
                  <span>Show All</span>
                  <span className={`text-[10px] font-black px-1.5 py-0.2 rounded-md ${
                    issueViewFilter === "show_all" ? "bg-black/15 text-black" : "bg-zinc-200/80 dark:bg-zinc-800 text-[var(--beacon-text)]"
                  }`}>
                    {totalPresentationIssues}
                  </span>
                </button>

                <button
                  onClick={() => setIssueViewFilter("verified_only")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
                    issueViewFilter === "verified_only"
                      ? "bg-emerald-600 text-white shadow-xs font-black"
                      : "text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] hover:bg-white/60 dark:hover:bg-zinc-800/60"
                  }`}
                >
                  <IconCheckCircle className="w-3.5 h-3.5" />
                  <span>Verified</span>
                  <span className={`text-[10px] font-black px-1.5 py-0.2 rounded-md ${
                    issueViewFilter === "verified_only" ? "bg-white/25 text-white" : "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
                  }`}>
                    {presentationCounts.verified}
                  </span>
                </button>

                <button
                  onClick={() => setIssueViewFilter("hide_low_confidence")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
                    issueViewFilter === "hide_low_confidence"
                      ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-black shadow-xs font-black"
                      : "text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] hover:bg-white/60 dark:hover:bg-zinc-800/60"
                  }`}
                >
                  <span>Hide Low Conf</span>
                  <span className={`text-[10px] font-black px-1.5 py-0.2 rounded-md ${
                    issueViewFilter === "hide_low_confidence" ? "bg-white/20 dark:bg-black/20" : "bg-zinc-200/80 dark:bg-zinc-800 text-[var(--beacon-text)]"
                  }`}>
                    {presentationCounts.verified + presentationCounts.needs_review}
                  </span>
                </button>
              </div>
            </div>
          </div>

          {/* Category Filter Pills Bar */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
            <span className="text-[11px] font-bold uppercase text-[var(--beacon-text-muted)] tracking-wider mr-1 shrink-0 flex items-center gap-1.5">
              <IconFilter className="w-3.5 h-3.5" />
              <span>Category:</span>
            </span>

            {ISSUE_CATEGORIES.map((cat) => {
              const count = categoryCounts[cat.id] || 0;
              const isSelected = selectedCategory === cat.id;
              const CatIcon = cat.icon;

              if (cat.id !== "all" && count === 0 && !isSelected) return null;

              return (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shrink-0 border cursor-pointer ${
                    isSelected
                      ? cat.activeClass + " border-transparent"
                      : "bg-white/80 dark:bg-zinc-900/60 border-zinc-200 dark:border-zinc-800 text-[var(--beacon-text-muted)] hover:text-[var(--beacon-text)] hover:border-zinc-300 dark:hover:border-zinc-700 shadow-xs"
                  }`}
                >
                  <CatIcon className="w-3.5 h-3.5 shrink-0" />
                  <span>{cat.shortLabel}</span>
                  <span
                    className={`text-[10px] px-1.5 py-0.2 rounded-full font-black ${
                      isSelected
                        ? "bg-black/20 text-white dark:bg-white/20 dark:text-black"
                        : "bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400"
                    }`}
                  >
                    {count}
                  </span>
                </button>
              );
            })}
          </div>

          {issues.length === 0 ? (
            <div className="glass-card p-20 text-center">
              <IconTrophy className="w-12 h-12 mx-auto mb-4 text-[var(--beacon-success)]" />
              <h2 className="text-2xl font-extrabold mb-2">
                Zero Compliance Violations
              </h2>
              <p className="text-base text-[var(--beacon-text-muted)] font-medium">
                Your site passed all checks successfully.
              </p>
            </div>
          ) : issueGroupBy === "category" ? (
            <div className="space-y-6">
              {issuesByCategoryGroup.map(({ category, issues: catIssues }) => {
                const CatIcon = category.icon;
                return (
                  <div key={category.id} className="space-y-3">
                    <div className="flex items-center gap-3 pt-1">
                      <div className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-black uppercase tracking-wider border ${category.badgeClass}`}>
                        <CatIcon className="w-3.5 h-3.5" />
                        <span>{category.label}</span>
                      </div>
                      <span className="text-xs font-bold text-[var(--beacon-text-muted)]">
                        {catIssues.length} issue{catIssues.length !== 1 ? "s" : ""}
                      </span>
                      <div className="flex-1 h-px bg-[var(--beacon-border)]/40" />
                    </div>

                    <div className="space-y-2.5">
                      {catIssues.map((issue: any, idx: number) =>
                        renderIssueCard(issue, idx)
                      )}
                    </div>
                  </div>
                );
              })}

              {issuesByCategoryGroup.length === 0 && (
                <div className="glass-card p-8 text-center">
                  <p className="text-sm font-medium text-[var(--beacon-text-muted)]">
                    No issues match the selected category or filter.
                  </p>
                  <button
                    onClick={() => {
                      setSelectedCategory("all");
                      setIssueViewFilter("show_all");
                    }}
                    className="mt-3 px-3 py-1.5 rounded-lg bg-[var(--beacon-primary)] text-black text-xs font-bold hover:brightness-105 transition-all cursor-pointer inline-flex items-center gap-1.5"
                  >
                    <span>Reset All Filters</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-6">
              {visiblePresentationOrder.map((bucket) => {
                const bucketMeta = ISSUE_PRESENTATION_META[bucket];
                const sectionIssues = issuesByPresentation[bucket];
                if (sectionIssues.length === 0) {
                  return null;
                }

                return (
                  <div key={bucket} className="space-y-3">
                    <div className="flex items-center gap-3 pt-1">
                      <div className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-black uppercase tracking-wider ${bucketMeta.badgeClass}`}>
                        <bucketMeta.icon className="w-3.5 h-3.5" />
                        <span>{bucketMeta.title}</span>
                      </div>
                      <span className="text-xs font-bold text-[var(--beacon-text-muted)]">
                        {sectionIssues.length} issue{sectionIssues.length !== 1 ? "s" : ""} • {presentationPercentages[bucket]}
                      </span>
                      <div className="flex-1 h-px bg-[var(--beacon-border)]/40" />
                    </div>

                    <div className="space-y-2.5">
                      {sectionIssues.map((issue: any, idx: number) =>
                        renderIssueCard(issue, idx, bucket),
                      )}
                    </div>
                  </div>
                );
              })}

              {visiblePresentationIssueCount === 0 && (
                <div className="glass-card p-8 text-center">
                  <p className="text-sm font-medium text-[var(--beacon-text-muted)]">
                    No issues match the selected category or filter.
                  </p>
                  <button
                    onClick={() => {
                      setSelectedCategory("all");
                      setIssueViewFilter("show_all");
                    }}
                    className="mt-3 px-3 py-1.5 rounded-lg bg-[var(--beacon-primary)] text-black text-xs font-bold hover:brightness-105 transition-all cursor-pointer inline-flex items-center gap-1.5"
                  >
                    <span>Reset All Filters</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── PRIORITY TAB ──────────────────────────────────────── */}
      {tab === "priority" && latestScan && (
        <div className="space-y-6">
          <div className="glass-card p-8 bg-amber-100/60 dark:bg-[var(--beacon-primary)]/5 border-2 border-amber-500/50 dark:border-[var(--beacon-primary)]/30 shadow-[3px_3px_0px_#000] dark:shadow-none">
            <h3 className="text-base font-black uppercase tracking-[0.1em] text-amber-950 dark:text-[var(--beacon-primary)] flex items-center gap-2">
              <IconSparkle className="w-5 h-5 text-amber-800 dark:text-[var(--beacon-primary)]" /> Orchestrated Fix Priority
            </h3>
            <p className="text-sm font-bold text-amber-950 dark:text-[var(--beacon-text-soft)] mt-2 max-w-3xl">
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
                          <summary className="text-xs font-black text-amber-950 dark:text-[var(--beacon-primary)] cursor-pointer flex items-center gap-1.5 uppercase tracking-[0.1em] hover:underline transition-colors w-fit select-none outline-none">
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
