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
| V5 | Second person enters frame (consent for both!) | ✱ |
| V6 | Fine texture — hair, mesh fabric | |
| V7 | Printed text / logo held to camera | |
| V8 | Rapid horizontal pan | ✱ |
| V9 | Hard scene cut | ✱✱ |
| V10 | 60 s sustained single take | ✱ (fatigue) |

Anchor-R (digital human): the same performer reading scripts S1–S4 on camera,
same framing as the avatar products' output; this is the "real filmed
reference" every computed metric is anchored against, for every category that
has a face.

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
