export type Complaint = {
  id: string;
  customer: string;
  account: string;
  channel: string;
  issue: string;
  category: string;
  sentiment: "negative" | "neutral" | "positive";
  priority: "urgent" | "high" | "normal";
  status: "open" | "closed";
  created_at: string;
  summary: string;
  requested_action: string;
};

export type ChatResponse = {
  response: string;
  tool: string;
  mcpServer: string;
  connection: "internal" | "external";
  source: string;
  traceId: string;
  latencyMs: number;
  sessionId: string;
  tokenCount: number;
  discoveredTools: Array<{
    tool: string;
    name: string;
    connection: "internal" | "external";
    description: string;
    score: number;
  }>;
};

export type StreamChunk = {
  chunk?: string;
  type: "content" | "done";
  tool?: string;
  mcpServer?: string;
  connection?: string;
  source?: string;
  traceId?: string;
  latencyMs?: number;
  sessionId?: string;
  tokenCount?: number;
  discoveredTools?: ChatResponse["discoveredTools"];
};

export type ObservabilityMetrics = {
  requests: {
    total: number;
    guarded: number;
    p95LatencyMs: number;
  };
  tools: Record<string, number>;
  mcpServers: {
    counts: {
      total: number;
      internal: number;
      external: number;
    };
    configured: Array<{
      name: string;
      tool: string;
      connection: "internal" | "external";
      description: string;
    }>;
    usage: Record<string, number>;
  };
  sources: Record<string, number>;
  recentEvents: Array<{
    traceId: string;
    tool: string;
    mcpServer: string;
    connection: "internal" | "external";
    source: string;
    latencyMs: number;
    guarded: boolean;
    createdAt: string;
  }>;
  traces: {
    status: {
      openTelemetryAvailable: boolean;
      consoleExporterEnabled: boolean;
      recentSpanCount: number;
    };
    recentSpans: Array<{
      name: string;
      traceId: string;
      durationMs: number;
      attributes: Record<string, unknown>;
    }>;
  };
  notes: string[];
};

export type IntegrationStatus = {
  name: string;
  mcpServer: string;
  status: "connected" | "not_configured";
  envVar: string;
};

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010";

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function authHeaders(token: string) {
  return token ? ({ Authorization: `Bearer ${token}` } as Record<string, string>) : ({} as Record<string, string>);
}

export function exportUrl(token: string) {
  const url = new URL(`${API_BASE}/api/export.csv`);
  if (token) {
    url.searchParams.set("token", token);
  }
  return url.toString();
}

export function reportUrl(token: string) {
  const url = new URL(`${API_BASE}/api/report.md`);
  if (token) {
    url.searchParams.set("token", token);
  }
  return url.toString();
}

export function createSessionId() {
  return `session-${Math.random().toString(36).slice(2)}-${Date.now()}`;
}

export async function* streamChat(
  message: string,
  sessionId: string,
  authToken: string
): AsyncGenerator<StreamChunk> {
  const response = await fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(authToken),
    },
    body: JSON.stringify({ message, sessionId }),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Response body is not readable");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6);
        try {
          const chunk: StreamChunk = JSON.parse(data);
          yield chunk;
        } catch {
          // Skip invalid JSON
        }
      }
    }
  }
}
