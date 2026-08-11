# Source Footage Shoot — Checklist and Consent

The shoot is a bigger blocker than it looks: ten V2V clips to spec plus the
Anchor-R references is a controlled half-day minimum, and two things must be
settled **before anyone films**.

## 1. Consent — signed before the shoot, not after

Faces sent through six vendors' inference stacks constitute biometric data
under several regimes (BIPA, GDPR Art. 9, PIPL). This surfaces at legal review
on day 5 if it isn't on paper on day 1. Every person appearing on camera signs
a release that explicitly covers, at minimum:

- [ ] Their likeness will be **transmitted to third-party AI services**,
      named where known (Decart, Xmax, Reactor, PixVerse, Shengshu, Alibaba),
      including services **operating in other jurisdictions**
- [ ] Recordings and AI-transformed derivatives will be **retained** in the
      capture library for the duration of the study and its reproduction
      appendix
- [ ] Stills or clips **may appear in a published report** (scope: internal /
      external — match the audience decision)
- [ ] Right to withdraw before publication, and the practical limits of
      withdrawal after third-party transmission
- [ ] Signature, date, printed name, contact

Template below (§4). One signed copy per person, filed with the rubric freeze.

## 2. Casting

Use a performer who can **repeat performances**. V3 (occlusion), V4 (lighting
change), and V9 (scene cut) are easier to reshoot than to salvage — treat
every stressor clip as needing take 2 and take 3 available on the day.

## 3. Shot list (plan §6.1) and technical requirements

Master format: film **above the highest product spec** on both axes so every
conform path is a downscale (conform.py refuses upscales). 4K60 recommended;
1440p60 minimum. Locked exposure and white balance except where the stressor
IS the change (V4). Tripod except V8.

**One camera setup, one framerate, all ten clips.** Mixed source framerates
would leave the conform recipe honest about itself while the inputs remain
temporally non-identical — motion cadence, shutter, frame timing — which is
precisely the confound the conform path exists to eliminate. If a clip must be
reshot later, reshoot it with the same body, lens, and framerate settings.

| ID | Clip | Reshoot-prone |
|---|---|---|
| V1 | Static face close-up, even light | |
| V2 | Fast head/body motion | ✱ |
| V3 | Hand occluding face, then removed | ✱✱ |
| V4 | Hard lighting change mid-clip | ✱✱ |
| V5 | Performer exits frame fully (~3 s empty scene), then re-enters | ✱ |
| V6 | Fine texture — hair, mesh fabric | |
| V7 | Printed text / logo held to camera | |
| V8 | Rapid horizontal pan | ✱ |
| V9 | Hard scene cut | ✱✱ |
| V10 | 60 s sustained single take — the differentiator | ✱ |

**V5 amendment (2026-08-11):** original spec was "second person enters
frame"; no second consenting performer is available. Replaced with a FULL
exit/re-entry (the harder E.5 stressor: total subject loss and re-lock, vs
V3's partial occlusion). Consequence stated for the report: multi-person
identity separation is UNTESTED in this corpus. If a second performer
becomes available later, shoot the original V5 as an additional clip with
the same camera/settings and log it as a corpus addition.

**10 clips, ~15 s each (V10 = 60 s+).** Corpus reverted from the 25-clip
variant (user decision 2026-08-10): one take per stressor, with on-the-day
retakes for the ✱✱ clips. Note the known limitation for the report: several
rubric dimensions rest on a single clip (temporal coherence on V10,
occlusion on V3) — state this in methodology rather than hiding it.

Anchor-R (digital human): the same performer reading scripts S1–S4 on camera,
same framing as the avatar products' output; this is the "real filmed
reference" every computed metric is anchored against, for every category that
has a face.

### The scripts (read calmly, newsreader pace, ~30-45 s each; audio ON)

**S1 — Mandarin, plosive-dense** (b/p/m closures drive the lip-sync metric):

> 白伯伯背着帆布背包,慢慢爬上北坡的木板棚。棚边摆着八个白瓷盘,
> 盘里放满饱满的苹果和半盆枇杷。他拍拍口袋,掏出笔记本,把每笔买卖
> 都标明白:苹果八块八,枇杷比苹果便宜半块。傍晚,泡一杯薄荷茶,
> 配一块牛奶面包,静看北边薄雾漫过山坡。

**S2 — English, plosive-dense:**

> "Peter packed a big brown box of paper maps beside the bakery's back
> door. Bob picked up both bundles, bumped past the pump, and put them
> by the mailbox. A bright morning breeze pushed the paper about, so
> Peter pinned each map down with a pebble, then paused to sip a cup of
> bitter black coffee before beginning the uphill climb back."

**S3 — Mandarin, natural conversational baseline:**

> 今天想跟大家聊一聊我们最近在做的一件事。其实一开始没有想到会这么
> 复杂,后来慢慢发现,每一个环节都需要认真对待。有些问题看起来很小,
> 真正解决的时候才知道背后牵扯很多。不过整体来说进展还算顺利,希望
> 接下来的每一步都能走得更稳一些。

**S4 — alphanumeric and precise articulation (mixed):**

> "Order number 7-0-4-2-9, shipping on August 15th at 9:40 a.m., total
> 386 dollars. 订单号七零四二九,八月十五日上午九点四十发货,合计
> 三百八十六元。Confirmation code: B as in Bravo, P as in Papa, M as in
> Mike, 2-2-8."

Rules for the readings: head-and-shoulders newsreader framing, look at the
lens, clean audio (quiet room, no fan hum), keep the mouth unobstructed,
normal pace with natural pauses. One clean take each; redo only if you
stumble hard or something bangs off-camera.

Pipeline order (so nobody burns flashes on set): **shoot raw → conform to
master → `render_reel` adds flashes + block strip and writes the ground-truth
sidecar → conform per product**. The impulse flashes are added in the
instrumentation pass; the camera never needs to see them.

## 4. Consent form template

> **Recording and AI-Processing Release**
>
> I, ______________________, consent to being filmed on ____________ for a
> comparative evaluation of video AI products.
>
> I understand and agree that: (1) recordings of my likeness and voice will be
> transmitted to third-party AI services for processing, including services
> operated outside my country of residence; (2) the recordings and
> AI-generated derivatives of them will be retained in an evaluation archive;
> (3) excerpts and stills, including AI-transformed versions of my likeness,
> may appear in the resulting report and its appendices; (4) I may withdraw
> consent for future use at any time before publication by written notice,
> and I understand that copies already transmitted to third-party services
> may not be retrievable.
>
> Signature: ____________  Date: ____________  Contact: ____________

*This is a working template, not legal advice — have it reviewed alongside the
ToS/publication review already in Phase 0.*
