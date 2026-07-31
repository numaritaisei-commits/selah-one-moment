# Selah — one moment before send

## Inspiration

One post can outlive one emotion. Most safety tools act after harm—or decide what a person may say. Selah enters at a more human moment: the instant before an angry reply becomes irreversible. It is inspired by the recurring Scriptural word *Selah*, without claiming a single settled translation of that word.

## What it does

Selah is a local working prototype that offers an optional eight-second pause; it does not connect to or post on a social network. It never censors, rewrites, or posts for the user. The original draft remains visible. The user names what matters most—being understood, protecting the relationship, or being accurate—then chooses whether to continue, edit, or keep the original.

The intervention is intentionally small. It is not a generic verse recommender. It brings a relevant Scriptural perspective into the exact decision where tone can change a conversation, while preserving the author’s agency.

## How we built it

The browser sends a synthetic draft and intent to a local, dependency-free Python backend. Gloo AI may return only two fields: one opaque `passage_key` from a server-side allowlist and one brief reflection question. Strict parsing rejects duplicate keys, extra fields, non-finite values, multiple choices, incomplete output, and any reference outside the allowlist.

The validated key maps to a fixed USFM reference. YouVersion then provides the exact passage text, human-readable reference, Bible version metadata, link, and copyright. Selah never asks a language model to quote, paraphrase, or invent a verse. If attribution is incomplete or the returned passage ID does not match the request, nothing is displayed.

The live adapter uses fixed HTTPS hosts and paths, refuses redirects, caps request and response sizes, and keeps credentials and OAuth tokens in process memory. The app does not write drafts or provider content to disk. This is an application boundary; provider handling remains governed by provider terms. For the demo, we use synthetic text only.

## Reliability and evidence

The 33-test standard-library safety suite covers strict JSON parsing, passage and question allowlisting, fixed synthetic live input, origin/session checks, atomic request budgets, the local HTTP flow, no-verse offline behavior, token reuse in memory, exact YouVersion attribution flow, and frontend non-persistence checks. Provider failure is fail-open: the optional pause ends, the untouched draft remains, and normal posting is still available. This count is adapter evidence, not a claim of real-world impact.

## Vision

Selah can become a voluntary layer for community replies, creator tools, and group chats. A future field test would measure voluntary activation, pause completion, and pre-send editing rates; it would not claim reduced harm without an appropriate study. Selah does not speak for you. It gives you one moment to choose who you want to be before you speak.

**Code:** https://github.com/numaritaisei-commits/selah-one-moment

**Notebook:** https://www.kaggle.com/code/numaritaisei/selah-technical-evidence

**Video:** PUBLIC_YOUTUBE_URL
