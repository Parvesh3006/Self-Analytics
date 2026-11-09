"use client";

import { Send } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { clsx } from "clsx";
import { Notice, PageTitle } from "@/components/ui";
import { useApi } from "@/lib/api";

type Citation = { n: number; title: string; url: string; kind: string };
type Message = { role: "user" | "assistant"; content: string; citations?: Citation[]; status?: string; error?: string };

const STARTERS = [
  "How many Python jobs are in Australia this month?",
  "Which skills are most in demand for data engineers in Canada?",
  "What is the median salary for machine learning jobs in the UK?",
  "Which jobs suit my CV best?",
  "Find remote backend roles that mention visa sponsorship",
  "What do the reports say about skill shortages in Australia?",
];

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const { data: status } = useApi("/api/status");
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [messages]);

  const ask = async (question: string) => {
    if (!question.trim() || busy) return;
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((m) => [...m, { role: "user", content: question }, { role: "assistant", content: "", status: "Starting" }]);
    setDraft("");
    setBusy(true);
    const patch = (fn: (m: Message) => Message) => setMessages((all) => [...all.slice(0, -1), fn(all[all.length - 1])]);
    try {
      const response = await fetch("/api/assistant", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, history }) });
      if (!response.ok || !response.body) throw new Error(`The assistant could not start (${response.status}).`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const event = frame.match(/^event: (.*)$/m)?.[1];
          const raw = frame.match(/^data: (.*)$/m)?.[1];
          if (!event || !raw) continue;
          const data = JSON.parse(raw);
          if (event === "status") patch((m) => ({ ...m, status: data.text }));
          if (event === "sources") patch((m) => ({ ...m, citations: data.citations }));
          if (event === "token") patch((m) => ({ ...m, status: undefined, content: m.content + data.text }));
          if (event === "error") patch((m) => ({ ...m, status: undefined, error: data.text }));
        }
      }
      patch((m) => ({ ...m, status: undefined }));
    } catch (error) {
      patch((m) => ({ ...m, status: undefined, error: error instanceof Error ? error.message : "The assistant is not responding." }));
    } finally {
      setBusy(false);
    }
  };

  const noModel = status && !status.llm.assistant_model && !status.llm.cloud_fallback;

  return (
    <div className="max-w-3xl mx-auto flex flex-col min-h-[calc(100dvh-5.5rem)]">
      <PageTitle title="Ask AI" note="Ask anything about the jobs and reports collected here. Answers cite what they used." />
      {noModel && <div className="mb-3"><Notice tone="warn">The language model is not available, so answers show the raw evidence. Start Ollama with {`qwen3:8b`} for written answers.</Notice></div>}
      <div className="flex-1 space-y-5 pb-4">
        {messages.length === 0 && (
          <ul className="grid sm:grid-cols-2 gap-2">
            {STARTERS.map((s) => <li key={s}><button onClick={() => ask(s)} className="panel w-full h-full text-left px-3 py-2.5 hover:border-air-blue transition-colors">{s}</button></li>)}
          </ul>
        )}
        {messages.map((m, i) => m.role === "user" ? (
          <p key={i} className="ml-auto w-fit max-w-[85%] bg-rail text-white px-3.5 py-2 rounded-md">{m.content}</p>
        ) : (
          <article key={i} className="panel p-4">
            {m.status && <div><div className="airmail-edge airmail-transit mb-2 rounded-full" aria-hidden /><p className="text-[0.8125rem] text-ink-2" role="status">{m.status}</p></div>}
            {m.content && <div className="leading-relaxed whitespace-pre-wrap max-w-[75ch]"><Cited text={m.content} citations={m.citations ?? []} /></div>}
            {m.error && <p role="alert" className="text-bad font-medium">{m.error}</p>}
            {!m.status && m.citations && m.citations.length > 0 && (
              <footer className="mt-3 pt-3 border-t border-line">
                <h2 className="text-[0.8125rem] font-semibold">Sources</h2>
                <ol className="mt-1 space-y-0.5 text-[0.8125rem]">
                  {m.citations.map((c) => <li key={c.n} id={`c-${i}-${c.n}`} className="flex gap-1.5"><span className="tnum text-ink-3">[{c.n}]</span><SourceLink c={c} /></li>)}
                </ol>
              </footer>
            )}
          </article>
        ))}
        <div ref={end} />
      </div>
      <form className="sticky bottom-0 bg-paper py-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); ask(draft); }}>
        <input aria-label="Your question" className={clsx("field flex-1 !h-10 min-w-0")} placeholder="Ask about jobs, salaries, skills or your CV" value={draft} onChange={(e) => setDraft(e.target.value)} />
        <button className="btn btn-primary !h-10" disabled={busy || !draft.trim()}><Send size={15} aria-hidden />Ask</button>
      </form>
    </div>
  );
}

function SourceLink({ c }: { c: Citation }) {
  return c.url.startsWith("/") ? <Link className="text-air-blue hover:underline" href={c.url}>{c.title}</Link> : <a className="text-air-blue hover:underline" href={c.url} target="_blank" rel="noreferrer">{c.title}</a>;
}

function Cited({ text, citations }: { text: string; citations: Citation[] }) {
  return <>{text.split(/(\[\d+\])/g).map((part, i) => {
    const n = part.match(/^\[(\d+)\]$/)?.[1];
    const c = n ? citations.find((x) => x.n === Number(n)) : undefined;
    return c ? <sup key={i} className="tnum font-semibold ml-0.5">{c.url.startsWith("/") ? <Link className="text-air-blue" href={c.url} title={c.title}>{n}</Link> : <a className="text-air-blue" href={c.url} target="_blank" rel="noreferrer" title={c.title}>{n}</a>}</sup> : <span key={i}>{part}</span>;
  })}</>;
}
