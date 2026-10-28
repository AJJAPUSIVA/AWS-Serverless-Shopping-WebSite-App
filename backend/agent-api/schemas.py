from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class AssistantRequest(ApiModel):
    message: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
    ]
    session_id: str | None = Field(default=None, alias="sessionId")


class ResponseType(str, Enum):
    MESSAGE = "message"
    PRODUCT_SEARCH = "product_search"
    CART = "cart"
    CHECKOUT_PREVIEW = "checkout_preview"
    ORDER = "order"
    ORDER_HISTORY = "order_history"
    POLICY = "policy"
    ERROR = "error"


class ProductCard(ApiModel):
    product_id: str | None = Field(default=None, alias="productId")
    name: str
    category: str | None = None
    description: str | None = None
    price: float | None = Field(default=None, ge=0)
    available_quantity: int | None = Field(default=None, alias="availableQuantity", ge=0)


class CommerceItem(ApiModel):
    product_id: str | None = Field(default=None, alias="productId")
    name: str
    quantity: int = Field(ge=1)
    unit_price: float | None = Field(default=None, alias="unitPrice", ge=0)
    line_total: float | None = Field(default=None, alias="lineTotal", ge=0)


class CartSummary(ApiModel):
    items: list[CommerceItem] = Field(default_factory=list)
    total: float | None = Field(default=None, ge=0)


class OrderSummary(ApiModel):
    order_id: str | None = Field(default=None, alias="orderId")
    status: str | None = None
    item_count: int | None = Field(default=None, alias="itemCount", ge=0)
    total: float | None = Field(default=None, ge=0)
    created_at: str | None = Field(default=None, alias="createdAt")
    items: list[CommerceItem] = Field(default_factory=list)


class Citation(ApiModel):
    source: str
    title: str
    excerpt: str


class StructuredAssistantPayload(ApiModel):
    """Model-generated fields. Server-owned identity and citations are added later."""

    response_type: ResponseType = Field(default=ResponseType.MESSAGE, alias="responseType")
    message: str = Field(min_length=1)
    products: list[ProductCard] = Field(default_factory=list)
    cart: CartSummary | None = None
    orders: list[OrderSummary] = Field(default_factory=list)
    order: OrderSummary | None = None
    requires_confirmation: bool = Field(default=False, alias="requiresConfirmation")


class AssistantResponse(StructuredAssistantPayload):
    session_id: str = Field(alias="sessionId")
    citations: list[Citation] = Field(default_factory=list)
