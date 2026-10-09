// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client"; // error boundaries must be client components
import Link from "next/link";
import { useEffect } from "react";
import { Button, buttonClass, StatusPanel } from "@/components/ui";

const CRASH_TITLE = "This page stopped working";
const CRASH_TEXT =
  "Something on this page failed while it was being shown. Runs keep going on the backend; trying again usually brings the page back.";

/**
 * Shown in place of a page that threw while rendering. It sits inside the root layout, so the navbar and theme
 * stay; "Try again" re-renders the page. A crash in the root layout itself is handled by global-error.tsx.
 */
export default function PageError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <>
      {/* React hoists this into <head>, so the tab no longer shows the crashed page's title. */}
      <title>{`${CRASH_TITLE} · Go Coverage Agent`}</title>
      <StatusPanel tone="danger" role="alert" title={CRASH_TITLE}
                   actions={<>
                     <Button variant="primary" onClick={() => retry()}>Try again</Button>
                     <Link href="/" className={buttonClass()}>Go to New run</Link>
                   </>}>
        <p>{CRASH_TEXT}</p>
        {error.digest && <p className="font-mono text-xs">Error reference: {error.digest}</p>}
      </StatusPanel>
    </>
  );
}
