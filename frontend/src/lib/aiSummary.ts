// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// "Copy as Markdown": the same Markdown as output/<id>/SUMMARY.md (backend/app/summary/report.py). Keep the two in step.
import type { CostUsd, SummaryGenerated } from "./types";

export const AI_NOTE = "AI-written from this run's measured data.";
export const EMPTY_PART = "Nothing in this part could be checked against the run's data.";

export const usd = (v: number) => `$${v >= 0.01 || v === 0 ? v.toFixed(2) : v.toFixed(4)}`;

/** The run's cost (what the text talks about), the summary call's, and both together. */
export const costLine = (c: CostUsd) =>
  `Run cost ${usd(c.run)} · summary ${usd(c.summary)} · total ${usd(c.total)} (input ${usd(c.input)}, output ${usd(c.output)})`;

/** False when the grounding check left nothing of this part. */
export const hasText = (part: object) =>
  Object.values(part).some((v) => (typeof v === "string" ? v.trim() !== "" : Array.isArray(v) && v.length > 0));

export function toMarkdown(ai: SummaryGenerated, { repo, model, generatedAt }: { repo: string; model: string; generatedAt: number }): string {
  const b = ai.business, t = ai.technical;
  const day = new Date(generatedAt * 1000).toISOString().slice(0, 10);
  const blocks: string[] = [`# AI summary: ${repo}`, `_${AI_NOTE} Generated ${day} with ${model}._`];
  const add = (text: string, prefix = "") => {
    if (text.trim()) blocks.push(`${prefix}${text.trim()}`);
  };
  const bullets = (title: string, items: string[]) => {
    if (items.length) blocks.push(`**${title}**`, items.map((i) => `- ${i}`).join("\n"));
  };

  blocks.push("## For stakeholders");
  if (!hasText(b)) blocks.push(`_${EMPTY_PART}_`);
  add(b.headline, "### ");
  add(b.outcome);
  add(b.efficiency);
  if (ai.cost_usd) blocks.push(costLine(ai.cost_usd));
  bullets("Risks", b.risks);
  add(b.recommendation, "**Recommendation:** ");

  blocks.push("## For engineering teams");
  if (!hasText(t)) blocks.push(`_${EMPTY_PART}_`);
  add(t.headline, "### ");
  add(t.what_was_tested, "**What was tested:** ");
  add(t.where_tests_live, "**Where the tests live:** ");
  bullets("Gaps", t.gaps.map((g) => `\`${g.file}\`: ${g.detail}`));
  bullets("Suspected bugs", t.suspected_bugs);
  add(t.rejected_or_failed, "**Rejected or failed:** ");
  add(t.how_to_run, "**How to run:** ");
  bullets("Next steps", t.next_steps);
  return blocks.join("\n\n") + "\n";
}
