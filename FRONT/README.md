# Frontend

Interfaz de HTML5, CSS3 y JavaScript vanilla; consume la API FastAPI con Fetch API. No utiliza frameworks, bibliotecas frontend ni almacenamiento local. Las transacciones permanecen únicamente en la memoria del backend.

## Inicio

1. Inicia el backend en una terminal:

   ```powershell
   Set-Location .\BACK
   python -m uvicorn app.main:app --reload
   ```

2. En otra terminal, sirve esta carpeta con el servidor HTTP incluido en Python:

   ```powershell
   Set-Location .\FRONT
   python -m http.server 5501 --bind 127.0.0.1
   ```

3. Abre `http://127.0.0.1:5501`.

La URL de la API se define al inicio de `app.js` (`http://127.0.0.1:8000/api`). El backend permite CORS para los orígenes locales `http://127.0.0.1:5500`, `http://localhost:5500`, `http://127.0.0.1:5501` y `http://localhost:5501`.

## Funcionalidades

- Panel de métricas, totales por moneda y conteo por estado.
- Importación de uno o varios archivos JSON.
- Tabla con búsqueda por identificador, filtros y estado visual de inválidos/duplicados.
- Detalle de registro con errores y `source_payload`.
- Limpieza de la memoria del backend con confirmación.
- Actualización manual y automática de la información.
