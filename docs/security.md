# Security and Access Controls

## Authentication

The local dashboard supports optional token protection through `DUCO_UI_TOKEN`.

```powershell
$env:DUCO_UI_TOKEN="replace-with-local-token"
python web_app.py
```

When enabled, browser requests must include the token in the query string or form payload:

```text
http://127.0.0.1:8000/?token=replace-with-local-token
```

## Authorization

The demo runtime is intentionally local-only:

- The HTTP server binds to `127.0.0.1`.
- Input writes are limited to the project `data/` files.
- Output serving rejects paths outside `outputs/`.

## Secrets

No credentials are hardcoded. Optional external model access uses environment variables:

- `GEMINI_API_KEY`
- `GOOGLE_API_KEY`

## Sensitive Data

The project uses mock patient data for assessment purposes. In a production implementation, the same boundaries would be paired with user authentication, encrypted storage, access logs, and retention policies.
