# Security Policy

Use this policy to report vulnerabilities privately and understand which security
controls FateBridge provides. For installation and configuration, see
[Getting started](docs/getting-started.md); ordinary defects belong in
[GitHub Issues](https://github.com/thomas-yanxin/FateBridge/issues).

On this page: [Supported Versions](#supported-versions) ·
[Reporting a Vulnerability](#reporting-a-vulnerability) ·
[Scope Notes](#scope-notes) · [Personal Data](#personal-data)

## Supported Versions

FateBridge is pre-1.0. Security fixes target the latest released version. The
current release is `0.1.1`; `0.2.0` entries in the
[Changelog](CHANGELOG.md) describe earlier, unpublished development work.

| Version | Supported |
| ------- | --------- |
| 0.1.1   | Yes       |
| Earlier or unpublished development versions | Upgrade to the current release |

If a problem affects an older version, include that version in your report and
check whether you can reproduce it on the current release when practical.

## Reporting a Vulnerability

Please do not open a public issue containing vulnerability details or sensitive
reproduction material.

Report privately via GitHub's
[Report a vulnerability](https://github.com/thomas-yanxin/FateBridge/security/advisories/new)
(Security → Advisories), or email **yx20001210@163.com** with:

- a description of the issue, its impact and any required access,
- steps to reproduce using fictional or redacted data,
- the affected version or commit, operating system and relevant configuration,
- whether you have observed the issue on the current release.

If GitHub private reporting is unavailable, use the email address above. Never
send API secrets or real birth records as part of a reproduction.

You can expect an initial acknowledgement within 7 days. Once a fix is
released, we will credit reporters who wish to be named.

## Scope Notes

FateBridge is a backend calculation toolkit. Its access controls depend on the
interface used:

| Interface | Built-in boundary | Deployment responsibility |
| --- | --- | --- |
| REST | Optional shared API keys | Configure keys and a gateway for TLS, request limits and network access |
| MCP | stdio process launched by the host | Restrict process access and provide authentication if exposing a network transport |
| CLI | Local process | Restrict host access, input files and output files |

REST API key authentication uses `FATEBRIDGE_API_KEYS` and
`API_KEY_HEADER_NAME` (default `X-API-Key`). An empty key configuration disables
authentication; malformed nonempty entries stop startup. Shared keys do not
provide accounts, roles or per-tool authorization.

`/health`, `/ready`, `/metrics`, `/docs`, `/redoc`, `/openapi.json` and `OPTIONS`
are exempt from API key checks. `/api/tools` and result-delivery routes are
protected when keys are configured. Keys share the service's accessible result
store; they do not establish per-user result ownership. Restrict operational
endpoints and isolate services when callers require separate data access.

REST binds to `0.0.0.0:8010` by default. For local use set
`API_HOST=127.0.0.1`. CORS controls browser origins and does not authenticate
callers. Heavy-calculation concurrency controls the amount of simultaneous
work in a process and does not provide a request rate limit.

FastMCP (`fatebridge-mcp`) uses stdio by default. REST API key settings do not
apply to MCP or CLI. If a host changes the MCP transport to expose a network
endpoint, it must provide transport authentication.

The Python distribution does not bundle Swiss Ephemeris `.se1` data. The
optional `uv run --locked python -m fatebridge.fetch_ephe` command downloads
data separately from a source checkout. Project code, third-party dependencies
and downloaded data have separate license declarations; see [LICENSE](LICENSE)
and [NOTICE](NOTICE).

## Personal Data

Birth information may appear in responses, snapshots, client histories and
calculation logs. When the response budget triggers full-result delivery, the
service writes the selected result to a private temporary directory owned by
the operating-system user. POSIX uses owner-only modes and flock; Windows uses
an owner-only ACL and native file locks, and rejects reparse points. These
artifacts have expiry and capacity limits;
they are not encrypted storage or a user account boundary.

Treat exported JSON, snapshots, result references and logs as potentially
sensitive. Use fictional examples in Issues and PRs, redact diagnostics before
sharing them, and apply your deployment's file-access and retention policies.
The [Agent guide](docs/agent-guide.md#完整结果交付与同次导出) explains how full-result
artifacts are read and verified.
