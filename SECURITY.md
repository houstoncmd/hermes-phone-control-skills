# Security Policy

## What this repository must NEVER contain

| Forbidden | Examples |
|---|---|
| Real unlock pattern / PIN / password | 7 keypad digits, a device's real `SEQ = "..."` |
| Private keys | WireGuard `PrivateKey` / `PresharedKey`, SSH keys, `-----BEGIN ...` |
| Token / session / API key | `ghp_...`, cookies, bearer tokens |
| Real server public IP / personal email | use `YOUR_VPS_PUBLIC_IP`, `you@example.com` instead |
| Personal content captured from a phone screen | chat messages, real screenshots, contact lists |

The scripts read secrets from an **external vault** (e.g. `~/.hermes/data/vault.json`) or from a
`0600` file the user creates on their own machine — no real value is ever embedded in the code.

## Pre-push checklist (run it every time)

```bash
# Run from the repo root — every command must come back empty
grep -rInE '[0-9]-[0-9]-[0-9]-[0-9]-[0-9]-[0-9]-[0-9]|[0-9]{7}|-----BEGIN|ghp_[A-Za-z0-9]|@gmail\.com|password\s*=\s*[^< ]' . \
  --exclude=LICENSE --exclude-dir=.git
# (first term = a 7-digit keypad pattern written in dash order — substitute your own shape if you like)
```

If a real value shows up → replace it with a placeholder (`YOUR_PATTERN`, `YOUR_VPS_PUBLIC_IP`,
`you@example.com`) and, if it was already committed, **rewrite it out of git history too**.

## Reporting

Found a leaked secret in this repo → open a GitHub Issue immediately with the file/commit link
(never paste the secret itself), and the repo owner must revoke/rotate that value at once.
