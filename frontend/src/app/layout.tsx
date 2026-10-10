// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import { NavBar } from "@/components/NavBar";
import { containerClass } from "@/components/ui";
import "./globals.css";

const plexSans = IBM_Plex_Sans({ variable: "--font-plex-sans", subsets: ["latin"], weight: ["400", "500", "600"] });
const plexMono = IBM_Plex_Mono({ variable: "--font-plex-mono", subsets: ["latin"], weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  // Pages set their own title ("How it works"); the New run page, which can't export metadata, gets the default.
  title: { template: "%s · Go Coverage Agent", default: "New run · Go Coverage Agent" },
  description: "Autonomously plans, writes and validates Go unit tests until a coverage target is met.",
};

// Runs before first paint so a stored light/dark choice never flashes the wrong theme.
const THEME_SCRIPT = `try{var t=localStorage.getItem("gca-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${plexSans.variable} ${plexMono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-screen bg-bg text-text antialiased">
        <NavBar />
        <main className={`${containerClass} py-8 sm:py-12`}>{children}</main>
      </body>
    </html>
  );
}
