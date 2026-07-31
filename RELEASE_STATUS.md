# Selah release status

Checkpoint: 2026-07-31 19:10:50 JST

## Complete

- Kaggle competition joined; no final competition submission created yet.
- Public Kaggle Notebook: https://www.kaggle.com/code/numaritaisei/selah-technical-evidence
- Public code repository: https://github.com/numaritaisei-commits/selah-one-moment
- YouVersion developer registration and the non-commercial Selah application are complete. A memory-only App Key check returned HTTP 200 for BSB Bible ID 3034 and `JAS.1.19`; the metadata includes title, abbreviation, copyright, and an official `www.bible.com` deep link.
- No extra fast-track publisher agreement was accepted because BSB is already available to the application through the official YouVersion API.
- Gloo Studio shows Pay As You Go with current weekly spend `$0.00` and no payment method. API Credentials still redirects to the Studio home page; the official challenge `$20` developer-credit code must be redeemed before any credential or live request is attempted.
- Notebook Version 3 official status: `COMPLETE`.
- Notebook scope: Public, Internet off, GPU off, no dataset, competition, kernel, or model sources.
- Notebook Version 3 records the hardened 37-test local evidence boundary. Official Kaggle execution logs contain the exact reviewed results `Gloo key-only contract fixtures: 7/7 passed` and `YouVersion exact-text fixtures: 4/4 passed`; no execution error or traceback was present.
- Local safety suite re-run on 2026-07-31 JST: 37/37 passed, including local HTTP, model-identity validation, session/origin controls, atomic live budget, strict enum contracts, exact-attribution fixtures, and offline no-verse behavior.
- Writeup draft: 473 whitespace-delimited words before link substitution.
- Cover: `static/selah-cover.png`, 1672×941 PNG.
- Public GitHub repository and README returned HTTP `200` without authentication; expected root, `static`, `tests`, and `notebook` inventory is present.
- High-confidence scan found no private key, known token prefix, or phone pattern. The sole email-shaped string is an explicit synthetic `example` test fixture.
- The official Gloo challenge page states that YouVersion access is free to participants with rate limits and that Gloo Studio offers `$20` credit to the first 500 participants. The account-specific flow has no payment method, but the credit has not yet been redeemed and API access remains locked.

## Hard gates before final submission

- The official participant account visibly confirms a specific Gloo model/route is covered by redeemed developer credit, with no card or billable fallback.
- BSB Bible ID 3034 and the required YouVersion display metadata are confirmed.
- One live dual-API smoke run succeeds using hidden, memory-only credentials and the fixed synthetic scenario.
- Sanitized public project link and public YouTube video are available and checked signed out.
- All placeholders in `WRITEUP_DRAFT.md` are replaced; Kaggle media, Notebook, video, and project link are attached and rechecked.

If the zero-cost dual-API proof is unavailable by 2026-08-01 02:00 JST, do not submit an offline-only claim as a valid entry.
