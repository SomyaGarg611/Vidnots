from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.ocr_extractor import ocr_extractor_node
from agents.synthesizer import synthesizer_node
from agents.transcriber import transcriber_node
from agents.visual_analyst import visual_analyst_node
from state import GraphState


def build_graph():
    """
        ┌─ Transcriber ─────────────┐
    START                            ├─▶ Synthesizer ─▶ END
        └─ Visual-Analyst ─▶ OCR ───┘

    Transcriber and Visual-Analyst run in parallel from START. OCR depends
    on the Visual-Analyst's `frames`. Synthesizer waits on Transcriber and
    OCR (OCR runs only after Visual-Analyst, so its completion implies
    Visual-Analyst's completion).
    """
    g = StateGraph(GraphState)

    g.add_node("transcriber", transcriber_node)
    g.add_node("visual_analyst", visual_analyst_node)
    g.add_node("ocr_extractor", ocr_extractor_node)
    g.add_node("synthesizer", synthesizer_node)

    g.add_edge(START, "transcriber")
    g.add_edge(START, "visual_analyst")
    g.add_edge("visual_analyst", "ocr_extractor")
    g.add_edge("transcriber", "synthesizer")
    g.add_edge("ocr_extractor", "synthesizer")
    g.add_edge("synthesizer", END)

    return g.compile()


compiled_graph = build_graph()
