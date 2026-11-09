"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

export const FILTER_KEYS = ["country", "state", "city", "role", "skill", "workplace", "salary_min", "days", "q", "visa"] as const;
export type FilterKey = (typeof FILTER_KEYS)[number];

/** Filters live in the URL, so every view can be bookmarked and all pages share one selection. */
export function useFilters() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const query = useMemo(() => {
    const out = new URLSearchParams();
    for (const key of FILTER_KEYS) {
      const value = params.get(key);
      if (value) out.set(key, value);
    }
    return out.toString();
  }, [params]);

  const get = useCallback((key: FilterKey) => params.get(key) ?? "", [params]);
  const getList = useCallback((key: FilterKey) => (params.get(key) ?? "").split(",").filter(Boolean), [params]);

  const setMany = useCallback(
    (changes: Partial<Record<FilterKey, string | null>>) => {
      const next = new URLSearchParams(params.toString());
      next.delete("page");
      for (const [key, value] of Object.entries(changes)) {
        if (value) next.set(key, value);
        else next.delete(key);
      }
      // A city or state belongs to a country, so they do not survive a country change.
      if ("country" in changes) { next.delete("state"); next.delete("city"); }
      if ("state" in changes && !("city" in changes)) next.delete("city");
      const text = next.toString();
      router.replace(text ? `${pathname}?${text}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  const set = useCallback((key: FilterKey, value: string | null) => setMany({ [key]: value }), [setMany]);
  const clear = useCallback(() => router.replace(pathname, { scroll: false }), [pathname, router]);
  const withQuery = useCallback((path: string, extra?: Record<string, string>) => {
    const merged = new URLSearchParams(query);
    for (const [k, v] of Object.entries(extra ?? {})) merged.set(k, v);
    const text = merged.toString();
    return text ? `${path}${path.includes("?") ? "&" : "?"}${text}` : path;
  }, [query]);

  return { query, get, getList, set, setMany, clear, withQuery, active: query.length > 0 };
}
