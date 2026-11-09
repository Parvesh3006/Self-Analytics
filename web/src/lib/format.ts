export const CURRENCIES = ["USD", "AUD", "CAD", "GBP", "EUR", "INR", "SGD", "NZD"] as const;
export type Currency = (typeof CURRENCIES)[number];

const SYMBOL: Record<string, string> = { USD: "US$", AUD: "A$", CAD: "C$", GBP: "£", EUR: "€", INR: "₹", SGD: "S$", NZD: "NZ$" };

export function compactMoney(usd: number | null | undefined, currency: string, perUsd: Record<string, number> | undefined): string {
  if (usd == null) return "Not stated";
  const value = usd * (currency === "USD" ? 1 : perUsd?.[currency] ?? 1);
  const unit = currency !== "USD" && !perUsd?.[currency] ? "US$" : SYMBOL[currency] ?? "";
  if (currency === "INR" && value >= 100000) return `₹${(value / 100000).toFixed(1)}L`;
  return `${unit}${value >= 1000 ? `${Math.round(value / 1000)}k` : Math.round(value)}`;
}

export function originalPay(job: { salary_min?: number | null; salary_max?: number | null; salary_currency?: string | null; salary_period?: string | null }): string | null {
  if (job.salary_min == null || !job.salary_currency) return null;
  const n = (v: number) => v.toLocaleString("en", { maximumFractionDigits: 0 });
  const unit = SYMBOL[job.salary_currency] ?? `${job.salary_currency} `;
  const range = job.salary_max ? `${unit}${n(job.salary_min)} to ${unit}${n(job.salary_max)}` : `${unit}${n(job.salary_min)}`;
  return `${range} a ${job.salary_period ?? "year"}`;
}

export const count = (n: number | null | undefined) => (n ?? 0).toLocaleString("en");

export function shortDate(value: string | null | undefined): string {
  if (!value) return "Unknown";
  return new Date(value).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function timeAgo(value: string | null | undefined): string {
  if (!value) return "never";
  const minutes = Math.round((Date.now() - new Date(value).getTime()) / 60000);
  if (minutes < 2) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 60) return `${days} day${days === 1 ? "" : "s"} ago`;
  return shortDate(value);
}

export function place(job: { city?: string | null; state?: string | null; country?: string | null; location_raw?: string | null; workplace?: string }): string {
  const known = [job.city, job.state, job.country].filter(Boolean).join(", ");
  if (known) return known;
  return job.location_raw || (job.workplace === "remote" ? "Remote" : "Location not stated");
}

export const WORKPLACE: Record<string, string> = { remote: "Remote", hybrid: "Hybrid", onsite: "On-site", unknown: "Not stated" };
