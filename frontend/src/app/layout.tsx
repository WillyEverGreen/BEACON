import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BEACON | Accessibility Intelligence",
  description:
    "Multi-page accessibility analysis platform with visual exploration, AI remediation, and benchmark-driven improvement.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <html lang="en" suppressHydrationWarning><body>{children}</body></html>;
}
