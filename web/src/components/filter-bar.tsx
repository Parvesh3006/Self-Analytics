"use client";

import * as Popover from "@radix-ui/react-popover";
import { useQueryClient } from "@tanstack/react-query";
import { Bell, Bookmark, Search, Trash2, X } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, useApi } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { Facet, type FacetOption } from "./facet";
import { useMoney } from "./providers";

const SALARY_USD = [30000, 50000, 75000, 100000, 150000, 200000];
const DATES = [["1", "Last 24 hours"], ["7", "Last 7 days"], ["30", "Last 30 days"], ["90", "Last 90 days"]];

export function FilterBar() {
  const f = useFilters();
  const { money } = useMoney();
  const { data } = useApi(`/api/facets${f.query ? `?${f.query}` : ""}`);
  const [search, setSearch] = useState(f.get("q"));
  const urlQ = f.get("q");
  useEffect(() => setSearch(urlQ), [urlQ]);
  useEffect(() => {
    if (search === urlQ) return;
    const timer = setTimeout(() => f.set("q", search || null), 350);
    return () => clearTimeout(timer);
    // Only the typed text should restart the debounce.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const countries: FacetOption[] = data ? [
    ...data.countries.filter((c: any) => c.priority).map((c: any) => ({ value: c.value, label: c.label, count: c.count, group: "Your priority markets" })),
    ...(data.europe_total ? [{ value: data.europe_code, label: "Europe (all countries)", count: data.europe_total, group: "Your priority markets" }] : []),
    ...(data.no_country ? [{ value: "XX", label: "Remote, no single country", count: data.no_country, group: "Your priority markets" }] : []),
    ...data.countries.filter((c: any) => !c.priority).map((c: any) => ({ value: c.value, label: c.label, count: c.count, group: "All countries" })),
  ] : [];
  const hasCountry = f.getList("country").length > 0;
  const facet = (rows?: any[]): FacetOption[] => (rows ?? []).map((r) => ({ value: r.value, count: r.count }));
  const one = (key: "state" | "city" | "workplace" | "salary_min" | "days") => (v: string[]) => f.set(key, v[0] ?? null);

  return (
    <div className="bg-paper/95 border-b border-line px-4 lg:px-6 py-2.5 flex flex-wrap items-center gap-1.5 sticky top-[3px] z-10">
      <div className="relative">
        <Search size={15} aria-hidden className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-3" />
        <input aria-label="Search jobs" className="field w-36 !pl-8" placeholder="Search jobs" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      <Facet label="Country" multiple options={countries} selected={f.getList("country")} onChange={(v) => f.set("country", v.join(",") || null)} />
      <Facet label="State" options={facet(data?.states)} selected={f.get("state") ? [f.get("state")] : []} onChange={one("state")} disabled={!hasCountry} disabledHint="Choose a country first" />
      <Facet label="City" options={facet(data?.cities)} selected={f.get("city") ? [f.get("city")] : []} onChange={one("city")} disabled={!hasCountry} disabledHint="Choose a country first" />
      <Facet label="Role" multiple options={facet(data?.roles)} selected={f.getList("role")} onChange={(v) => f.set("role", v.join(",") || null)} />
      <Facet label="Skill" multiple options={facet(data?.skills)} selected={f.getList("skill")} onChange={(v) => f.set("skill", v.join(",") || null)} />
      <Facet label="Work type" options={[{ value: "remote", label: "Remote" }, { value: "hybrid", label: "Hybrid" }, { value: "onsite", label: "On-site" }]} selected={f.get("workplace") ? [f.get("workplace")] : []} onChange={one("workplace")} />
      <Facet label="Salary" options={SALARY_USD.map((v) => ({ value: String(v), label: `${money(v)} or more` }))} selected={f.get("salary_min") ? [f.get("salary_min")] : []} onChange={one("salary_min")} />
      <Facet label="Posted" options={DATES.map(([value, label]) => ({ value, label }))} selected={f.get("days") ? [f.get("days")] : []} onChange={one("days")} />
      <label className="field inline-flex items-center gap-1.5 font-medium cursor-pointer" data-active={f.get("visa") === "true"}>
        <input type="checkbox" className="accent-air-blue" checked={f.get("visa") === "true"} onChange={(e) => f.set("visa", e.target.checked ? "true" : null)} /> Visa
      </label>
      {f.active && <button className="btn !border-transparent !bg-transparent hover:!bg-sheet-2 text-air-blue" onClick={f.clear}><X size={14} aria-hidden />Clear all</button>}
      <SavedViews />
    </div>
  );
}

function SavedViews() {
  const f = useFilters();
  const pathname = usePathname();
  const router = useRouter();
  const client = useQueryClient();
  const { data: saved } = useApi<any[]>("/api/saved-filters");
  const [name, setName] = useState("");
  const [alert, setAlert] = useState(true);
  const refresh = () => client.invalidateQueries({ queryKey: ["/api/saved-filters"] });
  const newJobs = (saved ?? []).reduce((sum, s) => sum + (s.new_jobs ?? 0), 0);

  const save = async () => {
    await api("/api/saved-filters", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: name.trim(), filters: Object.fromEntries(new URLSearchParams(f.query)), alert }) });
    setName("");
    refresh();
  };
  const open = async (item: any) => {
    if (item.alert) { await api(`/api/saved-filters/${item.id}/seen`, { method: "POST" }); refresh(); }
    const text = new URLSearchParams(item.filters).toString();
    router.replace(text ? `${pathname}?${text}` : pathname);
  };
  const remove = async (id: number) => { await api(`/api/saved-filters/${id}`, { method: "DELETE" }); refresh(); };

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button className="btn ml-auto"><Bookmark size={14} aria-hidden />Saved views{newJobs > 0 && <span className="ml-0.5 px-1.5 rounded-full bg-air-red text-white text-xs tnum">{newJobs}</span>}</button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="end" sideOffset={4} className="z-50 w-80 bg-sheet rounded-md shadow-pop border border-line p-3">
          <h2 className="font-semibold">Save this view</h2>
          <div className="flex gap-1.5 mt-2">
            <input aria-label="View name" className="field flex-1 min-w-0" placeholder="e.g. Data roles in Sydney" value={name} onChange={(e) => setName(e.target.value)} />
            <button className="btn btn-primary" disabled={!name.trim() || !f.active} onClick={save}>Save</button>
          </div>
          {!f.active && <p className="text-xs text-ink-2 mt-1.5">Choose at least one filter first.</p>}
          <label className="flex items-center gap-1.5 mt-2 text-[0.8125rem]"><input type="checkbox" className="accent-air-blue" checked={alert} onChange={(e) => setAlert(e.target.checked)} />Count new jobs that match</label>
          <ul className="mt-3 border-t border-line divide-y divide-line">
            {(saved ?? []).map((item) => (
              <li key={item.id} className="flex items-center gap-1 py-1">
                <button className="flex-1 text-left truncate hover:underline font-medium" onClick={() => open(item)}>{item.name}</button>
                {item.new_jobs > 0 && <span className="text-xs tnum inline-flex items-center gap-0.5 text-air-red font-semibold"><Bell size={11} aria-hidden />{item.new_jobs} new</span>}
                <button aria-label={`Delete ${item.name}`} className="p-1 text-ink-3 hover:text-bad" onClick={() => remove(item.id)}><Trash2 size={14} aria-hidden /></button>
              </li>
            ))}
            {saved?.length === 0 && <li className="py-2 text-[0.8125rem] text-ink-2">Saved views appear here, ready to reopen.</li>}
          </ul>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
