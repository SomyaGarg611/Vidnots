export type SSEEvent = { event: string; data: Record<string, unknown> };

export type JobInput = {
  url: string;
  provider: string;
  model?: string;
  api_key: string;
};

/**
 * POST SSE client — fetch() + ReadableStream. Native EventSource can't do
 * POST, so we parse the event-stream format manually.
 */
export async function streamJob(
  apiUrl: string,
  body: JobInput,
  signal: AbortSignal,
  onEvent: (e: SSEEvent) => void
): Promise<void> {
  const res = await fetch(`${apiUrl}/api/jobs`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok || !res.body) {
    const txt = await res.text().catch(() => "");
    throw new Error(`job failed: ${res.status} ${txt}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  // Find the next event separator — SSE servers use either \n\n or \r\n\r\n.
  // Accept both so we never silently swallow events.
  function nextSep(s: string): { idx: number; len: number } | null {
    const a = s.indexOf("\r\n\r\n");
    const b = s.indexOf("\n\n");
    if (a === -1 && b === -1) return null;
    if (a !== -1 && (b === -1 || a < b)) return { idx: a, len: 4 };
    return { idx: b, len: 2 };
  }

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    let sep: { idx: number; len: number } | null;
    while ((sep = nextSep(buf)) !== null) {
      const raw = buf.slice(0, sep.idx);
      buf = buf.slice(sep.idx + sep.len);

      let eventName = "message";
      const dataLines: string[] = [];
      for (const line of raw.split(/\r?\n/)) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (!dataLines.length) continue;

      let data: Record<string, unknown> = {};
      try {
        data = JSON.parse(dataLines.join("\n"));
      } catch {
        data = { raw: dataLines.join("\n") };
      }
      onEvent({ event: eventName, data });
    }
  }
}
