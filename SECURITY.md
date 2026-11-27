# Security Policy

Use this policy to report vulnerabilities privately and understand FateBridge's built-in security boundaries. For installation and configuration, see [Getting started](docs/getting-started.md); ordinary bugs belong in [GitHub Issues](https://github.com/thomas-yanxin/FateBridge/issues).

On this page: [Supported Versions](#supported-versions) · [Reporting a Vulnerability](#reporting-a-vulnerability) · [Scope Notes](#scope-notes) · [Personal Data](#personal-data)

## Supported Versions

FateBridge is pre-1.0, and security fixes target the latest release (`0.1.1`). Pending development changes appear in [CHANGELOG](CHANGELOG.md#unreleased); check your installed version and corresponding Git tag before reporting.

| Version | Supported |
| --- | --- |
| `0.1.1` | Yes |
| Earlier or unpublished development versions | Upgrade to the current release |

## Reporting a Vulnerability

Do not open public issues with vulnerability details or sensitive reproduction inputs. Report privately through GitHub [Security Advisories](https://github.com/thomas-yanxin/FateBridge/security/advisories/new), or email **yx20001210@163.com** with:

- Issue description, impact, and required access.
- Fictional or redacted reproduction steps, affected version/commit, OS, and configuration.
- Whether the issue reproduces on the latest release.

Expect an initial acknowledgement within 7 days. Reporters who wish to be credited are acknowledged once a fix is released.

## Scope Notes

FateBridge provides local calculation interfaces; host applications supply user interfaces, model conversations, and perimeter controls. Built-in access boundaries depend on the transport:

| Interface | Built-in boundary | Deployment responsibility |
| --- | --- | --- |
| REST | Optional shared API keys (`FATEBRIDGE_API_KEYS`) | Configure keys and terminate TLS, rate limits, and network access at a gateway |
| MCP | Host-managed stdio process (`0` MCP resources) | Restrict host process access and add transport authentication if exposed over HTTP |
| CLI | Local process | Restrict host access, input files, and output logs |

- **REST authentication and bind scope:** `FATEBRIDGE_API_KEYS` and `API_KEY_HEADER_NAME` (default `X-API-Key`) protect `/api/tools` and calculation endpoints; empty configuration disables auth, and malformed nonempty entries fail startup. `/health`, `/ready`, `/metrics`, `/docs`, `/redoc`, `/openapi.json`, and `OPTIONS` are exempt. Shared keys do not provide per-user roles or isolation. REST binds to `0.0.0.0:8010` by default (use `API_HOST=127.0.0.1` for local-only access). `ALLOWED_ORIGINS` restricts browser CORS origins and does not authenticate callers; `FATEBRIDGE_HEAVY_CALC_MAX_CONCURRENCY` bounds process-local heavy work and is not a request rate limit.
- **MCP and CLI:** `fatebridge-mcp` runs over stdio by default and does not read REST API keys. If you expose FastMCP over Streamable HTTP, keep it on loopback behind SSH or add gateway authentication and TLS.
- **External data and licensing:** Swiss Ephemeris `.se1` files and optional solar/DE441 archives are not bundled in the wheel; see [ephemeris setup](docs/ephemeris.md), [LICENSE](LICENSE), and [NOTICE](NOTICE).

## Personal Data

Birth inputs may appear in responses, client chat histories, and host logs. FateBridge does not persist a calculation database on disk and returns results directly in each response payload. Always use fictional inputs in Issues and PRs, redact diagnostics before sharing, and use `detail=compact` or targeted `fields` when minimizing payload exposure (see [output controls](docs/agent-guide.md#输出控制与结果读取)).
