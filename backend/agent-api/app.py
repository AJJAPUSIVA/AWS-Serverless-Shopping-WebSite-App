import logging
import os

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

import service
from schemas import AssistantRequest, AssistantResponse
from session_store import claim_session, normalize_session_id


logger = logging.getLogger(__name__)
app = FastAPI(
    title="Shopping Assistant API",
    version="2.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("ALLOWED_ORIGIN", "http://localhost:8080")],
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


def current_user_sub(request: Request) -> str:
    event = request.scope.get("aws.event", {})
    user_sub = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
        .get("sub")
    )
    if not user_sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to use the shopping assistant",
        )
    return user_sub


@app.post("/assistant", response_model=AssistantResponse, response_model_by_alias=True)
def assistant(
    request: AssistantRequest,
    user_sub: str = Depends(current_user_sub),
) -> AssistantResponse:
    try:
        session_id = normalize_session_id(request.session_id)
        claim_session(session_id, user_sub)
        payload, citations = service.answer(request.message, session_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except Exception as error:
        logger.exception("Shopping assistant request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The shopping assistant is temporarily unavailable",
        ) from error

    return AssistantResponse(
        **payload.model_dump(by_alias=True),
        sessionId=session_id,
        citations=citations,
    )


handler = Mangum(app, lifespan="off")
