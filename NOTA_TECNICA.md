# Nota técnica

## Arquitectura

Para desarrollar el proyecto separé el backend y el frontend, con el objetivo de mantener organizada la aplicación y facilitar su mantenimiento.

El backend lo desarrollé en Python utilizando FastAPI para crear los servicios REST y Uvicorn para ejecutarlos. Separé las funcionalidades en módulos para manejar las rutas, los modelos de datos, la normalización, las validaciones, las métricas y el almacenamiento temporal en memoria.

Para la interfaz utilicé HTML5, CSS3 y JavaScript. Esta se comunica con el backend mediante Fetch y permite cargar archivos JSON, consultar las métricas, visualizar las transacciones, aplicar filtros, realizar búsquedas y consultar el detalle de cada registro.

## Normalización y reglas

Como las transacciones provienen de tres fuentes con estructuras diferentes, definí un modelo común para trabajar con todos los registros de la misma manera. Este modelo contiene el identificador, monto, moneda, fecha, estado, indicador de validez, indicador de duplicado, errores encontrados y los datos originales de cada transacción.

Para identificar cada fuente utilicé los campos que distinguen sus respectivos formatos. Si un registro no corresponde a ninguna estructura reconocida, lo identifico como fuente desconocida.

Las monedas permitidas son USD, EUR y GTQ, según lo establecido en `config.json`. Para los montos decidí utilizar Decimal, aceptar únicamente valores finitos y no negativos, con un máximo de dos decimales. No realicé conversiones entre monedas ni redondeos, porque no se proporcionaron tasas de cambio ni reglas para hacerlo.

También definí un mapeo de estados para cada fuente, de manera que los diferentes valores originales se conviertan a estados comunes. En cuanto a las fechas, configuré los formatos permitidos y las normalicé a UTC. Cuando una fecha no contiene zona horaria, la interpreto como UTC.

Para las validaciones establecí que los campos obligatorios deben estar presentes y tener valores correctos. Cuando encuentro un problema, registro el error correspondiente para poder identificarlo posteriormente. Por ejemplo, el Formato 3 no proporciona la moneda en algunos registros. En lugar de asignar una moneda por defecto, decidí marcarlos como inválidos porque no sería correcto asumir ese dato.

Los registros inválidos y duplicados se conservan en memoria para poder consultarlos desde la interfaz. Los duplicados se identifican utilizando la fuente y el identificador de la transacción. Además, mantuve separados los indicadores de duplicidad y validez, ya que un registro puede cumplir las validaciones y aun así ser duplicado. Ambos tipos de registros se excluyen de los totales financieros.

El almacenamiento es temporal: los registros desaparecen cuando se reinicia el backend o cuando se utiliza la opción de limpiar los datos. No implementé una base de datos porque el objetivo de esta actividad es trabajar con archivos JSON y explorar las transacciones procesadas.

## Métricas, datos y pruebas

En el dashboard incluí métricas para consultar el total de transacciones procesadas, válidas, inválidas y duplicadas, así como el porcentaje de validez, el conteo por estado y los totales agrupados por moneda.

También incorporé tres archivos JSON de prueba, uno por cada formato, con los que puedo comprobar el comportamiento del sistema ante registros correctos e inconsistencias. Estos archivos se utilizan como datos de entrada y no como almacenamiento de los resultados procesados.

Para verificar el funcionamiento desarrollé pruebas con pytest que cubren la normalización, las validaciones, la detección de duplicados, el cálculo de métricas y los endpoints de la API.

## Uso de IA

Utilicé ChatGPT como apoyo durante el desarrollo para organizar el código, implementar algunas funciones, revisar la lógica de normalización y validación, preparar las pruebas y desarrollar la interfaz.

Entre las consultas que realicé estuvieron la integración de los tres formatos JSON en un modelo común, la definición de reglas para detectar datos inconsistentes y la revisión de la lógica para identificar transacciones duplicadas.

No acepté automáticamente todas las sugerencias. Revisé las propuestas y adapté las soluciones a los requisitos de la actividad. Por ejemplo, mantuve el uso de `Decimal` para manejar los montos, evité asignar monedas por defecto cuando el dato no estaba disponible y separé los indicadores de validez y duplicidad.

También utilicé las pruebas y la ejecución del sistema para comprobar el comportamiento de las funcionalidades implementadas. La IA fue una herramienta de apoyo, pero las decisiones técnicas y la validación final quedaron bajo mi responsabilidad.