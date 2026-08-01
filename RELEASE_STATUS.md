# Selah release status

Checkpoint: 2026-08-01 08:55 JST

## Reopened zero-cost activation check

- The user explicitly reopened the card-free support path after the earlier
  02:00 cutoff. The official challenge promo was recovered from the exact
  organizer email without displaying or storing its value.
- Historical official records show the challenge promo as redeemed successfully,
  while a fresh redemption attempt on the official Gloo Studio Billing page
  returned `Organization must complete onboarding before redeeming promo codes`.
  The inactive organization still exposes no usable credit or API access.
- The organization exists but is currently shown as inactive. Weekly spend is
  still `$0.00`, and no payment method was added.
- A bounded reply was sent in the existing official support thread requesting
  card-free onboarding activation. It included neither the promo value nor any
  credential and expressly declined paid usage.
- A deadline-critical follow-up asked official support to confirm promo-first
  charging, a USD 20-or-lower hard spend cap, zero paid overage, and no card
  authorization/minimum/immediate charge. No reply has arrived yet.
- Gloo's official developer page led to the official Developer Network on
  Discord, but membership is still pending review, so no Discord message could
  be posted. No account details or promo value were disclosed.
- Official billing documentation confirms that a configured weekly limit stops
  later API access and can be set before credentials/calls, but does not prove
  that USD 20 or less is accepted, that promo credit is consumed first, that a
  single request cannot overrun the limit, or that adding a card has no
  authorization/minimum charge. Card registration therefore remains blocked.
- This branch remains non-submittable until a real Gloo API call succeeds under
  a card-free, non-billable account. No fixture-only demo or API claim is
  permitted.

## Complete

- Kaggle competition joined; no final competition submission created yet.
- Public Kaggle Notebook: https://www.kaggle.com/code/numaritaisei/selah-technical-evidence
- Public code repository: https://github.com/numaritaisei-commits/selah-one-moment
- YouVersion developer registration and the non-commercial Selah application are complete. A memory-only App Key check returned HTTP 200 for BSB Bible ID 3034 and `JAS.1.19`; the metadata includes title, abbreviation, copyright, and an official `www.bible.com` deep link.
- No extra fast-track publisher agreement was accepted because BSB is already available to the application through the official YouVersion API.
- Gloo Studio shows Pay As You Go with current weekly spend `$0.00` and no payment method. A fresh official Billing check did not confirm usable credit: redemption is blocked by incomplete organization onboarding, and API access remains inactive. One explicit card-free activation request is pending with official support.
- Notebook Version 3 retained stale subtotals (`33`) after four tests were added. Version 4 fixed the total but grouped two tests semantically rather than by their actual unittest class. Version 5 now reports the exact class inventory: Live Adapter `9`, Static Safety `6`, and Total `37`.
- Notebook Version 5 official status is `COMPLETE`; its pulled latest source matches the local cell-source hash, and its metadata remains Public, Internet off, GPU off, with no dataset, competition, kernel, or model sources.
- Version 5 is a markdown-only precision correction and does not alter the reviewed executable fixture cells.
- Local safety suite re-run on 2026-08-01 JST: 37/37 passed, including local HTTP, model-identity validation, session/origin controls, atomic live budget, strict enum contracts, exact-attribution fixtures, and offline no-verse behavior.
- Writeup draft: 473 whitespace-delimited words before link substitution.
- Cover: `static/selah-cover.png`, 1672×941 PNG.
- Public GitHub repository and README returned HTTP `200` without authentication; expected root, `static`, `tests`, and `notebook` inventory is present.
- High-confidence scan found no private key, known token prefix, or phone pattern. The sole email-shaped string is an explicit synthetic `example` test fixture.
- The official Gloo challenge page states that YouVersion access is free to participants with rate limits and that Gloo Studio offers `$20` credit to the first 500 participants. The account-specific flow has no payment method and records the promo as redeemed, but the inactive organization still exposes neither usable credit nor API access.

## Earlier terminal decision (superseded by the reopened check above)

- `No-safe-candidate` as of the pre-registered `2026-08-01 02:00 JST` cutoff.
- A final bounded Gmail check found no newer organizer/support reply granting an
  official card-free sandbox, temporary challenge credential, or endpoint with
  guaranteed `$0` spend and no billable fallback. The latest inbound position
  remains that payment-method bypass and exceptions are unavailable.
- No live Gloo API proof was fabricated, no card or payment method was added,
  and no fixture-only YouTube video or Kaggle final submission was created.
- The existing public repository and public technical-evidence Notebook remain
  unchanged; they are not represented as a completed dual-API competition
  entry. The earlier no-more-support restriction was superseded by the user's
  later explicit authorization for one card-free activation request.

## Unmet release gates

- The challenge organization is active, the promo is accepted, API Credentials is available, and the selected Gloo model/route remains covered by developer credit with no card or billable fallback.
- BSB Bible ID 3034 and the required YouVersion display metadata are confirmed.
- One live dual-API smoke run succeeds using hidden, memory-only credentials and the fixed synthetic scenario.
- Sanitized public project link and public YouTube video are available and checked signed out.
- All placeholders in `WRITEUP_DRAFT.md` are replaced; Kaggle media, Notebook, video, and project link are attached and rechecked.
- Corrected public Notebook Version 5 is `COMPLETE` and its rendered 37-test table matches the verified local inventory. (Satisfied.)

If the zero-cost dual-API proof cannot be captured, validated, published, and attached with a safe buffer before the 2026-08-01 13:59 JST deadline, do not submit an offline-only claim as a valid dual-API entry.
