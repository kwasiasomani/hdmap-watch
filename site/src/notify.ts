import type { RegionBundle, CheckName } from "./types";
import { byId } from "./dom";

const CHECK_LABELS: Record<CheckName, string> = {
  geometry: "Geometry",
  topology: "Topology",
  semantic: "Semantic",
};

const S3_BUCKET = "hdmap-watch-455515343653";

/** No backend: builds a mailto: link summarizing the flagged segments.
 * A production version would replace this with AWS SES or a Slack
 * webhook called from hdmap_watch/etl/load.py after scoring. */
export function buildReviewEmail(data: RegionBundle): { subject: string; body: string } {
  const flagged = data.segments.filter((s) => s.status === "REVIEW").sort((a, b) => b.risk - a.risk);
  const top = flagged.slice(0, 15);

  const subject = `HDMap Watch: ${flagged.length} segments flagged for review — ${data.city_name}`;
  const lines = [
    `${flagged.length} of ${data.summary.total} lane segments in ${data.city_name} (${data.city}, log ${data.log_id}) are flagged REVIEW.`,
    "",
    `Top ${top.length} by risk:`,
    ...top.map((s) => `  segment ${s.id} — risk ${s.risk}/3 — checks: ${s.checks.map((c) => CHECK_LABELS[c]).join(", ") || "none"}`),
    "",
    `Full queue: s3://${S3_BUCKET}/processed/review_queue/${data.log_id}.csv`,
  ];
  return { subject, body: lines.join("\n") };
}

/** Sets the notify link's href directly rather than navigating via script —
 * a script-triggered `location.href = "mailto:..."` is a top-level
 * navigation attempt to a non-http scheme, which a sandboxed embed (this
 * page's Artifact preview included) refuses outright. A real anchor the
 * user clicks themselves is the standard, portable way to do this, and
 * it behaves identically once deployed for real. */
export function updateNotifyLink(data: RegionBundle): void {
  const { subject, body } = buildReviewEmail(data);
  const link = byId<HTMLAnchorElement>("notify-btn");
  link.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}
