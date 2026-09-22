"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { TimelineSection } from "@/components/timeline-section";
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
  const router = useRouter();
  const [url, setUrl] = useState("");

  const handleScan = (e: React.FormEvent) => {
    e.preventDefault();
    if (url.trim()) {
      try {
        localStorage.setItem("beacon_pending_scan_url", url.trim());
      } catch {
        // ignore storage errors
      }
      router.push(`/dashboard?url=${encodeURIComponent(url.trim())}`);
    } else {
      router.push("/dashboard");
    }
  };

  useEffect(() => {
    if (!rootRef.current) return;

    gsap.registerPlugin(ScrollTrigger);

    const ctx = gsap.context(() => {
      gsap.from("[data-hero-eyebrow]", {
        y: 20,
        opacity: 0,
        duration: 0.6,
        ease: "power2.out",
      });

      gsap.from("[data-hero-title]", {
        y: 50,
        opacity: 0,
        duration: 0.85,
        delay: 0.1,
        ease: "power3.out",
      });

      gsap.from("[data-hero-copy], [data-hero-form], [data-hero-social]", {
        y: 28,
        opacity: 0,
        duration: 0.75,
        delay: 0.2,
        stagger: 0.12,
        ease: "power2.out",
      });

      gsap.from("[data-hero-lighthouse]", {
        opacity: 0,
        scale: 0.95,
        duration: 1.1,
        delay: 0.25,
        ease: "power2.out",
      });

      gsap.from("[data-hero-birds]", {
        opacity: 0,
        x: -24,
        duration: 1.2,
        delay: 0.45,
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
      {/* Header / Navbar */}
      <header className="fixed top-0 z-40 h-20 w-full border-b border-black bg-[#ffe17c]">
        <nav className="mx-auto flex h-full w-full max-w-7xl items-center justify-between px-6 sm:px-10 lg:px-12">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-3 group">
            <img src="/logo.png" alt="BEACON" className="h-9 w-auto object-contain transition-transform group-hover:scale-105" />
            <span className="font-cabinet text-2xl font-black tracking-tight uppercase text-black">
              BEACON
            </span>
          </Link>

          {/* Navigation Links */}
          <ul className="hidden md:flex items-center gap-8 text-xs font-black uppercase tracking-widest text-black">
            <li>
              <a href="#features" className="hover:opacity-60 transition-opacity">
                Features
              </a>
            </li>
            <li>
              <Link href="/dashboard" className="hover:opacity-60 transition-opacity">
                Audit
              </Link>
            </li>
            <li>
              <a href="#extensions" className="hover:opacity-60 transition-opacity">
                Extensions
              </a>
            </li>
            <li>
              <Link href="/dashboard/help" className="hover:opacity-60 transition-opacity">
                Docs
              </Link>
            </li>
          </ul>

          {/* Start Audit CTA */}
          <Link
            href="/dashboard"
            className="rounded-full bg-black px-6 py-2.5 text-xs font-black uppercase tracking-wider text-white hover:bg-neutral-800 transition-all hover:scale-105 flex items-center gap-2 shadow-[2px_2px_0px_rgba(0,0,0,0.2)]"
          >
            <span>Start Audit</span>
            <span className="text-sm font-bold leading-none">&rarr;</span>
          </Link>
        </nav>
      </header>

      <main className="pt-20">
        {/* Revamped Hero Section with Lighthouse Artwork */}
        <section className="relative bg-[#ffe17c] border-b-2 border-black overflow-hidden pt-8 pb-16 sm:py-16 lg:py-20 xl:py-24">
          <div className="mx-auto max-w-7xl px-6 sm:px-10 lg:px-12">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
              
              {/* Left Column: Eyebrow, Main Headline, Subtitle, Scan Input, Trusted By */}
              <div className="lg:col-span-7 flex flex-col justify-center space-y-6 sm:space-y-8 z-10">
                
                {/* Eyebrow */}
                <p 
                  className="font-cabinet text-xs sm:text-sm font-extrabold uppercase tracking-[0.22em] text-black/90"
                  data-hero-eyebrow
                >
                  CLEANER WEBSITES. A BRIGHTER INTERNET.
                </p>

                {/* Main Headline */}
                <h1 
                  className="font-cabinet text-6xl sm:text-7xl lg:text-[5.5rem] xl:text-[6.2rem] font-black leading-[0.98] tracking-tight text-black"
                  data-hero-title
                >
                  Find. Fix.
                  <span className="block mt-2 sm:mt-3">
                    <span className="inline-block bg-black text-white px-4 sm:px-6 py-1 sm:py-2 rounded-2xl sm:rounded-3xl">
                      Be Seen.
                    </span>
                  </span>
                </h1>

                {/* Subtitle (Strictly NO mdash) */}
                <p 
                  className="text-base sm:text-lg lg:text-xl font-medium text-black/85 leading-relaxed max-w-xl"
                  data-hero-copy
                >
                  Audit your website for accessibility, AI crawler readiness, SEO visibility, and technical issues in seconds.
                </p>

                {/* URL Input and Scan Button Form */}
                <div className="pt-2 flex flex-col gap-3.5" data-hero-form>
                  <form onSubmit={handleScan} className="flex flex-col sm:flex-row items-stretch gap-3 max-w-xl">
                    <div className="relative flex-1">
                      <input
                        type="url"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        placeholder="Enter your website URL (https://...)"
                        className="w-full h-14 rounded-xl border-2 border-black bg-white px-5 text-sm sm:text-base font-semibold text-black placeholder:text-zinc-500 outline-none focus:ring-4 focus:ring-black/10 transition-all shadow-[2px_2px_0px_rgba(0,0,0,1)]"
                        required
                      />
                    </div>
                    <button
                      type="submit"
                      className="h-14 shrink-0 rounded-xl border-2 border-black bg-black px-7 text-xs sm:text-sm font-black uppercase tracking-wider text-white transition-all hover:bg-neutral-800 hover:-translate-y-0.5 active:translate-y-0 flex items-center justify-center gap-2 cursor-pointer shadow-[2px_2px_0px_rgba(0,0,0,1)]"
                    >
                      <span>SCAN FREE</span>
                      <span className="text-base font-bold leading-none">&rarr;</span>
                    </button>
                  </form>

                  {/* Micro-copy bullet points */}
                  <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs sm:text-sm font-semibold text-black/75">
                    <span>No signup required</span>
                    <span className="text-black/40">&bull;</span>
                    <span>Instant results</span>
                    <span className="text-black/40">&bull;</span>
                    <span>Better web for everyone</span>
                  </div>
                </div>

                {/* Trusted By Builders Row */}
                <div className="pt-6 sm:pt-10 flex flex-wrap items-center gap-3 sm:gap-5 text-black" data-hero-social>
                  <span className="text-[11px] sm:text-xs font-black uppercase tracking-[0.2em] text-black/75">
                    TRUSTED BY BUILDERS AT
                  </span>
                  <div className="h-4 w-px bg-black/40 hidden sm:block" />
                  <div className="flex flex-wrap items-center gap-5 sm:gap-7">
                    {/* Vercel */}
                    <div className="flex items-center gap-1.5 font-bold text-sm tracking-tight text-black">
                      <svg className="w-3.5 h-3.5 fill-black" viewBox="0 0 76 65">
                        <path d="M37.5274 0L75.0548 65H0L37.5274 0Z" />
                      </svg>
                      <span className="font-bold text-sm">Vercel</span>
                    </div>
                    {/* GitHub */}
                    <div className="flex items-center gap-1.5 font-bold text-sm tracking-tight text-black">
                      <svg className="w-4 h-4 fill-black" viewBox="0 0 24 24">
                        <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                      </svg>
                      <span className="font-bold text-sm">GitHub</span>
                    </div>
                    {/* Google */}
                    <div className="flex items-center gap-1.5 font-bold text-sm tracking-tight text-black">
                      <svg className="w-3.5 h-3.5 fill-black" viewBox="0 0 24 24">
                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
                      </svg>
                      <span className="font-bold text-sm">Google</span>
                    </div>
                    {/* Notion */}
                    <div className="flex items-center gap-1.5 font-bold text-sm tracking-tight text-black">
                      <svg className="w-4 h-4 fill-black" viewBox="0 0 24 24">
                        <path d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.093-.373L18.363 2.25c-.466-.373-.84-.56-1.587-.513L3.62 2.67c-.466.046-.56.326-.373.56zm.793 4.246v12.224c0 .84.42 1.166 1.307 1.12l14.475-.84c.84-.047 1.073-.606 1.073-1.353V7.52c0-.747-.327-1.12-1.073-1.073l-14.708.84c-.793.047-1.074.42-1.074 1.167zm12.368 1.4c.093.42 0 .84-.42.887l-.746.14v7.746c-.513.327-1.073.513-1.587.513-.746 0-1.026-.233-1.54-.887l-4.76-7.465v7.232l1.353.327c.047.466-.233.793-.7.84l-3.407.233c-.093-.42 0-.84.42-.887l.793-.186V10.83l-1.073-.093c-.047-.466.186-.793.653-.84l3.5-.233 4.993 7.698v-6.952l-1.167-.187c-.046-.466.187-.84.654-.886z" />
                      </svg>
                      <span className="font-bold text-sm">Notion</span>
                    </div>
                  </div>
                </div>

              </div>

              {/* Right Column: Lighthouse Illustration Artwork */}
              <div className="lg:col-span-5 relative flex items-center justify-center lg:justify-end" data-hero-lighthouse>
                
                {/* Sun Disc backdrop behind Lighthouse */}
                <div className="absolute top-[48%] left-1/2 lg:left-[46%] -translate-x-1/2 -translate-y-1/2 w-[300px] h-[300px] sm:w-[390px] sm:h-[390px] lg:w-[440px] lg:h-[440px] rounded-full bg-[#FFF5C4]/90 pointer-events-none -z-0" />

                {/* Flying Birds Silhouettes */}
                <div className="absolute inset-0 pointer-events-none z-10" data-hero-birds>
                  {/* Bird 1 */}
                  <svg className="absolute top-[34%] left-[6%] sm:left-[10%] w-6 h-3.5 text-black/85 -rotate-6" viewBox="0 0 24 14" fill="currentColor">
                    <path d="M0 7c3-4 7-6 11-1 3-5 8-3 13 1-3-1-6-2-9-1-2 1-3 2-3 2s-1-1-3-2c-3-1-6 0-9 1z"/>
                  </svg>
                  {/* Bird 2 */}
                  <svg className="absolute top-[42%] left-[16%] sm:left-[22%] w-5 h-3 text-black/85 rotate-6" viewBox="0 0 24 14" fill="currentColor">
                    <path d="M0 7c3-4 7-6 11-1 3-5 8-3 13 1-3-1-6-2-9-1-2 1-3 2-3 2s-1-1-3-2c-3-1-6 0-9 1z"/>
                  </svg>
                  {/* Bird 3 */}
                  <svg className="absolute top-[52%] left-[4%] sm:left-[7%] w-4 h-2.5 text-black/85 -rotate-12" viewBox="0 0 24 14" fill="currentColor">
                    <path d="M0 7c3-4 7-6 11-1 3-5 8-3 13 1-3-1-6-2-9-1-2 1-3 2-3 2s-1-1-3-2c-3-1-6 0-9 1z"/>
                  </svg>
                </div>

                {/* Lighthouse Image (light.png) */}
                <img 
                  src="/light.png" 
                  alt="BEACON Lighthouse illuminating the web" 
                  className="relative z-10 w-full max-w-[500px] sm:max-w-[560px] lg:max-w-[620px] h-auto object-contain select-none pointer-events-none drop-shadow-sm" 
                />

                {/* Slanted Editorial Poster Stamp */}
                <div className="absolute right-0 top-[48%] translate-x-2 sm:translate-x-6 rotate-[-10deg] text-right select-none pointer-events-none hidden sm:block z-20">
                  <p className="font-cabinet text-[11px] sm:text-xs font-black uppercase tracking-widest text-black/85 leading-tight">
                    BETTER WEBSITES
                    <br />
                    FOR A BRIGHTER
                    <br />
                    INTERNET.
                  </p>
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
                The Intelligence Engine <br/>behind BEACON v3.0
              </h2>
              <p className="mt-6 text-lg font-medium text-black/70">
                Built for precision at scale. We audit your website using a multi-engine orchestrator cross-calibrating axe-core, IBM Equal Access, Siteimprove Alfa, Guidepup screen reader probes, and a Zero-Regression AI Remediation Sandbox.
              </p>
            </div>
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
              <div className="neo-panel rounded-xl bg-[#ffe17c] p-6 border-[3px] border-black" data-reveal>
                <div className="mb-4 font-cabinet text-3xl font-extrabold text-black">01</div>
                <h3 className="font-bold uppercase tracking-tight text-black text-lg mb-2">Native Topology</h3>
                <p className="text-black/80 text-sm font-medium">DOM tag-tree skeleton clustering cuts redundant crawl loops by 66.7% while preserving template diversity across complex web apps.</p>
              </div>
              <div className="neo-panel rounded-xl bg-[#b7c6c2] p-6 border-[3px] border-black" data-reveal>
                <div className="mb-4 font-cabinet text-3xl font-extrabold text-black">02</div>
                <h3 className="font-bold uppercase tracking-tight text-black text-lg mb-2">Consensus &amp; ACT</h3>
                <p className="text-black/80 text-sm font-medium">Multi-engine agreement reconciles Axe, IBM, Alfa, and Guidepup. 100% W3C ACT Rule Adjudication eliminates false positives.</p>
              </div>
              <div className="neo-panel rounded-xl bg-white p-6 border-[3px] border-black" data-reveal>
                <div className="mb-4 font-cabinet text-3xl font-extrabold text-black">03</div>
                <h3 className="font-bold uppercase tracking-tight text-black text-lg mb-2">AI Patch Sandbox</h3>
                <p className="text-black/80 text-sm font-medium">Candidate fixes run in an isolated DOM AST container. Zero-regression gating guarantees fixes never introduce new violations or XSS.</p>
              </div>
              <div className="neo-panel rounded-xl bg-[#171e19] p-6 border-[3px] border-black text-white" data-reveal>
                <div className="mb-4 font-cabinet text-3xl font-extrabold text-white">04</div>
                <h3 className="font-bold uppercase tracking-tight text-white text-lg mb-2">SARIF &amp; EARL</h3>
                <p className="text-white/80 text-sm font-medium">Native machine-readable exports for OASIS SARIF 2.1.0 (GitHub Code Scanning) and W3C EARL 1.0 JSON-LD (EU EAA / ADA compliance).</p>
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
                  text: "Let AI generate exact code fixes: copy and paste to instantly boost your Visibility Score.",
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
            <p className="text-zinc-300">NVIDIA NIM</p>
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
