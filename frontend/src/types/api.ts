export interface HealthResponse {
  status: "healthy";
  service: string;
  version: string;
}
export interface ReadyResponse {
  status: "ready";
  database: "connected";
}
export interface IntegrationStatus {
  configured: boolean;
  connectivity: "not_verified";
}
export interface SystemStatus {
  backend: "available";
  database: "connected" | "unavailable";
  environment: "development";
  integrations: Record<string, IntegrationStatus>;
}
export type Result<T> =
  { data: T; error: null } | { data: null; error: string };
export interface ServiceSnapshot {
  health: Result<HealthResponse>;
  ready: Result<ReadyResponse>;
  system: Result<SystemStatus>;
}
