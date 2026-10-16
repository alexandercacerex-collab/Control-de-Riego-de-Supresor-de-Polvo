# Dashboard de riego y supresión de polvo — LB-VEILLE-ESPINAR

Aplicación interactiva en **Streamlit** que utiliza el eje extraído del KMZ original.

**Eje incluido:** PK 11+200 a PK 276+900 (265,70 km por progresivas); 53.142 vértices y puntos de control cada 100 m. La geometría se entrega en `data/eje.npz`, así que no es necesario subir nuevamente el KMZ. Las progresivas provienen de las estacas identificadas en el KML; no se estiman usando distancia en línea recta.

## Funcionalidades

- Buscar por progresiva inicial y final (`11+200`, `12+450`) y visualizar el tramo en el mapa.
- Crear capas de riego programado, en proceso, ejecutado o pendiente.
- Registrar fecha, empresa, cisterna, supresor, volumen, viajes y observaciones.
- Activar/desactivar capas por estado y filtrar empresas/fechas.
- Dashboard con longitud única ejecutada (sin duplicar los tramos superpuestos), volumen, viajes y gráficos.
- Descargar reportes CSV y capas KMZ para Google Earth; respaldar/restaurar registros mediante CSV.

## Instalación local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub y Streamlit Community Cloud

1. Cree un repositorio en GitHub y suba **todo el contenido de esta carpeta**, conservando `data/eje.npz`.
2. Visite [share.streamlit.io](https://share.streamlit.io), elija **Create app**, conecte su repositorio y rama principal.
3. En **Main file path**, escriba `app.py` y despliegue.
4. Registre las actividades; descargue un CSV de respaldo al finalizar cada jornada.

> **Limitación del despliegue:** los registros se almacenan en una base SQLite local creada al arrancar la aplicación. El disco de Streamlit Community Cloud **no garantiza persistencia** entre reinicios o réplicas y SQLite local no sirve para edición multiusuario concurrente entre instancias. Para operación continua/multiusuario use una base externa (Supabase/PostgreSQL u otra); la versión entregada incluye importación/exportación CSV como respaldo.

## Cómo se calculan los indicadores

- `km actividad = (PK fin - PK inicio) / 1000`.
- `km únicos ejecutados` = longitud de la unión de todos los intervalos con estado **Ejecutado** que cumplen los filtros.
- `% cobertura` = km únicos ejecutados / 265,70 km × 100.
- Volumen y viajes son sumas de actividades, por lo que consideran aplicaciones repetidas.
- La cobertura representa registro operacional por tramo, **no verifica físicamente** la aplicación ni acredita una dosificación de producto.

## Estructura

- `app.py`: aplicación Streamlit.
- `data/eje.npz`: eje y progresivas obtenidos del KMZ facilitado.
- `requirements.txt`: dependencias.
- `.gitignore`: evita subir bases con datos de operación.

## Próximas mejoras opcionales

Persistencia multiusuario vía Supabase/PostgreSQL, control de usuarios, evidencia fotográfica por actividad, seguimiento GPS de cisternas, indicadores por turno, estimación de dosificación por km y emisión de informes PDF.
