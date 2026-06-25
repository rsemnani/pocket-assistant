# Runbook: a secret was committed

A secret is **compromised the moment it is pushed** to a public repo. Rotation is mandatory,
not optional. Work top to bottom.

## 1. Rotate the secret at its source (do this FIRST)

- **LLM API key** (Anthropic/OpenAI): revoke the key in the provider console; issue a new
  one; update the `.env` on `@mini`.
- **GitHub token:** revoke the fine-grained PAT in GitHub settings; issue a new one scoped to
  the repo allowlist.
- **Gmail OAuth client/token:** revoke in Google Cloud console; re-issue.
- **Calendar iCal feed URL:** reset/regenerate the private feed URL in the calendar provider
  (the old URL is a bearer secret).
- **Device-token pepper / device tokens:** rotate the pepper and revoke/re-register device
  tokens.

## 2. Remove it from git history

```bash
# Using git-filter-repo (preferred) — example for a file:
git filter-repo --path path/to/leaked --invert-paths
# or BFG for a specific string/file. Then:
git push --force --all
git push --force --tags
```

Force-push **after** rotation, so the now-dead value is what gets scrubbed.

## 3. Invalidate derived state

- Expire all active sessions / re-issue session tokens.
- Re-register the phone's device token if the device-token pepper changed.

## 4. Audit & prevent recurrence

- Check the provider's access logs for misuse during the exposure window.
- Add a `gitleaks` rule for the leaked pattern in `.gitleaks.toml`.
- Confirm pre-commit is installed locally (`pre-commit install`) so it can't recur.
- Note the incident (date, what, remediation) in your private ops log (not committed).
