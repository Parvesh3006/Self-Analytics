"use client";

import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { clsx } from "clsx";
import { type MapPlace, WorldMap } from "@/components/charts";
import { Postmark } from "@/components/postmark";
import { useMoney } from "@/components/providers";
import { Empty, ErrorNote, Hint, Notice, PageTitle, Panel, RankBars, Rows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { count } from "@/lib/format";

type Country = { code: string; name: string; jobs: number; median_usd: number | null; with_salary: number; remote_share: number; new_7d: number; top_skill: string | null; priority: boolean };
type SortKey = "jobs" | "new_7d" | "median_usd" | "remote_share";
const MIN_FOR_MEDIAN = 5; // a median of two postings is an anecdote

export default function MarketsPage() {
  const f = useFilters();
  const { money } = useMoney();
  const suffix = f.query ? `?${f.query}` : "";
  const overview = useApi(`/api/market/overview${suffix}`);
  const countries = useApi<Country[]>(`/api/market/countries${suffix}`);
  const skills = useApi(`/api/market/skills${suffix}${suffix ? "&" : "?"}limit=12`);
  const roles = useApi<any[]>(`/api/market/roles${suffix}`);
  const companies = useApi<any[]>(`/api/market/companies${suffix}`);
  const provenance = useApi(`/api/market/provenance${suffix}`);
  const status = useApi("/api/status");
  const selected = f.getList("country");
  const singleCountry = selected.length === 1 && selected[0] !== "EU" && selected[0] !== "XX";
  const states = useApi<any[]>(singleCountry ? `/api/market/locations?${f.query}&level=state` : null);
  const cities = useApi<any[]>(singleCountry ? `/api/market/locations?${f.query}&level=city` : null);
  const [sort, setSort] = useState<SortKey>("jobs");
  const [priorityOnly, setPriorityOnly] = useState(false);

  const o = overview.data;
  const toggleCountry = (code: string) => f.set("country", (selected.includes(code) ? selected.filter((c) => c !== code) : [...selected, code]).join(",") || null);
  const pickPlace = (place: MapPlace, level: "state" | "city") => {
    if (level === "state") f.setMany(f.get("state") === place.name ? { state: null } : { country: place.code, state: place.name });
    else f.setMany(f.get("city") === place.name ? { city: null } : { country: place.code, state: place.state, city: place.name });
  };
  // A first crawl finds mostly recent postings, so week-on-week means nothing until two weeks have been collected.
  const collectedDays = status.data?.first_collected ? (Date.now() - new Date(status.data.first_collected).getTime()) / 86_400_000 : 0;
  const change = o && o.prev_7d > 0 && collectedDays >= 14 ? Math.round(((o.new_7d - o.prev_7d) / o.prev_7d) * 100) : null;
  const median = (row: { median_usd: number | null; with_salary: number }) => (row.median_usd && row.with_salary >= MIN_FOR_MEDIAN ? money(row.median_usd) : undefined);
  const rows = useMemo(() => {
    const list = (countries.data ?? []).filter((c) => !priorityOnly || c.priority);
    return [...list].sort((a, b) => (b[sort] ?? -1) - (a[sort] ?? -1));
  }, [countries.data, priorityOnly, sort]);
  const countryName = singleCountry ? countries.data?.find((c) => c.code === selected[0])?.name : null;
  const topSource = provenance.data?.top?.[0];

  if (status.data && status.data.jobs === 0) {
    return (
      <>
        <PageTitle title="Markets" />
        <Panel><Empty title="No jobs collected yet">Open <Link className="text-air-blue underline" href="/sources">Sources</Link> and run a source, or wait for the next scheduled collection.</Empty></Panel>
      </>
    );
  }

  const Header = ({ k, children }: { k: SortKey; children: React.ReactNode }) => (
    <th className="num" aria-sort={sort === k ? "descending" : "none"}><button className={clsx("hover:text-ink", sort === k && "text-ink underline underline-offset-4 decoration-air-red decoration-2")} onClick={() => setSort(k)}>{children}</button></th>
  );

  return (
    <>
      <PageTitle title={countryName ? `${countryName} market` : "Compare markets"} note="Open jobs collected from your sources. These are counts of what was collected, not totals for the whole job market." />

      <section className={clsx("panel px-4 py-3 mb-4 flex flex-wrap items-center gap-x-9 gap-y-3 transition-opacity", overview.isPlaceholderData && "opacity-60")} aria-label="Summary">
        {overview.isError ? <ErrorNote error={overview.error} retry={overview.refetch} /> : <>
          <Stat label="Open jobs" value={o ? count(o.jobs) : null} sub={o ? `at ${count(o.companies)} companies` : ""} />
          <Stat label="Posted in last 7 days" value={o ? count(o.new_7d) : null} sub={change != null ? <Delta value={change} /> : "Weekly change needs 2 weeks of history"} />
          <Stat label="Median advertised salary" hint="Half of jobs that state pay offer more than this, annualised and converted at current exchange rates." value={o ? median({ median_usd: o.median_usd, with_salary: o.with_salary }) ?? "Too few" : null} sub={o ? `from ${count(o.with_salary)} jobs stating pay` : ""} />
          <Stat label="Remote" value={o ? `${Math.round(o.remote_share)}%` : null} sub="of open jobs" />
          <div className="ml-auto flex items-center gap-2.5">
            <p className="text-xs text-ink-2 text-right leading-snug max-w-40 hidden sm:block">Built from <b className="text-ink tnum">{count(provenance.data?.total_sources)}</b> sources. Largest is {topSource?.name ?? "..."}.</p>
            {topSource && <Postmark source={topSource.name} date={topSource.last_seen} detail={`${count(topSource.jobs)} jobs`} />}
          </div>
        </>}
      </section>

      <div className="grid xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] gap-4 mb-4">
        <Panel title="Where the jobs are" note="Darker means more open jobs. Zoom in for states and cities, where larger circles mean more jobs. Select a place to focus every view on it." dimmed={countries.isPlaceholderData}>
          {countries.isError ? <ErrorNote error={countries.error} retry={countries.refetch} /> : <WorldMap rows={countries.data ?? []} selected={selected} onPick={toggleCountry} query={f.query} onPlace={pickPlace} />}
        </Panel>
        {singleCountry ? (
          <Panel title="Top states and regions" note="Select one to narrow to it." dimmed={states.isPlaceholderData}>
            {states.isLoading ? <Rows n={9} /> : states.data?.length ? <RankBars valueLabel="Open jobs by state" rows={states.data.slice(0, 11).map((s) => ({ label: s.name, value: s.jobs, hint: median(s), selected: f.get("state") === s.name }))} onPick={(name) => f.set("state", f.get("state") === name ? null : name)} /> : <Empty title="No state information">These postings do not name a state or region.</Empty>}
          </Panel>
        ) : (
          <Panel title="Your priority markets" note="Open jobs, with the median salary where stated." dimmed={countries.isPlaceholderData}>
            {countries.isLoading ? <Rows n={8} /> : <RankBars valueLabel="Open jobs in priority markets" rows={(countries.data ?? []).filter((c) => c.priority).map((c) => ({ key: c.code, label: c.name, value: c.jobs, hint: median(c) ?? "too few salaries" }))} onPick={toggleCountry} />}
          </Panel>
        )}
      </div>

      {singleCountry && (
        <Panel title={`Cities in ${countryName ?? "this country"}`} className="mb-4" dimmed={cities.isPlaceholderData}>
          {cities.data?.length ? <div className="columns-1 md:columns-2 xl:columns-3 gap-6"><RankBars valueLabel="Open jobs by city" rows={cities.data.slice(0, 30).map((c) => ({ label: c.name, value: c.jobs, hint: median(c), selected: f.get("city") === c.name }))} onPick={(name) => f.set("city", f.get("city") === name ? null : name)} /></div> : <Empty title="No city information">These postings do not name a city.</Empty>}
        </Panel>
      )}

      <Panel className="mb-4" title="Country comparison" note="Select a column heading to rank by it." dimmed={countries.isPlaceholderData}
        action={<label className="flex items-center gap-1.5 text-[0.8125rem] font-medium"><input type="checkbox" className="accent-air-blue" checked={priorityOnly} onChange={(e) => setPriorityOnly(e.target.checked)} />Priority markets only</label>}>
        <div className="overflow-auto max-h-[28rem]">
          <table className="data-table">
            <thead><tr><th>Country</th><Header k="jobs">Open jobs</Header><Header k="new_7d">New in 7 days</Header><Header k="median_usd">Median salary</Header><th className="num">Jobs stating pay</th><Header k="remote_share">Remote</Header><th>Most named skill</th></tr></thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.code} className="cursor-pointer" onClick={() => toggleCountry(c.code)}>
                  <td className="font-medium"><button className="hover:underline text-left">{c.name}</button></td>
                  <td className="num font-semibold">{count(c.jobs)}</td><td className="num">{count(c.new_7d)}</td><td className="num">{median(c) ?? <span className="text-ink-3">Too few</span>}</td>
                  <td className="num text-ink-2">{count(c.with_salary)}</td><td className="num">{Math.round(c.remote_share)}%</td><td>{c.top_skill ?? <span className="text-ink-3">None found</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {countries.data?.length === 0 && <Empty title="No jobs match these filters">Remove a filter to see more.</Empty>}
        </div>
      </Panel>

      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        <Panel title="Skills in demand" note="Share of these jobs that name the skill." dimmed={skills.isPlaceholderData}>
          {skills.isLoading ? <Rows n={10} /> : <RankBars valueLabel="Skills" rows={(skills.data?.skills ?? []).map((s: any) => ({ label: s.skill, value: s.jobs, display: `${s.share}%`, selected: f.getList("skill").includes(s.skill) }))} onPick={(name) => { const list = f.getList("skill"); f.set("skill", (list.includes(name) ? list.filter((x) => x !== name) : [...list, name]).join(",") || null); }} />}
        </Panel>
        <Panel title="Roles" note="Open jobs and median salary." dimmed={roles.isPlaceholderData}>
          {roles.isLoading ? <Rows n={10} /> : <RankBars valueLabel="Roles" rows={(roles.data ?? []).slice(0, 12).map((r) => ({ label: r.role, value: r.jobs, hint: median(r) }))} onPick={(name) => f.set("role", name)} />}
        </Panel>
        <Panel title="Hiring companies" note="Companies with the most open jobs here." dimmed={companies.isPlaceholderData}>
          {companies.isLoading ? <Rows n={10} /> : <RankBars valueLabel="Companies" rows={(companies.data ?? []).slice(0, 12).map((c) => ({ label: c.company, value: c.jobs }))} />}
        </Panel>
      </div>
      {o && o.with_salary < o.jobs * 0.2 && <div className="mt-4"><Notice tone="warn">Only {Math.round((100 * o.with_salary) / Math.max(o.jobs, 1))}% of these jobs state a salary, so salary figures describe that smaller group.</Notice></div>}
    </>
  );
}

function Stat({ label, value, sub, hint }: { label: string; value: string | null; sub: React.ReactNode; hint?: string }) {
  return (
    <div>
      <p className="text-[0.8125rem] text-ink-2 flex items-center gap-1">{label}{hint && <Hint text={hint} />}</p>
      {value === null ? <div className="skeleton h-7 w-24 my-0.5" /> : <p className="text-[1.625rem] leading-8 font-bold tracking-tight">{value}</p>}
      <p className="text-xs text-ink-2">{sub}</p>
    </div>
  );
}

function Delta({ value }: { value: number }) {
  const Icon = value >= 0 ? ArrowUpRight : ArrowDownRight;
  return <span className="inline-flex items-center gap-0.5"><Icon size={13} aria-hidden />{value >= 0 ? "Up" : "Down"} {Math.abs(value)}% on the week before</span>;
}
