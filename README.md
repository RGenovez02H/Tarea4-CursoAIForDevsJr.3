# Sistema de Normalización de Transacciones

Desarrollé este proyecto en Python para procesar, normalizar, validar y consultar transacciones provenientes de tres formatos JSON diferentes.

El sistema utiliza FastAPI para el backend y una interfaz web desarrollada con HTML, CSS y JavaScript para visualizar y explorar la información.

Los registros procesados se almacenan únicamente en memoria. Esto significa que se mantienen disponibles mientras el backend está ejecutándose, pero desaparecen al reiniciarlo o utilizar la opción de limpieza.

## Requisitos

- Python 3.12 o superior.

## Instalación y ejecución

Para ejecutar el proyecto, primero abre una terminal en la carpeta principal y crea un entorno virtual. Después instala las dependencias necesarias:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Iniciar el backend

Desde la misma terminal, ingresa a la carpeta `BACK` y ejecuta el servidor:

```powershell
Set-Location .\BACK
python -m uvicorn app.main:app --reload
```

El backend estará disponible en:

- API: http://127.0.0.1:8000
- Documentación interactiva: http://127.0.0.1:8000/docs
- Estado del servicio: http://127.0.0.1:8000/api/health

### Iniciar el frontend

Mantén ejecutándose el backend y abre una segunda terminal desde la carpeta principal del proyecto.

Ejecuta los siguientes comandos:

```powershell
Set-Location .\FRONT
python -m http.server 5501 --bind 127.0.0.1
```

Una vez iniciado el servidor, abre el navegador e ingresa a:

http://127.0.0.1:5501

Desde esta interfaz puedes cargar los archivos JSON, consultar las transacciones, aplicar filtros, realizar búsquedas, revisar las métricas y consultar el detalle de los registros.

La URL base de la API se encuentra configurada en `FRONT/app.js`. El backend permite solicitudes CORS desde los puertos locales 5500 y 5501.

## Archivos JSON de prueba

El proyecto incluye tres archivos JSON de ejemplo para probar la normalización y validación de las transacciones. Se encuentran en la carpeta `data`:

| Archivo | Descripción |
|---|---|
| `formato_1.json` | Transacciones de la primera fuente. |
| `formato_2.json` | Transacciones de la segunda fuente. |
| `formato_3.json` | Transacciones de la tercera fuente. |

Para probar cada formato, desde el dashboard selecciona **Importar transacciones** y busca el archivo correspondiente dentro de la carpeta `data`.

Se recomienda procesar cada archivo por separado. Para ello, utiliza la opción **Limpiar memoria** antes de iniciar una nueva prueba. Así podrás observar los resultados de normalización y validación de cada fuente de manera independiente.

## Pruebas

Para ejecutar las pruebas automatizadas, abre una terminal, ingresa a la carpeta `BACK` y ejecuta:

```powershell
python -m pytest -q
```

Las pruebas permiten comprobar el funcionamiento de la normalización, las validaciones, la detección de duplicados, las métricas y los endpoints de la API.

## Endpoints disponibles

El backend cuenta con los siguientes endpoints:

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/transactions/upload` | Recibe uno o varios registros JSON y los procesa. |
| GET | `/api/transactions` | Consulta todos los registros procesados. |
| GET | `/api/transactions/valid` | Consulta las transacciones válidas. |
| GET | `/api/transactions/invalid` | Consulta los registros inválidos, incluidos los de fuente desconocida. |
| GET | `/api/transactions/search?transaction_id=...` | Busca transacciones por identificador y permite filtrar por fuente. |
| GET | `/api/metrics` | Consulta los contadores, estados y totales por moneda. |
| GET | `/api/health` | Comprueba el estado del backend. |
| DELETE | `/api/transactions` | Limpia los registros y el historial de duplicados almacenados en memoria. |

## Ejemplo de carga de una transacción

También es posible probar la API directamente desde PowerShell utilizando el siguiente ejemplo:

```powershell
@'
[
  {
    "id": "TX-001",
    "amount": 100.50,
    "currency": "USD",
    "timestamp": "2026-10-29T14:30:00-06:00",
    "status": "success"
  }
]
'@ | Set-Content -Encoding utf8 transacciones.json

curl.exe -X POST http://127.0.0.1:8000/api/transactions/upload `
  -H "Content-Type: application/json" `
  --data-binary "@transacciones.json"
```

Los montos normalizados se devuelven como cadenas para conservar su precisión decimal. Los datos originales se mantienen en `source_payload` con su estructura de origen.

Los totales financieros solamente consideran las transacciones válidas que no son duplicadas. El porcentaje de validez se calcula considerando todos los registros procesados.

## Configuración de las reglas

Las reglas que utiliza el sistema se encuentran en el archivo `config.json`. Allí definí las monedas soportadas, los estados, las fuentes, las condiciones de los montos, los identificadores, los duplicados y los formatos de fecha.

Las fechas que no incluyen zona horaria se interpretan como UTC. Las demás se convierten a UTC y se presentan en formato ISO 8601.

En el Formato 3 no se proporciona la moneda en su estructura original. Por este motivo, decidí marcar como inválidos los registros que no contienen ese dato, en lugar de asignar una moneda predeterminada o realizar una conversión sin información suficiente.

## Interfaz web

La interfaz se encuentra en la carpeta `FRONT` y está desarrollada con HTML5, CSS3 y JavaScript, utilizando Fetch API para comunicarse con el backend.

Desde ella se pueden cargar archivos JSON, visualizar las transacciones, aplicar filtros, realizar búsquedas, consultar detalles y revisar las métricas generadas.

El sistema no utiliza una base de datos ni almacenamiento local para conservar los resultados procesados. Toda la información permanece en memoria mientras el backend está ejecutándose.