"""Dominio TechStore U4: Value Objects, entidades, máquina de estados y eventos.

Regla de cada transición: validar primero, cambiar el estado después y
registrar el Domain Event al final. Si una validación falla, el pedido no
cambia y no se agrega ningún evento.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

MAX_UNITS = 20


# ---------------------------------------------------------------- Excepciones
class DomainException(Exception):
    """Raíz de las excepciones de dominio."""


class OrderException(DomainException):
    """Errores propios del pedido."""


class InvalidOrderData(OrderException):
    """Datos que violan una invariante (HTTP 422)."""


class InvalidOrderTransition(OrderException):
    """Transición no permitida desde el estado actual (HTTP 409)."""


class OrderItemLimitExceeded(OrderException):
    """El pedido superaría las 20 unidades (HTTP 422)."""


# ---------------------------------------------------------------- Value Objects
@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "MXN"

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            raise InvalidOrderData("El monto debe ser Decimal")
        if not self.amount.is_finite() or self.amount < 0:
            raise InvalidOrderData("Monto inválido")
        if self.currency != "MXN":
            raise InvalidOrderData("Solo se admite MXN")

    def add(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise InvalidOrderData("Monedas distintas")
        return Money(self.amount + other.amount, self.currency)


@dataclass(frozen=True)
class OrderItem:
    sku: str
    quantity: int
    unit_price: Money

    def __post_init__(self):
        if not isinstance(self.sku, str) or not self.sku.strip():
            raise InvalidOrderData("Artículo inválido: SKU vacío")
        if not isinstance(self.quantity, int) or self.quantity <= 0:
            raise InvalidOrderData("Artículo inválido: cantidad debe ser mayor a 0")

    @property
    def subtotal(self) -> Money:
        return Money(self.unit_price.amount * self.quantity, self.unit_price.currency)


# ---------------------------------------------------------------- Entidades
@dataclass(frozen=True)
class Customer:
    id: str
    is_vip: bool = False
    active: bool = True


class OrderStatus(str, Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"


@dataclass(frozen=True)
class DomainEvent:
    """Hecho que ya ocurrió. Inmutable."""
    name: str
    order_id: str
    customer_id: str = ""
    total: Decimal = Decimal("0")
    detail: str = ""
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Order:
    """Aggregate Root: concentra las reglas y el ciclo de vida del pedido."""
    customer: Customer
    id: str
    has_promotion: bool = False
    status: OrderStatus = OrderStatus.DRAFT
    items: list[OrderItem] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)

    @property
    def units(self) -> int:
        # Suma de cantidades, NO número de renglones.
        return sum(item.quantity for item in self.items)

    @property
    def total(self) -> Money:
        amount = sum((item.subtotal.amount for item in self.items), Decimal("0"))
        return Money(amount)

    def _event(self, name: str, detail: str = "") -> None:
        self.events.append(DomainEvent(name, self.id, self.customer.id, self.total.amount, detail))

    # --- artículos -------------------------------------------------------
    def add_item(self, item: OrderItem) -> None:
        if self.status != OrderStatus.DRAFT:
            raise InvalidOrderTransition("Solo un pedido DRAFT admite artículos")
        if item.unit_price.currency != "MXN":
            raise InvalidOrderData("Solo MXN")
        if self.units + item.quantity > MAX_UNITS:
            raise OrderItemLimitExceeded(
                f"Máximo {MAX_UNITS} unidades: hay {self.units} y se intentan agregar {item.quantity}")
        self.items.append(item)

    # --- máquina de estados ---------------------------------------------
    #  DRAFT --confirm--> CONFIRMED --ship--> SHIPPED --deliver--> DELIVERED
    #                         |                  |
    #                       cancel             return
    #                         v                  v
    #                     CANCELLED           RETURNED
    def confirm(self) -> None:
        if self.status != OrderStatus.DRAFT:
            raise InvalidOrderTransition(f"Solo DRAFT puede confirmarse (estado actual: {self.status.value})")
        if not self.items:
            raise InvalidOrderData("No se puede confirmar un pedido sin artículos")
        if not self.customer.active:
            raise InvalidOrderData("El cliente está inactivo")
        self.status = OrderStatus.CONFIRMED
        self._event("OrderConfirmed")

    def ship(self, tracking_number: str) -> None:
        if self.status != OrderStatus.CONFIRMED:
            raise InvalidOrderTransition(f"Solo CONFIRMED puede enviarse (estado actual: {self.status.value})")
        if tracking_number is None or not str(tracking_number).strip():
            raise InvalidOrderData("El número de guía es obligatorio")
        self.status = OrderStatus.SHIPPED
        self._event("OrderShipped", str(tracking_number).strip())

    def cancel(self, reason: str) -> None:
        if self.status != OrderStatus.CONFIRMED:
            raise InvalidOrderTransition(f"Solo CONFIRMED puede cancelarse (estado actual: {self.status.value})")
        if reason is None or not str(reason).strip():
            raise InvalidOrderData("El motivo de cancelación es obligatorio")
        self.status = OrderStatus.CANCELLED
        self._event("OrderCancelled", str(reason).strip())

    def deliver(self) -> None:
        if self.status != OrderStatus.SHIPPED:
            raise InvalidOrderTransition(f"Solo SHIPPED puede entregarse (estado actual: {self.status.value})")
        self.status = OrderStatus.DELIVERED
        self._event("OrderDelivered")

    def return_order(self) -> None:
        if self.status != OrderStatus.SHIPPED:
            raise InvalidOrderTransition(f"Solo SHIPPED puede devolverse (estado actual: {self.status.value})")
        self.status = OrderStatus.RETURNED
        self._event("OrderReturned")
