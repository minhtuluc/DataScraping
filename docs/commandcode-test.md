# Command Code live probe — 2026-09-23 (Asia/Saigon)

## Resolved: application User-Agent missing on model requests

The initial conclusion below was incomplete. A controlled follow-up kept the same
MiMo endpoint, key, body, Python transport and network, changing only the request
User-Agent from urllib's default to the truthful application identifier `DataScr/0.1`.
The request returned HTTP 200 with `PONG` in 7.14 seconds (30 reported total tokens).
The catalog client already set this header; the model adapter did not.

`datascr/models.py` now identifies the application consistently. A regression test
at the outgoing request boundary failed before the fix and passed afterward.
All 26 offline tests pass. Real extraction through the repaired adapter also passed:

| Model | Result | Elapsed |
|---|---|---|
| `xiaomi/mimo-v2.6-flash` | Valid JSON, length=100 m and crew=120, both quotes verified | 4.91 s |
| `deepseek/deepseek-v4-flash` | Same expected extraction | 3.39 s |
| `z-ai/glm-5.3-flash` | Same expected extraction | 6.53 s |

Evidence: `output/mimo-ping-20260922T172311423580Z.json` and
`output/commandcode-probe-20260922T172503863127Z.json`.
These are single small synthetic tests, not a model quality or speed benchmark.
No Wikipedia request was made. The earlier recommendation to contact support is
superseded by this confirmed client fix. No browser identity impersonation was used.

## Initial failed attempts (historical)

Endpoint: `https://api.commandcode.ai/provider/v1`.
Key supplied by the operator was entered through a hidden prompt and retained only in process memory.
No key is stored in source files or result files.

Authenticated GET `/models` returned a catalog with 76 entries. This catalog is not proof
that the account can invoke every listed model or that the key has been validated by generation.

Three generation requests used the existing `JsonModel` Chat Completions adapter,
with a synthetic document and a 1,024 output-token cap per request:

| Model | Result | Elapsed |
|---|---|---|
| `deepseek/deepseek-v4-flash` | HTTP 403 | 0.23 s |
| `moonshotai/Kimi-K2.5` | HTTP 403 | 0.20 s |
| `z-ai/glm-5.3-flash` | HTTP 403 | 0.20 s |

One additional diagnostic request to the same DeepSeek model captured the response body:
`error code: 1010`. It also returned HTTP 403 in 0.23 s.
No model generated a usable response; JSON extraction quality and billing remain unverified.

[Cloudflare documents 1010](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/)
as a block based on the client/browser signature. We stopped without impersonating another
client or attempting to bypass the block. This response does not establish that the API key is
invalid, the plan lacks credits, or these models are inaccessible to the account.

Initial proposed next action (superseded): ask Command Code support to investigate the API client block on
`POST /provider/v1/chat/completions`; provide the timestamp, status and code above, never the key.
No support message has been sent automatically.

The reusable probe is `scripts/probe_commandcode.py`. It now stops on 401/403/429 and writes
uniquely named reports to avoid overwriting results. The access problem is now resolved as described above.

References: [Provider API](https://commandcode.ai/docs/provider),
[GOAT plan](https://commandcode.ai/docs/plans/goat).
