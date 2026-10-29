# TechStore U4 · Componentes de Lógica de Negocio

Actividad 4 (FIME · UANL). El programa administra los pedidos de una tienda ficticia:

- Lee clientes, productos y pedidos de CSV y los convierte en objetos.
- Aplica reglas de descuento con el **Specification Pattern**.
- Controla el estado de cada pedido con una **máquina de estados** que emite **Domain Events**.
- Expone las operaciones mediante una **API REST con FastAPI**.

No usa base de datos: los pedidos viven en memoria.

## Estructura

```
techstore-u4/
├── datos/                  # 5 CSV del paquete del profesor (sin modificar)
├── cargar_csv.py           # cargador del paquete (sin modificar)
├── run.py                  # arranque único (Visual Studio, consola e IIS)
├── requirements.txt        # dependencias
├── web.config              # configuración para IIS (HttpPlatformHandler)
├── README.txt              # reglas del paquete
├── app/
│   ├── __init__.py
│   ├── domain.py           # Money, OrderItem, Customer, Order, estados, eventos, excepciones
│   ├── specifications.py   # Specification AND/OR/NOT, 4 reglas, discount_rate()
│   └── api.py              # endpoints FastAPI
├── tests/
│   ├── test_domain.py      # Value Objects, descuentos, límite, transiciones, E01–E15
│   └── test_api.py         # 200/201, 404, 409, 422
├── ejecutar_escenarios.py  # corre E01–E15 y genera bitacora_escenarios.csv
├── bitacora_escenarios.csv
└── docs/
    ├── REPORTE.md          # diagrama, eventos, respuestas y reflexión
    ├── diagrama_estados.png
    └── capturas/           # evidencias (carga, pytest y Swagger)
```

## Instalación

Requiere Python 3.11 o superior.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Windows CMD:        .venv\Scripts\activate.bat
# macOS / Linux:      source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Ejecución

```bash
python cargar_csv.py            # 16 pedidos en DRAFT (O001 → 4 unidades, 2100.00)
python ejecutar_escenarios.py   # E01–E15 y bitácora
python -m pytest -q             # 51 pruebas
uvicorn app.api:app --reload    # http://127.0.0.1:8000/docs
```

También puede arrancarse con `python run.py`, que abre Swagger automáticamente.

### Visual Studio 2022 (opcional)

Requiere la carga de trabajo "Desarrollo de Python". Ejecuta `instalar.bat` una vez, abre `TechStoreU4.sln` y presiona la flecha verde: arranca `run.py` y abre `http://127.0.0.1:8000/docs`.

### Publicación en IIS (opcional)

Ejecuta `publicar.bat` para generar la carpeta `publish`, cópiala al servidor, crea ahí el `.venv` e instala `requirements.txt`. El sitio usa `web.config` con el módulo HttpPlatformHandler; ajusta `processPath` a la ruta de tu `python.exe`.

## Reglas de negocio

| Regla | Dónde se protege |
|---|---|
| `Money` usa `Decimal`, no admite negativos, valores no finitos ni moneda distinta de MXN | `Money.__post_init__` |
| Un artículo exige un SKU no vacío y una cantidad mayor a 0; el subtotal se calcula | `OrderItem` |
| Máximo **20 unidades** por pedido (suma de cantidades, no de renglones) | `Order.add_item` |
| Solo un pedido DRAFT admite artículos | `Order.add_item` |
| **10 %:** VIP AND total **> 500** AND **≥ 4** unidades AND NOT promoción | `TEN_PERCENT` |
| **5 %:** total **> 5000** AND NOT promoción | `FIVE_PERCENT` |
| Si se cumplen ambas reglas, se aplica el 10 % | `discount_rate()` |
| `confirm()`: solo desde DRAFT, con artículos y con cliente activo | `Order.confirm` |
| `ship(guía)`: solo desde CONFIRMED y con guía no vacía | `Order.ship` |
| `cancel(motivo)`: solo desde CONFIRMED y con motivo no vacío | `Order.cancel` |
| `deliver()` y `return_order()`: solo desde SHIPPED | `Order.deliver`, `Order.return_order` |
| Una operación inválida no cambia el estado ni agrega eventos | Cada método valida antes de modificar |

## Endpoints

| Método | Ruta | Descripción | Errores |
|---|---|---|---|
| GET | `/orders` | Lista los pedidos con su descuento | — |
| GET | `/orders/{id}` | Detalle, descuento y eventos | 404 |
| POST | `/orders` | Crea un pedido DRAFT (ampliación) | 404 si el cliente no existe, 409 si el pedido ya existe |
| POST | `/orders/{id}/items` | Agrega un artículo (ampliación) | 404, 409, 422 |
| POST | `/orders/{id}/confirm` | Confirma | 404, 409 (no está en DRAFT), 422 (vacío o cliente inactivo) |
| POST | `/orders/{id}/ship` | Envía, con `{"tracking_number": "..."}` | 404, 409, 422 (sin guía) |
| POST | `/orders/{id}/cancel` | Cancela, con `{"reason": "..."}` | 404, 409, 422 (sin motivo) |
| POST | `/orders/{id}/deliver` | Entrega | 404, 409 |
| POST | `/orders/{id}/return` | Devuelve | 404, 409 |
| POST | `/reset` | Recarga los 16 pedidos desde los CSV | — |

Errores: **404** el pedido no existe; **409** `InvalidOrderTransition`; **422** `InvalidOrderData` u `OrderItemLimitExceeded`. Como los cambios se acumulan en memoria, usa `POST /reset` (o reinicia el servidor) entre pruebas.

### Pruebas sugeridas en Swagger (`/docs`)

1. `POST /orders/O999/confirm` → **404**
2. `POST /orders/O013/confirm` dos veces → **200** y luego **409**
3. `POST /orders/O007/confirm` → **422** (pedido sin artículos)

## Evidencias

En `docs/capturas/`: carga de los 16 pedidos (`python cargar_csv.py`), resultado de `python -m pytest -q` y capturas de Swagger con una operación exitosa (200) y una rechazada (404, 409 o 422). La bitácora de E01–E15 está en `bitacora_escenarios.csv`, y el diagrama, los eventos y la reflexión en `docs/REPORTE.md`.
