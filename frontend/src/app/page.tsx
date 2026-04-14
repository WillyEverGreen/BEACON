"use client";

import { useEffect, useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { TimelineSection } from "@/components/timeline-section";
import { Features } from "@/components/blocks/features-8";
import Link from "next/link";

const brands = [
  "ACCESSIBILITY",
  "AI VISIBILITY",
  "SEO",
  "PERFORMANCE",
  "LLM CRAWLERS",
  "WCAG 2.2",
  "BEACON",
  "INTELLIGENCE",
];

export default function Home() {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!rootRef.current) return;

    gsap.registerPlugin(ScrollTrigger);

    const ctx = gsap.context(() => {
      gsap.from("[data-hero-title]", {
        y: 72,
        opacity: 0,
        duration: 0.9,
        ease: "power3.out",
      });

      gsap.from("[data-hero-copy], [data-hero-cta]", {
        y: 30,
        opacity: 0,
        duration: 0.8,
        delay: 0.2,
        stagger: 0.12,
        ease: "power2.out",
      });

      gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach((element) => {
        gsap.from(element, {
          scrollTrigger: {
            trigger: element,
            start: "top 85%",
          },
          opacity: 0,
          y: 48,
          duration: 0.7,
          ease: "power2.out",
        });
      });
    }, rootRef);

    return () => ctx.revert();
  }, []);

  return (
    <div ref={rootRef} className="min-h-screen bg-[#ffe17c] text-black">
      <header className="fixed top-0 z-40 h-20 w-full border-b-2 border-black bg-[#ffe17c]">
        <nav className="mx-auto flex h-full w-full max-w-7xl items-center justify-between px-4 md:px-10">
          <div className="flex items-center gap--2">
  <img src="/logo.png" alt="BEACON logo" className="h-18 w-auto" />
  <p className="font-cabinet text-xl font-extrabold tracking-tight uppercase">
    BEACON
  </p>
</div>
          <ul className="hidden items-center gap-8 text-sm font-bold uppercase tracking-wide md:flex">
            <li>Features</li>
            <li>
              <Link href="/dashboard" className="hover:opacity-80 transition-opacity">
                Dashboard
              </Link>
            </li>
            <li>Extensions</li>
            <li>Docs</li>
          </ul>
          <Link
            href="/dashboard"
            className="neo-btn bg-black px-5 py-3 text-sm font-bold uppercase tracking-wide text-white"
          >
            Start Audit
          </Link>
        </nav>
      </header>

      <main className="pt-20">
        <section className="bg-[#ffe17c] border-b-2 border-black flex items-center min-h-[calc(100vh-5rem)] overflow-hidden relative">
          <div className="mx-auto grid w-full max-w-6xl items-center gap-10 lg:gap-12 px-4 py-12 md:grid-cols-2 md:px-8 relative z-10">
            {/* Left side: Copy & CTA */}
            <div className="space-y-6 sm:space-y-8 flex flex-col justify-center">
              <h1 className="font-cabinet text-5xl sm:text-6xl lg:text-[4.5rem] font-extrabold leading-[1.05] tracking-tight text-black" data-hero-title>
                Fix what's making your website <br />
                <span className="text-white relative inline-block mt-2 px-4 py-1">
                  <span className="absolute inset-0 block bg-black rounded-lg transform -skew-x-3"></span>
                  <span className="relative z-10">invisible.</span>
                </span>
              </h1>
              <p className="max-w-md text-lg sm:text-xl font-medium text-black/80 leading-relaxed" data-hero-copy>
                Scan your site. Fix the top 5 issues. Improve visibility for AI crawlers, screen readers, and search engines instantly.
              </p>
              
              <div className="mt-8 flex flex-col gap-4" data-hero-cta>
                <form className="flex flex-col sm:flex-row gap-3 w-full max-w-xl relative">
                  <input 
                    type="url" 
                    placeholder="Enter your website URL (https://...)" 
                    className="w-full rounded-xl border-2 border-black bg-white px-5 py-4 text-base font-semibold placeholder-zinc-500 outline-none focus:ring-4 focus:ring-black/10 transition-all shadow-[4px_4px_0px_rgba(0,0,0,1)]"
                    required
                  />
                  <button 
                    type="submit" 
                    className="shrink-0 rounded-xl border-2 border-black bg-black px-8 py-4 text-sm font-bold uppercase tracking-wide text-white transition-all hover:-translate-y-1 hover:shadow-[6px_6px_0px_rgba(0,0,0,1)] shadow-[4px_4px_0px_rgba(0,0,0,1)] focus:outline-none focus:ring-4 focus:ring-black/10"
                  >
                    Scan Free &rarr;
                  </button>
                </form>
                
                <div className="flex items-center gap-3 text-sm font-semibold text-black/70 mt-2">
                  <span>Try:</span>
                  <button type="button" className="text-black underline decoration-2 underline-offset-4 hover:text-[#ff5f57] transition-colors">apple.com</button>
                  <span className="px-1 text-black/30">&bull;</span>
                  <button type="button" className="text-black underline decoration-2 underline-offset-4 hover:text-[#ff5f57] transition-colors">See Example Report</button>
                </div>
              </div>
            </div>

            {/* Right side: Dashboard Preview */}
            <div className="w-full relative mx-auto" data-hero-copy>
              {/* Decorative background shadow */}
              <div className="absolute inset-0 bg-black rounded-2xl translate-y-3 translate-x-3 transition-transform"></div>
              
              {/* Dashboard Container */}
              <div className="relative rounded-2xl border-2 border-black bg-[#f9fafb] overflow-hidden flex flex-col h-full z-10 w-full transform transition-transform hover:-translate-y-1 hover:-translate-x-1">
                {/* Dashboard Header */}
                <div className="flex items-center justify-between border-b-2 border-black bg-[#171e19] px-4 py-3">
                  <div className="flex gap-2">
                    <span className="h-3 w-3 rounded-full bg-[#ff5f57] border border-black/20" />
                    <span className="h-3 w-3 rounded-full bg-[#febc2e] border border-black/20" />
                    <span className="h-3 w-3 rounded-full bg-[#28c840] border border-black/20" />
                  </div>
                  <div className="absolute left-1/2 -translate-x-[50%] px-4 py-0.5 bg-white/10 rounded-full border border-white/10 text-xs font-semibold text-white/50">beacon.report/dashboard</div>
                </div>
                
                {/* Dashboard Body */}
                <div className="flex flex-col p-6 sm:p-8 gap-6 bg-[#f9fafb]">
                  <div className="grid grid-cols-1 sm:grid-cols-5 gap-6">
                    {/* Main Score Area */}
                    <div className="col-span-3 flex flex-col rounded-2xl border-2 border-black bg-white p-6 shadow-[4px_4px_0px_rgba(0,0,0,1)] relative overflow-hidden group">
                      <div className="flex justify-between items-start mb-6">
                        <div className="space-y-1">
                          <p className="text-sm font-bold uppercase tracking-widest text-black/70">Visibility Score</p>
                          <div className="flex items-baseline gap-1">
                            <span className="text-7xl font-cabinet font-extrabold text-black">61</span>
                            <span className="text-2xl font-bold text-black/40">/100</span>
                          </div>
                        </div>
                      </div>
                      
                      <div className="mt-auto">
                        <div className="flex h-3 w-full overflow-hidden rounded-full border-2 border-black bg-black/5">
                          <div className="h-full w-[61%] bg-[#28c840]" />
                        </div>
                        <div className="mt-4 flex items-center justify-between">
                          <span className="text-xs font-bold text-black/60">Needs improvement</span>
                          <span className="text-xs font-bold text-[#ff5f57] bg-[#ff5f57]/10 px-2 py-1 rounded-md border border-[#ff5f57]/20 flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-[#ff5f57]"></span> 47 Issues
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* AI Crawler Status */}
                    <div className="col-span-2 flex flex-col justify-center items-center text-center rounded-2xl border-2 border-black bg-[#111] p-6 shadow-[4px_4px_0px_rgba(0,0,0,1)] relative overflow-hidden group">
                      <div className="absolute inset-0 bg-gradient-to-br from-black/0 to-white/5 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                      <div className="p-3 bg-black/50 rounded-full border border-white/10 mb-4 shadow-inner">
                        <svg className="w-8 h-8 text-[#ff5f57]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                        </svg>
                      </div>
                      <p className="text-sm font-bold uppercase tracking-widest text-white/50 mb-1">AI Crawlers</p>
                      <span className="text-3xl font-cabinet font-extrabold text-[#ff5f57]">Blocked</span>
                    </div>
                  </div>

                  {/* Context Metrics */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="rounded-xl border-2 border-black bg-[#ffe17c] p-5 flex items-center gap-4 transition-transform hover:-translate-y-0.5">
                      <div className="w-12 h-12 rounded-full border-2 border-black bg-white flex items-center justify-center shrink-0">
                        <svg className="w-6 h-6 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                      </div>
                      <div>
                        <p className="text-2xl font-extrabold font-cabinet text-black leading-none">Missing</p>
                        <p className="text-sm font-bold text-black/70 mt-1">llms.txt config</p>
                      </div>
                    </div>
                    
                    <div className="rounded-xl border-2 border-black bg-white p-5 flex items-center gap-4 transition-transform hover:-translate-y-0.5">
                      <div className="w-12 h-12 rounded-full border-2 border-black bg-[#f4f4f5] flex items-center justify-center shrink-0">
                        <svg className="w-6 h-6 text-black" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16m-7 6h7" />
                        </svg>
                      </div>
                      <div>
                        <p className="text-2xl font-extrabold font-cabinet text-black leading-none">12 Pages</p>
                        <p className="text-sm font-bold text-black/70 mt-1">Vague headings</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="overflow-hidden border-b-2 border-black bg-[#171e19] py-8">
          <div className="marquee-track flex min-w-max items-center gap-20 text-4xl font-extrabold tracking-tight text-[#b7c6c2]/50">
            {[...brands, ...brands, ...brands].map((brand, idx) => (
              <span key={`${brand}-${idx}`} className="font-cabinet">
                {brand}
              </span>
            ))}
          </div>
        </section>

        <section className="bg-white py-24 sm:py-32 border-b-2 border-black">
          <div className="mx-auto w-full max-w-7xl px-4 md:px-10">
            <div className="mb-16 max-w-3xl" data-reveal>
              <h2 className="font-cabinet text-4xl font-extrabold tracking-tight md:text-5xl lg:text-6xl text-black">
                The Intelligence Engine <br/>behind BEACON v2.0
              </h2>
              <p className="mt-6 text-lg font-medium text-black/70">
                Built for precision at scale. We analyze your website using a multi-engine orchestrator that combines static checks, Playwright browser probes, and a custom 5-signal Confidence Engine.
              </p>
            </div>
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
              <div className="neo-panel rounded-xl bg-[#ffe17c] p-6 border-[3px] border-black" data-reveal>
                <div className="mb-4 font-cabinet text-3xl font-extrabold text-black">01</div>
                <h3 className="font-bold uppercase tracking-tight text-black text-lg mb-2">Fast & Deep Modes</h3>
                <p className="text-black/80 text-sm font-medium">Switch between httpx-only scans (5-15s) and full Playwright DOM renders (30-120s) for complex single-page apps.</p>
              </div>
              <div className="neo-panel rounded-xl bg-[#b7c6c2] p-6 border-[3px] border-black" data-reveal>
                <div className="mb-4 font-cabinet text-3xl font-extrabold text-black">02</div>
                <h3 className="font-bold uppercase tracking-tight text-black text-lg mb-2">Confidence Engine</h3>
                <p className="text-black/80 text-sm font-medium">No more false positives. Our 5-signal formula weighs source reliability, reproducibility, and cross-engine agreement.</p>
              </div>
              <div className="neo-panel rounded-xl bg-white p-6 border-[3px] border-black" data-reveal>
                <div className="mb-4 font-cabinet text-3xl font-extrabold text-black">03</div>
                <h3 className="font-bold uppercase tracking-tight text-black text-lg mb-2">LLM Fallback</h3>
                <p className="text-black/80 text-sm font-medium">Async remediation streams AI solutions via RAG. If offline, the Fix Cache and Rule-Based Fallbacks guarantee reports never fail.</p>
              </div>
              <div className="neo-panel rounded-xl bg-[#171e19] p-6 border-[3px] border-black text-white" data-reveal>
                <div className="mb-4 font-cabinet text-3xl font-extrabold text-white">04</div>
                <h3 className="font-bold uppercase tracking-tight text-white text-lg mb-2">Cognitive UX</h3>
                <p className="text-white/80 text-sm font-medium">Experimental layer measuring Flesch-Kincaid readability, jargon density, and form usability for neurodivergent accessibility.</p>
              </div>
            </div>
          </div>
        </section>

        <section className="border-b-2 border-black bg-[#171e19] px-4 py-32 lg:py-40 md:px-10">
          <div className="mx-auto w-full max-w-7xl">
            <div className="mb-16 text-center" data-reveal>
              <p className="font-cabinet text-5xl font-extrabold tracking-tight text-white md:text-6xl">See it in action</p>
              <p className="mx-auto mt-6 max-w-2xl text-lg font-medium text-zinc-300">A comprehensive dashboard that brings accessibility data to life across your entire application.</p>
            </div>
            <div className="neo-panel-xl rounded-2xl overflow-hidden" data-reveal>
              <img src="/dashboard-mockup.png" alt="BEACON accessibility dashboard showing WCAG compliance scores, violation charts, and page route analysis" className="w-full h-auto block" />
            </div>
          </div>
        </section>

        <section className="border-b-2 border-black bg-[#171e19] px-4 py-32 lg:py-40 text-white md:px-10">
          <div className="mx-auto w-full max-w-7xl">
            <div className="mb-16" data-reveal>
              <h2 className="font-cabinet text-5xl font-extrabold tracking-tight md:text-6xl">
                How it works
              </h2>
              <p className="mt-6 text-lg font-medium text-zinc-300 max-w-2xl">Three simple steps from discovery to becoming highly visible, powered by AI and builder-first tooling.</p>
            </div>
            <div className="grid gap-10 lg:gap-16 md:grid-cols-3">
              {[
                {
                  title: "Discover",
                  text: "Scan entire domains for Accessibility, semantic SEO, and AI Crawler Readiness (llms.txt).",
                  ring: "#b7c6c2",
                },
                {
                  title: "Diagnose",
                  text: "Immediately understand what is blocking Google bots, ChatGPT citations, and human users.",
                  ring: "#ffe17c",
                },
                {
                  title: "Remediate",
                  text: "Let AI generate exact code fixes—copy and paste to instantly boost your Visibility Score.",
                  ring: "#ffffff",
                },
              ].map((step) => (
                <article key={step.title} className="relative neo-panel rounded-2xl bg-[#272727] p-6" data-reveal>
                  <div className="mb-5 flex items-center gap-4">
                    <div className="flex h-24 w-24 items-center justify-center rounded-full border-2 border-black text-3xl font-extrabold" style={{ boxShadow: `0px 0px 0px 4px ${step.ring}` }}>
                      {step.title[0]}
                    </div>
                    <div className="h-[2px] flex-1 bg-[#3d3d3d]" />
                  </div>
                  <h3 className="font-cabinet text-4xl font-extrabold tracking-tight">{step.title}</h3>
                  <p className="mt-3 text-lg font-medium text-zinc-100">{step.text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <TimelineSection />

        <section className="border-b-2 border-black bg-white px-4 py-32 lg:py-40 md:px-10">
           <div className="mx-auto w-full max-w-7xl">
             <div className="mb-16 max-w-3xl" data-reveal>
                <h2 className="font-cabinet text-5xl font-extrabold tracking-tight md:text-6xl text-[#171e19]">
                  Persona Impact Views
                </h2>
             </div>
             <div className="mt-10 grid gap-10 lg:gap-16 md:grid-cols-3">
               <article className="neo-panel rounded-2xl bg-[#b7c6c2] p-6" data-reveal>
                 <span className="rounded-full border-2 border-black bg-white px-3 py-1 text-xs font-bold uppercase">Screen Reader Users</span>
                 <p className="mt-5 font-cabinet text-3xl font-extrabold text-[#171e19]">Understand semantic landmarks and alt text.</p>
               </article>
               <article className="neo-panel-lg rounded-2xl bg-[#ffe17c] p-6" data-reveal>
                 <span className="rounded-full border-2 border-black bg-white px-3 py-1 text-xs font-bold uppercase">Motor Impaired</span>
                 <p className="mt-5 font-cabinet text-3xl font-extrabold text-[#171e19]">Optimize tab order, focus, and hit targets.</p>
               </article>
               <article className="neo-panel rounded-2xl bg-[#272727] p-6 text-white" data-reveal>
                 <span className="rounded-full border-2 border-black bg-white px-3 py-1 text-xs font-bold uppercase text-black">Low Vision</span>
                 <p className="mt-5 font-cabinet text-3xl font-extrabold">Ensure contrast ratios and scaling behavior.</p>
               </article>
             </div>
           </div>
         </section>

        <section className="dot-yellow border-b-2 border-black px-4 py-32 lg:py-48 md:px-10">
          <div className="mx-auto w-full max-w-7xl">
            <div className="grid items-center gap-12 lg:gap-20 md:grid-cols-2">
              <div className="neo-panel-xl rounded-2xl overflow-hidden" data-reveal>
                <img src="/developer-workspace.png" alt="Developer workspace showing browser extension and VS Code integration for accessibility fixes" className="w-full h-auto block" />
              </div>
              <div className="text-left">
                <h2 className="font-cabinet text-5xl font-extrabold tracking-tight md:text-6xl lg:text-7xl" data-reveal>
                  Launch your first full-site analysis in under five minutes.
                </h2>
                <p className="mt-6 max-w-xl text-lg font-medium md:text-xl" data-reveal>
                  From project scorecards to route-level fixes, BEACON gives every developer a comprehensive path to inclusive experiences.
                </p>
                <div className="mt-10 flex flex-wrap gap-4" data-reveal>
                  <Link
                    href="/dashboard"
                    className="neo-btn bg-black px-8 py-4 font-bold uppercase tracking-wide text-white"
                  >
                    Start Audit
                  </Link>
                  <Link
                    href="/dashboard"
                    className="neo-btn bg-white px-8 py-4 font-bold uppercase tracking-wide text-black"
                  >
                    Install Extension
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-[#171e19] px-4 py-14 text-white md:px-10">
        <div className="mx-auto grid w-full max-w-7xl gap-10 md:grid-cols-4">
          <div>
            <p className="font-cabinet text-2xl font-extrabold uppercase tracking-widest">BEACON</p>
            <p className="mt-3 text-zinc-300">Accessibility auditing, simplified and actionable.</p>
          </div>
          <div>
            <p className="font-cabinet text-lg font-bold">Product</p>
            <p className="mt-3 text-zinc-300">Dashboard</p>
            <p className="text-zinc-300">Audits</p>
            <p className="text-zinc-300">Extensions</p>
          </div>
          <div>
            <p className="font-cabinet text-lg font-bold">Developers</p>
            <p className="mt-3 text-zinc-300">Documentation</p>
            <p className="text-zinc-300">GitHub</p>
            <p className="text-zinc-300">Featherless AI</p>
          </div>
          <div>
            <p className="font-cabinet text-lg font-bold">Follow</p>
            <div className="mt-3 flex gap-3">
              {"XLIN".split("").map((label) => (
                <a
                  key={label}
                  href="#"
                  className="flex h-10 w-10 items-center justify-center border-2 border-zinc-300 bg-[#272727] text-sm font-bold transition-colors hover:bg-[#ffe17c] hover:text-black"
                >
                  {label}
                </a>
              ))}
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
