from functools import lru_cache
from pathlib import Path

from llama_index.core import Document, SimpleKeywordTableIndex
from llama_index.core.llms import MockLLM

from schemas import Citation


KNOWLEDGE_DIRECTORY = Path(__file__).parent / "knowledge"
POLICY_QUERY_TERMS = {
    "cancel",
    "delivery",
    "payment",
    "privacy",
    "refund",
    "return",
    "returns",
    "secret",
    "shipping",
}


@lru_cache(maxsize=1)
def _retriever():
    documents = []
    for path in sorted(KNOWLEDGE_DIRECTORY.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        title = text.splitlines()[0].lstrip("# ").strip() or path.stem
        documents.append(
            Document(
                text=text,
                metadata={"source": path.name, "title": title},
            )
        )
    if not documents:
        raise RuntimeError("No store knowledge documents are configured")
    # The simple index uses deterministic regex keyword extraction. Supplying the
    # core mock prevents LlamaIndex from resolving an unrelated default OpenAI LLM.
    index = SimpleKeywordTableIndex.from_documents(documents, llm=MockLLM())
    return index.as_retriever(retriever_mode="simple")


def retrieve_policy_context(query: str, limit: int = 3) -> list[Citation]:
    query_terms = {term.strip(".,?!:;()[]{}\"").lower() for term in query.split()}
    if not query_terms.intersection(POLICY_QUERY_TERMS):
        return []
    citations = []
    for result in _retriever().retrieve(query)[:limit]:
        metadata = result.node.metadata
        excerpt = " ".join(result.node.get_content().split())[:600]
        citations.append(
            Citation(
                source=metadata["source"],
                title=metadata["title"],
                excerpt=excerpt,
            )
        )
    return citations


def render_policy_context(citations: list[Citation]) -> str:
    if not citations:
        return ""
    sections = [
        f"[{citation.source}] {citation.title}\n{citation.excerpt}"
        for citation in citations
    ]
    return "\n\n".join(sections)
