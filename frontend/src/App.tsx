import { useEffect, useMemo, useRef, useState } from "react";
import { LiveFeed, type LiveFrame } from "./components/LiveFeed";
import { NotesViewer } from "./components/NotesViewer";
import type { AgentName } from "./components/ProgressRail";
import { ProgressRail } from "./components/ProgressRail";
import { getCached, saveToCache } from "./lib/cache";
import { copyToClipboard, downloadMarkdown, printToPdf } from "./lib/export";
import { streamJob } from "./lib/sse";

// Same-origin in dev (via Vite proxy) and prod (single container).
// Override with VITE_API_URL only if you're pointing at a remote API.
const API_URL = import.meta.env.VITE_API_URL ?? "";

type ProviderInfo = {
  name: string;
  default_model: string;
  supports_vision: boolean;
  supports_native_video: boolean;
};

type AgentStatus = "idle" | "active" | "done" | "error";

const INITIAL_STATUS: Record<AgentName, AgentStatus> = {
  transcriber: "idle",
  visual_analyst: "idle",
  ocr_extractor: "idle",
  synthesizer: "idle",
};

export default function App() {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [url, setUrl] = useState("");
  const [providerName, setProviderName] = useState("gemini");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");

  const [running, setRunning] = useState(false);
  const [notes, setNotes] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [statuses, setStatuses] = useState<Record<AgentName, AgentStatus>>(INITIAL_STATUS);
  const [agentMsgs, setAgentMsgs] = useState<Partial<Record<AgentName, string>>>({});
  const [liveFrames, setLiveFrames] = useState<LiveFrame[]>([]);

  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/providers`)
      .then((r) => r.json())
      .then((data: ProviderInfo[]) => {
        setProviders(data);
        // match the selected provider, not just the first one in the list —
        // otherwise the dropdown shows gemini while the model box shows
        // anthropic's default (since the API returns them alphabetically).
        const match = data.find((p) => p.name === providerName) ?? data[0];
        if (match) setModel(match.default_model);
      })
      .catch(() => setProviders([]));
  }, []);

  const currentProvider = useMemo(
    () => providers.find((p) => p.name === providerName),
    [providers, providerName]
  );

  useEffect(() => {
    if (currentProvider) setModel(currentProvider.default_model);
  }, [currentProvider?.name]);

  function resetRun() {
    setNotes("");
    setErrorMsg(null);
    setStatuses(INITIAL_STATUS);
    setAgentMsgs({});
    setLiveFrames([]);
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!url || !apiKey || !providerName) return;

    const cached = getCached(url);
    if (cached && !running) {
      setNotes(cached.notes);
      return;
    }

    resetRun();
    setRunning(true);
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      await streamJob(
        API_URL,
        { url, provider: providerName, model: model || undefined, api_key: apiKey },
        ctrl.signal,
        (evt) => {
          // TEMP: remove once the UI-update bug is diagnosed.
          console.log("[sse]", evt.event, evt.data);
          if (evt.event === "progress") {
            const agent = evt.data.agent as AgentName | undefined;
            const status = evt.data.status as string | undefined;
            const message = evt.data.message as string | undefined;
            if (!agent) return;
            setStatuses((prev) => ({
              ...prev,
              [agent]:
                status === "done"
                  ? "done"
                  : status === "error"
                  ? "error"
                  : "active",
            }));
            if (message) setAgentMsgs((prev) => ({ ...prev, [agent]: message }));
          } else if (evt.event === "token") {
            setNotes((prev) => prev + (evt.data.text as string));
          } else if (evt.event === "frame") {
            const frame: LiveFrame = {
              ts: Number(evt.data.ts ?? 0),
              url: String(evt.data.url ?? ""),
              caption: String(evt.data.caption ?? ""),
              is_slide: Boolean(evt.data.is_slide),
            };
            setLiveFrames((prev) => [...prev, frame]);
            setAgentMsgs((prev) => ({
              ...prev,
              visual_analyst: `captioned @ ${frame.ts.toFixed(0)}s`,
            }));
          } else if (evt.event === "error") {
            setErrorMsg(String(evt.data.message ?? "unknown error"));
          }
        }
      );

      // on done, cache the result
      setNotes((current) => {
        if (current && !errorMsg) {
          saveToCache({
            url,
            provider: providerName,
            model: model || (currentProvider?.default_model ?? ""),
            notes: current,
            at: Date.now(),
          });
        }
        return current;
      });
    } catch (err) {
      setErrorMsg((err as Error).message);
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }

  function onCancel() {
    abortRef.current?.abort();
  }

  const canExport = notes.length > 0 && !running;

  return (
    <div className="app">
      <h1>Vidnots</h1>
      <p className="tagline">
        Paste a YouTube link, pick a model, bring your own API key — get back notes
        that cover everything spoken and shown.
      </p>

      <form className="card" onSubmit={onSubmit}>
        <div className="form-grid">
          <div>
            <label>YouTube URL</label>
            <input
              type="url"
              required
              placeholder="https://www.youtube.com/watch?v=…"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={running}
            />
          </div>
          <div>
            <label>Provider</label>
            <select
              value={providerName}
              onChange={(e) => setProviderName(e.target.value)}
              disabled={running || providers.length === 0}
            >
              {providers.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.name}
                  {p.supports_native_video ? " (native video)" : ""}
                </option>
              ))}
            </select>
          </div>

          <div className="form-row">
            <div>
              <label>API Key (BYOK — not stored)</label>
              <input
                type="password"
                required
                placeholder="sk-… / anthropic-… / AIza…"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                disabled={running}
              />
            </div>
            <div>
              <label>Model</label>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder={currentProvider?.default_model}
                disabled={running}
              />
            </div>
          </div>

          <div style={{ gridColumn: "1 / -1", display: "flex", gap: 12 }}>
            <button className="primary" type="submit" disabled={running}>
              {running ? "Generating…" : "Generate notes"}
            </button>
            {running && (
              <button className="ghost" type="button" onClick={onCancel}>
                Cancel
              </button>
            )}
          </div>
        </div>
      </form>

      {(running || notes) && (
        <ProgressRail statuses={statuses} messages={agentMsgs} />
      )}

      <LiveFeed frames={liveFrames} apiUrl={API_URL} running={running} />

      {errorMsg && (
        <div className="card" style={{ borderColor: "var(--danger)", marginTop: 16 }}>
          <strong>Error:</strong> {errorMsg}
        </div>
      )}

      {notes && (
        <div className="notes-wrap">
          <div className="notes-toolbar">
            <button
              className="ghost"
              onClick={() => downloadMarkdown("vidnots.md", notes)}
              disabled={!canExport}
            >
              Download .md
            </button>
            <button className="ghost" onClick={printToPdf} disabled={!canExport}>
              Print / PDF
            </button>
            <button
              className="ghost"
              onClick={() => copyToClipboard(notes)}
              disabled={!canExport}
            >
              Copy
            </button>
          </div>
          <NotesViewer markdown={notes} apiUrl={API_URL} />
        </div>
      )}
    </div>
  );
}
