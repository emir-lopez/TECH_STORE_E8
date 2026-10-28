"""Specification Pattern: reglas de descuento combinables.

``&`` = AND, ``|`` = OR, ``~`` = NOT. Una Specification solo responde
verdadero o falso; nunca modifica el pedido.
"""
from __future__ import annotations

from decimal import Decimal


class Specification:
    def is_satisfied_by(self, order) -> bool:
        raise NotImplementedError

    def __and__(self, other: Specification) -> Specification:
        return AndSpec(self, other)

    def __or__(self, other: Specification) -> Specification:
        return OrSpec(self, other)

    def __invert__(self) -> Specification:
        return NotSpec(self)


class AndSpec(Specification):
    def __init__(self, left: Specification, right: Specification):
        self.left, self.right = left, right

    def is_satisfied_by(self, order) -> bool:
        return self.left.is_satisfied_by(order) and self.right.is_satisfied_by(order)


class OrSpec(Specification):
    def __init__(self, left: Specification, right: Specification):
        self.left, self.right = left, right

    def is_satisfied_by(self, order) -> bool:
        return self.left.is_satisfied_by(order) or self.right.is_satisfied_by(order)


class NotSpec(Specification):
    def __init__(self, spec: Specification):
        self.spec = spec

    def is_satisfied_by(self, order) -> bool:
        return not self.spec.is_satisfied_by(order)


# ---------------------------------------------------------------- Reglas simples
class MinimumAmountSpec(Specification):
    """Total ESTRICTAMENTE mayor al mínimo (>, no >=)."""

    def __init__(self, minimum: Decimal):
        self.minimum = Decimal(minimum)

    def is_satisfied_by(self, order) -> bool:
        return order.total.amount > self.minimum


class VIPCustomerSpec(Specification):
    def is_satisfied_by(self, order) -> bool:
        return order.customer.is_vip


class MinimumUnitsSpec(Specification):
    """Al menos N unidades (suma de cantidades)."""

    def __init__(self, minimum: int):
        self.minimum = minimum

    def is_satisfied_by(self, order) -> bool:
        return order.units >= self.minimum


class ActivePromotionSpec(Specification):
    def is_satisfied_by(self, order) -> bool:
        return order.has_promotion


# ---------------------------------------------------------------- Reglas compuestas
# 10 %: VIP AND total > 500 AND unidades >= 4 AND NOT promoción.
TEN_PERCENT = (
    MinimumAmountSpec(Decimal("500"))
    & VIPCustomerSpec()
    & MinimumUnitsSpec(4)
    & ~ActivePromotionSpec()
)

# 5 %: total > 5000 AND NOT promoción.
FIVE_PERCENT = MinimumAmountSpec(Decimal("5000")) & ~ActivePromotionSpec()

# Elegible a algún descuento: 10 % OR 5 %.
ANY_DISCOUNT = TEN_PERCENT | FIVE_PERCENT


def discount_rate(order) -> Decimal:
    """Tasa aplicable. Si se cumplen ambas reglas, el 10 % tiene prioridad."""
    if TEN_PERCENT.is_satisfied_by(order):
        return Decimal("0.10")
    if FIVE_PERCENT.is_satisfied_by(order):
        return Decimal("0.05")
    return Decimal("0")


def discount_amount(order) -> Decimal:
    """Importe del descuento (no modifica el pedido)."""
    return (order.total.amount * discount_rate(order)).quantize(Decimal("0.01"))
