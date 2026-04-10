## V3 Stabilization Gap Analysis

### Scope
- Repo: `simplebalance89-ai/sb-enpro-portal-v2`
- Base branch analyzed: `v3.0-modular-architecture` at `c2e874a`
- Deploy target: Render service `enpro-fm-portal`

### Critical Gaps
1. API contract mismatch in v3 chat request model.
- Symptom: frontend shows generic connection error for valid requests.
- Root cause: v3 handler accessed `request.user_id` without model field.
- Status: fixed in commit `9df23ba`.

2. Voice endpoint mismatch between frontend and backend.
- Symptom: hold-to-speak fails even when app is up.
- Root cause: frontend posted to `/api/v3/voice`, backend serves `/api/voice-search`.
- Status: fixed in commit `dce052b`.

3. Startup ordering bug for logger initialization.
- Symptom: `NameError: logger is not defined` during import/startup.
- Root cause: logger used before initialization in `server.py`.
- Status: fixed in commit `c17bae2`.

4. Dependency pin blocks build.
- Symptom: Docker install fails on `itsdangerous==2.2.2`.
- Root cause: version not published on PyPI.
- Status: fixed in commit `de032d0` (`2.2.0`).

### High-Risk Operational Gaps
1. Unified handler hard dependency on Azure env setup.
- If `AZURE_OPENAI_KEY` is missing, v3 router initialization fails and chat endpoint degrades.
- Action: verify Render env var completeness before release.

2. Frontend rollback risk.
- Latest remote commit (`c2e874a`) changed only `static/index.html` ("Rollback UI to v2.x from backup").
- Action: confirm intended UI mode (`app.js` vs `app_v3.js`) before deployment.

3. Weak client-side error observability.
- Generic fallback message hides backend details.
- Action: log response status and error payload to console for faster triage.

### Release Strategy (Stabilization Branch)
1. Branch from `origin/v3.0-modular-architecture`.
2. Keep fixed commits for build/startup/v3 chat/voice contract.
3. Freeze UI entrypoint choice explicitly in `static/index.html`.
4. Deploy to Render from this branch only.
5. Gate promotion on smoke tests:
- `GET /health`
- `POST /api/chat`
- `POST /api/v3/chat`
- `POST /api/voice-search` (or text equivalent)

### Recommended Immediate Smoke Commands
```bash
curl -sS https://enpro-fm-portal.onrender.com/health
curl -sS -X POST https://enpro-fm-portal.onrender.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"lookup CLR510","session_id":"smoke"}'
curl -sS -X POST https://enpro-fm-portal.onrender.com/api/v3/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"lookup CLR510","session_id":"smoke"}'
```

