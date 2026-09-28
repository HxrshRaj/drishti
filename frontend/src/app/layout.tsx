import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { StatusBadges } from "@/components/StatusBadges";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Drishti Operator Dashboard",
  description: "Agentic aerial inspection platform — simulated drone fleet, real agent pipeline.",
};

const NAV_LINKS = [
  { href: "/", label: "Missions" },
  { href: "/findings", label: "Findings" },
  { href: "/approvals", label: "Approvals" },
  { href: "/metrics", label: "Metrics" },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-neutral-950 text-neutral-100">
        <header className="border-b border-neutral-800 bg-neutral-900/60 backdrop-blur sticky top-0 z-10">
          <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between gap-4">
            <div className="flex items-center gap-6">
              <span className="font-semibold tracking-tight text-lg">Drishti</span>
              <nav className="flex gap-4 text-sm">
                {NAV_LINKS.map((l) => (
                  <Link key={l.href} href={l.href} className="text-neutral-300 hover:text-white transition-colors">
                    {l.label}
                  </Link>
                ))}
              </nav>
            </div>
            <StatusBadges />
          </div>
        </header>
        <main className="flex-1 mx-auto w-full max-w-6xl px-4 py-6">{children}</main>
        <footer className="border-t border-neutral-800 px-4 py-3 text-xs text-neutral-500 text-center">
          Drishti is a portfolio demo. The drone fleet is entirely simulated — no physical hardware is controlled anywhere in this system.
        </footer>
      </body>
    </html>
  );
}
