"use client";

import { ScanSearch, Eye, Sparkles, LayoutDashboard, Code2 } from "lucide-react";
import RadialOrbitalTimeline from "@/components/ui/radial-orbital-timeline";

const timelineData = [
  {
    id: 1,
    title: "Route Discovery",
    date: "Step 1",
    content: "Automated crawling of all accessible DOM nodes and routes on your sitemap.",
    category: "Discovery",
    icon: ScanSearch,
    relatedIds: [2, 4],
    status: "completed" as const,
    energy: 100,
  },
  {
    id: 2,
    title: "Analysis & Diagnosis",
    date: "Step 2",
    content: "Interactive contextual mapping of DOM elements failing WCAG criteria.",
    category: "Diagnostics",
    icon: Eye,
    relatedIds: [1, 3],
    status: "completed" as const,
    energy: 90,
  },
  {
    id: 3,
    title: "NVIDIA NIM AI Fixes",
    date: "Step 3",
    content: "Real-time AI suggestions providing optimized code snippets for remediation.",
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
    content: "Track resolving issues and visual score improvements over time.",
    category: "Tracking",
    icon: LayoutDashboard,
    relatedIds: [1],
    status: "pending" as const,
    energy: 60,
  },
  {
    id: 5,
    title: "VS Code Action",
    date: "Developer",
    content: "Seamlessly route finalized AI fixes directly into your local IDE footprint.",
    category: "Integration",
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
