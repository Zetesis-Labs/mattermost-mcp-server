# mattermost-mcp-server

Imagen de solo lectura del servidor MCP independiente de Mattermost (`mcpserver/` de
[mattermost-plugin-agents](https://github.com/mattermost/mattermost-plugin-agents),
Apache-2.0). Mattermost no publica imagen ni binario, así que se compila aquí
desde el commit de la etiqueta upstream, con un único parche: `read-only.patch`.

```
ghcr.io/zetesis-labs/mattermost-mcp-server:<etiqueta upstream>-readonly
```

## Solo lectura

El parche hace dos cosas:

- Cierra el filtro de upstream para las herramientas que modifican datos. No
  aparecen en `tools/list` y `tools/call` las rechaza, en HTTP y en stdio, también
  con `--dev`. El mensaje de rechazo habla de «Enterprise» porque upstream usa ese
  filtro para sus licencias; aquí no tiene que ver con la licencia.
- Quita dos herramientas que sacarían un acceso sin autenticar:
  - `list_incoming_webhooks`: el ID de un webhook de entrada es su secreto, y con él
    se publica en `/hooks/<id>`.
  - `get_file_link`: devuelve un enlace público que cualquiera puede abrir, si el
    servidor los tiene activados.

Esto limita lo que hace el MCP, no el token. Quien tenga el token personal puede
seguir escribiendo directamente contra la API de Mattermost.

Contra Mattermost Team 10.11.2 fallan 12 de las 72 herramientas, con un error
claro: 10 requieren licencia, y `list_agents` y `read_file` requieren el plugin
Agents en marcha.

## Uso

En modo HTTP no guarda credenciales: cada cliente envía su token personal de
Mattermost en `Authorization: Bearer <token>` y las herramientas actúan con
los permisos de ese usuario.

```
mattermost-mcp-server --transport http --http-bind-addr 0.0.0.0 --http-port 8080 \
  --site-url https://<host público> --server-url https://mattermost.irontec.com
```

El endpoint MCP es `https://<host público>/mcp`. Con Claude Code:

```
claude mcp add --transport http mattermost https://<host público>/mcp \
  --header "Authorization: Bearer <token personal>"
```

## Prueba

```
python3 test/verify_read_only.py
```

Compila la imagen, levanta Mattermost Team 10.11.2 con MySQL y comprueba:

- que la lista de herramientas es exactamente `READ_TOOLS`;
- que el filtro rechaza cada herramienta de `BLOCKED_TOOLS` y que `create_post` no
  publica;
- que ninguna herramienta devuelve credenciales ni enlaces públicos;
- que a Mattermost solo le llegan peticiones `GET` y los `POST` de búsqueda de
  `READ_ONLY_POSTS`, según sus propios registros (estos no incluyen las rutas
  `/plugins/*`).

El workflow `Publish image` la pasa antes de publicar.

## Actualizar a otra versión upstream

1. Cambiar `MM_AGENTS_COMMIT` en el `Dockerfile` por el commit de la nueva
   etiqueta (`gh api repos/mattermost/mattermost-plugin-agents/git/ref/tags/<tag>`;
   si es una etiqueta anotada, resolver su `object.sha`). Subir también la imagen
   de Go si su `go.mod` pide otra versión.
2. Si `read-only.patch` deja de aplicarse, el build falla: hay que regenerarlo.
3. Pasar la prueba. Si upstream añade o renombra herramientas, falla hasta
   revisarlas y actualizar `READ_TOOLS` y `BLOCKED_TOOLS`. Revisar además el diff
   de `mcpserver/tools/`: la prueba no ejecuta el código de las 12 herramientas
   que fallan contra Team ni los argumentos opcionales, así que no vería que una
   herramienta de lectura pasara a escribir ahí.
4. Etiquetar este repo (`git tag v2.13.0-readonly && git push --tags`). El workflow
   publica la imagen multiarquitectura.
