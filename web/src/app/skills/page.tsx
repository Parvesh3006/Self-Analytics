"use client";

import { Fragment, useMemo, useState } from "react";
import { clsx } from "clsx";
import { SERIES, TrendLines } from "@/components/charts";
import { Facet } from "@/components/facet";
import { Empty, ErrorNote, Notice, PageTitle, Panel, Rows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { useFilters } from "@/lib/filters";
import { count, shortDate } from "@/lib/format";

const RAMP = ["#eef4fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];

export default function SkillsPage() {
  const f = useFilters();
  const [picked, setPicked] = useState<string[]>([]);
  const [asTable, setAsTable] = useState(false);
  const prefix = f.query ? `${f.query}&` : "";
  const trends = useApi(`/api/trends/skills?${prefix}weeks=16${picked.length ? `&skills=${encodeURIComponent(picked.join(","))}` : ""}`);
  const movers = useApi(`/api/trends/movers${f.query ? `?${f.query}` : ""}`);
  const heat = useApi(`/api/trends/heatmap${f.query ? `?${f.query}` : ""}`);
  const facets = useApi(`/api/facets${f.query ? `?${f.query}` : ""}`);
  const status = useApi("/api/status");

  const colorOf = useMemo(() => {
    const map: Record<string, string> = {};
    (trends.data?.series ?? []).forEach((s: any, i: number) => { map[s.skill] = SERIES[i % SERIES.length]; });
    return map;
  }, [trends.data]);
  const chartSeries = (trends.data?.series ?? []).map((s: any) => ({ name: s.skill, values: s.share, color: colorOf[s.skill] }));
  const cell = (country: string, skill: string) => heat.data?.cells.find((c: any) => c.country === country && c.skill === skill);
  const maxShare = Math.max(...(heat.data?.cells ?? []).map((c: any) => c.share), 1);

  return (
    <>
      <PageTitle title="Skill trends" note="Which skills employers are asking for, and how that is changing. Trends use each skill's share of postings, so collecting more jobs does not look like rising demand." />
      {status.data?.first_collected && <div className="mb-4"><Notice tone="warn">Collection began on {shortDate(status.data.first_collected)}. Earlier weeks only include jobs that were still open then, so older weeks look smaller and the trend gets more reliable as history builds.</Notice></div>}

      <Panel className="mb-4" title="Demand over time" note="Percent of each week's postings naming the skill." dimmed={trends.isPlaceholderData}
        action={<div className="flex items-center gap-1.5">
          <Facet label="Compare skills" multiple options={(facets.data?.skills ?? []).map((s: any) => ({ value: s.value, count: s.count }))} selected={picked} onChange={(v) => setPicked(v.slice(0, 8))} />
          <button className="btn" onClick={() => setAsTable(!asTable)}>{asTable ? "Show chart" : "Show table"}</button>
        </div>}>
        {trends.isLoading ? <Rows n={8} /> : trends.isError ? <ErrorNote error={trends.error} retry={trends.refetch} /> : !trends.data.weeks.length ? <Empty title="No postings in this period">Clear some filters to see trends.</Empty> : asTable ? (
          <div className="overflow-auto max-h-80">
            <table className="data-table"><thead><tr><th>Week of</th><th className="num">Postings</th>{trends.data.series.map((s: any) => <th key={s.skill} className="num">{s.skill}</th>)}</tr></thead>
              <tbody>{trends.data.weeks.map((w: string, i: number) => <tr key={w}><td>{shortDate(w)}</td><td className="num">{count(trends.data.totals[i])}</td>{trends.data.series.map((s: any) => <td key={s.skill} className="num">{s.share[i]}%</td>)}</tr>)}</tbody></table>
          </div>
        ) : (
          <>
            <TrendLines weeks={trends.data.weeks} series={chartSeries} />
            <ul className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-[0.8125rem]" aria-label="Legend">{chartSeries.map((s: any) => <li key={s.name} className="inline-flex items-center gap-1.5"><span className="w-3 h-0.5" style={{ background: s.color }} aria-hidden />{s.name}</li>)}</ul>
          </>
        )}
      </Panel>

      <div className="grid md:grid-cols-2 gap-4 mb-4">
        <Movers title="Gaining share" rows={movers.data?.rising} loading={movers.isLoading} direction="up" />
        <Movers title="Losing share" rows={movers.data?.falling} loading={movers.isLoading} direction="down" />
        {movers.data && !movers.data.enough && <div className="md:col-span-2"><Notice tone="warn">Early hints only. Until about four weeks have been collected, recent dates mostly reflect which sources post short-lived ads, so a change here may not be a real shift in demand.</Notice></div>}
      </div>

      <Panel title="Skills by country" note="Percent of each country's postings naming the skill. Darker means more common." dimmed={heat.isPlaceholderData}>
        {heat.isLoading ? <Rows n={8} /> : heat.isError ? <ErrorNote error={heat.error} retry={heat.refetch} /> : !heat.data.countries.length ? <Empty title="No country data for these filters" /> : (
          <div className="overflow-auto">
            <div className="grid gap-[2px] min-w-[52rem] text-[0.8125rem]" style={{ gridTemplateColumns: `9rem repeat(${heat.data.skills.length}, minmax(3.25rem, 1fr))` }}>
              <div />
              {heat.data.skills.map((s: string) => <div key={s} className="font-semibold text-xs px-1 pb-1 self-end truncate" title={s}>{s}</div>)}
              {heat.data.countries.map((c: any) => (
                <Fragment key={c.code}>
                  <div className="font-medium pr-2 self-center truncate">{c.name}<span className="block text-2xs text-ink-3 font-normal tnum">{count(c.jobs)} jobs</span></div>
                  {heat.data.skills.map((s: string) => {
                    const v = cell(c.code, s);
                    const step = v ? Math.min(RAMP.length - 1, Math.floor((v.share / maxShare) * RAMP.length)) : 0;
                    return <div key={s} title={`${c.name}, ${s}: ${v ? `${v.share}% (${v.jobs} jobs)` : "none"}`} className={clsx("h-9 flex items-center justify-center tnum text-xs rounded-[2px]", step >= 4 && "text-white")} style={{ background: RAMP[step] }}>{v ? `${Math.round(v.share)}` : ""}</div>;
                  })}
                </Fragment>
              ))}
            </div>
          </div>
        )}
      </Panel>
    </>
  );
}

function Movers({ title, rows, loading, direction }: { title: string; rows?: any[]; loading: boolean; direction: "up" | "down" }) {
  return (
    <Panel title={title} note="Share of postings in the last 14 days, against the six weeks before.">
      {loading ? <Rows /> : rows?.length ? (
        <table className="data-table"><thead><tr><th>Skill</th><th className="num">Before</th><th className="num">Now</th><th className="num">Change</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r.skill}><td className="font-medium">{r.skill}</td><td className="num">{r.share_before}%</td><td className="num">{r.share_now}%</td><td className="num font-semibold">{direction === "up" ? "+" : ""}{r.change} pts</td></tr>)}</tbody></table>
      ) : <Empty title="Nothing to show yet">This appears once there are enough postings in both periods.</Empty>}
    </Panel>
  );
}
