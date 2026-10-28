import re
from functools import lru_cache
from pathlib import Path

from llama_index.core import Document, SummaryIndex
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
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _terms(value: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(value.lower()))


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
    # SummaryIndex keeps ingestion and retrieval local and deterministic. Unlike
    # SimpleKeywordTableIndex, it does not load or download NLTK corpora at runtime.
    index = SummaryIndex.from_documents(documents, llm=MockLLM())
    return index.as_retriever()


def retrieve_policy_context(query: str, limit: int = 3) -> list[Citation]:
    query_terms = _terms(query)
    policy_terms = query_terms.intersection(POLICY_QUERY_TERMS)
    if not policy_terms:
        return []

    results = _retriever().retrieve(query)

    def rank(result):
        document_terms = _terms(result.node.get_content())
        return (
            -len(policy_terms.intersection(document_terms)),
            -len(query_terms.intersection(document_terms)),
            result.node.metadata["source"],
        )

    results.sort(key=rank)
    citations = []
    for result in results[:limit]:
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
