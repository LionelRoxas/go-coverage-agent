// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { SpectroCloudLogo } from "@/components/SpectroCloudLogo";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Badge, containerClass } from "@/components/ui";
import { api } from "@/lib/api";

const LINKS = [
  { href: "/", label: "New run", active: (p: string) => p === "/" },
  // The Walkthrough is the long version of How it works, linked from there; a third item would not fit at 390 px.
  { href: "/how-it-works", label: "How it works", active: (p: string) => p === "/how-it-works" || p === "/walkthrough" },
];

export function NavBar() {
  const pathname = usePathname() ?? "/";
  const [model, setModel] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.health().then((h) => { if (alive) setModel(h.model || null); }).catch(() => {});
    return () => { alive = false; };
  }, []);

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-bg/85 backdrop-blur">
      <div className={`${containerClass} flex h-14 items-center gap-2 sm:gap-4`}>
        <SpectroCloudLogo className="h-[22px] w-auto shrink-0 sm:h-[26px]" />
        <span aria-hidden className="h-5 w-px shrink-0 bg-border" />
        <Link href="/" aria-label="Go Coverage Agent" className="whitespace-nowrap text-sm font-semibold tracking-tight">
          <span className="sm:hidden">GCA</span>
          <span className="hidden sm:inline">Go Coverage Agent</span>
        </Link>
        <nav aria-label="Main" className="flex h-full min-w-0 items-stretch gap-0.5 sm:ml-2 sm:gap-1">
          {LINKS.map((l) => {
            const active = l.active(pathname);
            return (
              <Link key={l.href} href={l.href} aria-current={active ? "page" : undefined}
                    className={`relative flex items-center whitespace-nowrap px-1.5 text-sm transition-colors sm:px-3 ${active ? "font-medium text-text" : "text-muted hover:text-text"}`}>
                {l.label}
                {active && <span aria-hidden className="absolute inset-x-1.5 bottom-0 h-0.5 rounded-full bg-accent sm:inset-x-3" />}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          {/* From 1024 px only: at tablet width it would wrap. */}
          {model && <span title="Model" className="hidden lg:inline-flex"><Badge className="whitespace-nowrap bg-surface font-mono font-normal">{model}</Badge></span>}
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
