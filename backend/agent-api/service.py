import os
from functools import lru_cache

import boto3
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage

from knowledge import render_policy_context
from schemas import Citation, StructuredAssistantPayload


FORMATTER_INSTRUCTION = """You convert a shopping assistant answer into the requested schema.
Preserve the answer's meaning and do not invent products, prices, inventory, orders, or identifiers.
Populate product, inventory, cart, order, and order-item fields only when they are explicitly present in the answer.
Set requiresConfirmation only when the answer asks the customer to confirm a pending action.
Use responseType=policy for store-policy answers and responseType=message when no specific type fits.
Return a concise customer-facing message."""


@lru_cache(maxsize=1)
def _agent_runtime():
    return boto3.client("bedrock-agent-runtime")


@lru_cache(maxsize=1)
def _structured_formatter():
    model = ChatBedrockConverse(
        model_id=os.environ["FOUNDATION_MODEL_ID"],
        region_name=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"),
        temperature=0,
    )
    return model.with_structured_output(StructuredAssistantPayload)


def invoke_agent(message: str, session_id: str, policy_context: str) -> str:
    input_text = message
    if policy_context:
        input_text = (
            f"{message}\n\n"
            "Trusted store-policy context follows. Use it only for policy questions; "
            "continue using shopping tools for product, inventory, cart, and order facts.\n\n"
            f"{policy_context}"
        )
    response = _agent_runtime().invoke_agent(
        agentId=os.environ["AGENT_ID"],
        agentAliasId=os.environ["AGENT_ALIAS_ID"],
        sessionId=session_id,
        inputText=input_text,
        enableTrace=False,
    )
    chunks = []
    for event in response.get("completion", []):
        chunk = event.get("chunk")
        if chunk and chunk.get("bytes"):
            chunks.append(chunk["bytes"].decode("utf-8"))
    return "".join(chunks).strip()


def format_answer(
    customer_message: str,
    agent_answer: str,
    citations: list[Citation],
) -> StructuredAssistantPayload:
    context = render_policy_context(citations)
    prompt = (
        f"Customer message:\n{customer_message}\n\n"
        f"Shopping agent answer:\n{agent_answer}\n\n"
        f"Retrieved store-policy context:\n{context or 'None'}"
    )
    try:
        result = _structured_formatter().invoke(
            [SystemMessage(content=FORMATTER_INSTRUCTION), HumanMessage(content=prompt)]
        )
        if isinstance(result, StructuredAssistantPayload):
            return result
        return StructuredAssistantPayload.model_validate(result)
    except Exception:
        # A formatter failure must not discard a valid Bedrock Agent response.
        return StructuredAssistantPayload(
            message=agent_answer or "I could not produce a response. Please try again.",
            requiresConfirmation="confirm" in agent_answer.lower(),
        )


def answer(message: str, session_id: str) -> tuple[StructuredAssistantPayload, list[Citation]]:
    from knowledge import retrieve_policy_context

    citations = retrieve_policy_context(message)
    policy_context = render_policy_context(citations)
    agent_answer = invoke_agent(message, session_id, policy_context)
    payload = format_answer(message, agent_answer, citations)
    return payload, citations
