"""Pruebas del dominio y de las Specifications con los datos del paquete.

Estructura de cada prueba: preparar → ejecutar → comprobar.
Cada prueba usa load_fixture() para partir de los 16 pedidos en DRAFT.
"""
from decimal import Decimal

import pytest

from app.domain import (
    Customer, InvalidOrderData, InvalidOrderTransition, Money, Order, OrderItem,
    OrderItemLimitExceeded, OrderStatus,
)
from app.specifications import (
    ActivePromotionSpec, FIVE_PERCENT, MinimumAmountSpec, MinimumUnitsSpec, TEN_PERCENT,
    VIPCustomerSpec, discount_amount, discount_rate,
)
from cargar_csv import load_fixture


@pytest.fixture
def orders():
    return load_fixture()


def event_names(order):
    return [e.name for e in order.events]


def make_order(vip=True, active=True, promo=False, lines=()):
    """Pedido sintético para probar fronteras que los CSV no cubren."""
    order = Order(customer=Customer("CX", vip, active), id="OX", has_promotion=promo)
    for qty, price in lines:
        order.add_item(OrderItem("SKUX", qty, Money(Decimal(price))))
    return order


# ---------------------------------------------------------------- Value Objects
def test_money_negativo():
    with pytest.raises(InvalidOrderData):
        Money(Decimal("-1"))


def test_money_rechaza_float_y_no_finito():
    with pytest.raises(InvalidOrderData):
        Money(600.00)
    with pytest.raises(InvalidOrderData):
        Money(Decimal("NaN"))


def test_money_es_inmutable_y_add_crea_otro():
    a = Money(Decimal("100"))
    b = a.add(Money(Decimal("50")))
    assert b.amount == Decimal("150") and a.amount == Decimal("100")
    with pytest.raises(Exception):
        a.amount = Decimal("1")


def test_money_monedas_distintas():
    with pytest.raises(InvalidOrderData):
        Money(Decimal("1"), "USD")


@pytest.mark.parametrize("sku, qty", [("", 1), ("   ", 1), ("SKU001", 0), ("SKU001", -2)])
def test_order_item_invalido(sku, qty):
    with pytest.raises(InvalidOrderData):
        OrderItem(sku, qty, Money(Decimal("10")))


def test_subtotal_calculado():
    assert OrderItem("SKU001", 2, Money(Decimal("600.00"))).subtotal.amount == Decimal("1200.00")


# ---------------------------------------------------------------- carga
def test_carga_16_pedidos_en_draft(orders):
    assert len(orders) == 16
    assert all(o.status == OrderStatus.DRAFT for o in orders.values())


def test_pedido_o001_inicia_draft(orders):
    assert orders["O001"].status.value == "DRAFT"
    assert orders["O001"].units == 4
    assert orders["O001"].total.amount == Decimal("2100.00")


def test_unidades_suman_cantidades_no_renglones(orders):
    assert len(orders["O008"].items) == 1 and orders["O008"].units == 20


# ---------------------------------------------------------------- E01–E05, E09, E10: descuentos
@pytest.mark.parametrize("order_id, rate", [
    ("O001", Decimal("0.10")),  # E01 VIP, >500, 4 unidades, sin promoción
    ("O002", Decimal("0")),     # E02 no VIP y total < 5000
    ("O005", Decimal("0")),     # E04 promoción activa
    ("O006", Decimal("0.05")),  # E05 total > 5000 sin promoción
    ("O010", Decimal("0")),     # E09 total exactamente 500
    ("O011", Decimal("0")),     # E10 solo 3 unidades
])
def test_descuentos_escenarios(orders, order_id, rate):
    assert discount_rate(orders[order_id]) == rate


def test_importe_de_descuento(orders):
    assert discount_amount(orders["O001"]) == Decimal("210.00")
    assert discount_amount(orders["O006"]) == Decimal("900.00")


def test_umbral_estricto_500_aislado():
    # O010 no es VIP: este caso aísla la regla > 500 (con >= daría 10 %).
    exacto = make_order(lines=[(4, "125.00")])
    assert exacto.total.amount == Decimal("500.00") and exacto.units == 4
    assert discount_rate(exacto) == Decimal("0")
    assert discount_rate(make_order(lines=[(4, "125.01")])) == Decimal("0.10")


def test_umbral_estricto_5000():
    assert not MinimumAmountSpec(Decimal("5000")).is_satisfied_by(make_order(vip=False, lines=[(1, "5000.00")]))
    assert discount_rate(make_order(vip=False, lines=[(1, "5000.01")])) == Decimal("0.05")


def test_prioridad_10_si_se_cumplen_ambas():
    order = make_order(lines=[(4, "2000.00")])  # VIP, 8000, 4 unidades
    assert TEN_PERCENT.is_satisfied_by(order) and FIVE_PERCENT.is_satisfied_by(order)
    assert discount_rate(order) == Decimal("0.10")


def test_specs_individuales_y_composicion(orders):
    o = orders["O001"]
    assert VIPCustomerSpec().is_satisfied_by(o)
    assert MinimumUnitsSpec(4).is_satisfied_by(o)
    assert not ActivePromotionSpec().is_satisfied_by(o)
    assert (~ActivePromotionSpec()).is_satisfied_by(o)
    assert (VIPCustomerSpec() | ActivePromotionSpec()).is_satisfied_by(orders["O001"])
    assert not (VIPCustomerSpec() & ActivePromotionSpec()).is_satisfied_by(o)


def test_specification_no_modifica_el_pedido(orders):
    o = orders["O001"]
    antes = (o.status, list(o.items), list(o.events))
    discount_rate(o)
    assert (o.status, o.items, o.events) == antes


# ---------------------------------------------------------------- E03, E06–E08: confirmación y límite
def test_e03_cliente_inactivo_no_confirma(orders):
    o = orders["O003"]
    with pytest.raises(InvalidOrderData):
        o.confirm()
    assert o.status == OrderStatus.DRAFT and o.events == []


def test_e06_pedido_vacio_no_confirma(orders):
    o = orders["O007"]
    with pytest.raises(InvalidOrderData):
        o.confirm()
    assert o.status == OrderStatus.DRAFT and o.events == []


def test_e07_veinte_unidades_se_confirman(orders):
    o = orders["O008"]
    o.confirm()
    assert o.status == OrderStatus.CONFIRMED and event_names(o) == ["OrderConfirmed"]


def test_e08_veintiuna_unidades_se_rechazan_sin_modificar(orders):
    o = orders["O009"]
    with pytest.raises(OrderItemLimitExceeded):
        o.add_item(OrderItem("SKU003", 2, Money(Decimal("120.00"))))
    assert o.units == 19 and len(o.items) == 1


def test_no_se_agregan_articulos_fuera_de_draft(orders):
    o = orders["O013"]
    o.confirm()
    with pytest.raises(InvalidOrderTransition):
        o.add_item(OrderItem("SKU001", 1, Money(Decimal("600.00"))))


# ---------------------------------------------------------------- E11–E15: transiciones
def test_e11_envio_sin_guia(orders):
    o = orders["O012"]
    o.confirm()
    for guia in ("", "   ", None):
        with pytest.raises(InvalidOrderData):
            o.ship(guia)
    assert o.status == OrderStatus.CONFIRMED and event_names(o) == ["OrderConfirmed"]


def test_e12_confirmacion_doble(orders):
    o = orders["O013"]
    o.confirm()
    with pytest.raises(InvalidOrderTransition):
        o.confirm()
    assert event_names(o) == ["OrderConfirmed"]


def test_e13_no_se_cancela_desde_shipped(orders):
    o = orders["O014"]
    o.confirm()
    o.ship("GUIA-014")
    with pytest.raises(InvalidOrderTransition):
        o.cancel("Ya no lo quiero")
    assert o.status == OrderStatus.SHIPPED
    assert event_names(o) == ["OrderConfirmed", "OrderShipped"]


def test_e14_devolucion(orders):
    o = orders["O015"]
    o.confirm()
    o.ship("GUIA-015")
    o.return_order()
    assert o.status == OrderStatus.RETURNED
    assert event_names(o) == ["OrderConfirmed", "OrderShipped", "OrderReturned"]


def test_e15_entrega(orders):
    o = orders["O016"]
    o.confirm()
    o.ship("GUIA-016")
    o.deliver()
    assert o.status == OrderStatus.DELIVERED
    assert event_names(o) == ["OrderConfirmed", "OrderShipped", "OrderDelivered"]


def test_cancelacion_valida_requiere_motivo(orders):
    o = orders["O002"]
    o.confirm()
    with pytest.raises(InvalidOrderData):
        o.cancel("  ")
    o.cancel("Cliente lo solicitó")
    assert o.status == OrderStatus.CANCELLED
    assert o.events[-1].name == "OrderCancelled" and o.events[-1].detail == "Cliente lo solicitó"


@pytest.mark.parametrize("accion", ["ship", "cancel", "deliver", "return_order"])
def test_transiciones_prohibidas_desde_draft(orders, accion):
    o = orders["O001"]
    with pytest.raises(InvalidOrderTransition):
        getattr(o, accion)(*(["X"] if accion in ("ship", "cancel") else []))
    assert o.status == OrderStatus.DRAFT and o.events == []


def test_estados_finales_no_admiten_transiciones(orders):
    o = orders["O016"]
    o.confirm()
    o.ship("G")
    o.deliver()
    for accion in (o.confirm, o.deliver, o.return_order):
        with pytest.raises(InvalidOrderTransition):
            accion()


def test_evento_confirmado_incluye_datos(orders):
    o = orders["O001"]
    o.confirm()
    e = o.events[0]
    assert (e.order_id, e.customer_id, e.total) == ("O001", "C001", Decimal("2100.00"))
    assert e.occurred_at.tzinfo is not None
