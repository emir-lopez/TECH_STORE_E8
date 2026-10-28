"""Ejecuta los escenarios E01–E15 de datos/escenarios.csv y genera la bitácora.

Cada caso parte de una carga nueva (load_fixture) para no arrastrar cambios.
Salida: tabla en terminal y bitacora_escenarios.csv con las cinco columnas
(caso, estado inicial, operación, resultado real, explicación) más el evento.

Uso:  python ejecutar_escenarios.py
"""
import csv
from decimal import Decimal
from pathlib import Path

from app.domain import DomainException, Money, OrderItem
from app.specifications import discount_amount, discount_rate
from cargar_csv import load_fixture, rows

BASE = Path(__file__).resolve().parent


def paso(nombre, accion):
    try:
        accion()
        return f"{nombre}: OK"
    except DomainException as exc:
        return f"{nombre}: RECHAZO {type(exc).__name__} ({exc})"


def descuento(order):
    tasa = discount_rate(order)
    return f"evaluar: {tasa * 100:.0f}% (total {order.total.amount}, descuento {discount_amount(order)})"


def ejecutar_caso(caso, order):
    precio_sku003 = {x["sku"]: Decimal(x["precio_mxn"]) for x in rows("productos.csv")}["SKU003"]
    acciones = {
        "E01": lambda: [descuento(order)],
        "E02": lambda: [descuento(order)],
        "E03": lambda: [paso("confirm()", order.confirm)],
        "E04": lambda: [descuento(order)],
        "E05": lambda: [descuento(order)],
        "E06": lambda: [paso("confirm()", order.confirm)],
        "E07": lambda: [paso("confirm()", order.confirm)],
        "E08": lambda: [paso("add_item(SKU003 x2)",
                             lambda: order.add_item(OrderItem("SKU003", 2, Money(precio_sku003))))],
        "E09": lambda: [descuento(order)],
        "E10": lambda: [descuento(order)],
        "E11": lambda: [paso("confirm()", order.confirm), paso("ship('')", lambda: order.ship(""))],
        "E12": lambda: [paso("confirm() #1", order.confirm), paso("confirm() #2", order.confirm)],
        "E13": lambda: [paso("confirm()", order.confirm),
                        paso("ship('GUIA-014')", lambda: order.ship("GUIA-014")),
                        paso("cancel('Cliente desistió')", lambda: order.cancel("Cliente desistió"))],
        "E14": lambda: [paso("confirm()", order.confirm),
                        paso("ship('GUIA-015')", lambda: order.ship("GUIA-015")),
                        paso("return_order()", order.return_order)],
        "E15": lambda: [paso("confirm()", order.confirm),
                        paso("ship('GUIA-016')", lambda: order.ship("GUIA-016")),
                        paso("deliver()", order.deliver)],
    }
    return acciones[caso]()


def main():
    bitacora = []
    for esc in rows("escenarios.csv"):
        orders = load_fixture()
        order = orders[esc["pedido_id"]]
        inicial = f"{order.status.value} · {order.units} u · {order.total.amount} MXN"
        resultado = ejecutar_caso(esc["caso_id"], order)
        eventos = ", ".join(e.name for e in order.events) or "ninguno"
        bitacora.append({
            "caso": esc["caso_id"],
            "pedido": esc["pedido_id"],
            "estado_inicial": inicial,
            "operacion": esc["accion"],
            "esperado": esc["objetivo"],
            "resultado_real": " | ".join(resultado),
            "estado_final": order.status.value,
            "eventos_emitidos": eventos,
            "explicacion": esc["pista"],
        })

    for f in bitacora:
        print(f"{f['caso']} {f['pedido']} — {f['operacion']} (esperado: {f['esperado']})")
        print(f"   inicial: {f['estado_inicial']}  →  final: {f['estado_final']}")
        print(f"   resultado: {f['resultado_real']}")
        print(f"   eventos: {f['eventos_emitidos']}\n")

    destino = BASE / "bitacora_escenarios.csv"
    with destino.open("w", newline="", encoding="utf-8-sig") as archivo:
        writer = csv.DictWriter(archivo, fieldnames=list(bitacora[0]))
        writer.writeheader()
        writer.writerows(bitacora)
    print(f"Bitácora guardada en {destino.name}")


if __name__ == "__main__":
    main()
