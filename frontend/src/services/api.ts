import type {
  HealthResponse,
  ReadyResponse,
  Result,
  ServiceSnapshot,
  SystemStatus,
} from "../types/api";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1"
).replace(/\/$/, "");

async function request<T>(
  path: string,
  signal: AbortSignal,
): Promise<Result<T>> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal.addEventListener("abort", cancel, { once: true });
  if (signal.aborted) controller.abort();
  const timeout = window.setTimeout(cancel, 6000);
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      signal: controller.signal,
    });
    if (!response.ok) {
      const message =
        response.status === 404 && path === "/system/status"
          ? "Development diagnostics are disabled on this backend."
          : `Request failed (HTTP ${response.status}).`;
      return { data: null, error: message };
    }
    return { data: (await response.json()) as T, error: null };
  } catch (error) {
    return {
      data: null,
      error:
        error instanceof DOMException && error.name === "AbortError"
          ? "Request timed out or was cancelled."
          : "Cannot reach the API. Check the server and CORS configuration.",
    };
  } finally {
    clearTimeout(timeout);
    signal.removeEventListener("abort", cancel);
  }
}

export async function getServiceSnapshot(
  signal: AbortSignal,
): Promise<ServiceSnapshot> {
  const [health, ready, system] = await Promise.all([
    request<HealthResponse>("/health", signal),
    request<ReadyResponse>("/ready", signal),
    request<SystemStatus>("/system/status", signal),
  ]);
  return { health, ready, system };
}
