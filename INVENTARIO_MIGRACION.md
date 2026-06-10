# Inventario De Migración

Origen revisado: `C:\Users\LLangon03\Documents\Codex\llangon-suite`

| Elemento origen | Destino en `Llangon-SuiteV2` | Clasificación | Decisión | Motivo |
|---|---|---|---|---|
| `.git/` raíz | ninguno | historial Git | excluido | El repositorio nuevo comienza sin historia ni remoto heredado. |
| `.git/config` | ninguno | configuración Git | excluido | Refería a `Llangon/llangon-suite.git`. |
| `.gitattributes` | `.gitattributes` | configuración | copiado | Configuración neutra y reutilizable. |
| `.gitignore` | `.gitignore` | seguridad | sustituido | Se creó una política más estricta para datos, secretos y temporales. |
| `README.md`, `PROJECT_CONTEXT.md` | raíz | documentación | sustituidos | Describían el repositorio anterior. |
| `INVENTARIO_MIGRACION.md`, `MIGRACION_LOG.md` | raíz | documentación histórica | sustituidos | Registraban una migración previa y rutas ya obsoletas. |
| `docs/DESPLIEGUE_COLABORACION.md` | mismo destino | documentación | copiado | Guía útil de trabajo interno. |
| `docs/ROLES_Y_FLUJO.md` | mismo destino | documentación | copiado | Contexto funcional vigente. |
| `docs/SANEAMIENTO_REPOSITORIO.md` | `SANEAMIENTO_REPOSITORIO.md` | documentación | sustituido | Contenía rutas históricas; se creó una versión vigente en raíz. |
| `documentos_contexto/` | mismo destino | contexto histórico | copiado con advertencia | Conserva antecedentes, sin convertir conversaciones antiguas en instrucciones actuales. |
| `webapp/infonalia_webapp/app.py` | mismo destino | código | copiado y saneado | Se eliminaron credenciales utilizables por defecto y referencias operativas antiguas. |
| `webapp/infonalia_webapp/static/` | mismo destino | frontend | copiado y saneado | Activos necesarios; se generalizaron etiquetas visibles del rol revisor. |
| `webapp/infonalia_webapp/.env.example` | mismo destino | plantilla | copiado y saneado | Sin usuarios, contraseñas, correos ni rutas reales. |
| Lanzadores BAT | mismo destino | configuración local | copiados y saneados | Arranque local en `127.0.0.1` y monitor desactivado. |
| `webapp/infonalia_webapp/data/.gitkeep` y `README_DATOS.md` | mismo destino | estructura segura | copiados | Mantienen la carpeta sin datos reales. |
| Bases de datos, claves, MSG, PDF, TXT y descargas | ninguno | sensible | excluido | No estaban presentes en la fuente versionable y quedan bloqueados por `.gitignore`. |
| `firebase/public_firebase/` | mismo destino | web pública | copiado parcialmente | Se conservaron web y configuración de hosting. |
| `firebase/public_firebase/.firebaserc` | `.firebaserc.example` | configuración Firebase | sustituido | Se eliminó el proyecto operativo de prueba y se dejó un marcador. |
| `herramientas_python/*.py` | mismo destino | herramientas | copiado | Código necesario; no se ejecutó. |
| `macros/CrearCarpetas_corregido.bas` | mismo destino | VBA | copiado | Macro necesaria sin hallazgos sensibles. |
| `macros/CrearEmailOutlook_Llangon_mejorado.bas` | mismo destino | VBA | copiado y saneado | Se retiró el correo incrustado; ahora se solicita localmente. |
| `inventario-licitaciones-langon/` | ninguno | repositorio anidado | excluido | Contenía otro `.git` y remoto independiente. |
| `_NO_SUBIR_GITHUB/` | ninguno | cuarentena | excluido/ausente | No estaba dentro del origen revisado; la documentación previa indica que pudo existir fuera. |
| `.venv`, `venv`, `node_modules`, cachés, logs, ZIP y backups | ninguno | generado/temporal | excluido/ausente | No son necesarios para reconstruir el proyecto. |
| Identificadores internos heredados del rol de revisión | código existente | compatibilidad | pendiente de revisión | Eliminarlos exige migrar esquema, estados, API y posibles bases de datos externas. |
| Proyecto Firebase real | configuración local | despliegue | pendiente de revisión | Debe confirmarse antes de crear `.firebaserc` y antes de cualquier deploy. |
