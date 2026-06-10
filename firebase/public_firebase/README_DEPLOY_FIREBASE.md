## Publicar la web publica en Firebase Hosting

Carpeta a publicar:

`public_firebase`

### Pasos

1. Confirmar que la web no contiene datos privados.
2. Copiar `.firebaserc.example` como `.firebaserc`.
3. Sustituir `REPLACE_WITH_FIREBASE_PROJECT_ID` por el proyecto autorizado.
4. Abrir una terminal dentro de esta carpeta.
5. Instalar la herramienta de Firebase si fuera necesario:

```bash
npm install -g firebase-tools
```

6. Iniciar sesion en Google:

```bash
firebase login
```

7. Confirmar o asociar esta carpeta al proyecto:

```bash
firebase use --add
```

8. Revisar los archivos que se publicarán.
9. Publicar únicamente con autorización expresa:

```bash
firebase deploy
```

### Notas

- Esta version publica no incluye la zona privada.
- `.firebaserc` es local y no se versiona; solo se conserva el ejemplo.
- El boton de acceso privado apunta temporalmente a la pagina de contacto.
- Las rutas internas (`/servicios`, `/metodologia`, etc.) ya quedan resueltas por `firebase.json`.
