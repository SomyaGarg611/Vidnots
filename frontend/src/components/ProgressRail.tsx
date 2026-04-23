type AgentStatus = "idle" | "active" | "done" | "error";

export type AgentName =
  | "transcriber"
  | "visual_analyst"
  | "ocr_extractor"
  | "synthesizer";

const AGENT_LABEL: Record<AgentName, string> = {
  transcriber: "Transcriber",
  visual_analyst: "Visual-Analyst",
  ocr_extractor: "OCR-Extractor",
  synthesizer: "Synthesizer",
};

type Props = {
  statuses: Record<AgentName, AgentStatus>;
  messages: Partial<Record<AgentName, string>>;
};

export function ProgressRail({ statuses, messages }: Props) {
  const agents: AgentName[] = [
    "transcriber",
    "visual_analyst",
    "ocr_extractor",
    "synthesizer",
  ];
  return (
    <div className="progress-rail">
      {agents.map((a) => {
        const s = statuses[a];
        const cls =
          s === "done" ? "done" : s === "error" ? "error" : s === "active" ? "active" : "";
        return (
          <span key={a} className={`pill ${cls}`} title={messages[a] ?? ""}>
            {AGENT_LABEL[a]}
            {messages[a] ? ` · ${messages[a]}` : ""}
          </span>
        );
      })}
    </div>
  );
}
