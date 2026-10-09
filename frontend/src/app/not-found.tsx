// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import type { Metadata } from "next";
import Link from "next/link";
import { actionLinkClass, buttonClass, StatusPanel } from "@/components/ui";

export const metadata: Metadata = { title: "Page not found" };

export default function NotFound() {
  return (
    <StatusPanel title="Page not found"
                 actions={<>
                   <Link href="/" className={buttonClass({ variant: "primary" })}>Go to New run</Link>
                   <Link href="/how-it-works" className={`text-sm ${actionLinkClass}`}>How it works</Link>
                 </>}>
      <p>There is no page at this address. Runs are opened from Run history on the New run page.</p>
    </StatusPanel>
  );
}
