# Selah — one moment before send

## Inspiration

One post can outlive one emotion. Selah targets the eight seconds before an angry reply is sent: a moment when the author can still choose what happens next. It is inspired by the recurring Scriptural word *Selah*, without claiming a single settled translation of that word.

## What it does

Selah is a local prototype with a gated live adapter. It offers an optional eight-second pause and does not connect to or post on a social network. It never censors, rewrites, or posts for the user. The original draft remains visible. The author names what matters most—being understood, protecting the relationship, or being accurate—then chooses whether to continue, edit, or keep the original.

The intervention is intentionally small. It is not a generic verse recommender. It offers an allowlisted Scriptural perspective at the decision point while preserving the author’s agency.

## How we built it

The browser sends a fixed synthetic draft and intent to a dependency-free local Python backend. Gloo AI may return exactly two opaque enum keys—`passage_key` and `question_key`—from server-side allowlists. Its output is never shown directly. The server maps the keys to a fixed USFM reference and a prewritten reflection question. Strict parsing rejects malformed output, model mismatch, automatic routing, and anything outside those allowlists.

YouVersion then provides the exact passage text, human-readable reference, Bible version metadata, link, and copyright. Gloo supplies bounded contextual selection; YouVersion is the sole source of displayed Scripture text and attribution. Selah never asks a language model to quote, paraphrase, or invent a verse. If attribution is incomplete or the returned passage ID does not match the request, nothing is displayed.

The live adapter fixes provider hosts and paths, refuses redirects, bounds network data, and keeps credentials in process memory. The app writes no draft or provider content to disk; provider handling remains governed by provider terms. The public Notebook uses synthetic fixtures only. Live-provider evidence will be claimed only after a zero-cost dual-API run passes entitlement and Bible-license gates.

## Reliability and evidence

All 37 local tests passed. The public Notebook separately reproduces 7/7 Gloo-contract fixtures and 4/4 YouVersion exact-text and attribution fixtures. Tests cover the allowlists, model identity, fixed synthetic input, origin/session controls, one-request budgets, offline no-verse behavior, exact attribution, and frontend non-persistence. Provider failure is fail-open: no provider result blocks or changes the draft. These are adapter results, not evidence of provider uptime or real-world impact.

## Vision

Selah can become a voluntary layer for community replies, creator tools, and group chats. A future field test would measure voluntary activation, pause completion, and pre-send editing rates; it would not claim reduced harm without an appropriate study. Selah does not speak for you. It gives you one moment to choose who you want to be before you speak.

**Code:** https://github.com/numaritaisei-commits/selah-one-moment

**Notebook:** https://www.kaggle.com/code/numaritaisei/selah-technical-evidence

**Video:** PUBLIC_YOUTUBE_URL
