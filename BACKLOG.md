# Backlog — a2a-smol-adapter

## Completed

- [x] **P0-1** Test d'intégration serveur + client (e2e avec ASGI transport)
- [x] **P0-2** Authentification API key (Bearer token, middleware Starlette)
- [x] **P0-3** Streaming SSE (server-side via `execute_streaming`, agent card `streaming=True`)
- [x] **P1-4** Retry client avec backoff exponentiel (ConnectError/TimeoutException, configurable)
- [x] **P1-5** Timeout configurable serveur (`asyncio.wait_for`, emit `failed` on timeout)
- [x] **P2-7** Healthcheck endpoint (`GET /health`)

## Skipped (YAGNI)

- **P2-6** Task store persistant — `InMemoryTaskStore` suffit, pas de scale horizontal prévu
- **P2-8** Métriques/observabilité — pas de déploiement prod à monitorer pour l'instant

## Future Ideas

- Client-side SSE consumption (`message/stream` consumer in `SmolA2ADelegateTool`)
- Multi-part message support (file, data parts)
- Task cancellation propagation to running `CodeAgent`
- PyPI publication
