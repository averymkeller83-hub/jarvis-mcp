import { useEffect, useRef, useState, useCallback } from "react";

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  enabled: boolean = true,
): { data: T | null; loading: boolean; error: string | null; refetch: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);
  const fetcherRef = useRef(fetcher);

  // Keep fetcher ref current without restarting the interval
  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);

  const fetchData = useCallback(async () => {
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    fetchData();
    if (intervalMs > 0) {
      timerRef.current = window.setInterval(fetchData, intervalMs);
    }
    return () => {
      if (timerRef.current !== null) clearInterval(timerRef.current);
    };
  }, [fetchData, intervalMs, enabled]);

  return { data, loading, error, refetch: fetchData };
}
