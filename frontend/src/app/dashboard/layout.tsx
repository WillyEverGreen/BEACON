"use client";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ThemeToggle } from "@/components/ThemeToggle";
import { BeaconConfigProvider } from "@/lib/beaconConfig";

/* ── Icons ────────────────────────────────────────────────────────── */
function GridIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  );
}
function HelpIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}
function HomeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  );
}

/* ── Layout ───────────────────────────────────────────────────────── */
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  const navItems = [
    { href: "/dashboard", label: "All Projects", icon: GridIcon, exact: true },
  ];

  const bottomNavItems = [
    { href: "/", label: "Home", icon: HomeIcon, exact: true },
    { href: "/dashboard/help", label: "Help & Docs", icon: HelpIcon, exact: false },
  ];

  function isActive(href: string, exact: boolean) {
    if (exact) return pathname === href;
    return pathname.startsWith(href);
  }

  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
      <BeaconConfigProvider>
        <div className="min-h-screen flex font-['Satoshi','Segoe_UI',sans-serif] bg-[var(--beacon-bg)] text-[var(--beacon-text)] transition-colors duration-200">

          {/* ── Sidebar ──────────────────────────────────────── */}
          <aside className="w-[15rem] bg-[var(--beacon-sidebar-bg)] border-r border-[#1E1E22] flex flex-col fixed h-full z-20 select-none">

            {/* Logo */}
            <div className="p-5 border-b border-[#1E1E22]">
              <Link
                href="/dashboard"
                className="flex items-center gap-3 w-fit group"
              >
                <div className="relative w-9 h-9 shrink-0">
                  <img
                    src="/BEACON_new.png"
                    alt="BEACON"
                    className="w-9 h-9 object-cover rounded-full border-2 border-[var(--beacon-primary)] shadow-[2px_2px_0px_#000] group-hover:scale-105 transition-transform duration-200"
                  />
                  {/* online pulse */}
                  <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-[var(--beacon-success)] rounded-full border-2 border-[var(--beacon-sidebar-bg)]" />
                </div>
                <div>
                  <span className="text-sm font-black tracking-[0.22em] uppercase text-white block leading-none">
                    BEACON
                  </span>
                  <span className="text-[9px] font-bold tracking-[0.15em] uppercase text-white/70 block mt-0.5">
                    Accessibility AI
                  </span>
                </div>
              </Link>
            </div>

            {/* Main nav */}
            <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
              <p className="text-[9px] font-extrabold tracking-[0.2em] uppercase text-white/60 px-2 pt-1 pb-2">
                Navigation
              </p>
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`sidebar-link ${isActive(item.href, item.exact) ? "active" : ""}`}
                >
                  <item.icon className="w-4 h-4 shrink-0" />
                  <span className="text-sm">{item.label}</span>
                </Link>
              ))}

              {/* Divider */}
              <div className="pt-5 pb-1">
                <div className="h-px bg-[#1E1E22]" />
              </div>

              <p className="text-[9px] font-extrabold tracking-[0.2em] uppercase text-white/60 px-2 pt-1 pb-2">
                General
              </p>
              {bottomNavItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`sidebar-link ${isActive(item.href, item.exact) ? "active" : ""}`}
                >
                  <item.icon className="w-4 h-4 shrink-0" />
                  <span className="text-sm">{item.label}</span>
                </Link>
              ))}
            </nav>

            {/* Footer */}
            <div className="px-4 py-3 border-t border-[#1E1E22]">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-[9px] text-white/70 uppercase tracking-[0.15em] font-bold leading-none">
                    v2.1.0
                  </p>
                  <p className="text-[9px] text-white/60 uppercase tracking-[0.1em] font-medium mt-0.5">
                    Production
                  </p>
                </div>
                <ThemeToggle />
              </div>
            </div>
          </aside>

          {/* ── Main content ─────────────────────────────────── */}
          <main className="flex-1 ml-[15rem] min-h-screen w-full beacon-layout-wrapper">
            <div className="p-6 md:p-8 mx-auto w-full max-w-7xl pb-20">
              {children}
            </div>
          </main>
        </div>
      </BeaconConfigProvider>
    </ThemeProvider>
  );
}
