import { useCallback, useEffect, useState } from "react";
import { getServiceSnapshot } from "../services/api";
import type { ServiceSnapshot } from "../types/api";

export function useSystemStatus() {
  const [snapshot, setSnapshot] = useState<ServiceSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    void getServiceSnapshot(controller.signal).then((result) => {
      if (!controller.signal.aborted) {
        setSnapshot(result);
        setCheckedAt(new Date());
        setLoading(false);
      }
    });
    return () => controller.abort();
  }, [revision]);
  return { snapshot, loading, checkedAt, refresh };
}
