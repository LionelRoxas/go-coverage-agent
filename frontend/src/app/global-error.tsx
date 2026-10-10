// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client"; // error boundaries must be client components
import { useEffect } from "react";
import { Button, buttonClass, containerClass, StatusPanel } from "@/components/ui";
import "./globals.css";

/**
 * Shown when the root layout itself throws (the navbar, the theme toggle). It replaces the whole document, so it
 * brings its own <html>, <body>, styles and title, and applies a stored light/dark choice itself. "Go to New run" is
 * a plain link so the app reloads from scratch.
 */
export default function GlobalError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
    try {
      const t = localStorage.getItem("gca-theme");
      if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
    } catch {
      // storage unavailable: the OS colour scheme applies
    }
  }, [error]);

  const actions = (
    <>
      <Button variant="primary" onClick={() => retry()}>Try again</Button>
      {/* A plain link on purpose: a full reload rebuilds the layout that crashed. */}
      {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
      <a href="/" className={buttonClass()}>Go to New run</a>
    </>
  );

  return (
    <html lang="en">
      <body className="min-h-screen bg-bg font-sans text-text antialiased">
        <title>Something went wrong · Go Coverage Agent</title>
        <main className={`${containerClass} py-12 sm:py-16`}>
          <StatusPanel tone="danger" role="alert" title="Something went wrong" actions={actions}>
            <p>The app hit an error. Runs on the backend are not affected. Try again.</p>
            {error.digest && <p className="font-mono text-xs">Error reference: {error.digest}</p>}
          </StatusPanel>
        </main>
      </body>
    </html>
  );
}
