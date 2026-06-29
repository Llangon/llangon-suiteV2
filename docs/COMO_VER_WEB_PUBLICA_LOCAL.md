# Como ver la web publica en local

Hay dos superficies distintas:

| Uso | URL | Carpeta |
| --- | --- | --- |
| Aplicacion privada | `http://127.0.0.1:8787/` | `webapp/infonalia_webapp/` |
| Web publica | `http://127.0.0.1:5500/` | `firebase/public_firebase` |

## Ver la aplicacion privada

La aplicacion privada se sirve con el despliegue local Windows ya instalado:

`http://127.0.0.1:8787/`

No usa la carpeta `firebase/public_firebase`.

## Ver la web publica

Desde la raiz del proyecto, ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\start_public_web_preview.ps1
```

Despues abre:

`http://127.0.0.1:5500/`

La vista previa sirve exclusivamente:

`firebase/public_firebase`

No interfiere con la aplicacion privada en `127.0.0.1:8787`.

## Parar la vista previa publica

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\stop_public_web_preview.ps1
```

## Carpeta activa de la web publica

La unica carpeta activa de contenido web publico es:

`firebase/public_firebase`

La configuracion de Firebase Hosting esta en:

`firebase.json`

y apunta a:

`firebase/public_firebase`

## Backups

Las versiones y configuraciones retiradas en la limpieza estan en:

`.local_backups/web_publica_cleanup_20260624_112340`

El backup anterior de la web publica se conserva en:

`.local_backups/public_firebase_20260624_104312`
