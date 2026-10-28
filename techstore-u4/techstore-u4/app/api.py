"""API REST TechStore U4 (FastAPI).

Los controladores solo buscan el pedido, llaman al método de Order y traducen
el resultado. Las reglas de negocio NO se copian aquí.

    uvicorn app.api:app --reload
    http://127.0.0.1:8000/docs
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.domain import (
    Customer, DomainException, InvalidOrderData, InvalidOrderTransition, Money, Order,
    OrderItem, OrderItemLimitExceeded,
)
from app.specifications import discount_amount, discount_rate
from cargar_csv import load_fixture, rows

app = FastAPI(
    title="TechStore U4",
    version="1.0.0",
    description="Pedidos con reglas de descuento (Specification), máquina de estados y Domain Events. "
                "Datos en memoria cargados desde datos/*.csv; usa POST /reset para recargarlos.",
)

orders: dict[str, Order] = load_fixture()


def _catalog() -> tuple[dict[str, Customer], dict[str, Decimal]]:
    customers = {x["cliente_id"]: Customer(x["cliente_id"], bool(int(x["es_vip"])), bool(int(x["activo"])))
                 for x in rows("clientes.csv")}
    prices = {x["sku"]: Decimal(x["precio_mxn"]) for x in rows("productos.csv")}
    return customers, prices


# ---------------------------------------------------------------- errores de dominio → HTTP
@app.exception_handler(DomainException)
async def domain_error(_: Request, exc: DomainException) -> JSONResponse:
    if isinstance(exc, InvalidOrderTransition):
        code = 409
    elif isinstance(exc, (InvalidOrderData, OrderItemLimitExceeded)):
        code = 422
    else:
        code = 400
    return JSONResponse(status_code=code, content={"error": type(exc).__name__, "detail": str(exc)})


def _get(order_id: str) -> Order:
    order = orders.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"No existe el pedido {order_id}")
    return order


# ---------------------------------------------------------------- DTOs
class ItemOut(BaseModel):
    sku: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class EventOut(BaseModel):
    name: str
    detail: str
    occurred_at: str


class OrderOut(BaseModel):
    id: str
    customer_id: str
    status: str
    has_promotion: bool
    units: int
    total: Decimal
    discount_rate: Decimal
    discount_amount: Decimal
    items: list[ItemOut]
    events: list[EventOut]


class StatusOut(BaseModel):
    id: str
    status: str
    events: list[str]


class NewOrderIn(BaseModel):
    id: str = Field(examples=["O100"])
    customer_id: str = Field(examples=["C001"])
    has_promotion: bool = False


class ItemIn(BaseModel):
    sku: str = Field(examples=["SKU001"])
    quantity: int = Field(examples=[2])


class ShipIn(BaseModel):
    tracking_number: str = Field(default="", examples=["GUIA-12345"])


class CancelIn(BaseModel):
    reason: str = Field(default="", examples=["El cliente cambió de opinión"])


def _out(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id, customer_id=order.customer.id, status=order.status.value,
        has_promotion=order.has_promotion, units=order.units, total=order.total.amount,
        discount_rate=discount_rate(order), discount_amount=discount_amount(order),
        items=[ItemOut(sku=i.sku, quantity=i.quantity, unit_price=i.unit_price.amount,
                       subtotal=i.subtotal.amount) for i in order.items],
        events=[EventOut(name=e.name, detail=e.detail, occurred_at=e.occurred_at.isoformat())
                for e in order.events],
    )


def _status(order: Order) -> StatusOut:
    return StatusOut(id=order.id, status=order.status.value, events=[e.name for e in order.events])


# ---------------------------------------------------------------- consultas
@app.get("/orders", tags=["consultas"])
def list_orders() -> list[OrderOut]:
    return [_out(o) for o in orders.values()]


@app.get("/orders/{order_id}", tags=["consultas"])
def get_order(order_id: str) -> OrderOut:
    return _out(_get(order_id))


# ---------------------------------------------------------------- creación (ampliación)
@app.post("/orders", status_code=201, tags=["pedidos"])
def create_order(body: NewOrderIn) -> OrderOut:
    if body.id in orders:
        raise HTTPException(status_code=409, detail=f"El pedido {body.id} ya existe")
    customers, _ = _catalog()
    if body.customer_id not in customers:
        raise HTTPException(status_code=404, detail=f"No existe el cliente {body.customer_id}")
    orders[body.id] = Order(customer=customers[body.customer_id], id=body.id, has_promotion=body.has_promotion)
    return _out(orders[body.id])


@app.post("/orders/{order_id}/items", tags=["pedidos"])
def add_item(order_id: str, body: ItemIn) -> OrderOut:
    order = _get(order_id)
    _, prices = _catalog()
    if body.sku not in prices:
        raise HTTPException(status_code=404, detail=f"No existe el producto {body.sku}")
    order.add_item(OrderItem(body.sku, body.quantity, Money(prices[body.sku])))
    return _out(order)


# ---------------------------------------------------------------- transiciones (POST: cambian estado)
@app.post("/orders/{order_id}/confirm", tags=["transiciones"])
def confirm_order(order_id: str) -> StatusOut:
    order = _get(order_id)
    order.confirm()
    return _status(order)


@app.post("/orders/{order_id}/ship", tags=["transiciones"])
def ship_order(order_id: str, body: ShipIn) -> StatusOut:
    order = _get(order_id)
    order.ship(body.tracking_number)
    return _status(order)


@app.post("/orders/{order_id}/cancel", tags=["transiciones"])
def cancel_order(order_id: str, body: CancelIn) -> StatusOut:
    order = _get(order_id)
    order.cancel(body.reason)
    return _status(order)


@app.post("/orders/{order_id}/deliver", tags=["transiciones"])
def deliver_order(order_id: str) -> StatusOut:
    order = _get(order_id)
    order.deliver()
    return _status(order)


@app.post("/orders/{order_id}/return", tags=["transiciones"])
def return_order(order_id: str) -> StatusOut:
    order = _get(order_id)
    order.return_order()
    return _status(order)


# ---------------------------------------------------------------- utilidad de práctica
@app.post("/reset", tags=["práctica"])
def reset() -> dict[str, int]:
    """Vuelve a cargar los 16 pedidos desde los CSV (todos en DRAFT)."""
    orders.clear()
    orders.update(load_fixture())
    return {"orders": len(orders)}
