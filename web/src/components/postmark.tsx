import { useId } from "react";
import { shortDate } from "@/lib/format";

/** The app's signature: a cancellation mark that says where a number came from and when it was collected. */
export function Postmark({ source, date, detail, size = 72 }: { source: string; date?: string | null; detail?: string; size?: number }) {
  const id = useId().replace(/:/g, "");
  const when = date ? new Date(date) : null;
  const day = when ? when.toLocaleDateString("en-GB", { day: "2-digit", month: "short" }).toUpperCase() : "NO DATE";
  // "Databricks (Greenhouse)" would overrun the ring, and the employer is the part that matters.
  const label = source.replace(/\s*\(.*\)$/, "").toUpperCase().slice(0, 20);
  return (
    <svg width={size} height={size} viewBox="0 0 80 80" role="img" aria-label={`Source: ${source}. Collected ${date ? shortDate(date) : "on an unknown date"}.`} className="shrink-0 -rotate-6 text-air-blue">
      <title>{`${source}${detail ? `, ${detail}` : ""}, collected ${date ? shortDate(date) : "unknown"}`}</title>
      <circle cx="40" cy="40" r="37" fill="none" stroke="currentColor" strokeWidth="1.75" />
      <circle cx="40" cy="40" r="23" fill="none" stroke="currentColor" strokeWidth="1" />
      <defs>
        <path id={`top-${id}`} d="M 11 40 A 29 29 0 0 1 69 40" />
        <path id={`bottom-${id}`} d="M 8.5 40 A 31.5 31.5 0 0 0 71.5 40" />
      </defs>
      <text fontSize="9.5" fontWeight="700" fill="currentColor" letterSpacing="0.6" style={{ fontStretch: "75%" }}>
        <textPath href={`#top-${id}`} startOffset="50%" textAnchor="middle">{label}</textPath>
      </text>
      {detail && (
        <text fontSize="8.5" fontWeight="600" fill="currentColor" letterSpacing="0.5" style={{ fontStretch: "75%" }}>
          <textPath href={`#bottom-${id}`} startOffset="50%" textAnchor="middle">{detail.toUpperCase().slice(0, 22)}</textPath>
        </text>
      )}
      <text x="40" y="39" textAnchor="middle" fontSize="11.5" fontWeight="800" fill="currentColor" style={{ fontStretch: "80%" }}>{day}</text>
      <text x="40" y="51" textAnchor="middle" fontSize="9.5" fontWeight="600" fill="currentColor">{when ? when.getFullYear() : ""}</text>
    </svg>
  );
}

/** Table-sized version: a small ring beside readable text. */
export function SourceStamp({ source, date }: { source?: string | null; date?: string | null }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-air-blue whitespace-nowrap">
      <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden><circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.5" /><circle cx="8" cy="8" r="3" fill="none" stroke="currentColor" /></svg>
      <span className="font-medium condensed">{source ?? "Unknown"}</span>
      {date && <span className="text-ink-3 condensed">{new Date(date).toLocaleDateString("en-GB", { day: "2-digit", month: "short" })}</span>}
    </span>
  );
}
