// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client"; // error boundaries must be client components
import Link from "next/link";
import { useEffect } from "react";
import { Button, buttonClass, StatusPanel } from "@/components/ui";

/**
 * Shown in place of a page that threw while rendering. It sits inside the root layout, so the navbar and theme
 * stay; "Try again" re-renders the page.
 */
export default function PageError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <StatusPanel tone="danger" role="alert" title="This page stopped working"
                 actions={<>
                   <Button variant="primary" onClick={() => retry()}>Try again</Button>
                   <Link href="/" className={buttonClass()}>Go to New run</Link>
                 </>}>
      <p>Something on this page failed while it was being shown. Runs keep going on the backend; trying again usually brings the page back.</p>
      {error.digest && <p className="font-mono text-xs">Error reference: {error.digest}</p>}
    </StatusPanel>
  );
}
