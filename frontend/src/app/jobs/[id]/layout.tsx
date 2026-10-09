// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import type { Metadata } from "next";
import type { ReactNode } from "react";

// The run page is a client component, so its title comes from this server layout: "Run e2de1ca387cb · Go Coverage Agent".
export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  return { title: `Run ${id}` };
}

export default function JobLayout({ children }: { children: ReactNode }) {
  return children;
}
