# Security and privacy boundaries

## Secrets

Live credentials are accepted only through hidden terminal prompts and retained only in process memory. They are never accepted by the browser, written to a file, included in a URL, printed, or returned to the frontend. The server binds only to `127.0.0.1`.

If a credential appears in a screenshot, repository, notebook, terminal transcript, or recording, revoke it immediately and do not publish that artifact.

## Data flow

Use synthetic text only. In live mode the draft is sent to Gloo AI so it can select an opaque allowlisted passage key and return one reflection question. The selected key is mapped on the server to a fixed USFM reference. YouVersion receives only the fixed Bible ID and USFM reference, not the draft.

The application does not persist drafts, provider bodies, scripture text, tokens, or credentials. This is an application boundary, not a claim about provider-side retention. Provider processing is governed by Gloo and YouVersion terms.

## Fail-closed and fail-open

Provider data fails closed: redirects, non-JSON responses, duplicate JSON keys, non-finite numbers, oversized bodies, multiple choices, incomplete generations, unknown passage keys, missing YouVersion attribution, and unexpected passage IDs are rejected.

The user experience fails open: if the optional pause cannot complete, the draft remains locally editable and the application does not block normal posting.

## Network allowlist

Live mode can contact only the fixed HTTPS hosts and paths listed in the README. It does not follow redirects, accept arbitrary URLs, use cookies, call tools/functions, or download code, models, wheels, or binaries.

## Reporting

Do not include credentials, raw requests, draft text, or provider response bodies in a report. Report only the affected component, safe reproduction conditions, and expected behavior.
