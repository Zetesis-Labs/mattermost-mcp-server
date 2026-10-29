# mattermost-mcp-server

Imagen del servidor MCP independiente de Mattermost (`mcpserver/` de
[mattermost-plugin-agents](https://github.com/mattermost/mattermost-plugin-agents),
Apache-2.0). Mattermost no publica imagen ni binario, así que se compila aquí
desde el commit de la etiqueta upstream, sin modificar el código.

```
ghcr.io/irontec-comms/mattermost-mcp-server:<etiqueta upstream>
```

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

## Actualizar a otra versión upstream

1. Cambiar `MM_AGENTS_COMMIT` en el `Dockerfile` por el commit de la nueva
   etiqueta (`gh api repos/mattermost/mattermost-plugin-agents/git/ref/tags/<tag>`;
   si es una etiqueta anotada, resolver su `object.sha`).
2. Etiquetar este repo con la misma versión (`git tag v2.3.0 && git push --tags`).
   El workflow `Publish image` publica la imagen multiarquitectura.
