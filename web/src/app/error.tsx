"use client";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="panel p-6 max-w-xl">
      <h1 className="panel-title">This page could not load</h1>
      <p className="panel-note mt-1">The data service may be starting up or stopped. Check that the API is running, then try again.</p>
      <button className="btn btn-primary mt-4" onClick={reset}>Try again</button>
    </div>
  );
}
