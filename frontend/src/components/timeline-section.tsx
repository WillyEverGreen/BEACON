"use client";

import dynamic from "next/dynamic";
import { ScanSearch, Eye, Sparkles, LayoutDashboard, Code2 } from "lucide-react";

const RadialOrbitalTimeline = dynamic(
  () => import("@/components/ui/radial-orbital-timeline"),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-[800px] flex flex-col items-center justify-center bg-[#171e19] overflow-hidden rounded-3xl border-2 border-black">
        <div className="text-white/60 text-lg">Loading timeline...</div>
      </div>
    ),
  }
);

const timelineData = [
  {
    id: 1,
    title: "Topology Discovery",
    date: "Step 1",
    content: "Native DOM skeleton clustering crawling accessible routes with 66.7% loop reduction.",
    category: "Discovery",
    icon: ScanSearch,
    relatedIds: [2, 4],
    status: "completed" as const,
    energy: 100,
  },
  {
    id: 2,
    title: "Consensus & ACT",
    date: "Step 2",
    content: "Cross-calibrating Axe, IBM, Alfa, and Guidepup with 100% W3C ACT rule adjudication.",
    category: "Diagnostics",
    icon: Eye,
    relatedIds: [1, 3],
    status: "completed" as const,
    energy: 90,
  },
  {
    id: 3,
    title: "Sandboxed AI Fixes",
    date: "Step 3",
    content: "NVIDIA NIM AI remediation validated in a headless AST container with zero-regression gating.",
    category: "Remediation",
    icon: Sparkles,
    relatedIds: [2, 5],
    status: "in-progress" as const,
    energy: 80,
  },
  {
    id: 4,
    title: "Compliance Review",
    date: "Continuous",
    content: "Track resolving issues, multi-engine trust metrics, and visual score improvements over time.",
    category: "Tracking",
    icon: LayoutDashboard,
    relatedIds: [1],
    status: "pending" as const,
    energy: 60,
  },
  {
    id: 5,
    title: "Enterprise Exporters",
    date: "Standards",
    content: "One-click export for OASIS SARIF 2.1.0 (GitHub Code Scanning) and W3C EARL 1.0 JSON-LD.",
    category: "Standards",
    icon: Code2,
    relatedIds: [3],
    status: "pending" as const,
    energy: 40,
  },
];

export function TimelineSection() {
  return (
    <section className="border-y-2 border-black bg-white px-4 py-32 lg:py-40 md:px-10">
      <div className="mx-auto w-full max-w-7xl">
        <div className="mb-16 max-w-3xl" data-reveal>
          <h2 className="font-cabinet text-5xl font-extrabold tracking-tight md:text-6xl">
            Audit Lifecycle
          </h2>
          <p className="mt-4 text-xl font-medium">Follow the connected workflow from discovery to AI-powered remediation.</p>
        </div>
        <div data-reveal>
          <RadialOrbitalTimeline timelineData={timelineData} />
        </div>
      </div>
    </section>
  );
}
