# TechStore U4 · Componentes de Lógica de Negocio

Sistema de gestión del ciclo de vida de pedidos y reglas de negocio para comercio electrónico, desarrollado para la Actividad 4 de la unidad de aprendizaje Componentes de Lógica de Negocio (FIME · UANL).

La solución implementa principios de diseño guiado por el dominio (DDD), desacoplamiento de reglas comerciales mediante el patrón Specification y control de transiciones a través de una máquina de estados finitos orientada a eventos. La capa de servicios expone las operaciones del agregado mediante una API REST en FastAPI.

---

## Características del Sistema

* Repositorio en Memoria: Inicialización del modelo de datos a partir de fixtures en archivos CSV. Los cambios de estado no persisten en base de datos entre ejecuciones.
* Objetos de Valor (Value Objects): Modelado monetario mediante la clase Money con precisión fija (Decimal), validando divisas válidas (MXN) y prohibiendo montos negativos.
* Motor de Descuentos Desacoplado: Reglas de elegibilidad evaluadas de forma aislada y combinadas jerárquicamente con operadores lógicos (AND, OR, NOT).
* Integridad de Estados y Eventos de Dominio: Flujo unidireccional de estados de pedido (DRAFT -> CONFIRMED -> SHIPPED -> DELIVERED / RETURNED / CANCELLED) con emisión de eventos trazables.
* API RESTful y Mapeo de Excepciones: Controladores HTTP con validaciones estrictas y retorno de códigos de estado según el estándar RFC (200, 201, 404, 409, 422).

---

## Estructura del Repositorio

techstore-u4/
├── app/
│   ├── __init__.py
│   ├── domain.py             # Entidades (Customer, Order), Value Objects (Money, OrderItem), eventos y excepciones
│   ├── specifications.py     # Implementación del patrón Specification y cálculo de descuentos
│   └── api.py                # Endpoints de la API REST, esquemas y manejadores de excepciones
├── datos/                    # Fixtures CSV base (clientes, productos, pedidos, detalle y escenarios)
├── docs/                     # Diagramas de estados y documentación técnica
├── tests/
│   ├── test_domain.py        # Pruebas unitarias de reglas, invariantes y escenarios E01–E15
│   └── test_api.py           # Pruebas funcionales de la API y códigos de error HTTP
├── bitacora_escenarios.csv   # Registro resultante de la ejecución de los escenarios E01–E15
├── cargar_csv.py             # Módulo de carga y parsing de fixtures a memoria
├── ejecutar_escenarios.py    # Runner de evaluación de los 15 escenarios de negocio
├── pytest.ini                # Configuración de ejecución del suite de pruebas
├── requirements.txt          # Dependencias de producción y pruebas
└── README.md                 # Documentación del proyecto

---

## Reglas de Negocio

* Invariante Monetario: Uso estricto de Decimal. No admite importes negativos ni valores no finitos. Exclusivo en divisa MXN (Money.__post_init__).
* Línea de Pedido: Requiere SKU existente y cantidad entera positiva. El subtotal se deriva del precio unitario (OrderItem).
* Restricción de Volumen: Máximo 20 unidades en total por pedido, siendo la suma agregada de cantidades de artículos, no de líneas (Order.add_item).
* Modificación de Pedido: Solo se permite agregar artículos si el pedido permanece en estado DRAFT (Order.add_item).
* Descuento del 10%: Cliente VIP AND total > 500 MXN AND >= 4 unidades AND NOT con promoción previa (Especificación TEN_PERCENT).
* Descuento del 5%: Total > 5000 MXN AND NOT con promoción previa (Especificación FIVE_PERCENT).
* Jerarquía de Descuentos: En caso de concurrencia de condiciones para el 5% y el 10%, se aplica de forma preferente el 10% (discount_rate).
* Confirmación: Solo desde DRAFT. Exige cliente activo y al menos un artículo registrado en el pedido (Order.confirm).
* Despacho / Envío: Solo desde CONFIRMED. Exige registrar una guía de rastreo no vacía (Order.ship).
* Cancelación: Solo desde CONFIRMED. Exige proveer un motivo de cancelación no vacío (Order.cancel).
* Entrega y Devolución: Solo permitidas si el pedido se encuentra en estado SHIPPED (Order.deliver, Order.return_order).
* Atomicidad Operacional: Las operaciones inválidas lanzan excepciones de dominio sin modificar el estado ni generar eventos.

---

## Instalación y Configuración

Requisitos del Sistema: Python 3.11 o superior.

1. Clonar el repositorio localmente:
git clone https://github.com/tu-usuario/techstore-u4.git
cd techstore-u4

2. Configurar y activar el entorno virtual de trabajo:

Linux / macOS:
python3 -m venv .venv
source .venv/bin/activate

Windows (PowerShell):
python -m venv .venv
.venv\Scripts\Activate.ps1

Windows (CMD):
python -m venv .venv
.venv\Scripts\activate.bat

3. Instalar las dependencias del proyecto:
pip install -r requirements.txt

---

## Ejecución y Verificación

1. Verificación de Carga de Datos (Comprueba la correcta lectura e instanciación de los 16 pedidos base):
python cargar_csv.py

2. Ejecución de la Suite de Escenarios de Negocio (Ejecuta los escenarios E01 a E15 y actualiza el archivo bitacora_escenarios.csv):
python ejecutar_escenarios.py

3. Ejecución de Pruebas Unitarias y de Integración:
pytest

4. Inicialización del Servidor API:
uvicorn app.api:app --reload

La interfaz interactiva Swagger UI se encuentra disponible en http://127.0.0.1:8000/docs.

---

## Especificación de la API REST

* GET /orders : Lista la totalidad de los pedidos y el cálculo de sus descuentos (200).
* GET /orders/{id} : Retorna el detalle del pedido, eventos emitidos y tasa de descuento aplicada (200, 404).
* POST /orders : Registra un nuevo pedido en estado DRAFT (201, 404, 409).
* POST /orders/{id}/items : Incorpora un nuevo artículo a un pedido en borrador (200, 404, 409, 422).
* POST /orders/{id}/confirm : Realiza la confirmación de la orden de compra (200, 404, 409, 422).
* POST /orders/{id}/ship : Asigna la guía de rastreo y cambia el estado a enviado. Payload: {"tracking_number": "..."} (200, 404, 409, 422).
* POST /orders/{id}/cancel : Registra la cancelación del pedido. Payload: {"reason": "..."} (200, 404, 409, 422).
* POST /orders/{id}/deliver : Registra la entrega formal del pedido al cliente (200, 404, 409).
* POST /orders/{id}/return : Procesa la devolución del producto previamente despachado (200, 404, 409).
* POST /reset : Restablece los pedidos en memoria al estado inicial de los archivos CSV (200).

Códigos de Respuesta y Manejo de Errores:
* 404 Not Found: El identificador de pedido o cliente solicitado no existe en memoria.
* 409 Conflict (InvalidOrderTransition): Transición de estado incompatible con el estado actual del pedido.
* 422 Unprocessable Entity (InvalidOrderData, OrderItemLimitExceeded): Carga útil inválida, campos requeridos vacíos o exceso del límite de 20 unidades permitidas.
