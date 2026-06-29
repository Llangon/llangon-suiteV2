# Cambios en la web pública

> Nota del 24/06/2026: esta version fue descartada y la web publica activa se revirtio a la version anterior. Ver `docs/INFORME_REVERSION_WEB_PUBLICA_20260624.md`.

## Resumen

Se ha rehecho la web pública de ASESORES LLANGON, S.L. como web comercial estática para Firebase Hosting.

La versión anterior cargaba la mayor parte del contenido desde JavaScript. La nueva versión entrega el contenido principal directamente en HTML para mejorar SEO, accesibilidad, legibilidad y mantenimiento.

## Estructura nueva

- `/`
- `/servicios/`
- `/como-trabajamos/`
- `/nosotros/`
- `/recursos/`
- `/contacto/`
- `/aviso-legal/`
- `/politica-privacidad/`
- `/politica-cookies/`
- `/accesibilidad/`

## Redirecciones

- `/metodologia` -> `/como-trabajamos/`
- `/metodologia/**` -> `/como-trabajamos/`
- `/noticias` -> `/recursos/`
- `/noticias/**` -> `/recursos/`
- `/zona-privada` -> `/contacto/`

## SEO y entorno de prueba

- Titles y descriptions específicos por página.
- Canonical por página apuntando al dominio de prueba.
- Open Graph básico.
- `robots.txt` con `Disallow: /`.
- Header `X-Robots-Tag: noindex, nofollow`.
- Metatag `robots` con `noindex, nofollow`.
- `sitemap.xml` creado para validación de estructura.
- Datos estructurados JSON-LD externos para evitar scripts inline.

## Accesibilidad y UX

- HTML semántico con un único H1 por página.
- Enlace de salto al contenido.
- Menú móvil con `aria-expanded`.
- Foco visible.
- Campos de formulario con etiquetas.
- Mensajes de validación claros.
- Diseño mobile-first sin carruseles ni dependencias pesadas.

## Límites conocidos

- El formulario de contacto no envía aún datos a un backend ni a un correo confirmado.
- Los textos legales definitivos requieren validación.
- No se han creado artículos reales en Recursos; se ha preparado la estructura editorial.
- No se ha desplegado en Firebase desde Codex.
