// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const plexSans = IBM_Plex_Sans({ variable: "--font-plex-sans", subsets: ["latin"], weight: ["400", "500", "600"] });
const plexMono = IBM_Plex_Mono({ variable: "--font-plex-mono", subsets: ["latin"], weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  title: "Go Coverage Agent",
  description: "Autonomously plans, writes and validates Go unit tests until a coverage target is met.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${plexSans.variable} ${plexMono.variable}`}>
      <body className="min-h-screen bg-bg text-text antialiased">
        <header className="border-b border-border">
          <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-3">
            <Link href="/" className="font-mono text-sm font-semibold tracking-tight">go-coverage-agent</Link>
            <span className="text-xs text-muted">Tests written by an LLM, validated by the Go toolchain</span>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-8 sm:py-12">{children}</main>
      </body>
    </html>
  );
}
