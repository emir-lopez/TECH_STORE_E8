"""Pruebas de la API: respuestas 200/201, 404, 409 y 422."""
import pytest
from fastapi.testclient import TestClient

from app.api import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def datos_limpios():
    client.post("/reset")
    yield


def test_docs_y_openapi():
    assert client.get("/docs").status_code == 200
    assert "/orders/{order_id}/confirm" in client.get("/openapi.json").json()["paths"]


def test_get_pedido():
    r = client.get("/orders/O001")
    assert r.status_code == 200
    body = r.json()
    assert (body["status"], body["units"], body["total"], body["discount_rate"]) == ("DRAFT", 4, "2100.00", "0.10")


def test_404_pedido_inexistente():
    assert client.get("/orders/O999").status_code == 404
    assert client.post("/orders/O999/confirm").status_code == 404


def test_confirmar_200_y_doble_409():
    ok = client.post("/orders/O013/confirm")
    assert ok.status_code == 200 and ok.json() == {"id": "O013", "status": "CONFIRMED", "events": ["OrderConfirmed"]}
    again = client.post("/orders/O013/confirm")
    assert again.status_code == 409
    assert client.get("/orders/O013").json()["events"].__len__() == 1


def test_confirmar_vacio_422_e_inactivo_422():
    assert client.post("/orders/O007/confirm").status_code == 422
    assert client.post("/orders/O003/confirm").status_code == 422


def test_envio_sin_guia_422_y_con_guia_200():
    client.post("/orders/O012/confirm")
    assert client.post("/orders/O012/ship", json={"tracking_number": ""}).status_code == 422
    assert client.post("/orders/O012/ship", json={}).status_code == 422
    r = client.post("/orders/O012/ship", json={"tracking_number": "GUIA-1"})
    assert r.status_code == 200 and r.json()["status"] == "SHIPPED"


def test_cancelar_desde_shipped_409():
    client.post("/orders/O014/confirm")
    client.post("/orders/O014/ship", json={"tracking_number": "G-14"})
    r = client.post("/orders/O014/cancel", json={"reason": "Ya no"})
    assert r.status_code == 409


def test_entregar_y_devolver():
    for oid, accion, final in (("O016", "deliver", "DELIVERED"), ("O015", "return", "RETURNED")):
        client.post(f"/orders/{oid}/confirm")
        client.post(f"/orders/{oid}/ship", json={"tracking_number": "G"})
        assert client.post(f"/orders/{oid}/{accion}").json()["status"] == final


def test_agregar_articulo_excede_20_es_422():
    r = client.post("/orders/O009/items", json={"sku": "SKU003", "quantity": 2})
    assert r.status_code == 422 and r.json()["error"] == "OrderItemLimitExceeded"
    assert client.get("/orders/O009").json()["units"] == 19


def test_crear_pedido_y_agregar():
    assert client.post("/orders", json={"id": "O100", "customer_id": "C001"}).status_code == 201
    r = client.post("/orders/O100/items", json={"sku": "SKU001", "quantity": 4})
    assert r.json()["total"] == "2400.00" and r.json()["discount_rate"] == "0.10"
    assert client.post("/orders", json={"id": "O100", "customer_id": "C001"}).status_code == 409
    assert client.post("/orders", json={"id": "O101", "customer_id": "C999"}).status_code == 404
    assert client.post("/orders/O100/items", json={"sku": "SKU999", "quantity": 1}).status_code == 404
    assert client.post("/orders/O100/items", json={"sku": "SKU001", "quantity": 0}).status_code == 422
