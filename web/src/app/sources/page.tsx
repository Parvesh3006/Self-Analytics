"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, CircleDashed, KeyRound, Link2, ShieldBan } from "lucide-react";
import { useMemo, useState } from "react";
import { Empty, ErrorNote, Notice, PageTitle, Panel, Rows, Tabs } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { count, timeAgo } from "@/lib/format";

const STATUS: Record<string, { label: string; icon: any; color: string }> = {
  active: { label: "Collecting", icon: CircleCheck, color: "text-good" },
  new: { label: "Waiting for first run", icon: CircleDashed, color: "text-ink-2" },
  needs_key: { label: "Needs API key", icon: KeyRound, color: "text-warn" },
  blocked: { label: "Blocked", icon: ShieldBan, color: "text-bad" },
  error: { label: "Problem", icon: CircleAlert, color: "text-bad" },
  reference: { label: "Not a job feed", icon: Link2, color: "text-ink-3" },
};
const METHOD: Record<string, string> = { api: "API or feed", jsonld: "Structured pages", crawl: "Polite crawl", auto: "To be checked", insight: "Report reader", blocked: "Not collected", none: "Not collected", discover: "Via employer boards", rss: "RSS" };

export default function SourcesPage() {
  const client = useQueryClient();
  const [tab, setTab] = useState("all");
  const [search, setSearch] = useState("");
  const [url, setUrl] = useState("");
  const { data, isLoading, isError, error, refetch } = useApi("/api/sources", 15_000);
  const runs = useApi<any[]>("/api/runs?limit=30", 15_000);
  const refresh = () => { client.invalidateQueries({ queryKey: ["/api/sources"] }); client.invalidateQueries({ queryKey: ["/api/runs?limit=30"] }); };
  const add = useMutation({ mutationFn: () => api("/api/sources", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) }), onSuccess: () => { setUrl(""); refresh(); } });
  const run = useMutation({ mutationFn: (id: number) => api(`/api/sources/${id}/run`, { method: "POST" }), onSuccess: refresh });

  const counts = data?.counts ?? {};
  const rows = useMemo(() => (data?.sources ?? []).filter((s: any) => (tab === "all" || s.status === tab) && (!search || `${s.name} ${s.url} ${s.section}`.toLowerCase().includes(search.toLowerCase()))), [data, tab, search]);
  const total = Object.values(counts).reduce<number>((a, b) => a + Number(b), 0);
  const tabs = [{ value: "all", label: "All", count: total }, ...["active", "new", "needs_key", "blocked", "error", "reference"].filter((s) => counts[s]).map((s) => ({ value: s, label: STATUS[s].label, count: counts[s] as number }))];

  return (
    <>
      <PageTitle title="Sources" note="Every site you gave this app, how it is collected, and why some are not." />
      {counts.needs_key > 0 && <div className="mb-3"><Notice tone="warn">{counts.needs_key} sources are waiting for a free API key. Add keys to the .env file, restart, and they start collecting.</Notice></div>}
      <div className="grid xl:grid-cols-[minmax(0,1fr)_18rem] gap-4 items-start">
        <Panel>
          <div className="flex flex-wrap gap-2 mb-2">
            <form className="flex gap-1.5 flex-1 min-w-64" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
              <input aria-label="Add a site" className="field flex-1 min-w-0" placeholder="Add a site: https://example.com/jobs" value={url} onChange={(e) => setUrl(e.target.value)} />
              <button className="btn btn-primary" disabled={!url.trim() || add.isPending}>{add.isPending ? "Adding..." : "Add and check"}</button>
            </form>
            <input aria-label="Search sources" className="field w-52" placeholder="Search sources" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          {add.isError && <p role="alert" className="text-bad mb-2 font-medium">{(add.error as Error).message}</p>}
          <Tabs tabs={tabs} value={tab} onChange={setTab} />
          {isLoading ? <div className="mt-3"><Rows n={14} /></div> : isError ? <ErrorNote error={error} retry={refetch} /> : rows.length === 0 ? <Empty title="No sources here" /> : (
            <div className="overflow-auto max-h-[70vh]">
              <table className="data-table">
                <thead><tr><th>Source</th><th>Status</th><th>Method</th><th className="num">Jobs</th><th>Last run</th><th /></tr></thead>
                <tbody>
                  {rows.map((s: any) => {
                    const st = STATUS[s.status] ?? STATUS.new;
                    const Icon = st.icon;
                    const canRun = s.enabled && !["blocked", "reference"].includes(s.status);
                    return (
                      <tr key={s.id}>
                        <td className="min-w-40"><a href={s.url} target="_blank" rel="noreferrer" className="font-medium hover:underline">{s.name}</a><div className="text-xs text-ink-2">{s.section} · {s.region}</div></td>
                        <td className="min-w-44"><span className={`inline-flex items-center gap-1 font-medium ${st.color}`}><Icon size={14} aria-hidden />{st.label}</span>{s.status_reason && <div className="text-xs text-ink-2 max-w-[34ch]">{s.status_reason}</div>}</td>
                        <td className="whitespace-nowrap">{METHOD[s.strategy] ?? s.strategy}</td>
                        <td className="num font-semibold">{s.jobs_total ? count(s.jobs_total) : ""}</td>
                        <td className="whitespace-nowrap text-ink-2">{s.last_run_at ? timeAgo(s.last_run_at) : "Not yet"}</td>
                        <td>{canRun && <button className="btn !h-7 text-xs" disabled={run.isPending && run.variables === s.id} onClick={() => run.mutate(s.id)}>Run now</button>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
        <Panel title="Recent activity" className="xl:sticky xl:top-6">
          {runs.isLoading ? <Rows /> : runs.data?.length ? (
            <ul className="divide-y divide-line max-h-[70vh] overflow-auto">
              {runs.data.map((r) => (
                <li key={r.id} className="py-2">
                  <p className="flex items-baseline justify-between gap-2"><span className="font-medium truncate">{r.source}</span><span className="text-xs text-ink-3 whitespace-nowrap">{r.status === "running" ? "Running" : timeAgo(r.finished_at)}</span></p>
                  <p className="text-xs text-ink-2 line-clamp-2">{r.message ?? "In progress"}</p>
                </li>
              ))}
            </ul>
          ) : <Empty title="No collection runs yet" />}
        </Panel>
      </div>
    </>
  );
}
