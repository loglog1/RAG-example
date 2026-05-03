from langgraph.graph import StateGraph, START, END

from graph.state import RAGState
from graph.nodes import retrieve_node, aggregate_node, generate_node, format_node


def build_pipeline():
    builder = StateGraph(RAGState)

    builder.add_node("retrieve", retrieve_node)
    builder.add_node("aggregate", aggregate_node)
    builder.add_node("generate", generate_node)
    builder.add_node("format", format_node)

    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "aggregate")
    builder.add_edge("aggregate", "generate")
    builder.add_edge("generate", "format")
    builder.add_edge("format", END)

    return builder.compile()


pipeline = build_pipeline()
