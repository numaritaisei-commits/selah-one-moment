# Final public video build — fail-closed handoff

This path turns **one real, sanitized, uninterrupted dual-API screen recording**
into the 2:45 public candidate. It never calls Gloo, YouVersion, YouTube, or any
other network service. It uses only the checked-in cards, captions, fallback
voiceover, and macOS system frameworks.

The fixture-only MP4 is not an input and must never be uploaded. The final
builder has no placeholder mode.

## 1. Capture contract

Only record after a real zero-cost Gloo + YouVersion request has succeeded and
the selected YouVersion Bible is licensed to this app.

Create a fresh, silent `1280×720` recording lasting `98–102` seconds:

- Record only the local Selah app viewport. No browser chrome, address bar,
  terminal, provider portal, menu bar, notifications, account name, email,
  face, voice, request, header, key, token, or credential may enter a frame.
- Disable microphone and system audio. The builder refuses an audio track.
- Use only the fixed fictional draft and the synthetic rewrite in
  `VIDEO_NARRATION.md`; never type real names or personal text.
- Start at the untouched fictional composer. Match the `0:00–1:38` shot timing
  in `VIDEO_NARRATION.md`.
- Keep `0:42–1:15` as one uncut interaction. The
  `LIVE · GLOO + YOUVERSION` badge stays visible; by about `1:10`, hold the real
  card long enough to read its exact passage reference, version title and
  abbreviation, YouVersion link, and full copyright.
- Continue the same capture through the manually authored fictional rewrite.
  Do not show an AI rewrite, auto-post, score, or impact claim.

Save the private input as `video_assets/selah-private-live-capture.mov`. `.gitignore`
keeps MOV and MP4 media out of Git; still inspect `git status` before any push.

## 2. Capture preflight

From the repository root:

```sh
/usr/bin/swift -suppress-warnings video_assets/verify_final_video.swift --capture \
  video_assets/selah-private-live-capture.mov
```

This checks the single silent 1280×720 track, duration, sampled OCR, synthetic
opening, continuously visible live badge, attribution-link text, draft markers,
and common PII/credential patterns. OCR is only a backstop: watch all 98 seconds
and confirm the exact passage reference, Bible version, copyright, and live
badge yourself. Stop if any text is unreadable or if any account/browser/terminal
pixel appears.

## 3. Deterministic assembly

```sh
/usr/bin/swift -suppress-warnings video_assets/build_final_video.swift \
  video_assets/selah-private-live-capture.mov \
  video_assets/selah-final-public.mp4
```

The builder refuses overwrite, symlinks, non-1280×720 capture, capture audio,
wrong duration, recognized fixture/placeholder frames, malformed captions, or
the obsolete `33 / 33` claim. It uses:

- `0:00–1:38`: first 98 seconds of the one real capture, uncut;
- `1:38–2:08`: reviewed architecture card;
- `2:08–2:31`: reviewed `37/37` evidence card;
- `2:31–2:45`: reviewed end card;
- all 13 captions burned into a dedicated band that cannot cover source text;
- the checked-in synthetic voiceover, pitch-preservingly stretched to 2:45.

The result is a new 165-second 1280×720 H.264/AAC MP4 with no copied metadata.

## 4. Final automated and manual gate

```sh
/usr/bin/swift -suppress-warnings video_assets/verify_final_video.swift --final \
  video_assets/selah-private-live-capture.mov \
  video_assets/selah-final-public.mp4

/usr/bin/mdls -name kMDItemDurationSeconds -name kMDItemCodecs \
  -name kMDItemPixelWidth -name kMDItemPixelHeight \
  video_assets/selah-final-public.mp4
/usr/bin/afinfo video_assets/selah-final-public.mp4
/usr/bin/afclip video_assets/selah-final-public.mp4
/usr/bin/shasum -a 256 video_assets/selah-final-public.mp4
```

Before upload, watch the complete MP4 once at normal speed and scrub it once
without skipping. Fail the candidate unless every item below is true:

- runtime is 165 seconds and never over 180; picture is 1280×720;
- voice is audible, unclipped, intelligible, and synchronized with all seven
  storyboard sections; there is no capture audio or notification sound;
- all 13 captions are readable on a phone-sized player and `37 / 37` is used;
- `0:42–1:15` is visibly one uninterrupted live run;
- live badge, exact YouVersion passage reference, version title/abbreviation,
  link, and copyright are fully readable and never covered;
- no fixture-only banner, placeholder, browser chrome, terminal, account UI,
  email, phone, face, real name, token, key, request, header, or private URL is
  visible or audible;
- architecture, evidence, and end-card claims match the public repository and
  Notebook; the app never claims measured social impact;
- the final SHA-256 is recorded before upload and the uploaded file is verified
  against that frozen candidate.

Only the MP4 that passes both automated and complete human review is eligible
for YouTube publication. Never upload the private capture or fixture draft.
