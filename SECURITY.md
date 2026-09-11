# Security

## Reporting

Email **trommatic@icloud.com**. Please don't open a public issue for anything exploitable.

Expect a reply within a week. This is a solo MIT-licensed side project — there is no bug
bounty and no formal SLA.

## Scope

Conveyer runs arbitrary Claude-generated Python against a local FLE instance and a local
Docker-hosted Factorio server. There is no hosted deployment, no user data, and no network
service exposed by this repo itself.

Worth reporting:

- Anything that lets code generated in the agent loop escape the intended FLE/Docker sandbox.
- Leakage of the `ANTHROPIC_API_KEY` or other local secrets into logs, commits, or the
  Factorio server's own state.

Not in scope: bugs in FLE itself or in Factorio — report those upstream.
