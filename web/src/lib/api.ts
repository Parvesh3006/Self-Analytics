import { keepPreviousData, useQuery } from "@tanstack/react-query";

export class ApiError extends Error {}

export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {}
    throw new ApiError(detail);
  }
  return response.json();
}

/** Holds the previous result while refetching, so a filter change dims the view instead of blanking it. */
export function useApi<T = any>(path: string | null, refetchInterval?: number) {
  return useQuery<T>({
    queryKey: [path],
    queryFn: () => api<T>(path as string),
    enabled: path !== null,
    placeholderData: keepPreviousData,
    refetchInterval,
  });
}
