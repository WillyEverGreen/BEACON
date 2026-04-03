"use client";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ThemeToggle } from "@/components/ThemeToggle";

/* ── Icons ────────────────────────────────────────────────────────── */
function GridIcon({ className }: { className?: string }) {
  return (<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>);
}
function HelpIcon({ className }: { className?: string }) {
  return (<svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>);
}

/* ── Layout ───────────────────────────────────────────────────────── */
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  const navItems = [
    { href: "/dashboard", label: "All Projects", icon: GridIcon },
  ];

  const bottomNavItems = [
    { href: "/dashboard/help", label: "Help", icon: HelpIcon },
  ];

  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
      <div className="min-h-screen flex font-['Satoshi','Segoe_UI',sans-serif] bg-[var(--beacon-bg)] text-[var(--beacon-text)] transition-colors duration-200">
        {/* ── Sidebar ───────────────────────────────────────────── */}
        <aside className="w-[15rem] bg-[var(--beacon-sidebar-bg)] border-r border-[#2A2A2E] flex flex-col fixed h-full z-20">
          {/* Logo */}
          <div className="p-5 border-b border-[#2A2A2E]">
            <Link href="/dashboard" className="flex items-center gap-3 w-fit group">
              <img 
                src="/BEACON_new.png" 
                alt="BEACON" 
                className="w-10 h-10 object-cover rounded-full border-2 border-[var(--beacon-primary)] shadow-[2px_2px_0px_#000] group-hover:scale-105 transition-transform" 
              />
              <span className="text-base font-bold tracking-[0.2em] uppercase" style={{ color: "#ffffff" }}>BEACON</span>
            </Link>
          </div>

          {/* Main nav */}
          <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`sidebar-link ${pathname === item.href ? "active" : ""}`}
              >
                <item.icon className="w-4 h-4 shrink-0" />
                <span className="text-sm text-white/70">{item.label}</span>
              </Link>
            ))}

            {/* Divider */}
            <div className="pt-5 pb-1">
              <div className="h-px bg-[#2A2A2E]" />
            </div>

            {bottomNavItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`sidebar-link ${pathname.startsWith(item.href) ? "active" : ""}`}
              >
                <item.icon className="w-4 h-4 shrink-0" />
                <span className="text-sm text-white/70">{item.label}</span>
              </Link>
            ))}
          </nav>

          {/* Footer */}
          <div className="p-4 border-t border-[#2A2A2E] flex items-center justify-between gap-2 overflow-hidden">
            <p className="text-[10px] text-white/40 uppercase tracking-[0.1em] truncate" title="Accessibility Intelligence">
              Accessibility Intelligence
            </p>
            <ThemeToggle />
          </div>
        </aside>

        {/* ── Main content ──────────────────────────────────────── */}
        <main className="flex-1 ml-[15rem] p-8 min-h-screen w-full relative beacon-layout-wrapper">
          <div className="mx-auto w-full max-w-7xl">
            {children}
          </div>
        </main>
      </div>
    </ThemeProvider>
  );
}
