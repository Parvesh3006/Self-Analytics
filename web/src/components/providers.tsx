"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { compactMoney } from "@/lib/format";

const CurrencyContext = createContext<{ currency: string; setCurrency: (c: string) => void; rates?: Record<string, number> }>({ currency: "USD", setCurrency: () => {} });

function CurrencyProvider({ children }: { children: React.ReactNode }) {
  const [currency, setCurrencyState] = useState("USD");
  const { data: rates } = useApi<Record<string, number>>("/api/fx");
  useEffect(() => {
    try {
      const saved = localStorage.getItem("currency");
      if (saved) setCurrencyState(saved);
    } catch {}
  }, []);
  const setCurrency = (value: string) => {
    setCurrencyState(value);
    try { localStorage.setItem("currency", value); } catch {}
  };
  return <CurrencyContext.Provider value={{ currency, setCurrency, rates }}>{children}</CurrencyContext.Provider>;
}

export function useMoney() {
  const { currency, setCurrency, rates } = useContext(CurrencyContext);
  return { currency, setCurrency, rates, money: (usd: number | null | undefined) => compactMoney(usd, currency, rates) };
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 60_000, retry: 1, refetchOnWindowFocus: false } } }));
  return (
    <QueryClientProvider client={client}>
      <CurrencyProvider>{children}</CurrencyProvider>
    </QueryClientProvider>
  );
}
