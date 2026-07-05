# InspectorQ — demo script & sales run

## The 90-second jury demo

Stage: cardboard ramp with a taped "inspection zone", camera on a small mount, Atech
stack-light standing next to it, bin below the servo paddle. WebUI dashboard on the laptop
screen facing the judges. Pick a demo product that fails photogenically — e.g. a small
boxed product where you can crook the label, or a bottle with a cap you can leave unseated.
Bring one good unit + two pre-damaged units.

1. **(0:00) What & who:** "This is InspectorQ — a €60 quality-inspection cell for small
   manufacturers. Industrial vision inspection starts at ten thousand euros; most small
   factories just use eyeballs. This is for them."
2. **(0:15) Good part:** place good unit, press button → *green light, chirp,* TFT: "PASS —
   no defects found." Point at the dashboard counter.
3. **(0:30) Bad part:** place damaged unit → *red light, buzz,* TFT: "FAIL — label crooked"
   → **servo flicks it into the bin.** Pause. Let it land.
4. **(0:45) The kicker — teach it live:** "There's no trained model in here. Watch." Ask a
   judge for any object — their badge, a marker. Hold button 2 s → golden-sample flash →
   PASS it → then bend/cover part of it → FAIL with a spoken reason. "Reconfiguring this
   for a new product line is editing one sentence of English."
5. **(1:15) Close:** "Runs on an Arduino UNO Q + Atech modules. Cloud model today,
   drop-in on-device model for offline lines. We showed it to <company> this afternoon —
   here's their letter of intent." *(if the sales run worked — see below)*

**Rules:** never show code unless asked. Never mention what didn't work. If the servo
misbehaves, unplug it and demo stack-light only — the verdict+reason is the product,
the flick is theater.

## Failure-proofing the demo

- Phone hotspot pre-paired as WiFi fallback; test the switchover once.
- Rehearse with the actual lighting at the demo spot; re-shoot the golden sample there.
- Freeze code by 17:00. After that, only rehearsal.
- Keep a `failures/` gallery from the whole day on the dashboard — "it inspected 60 parts
  today, caught these 9" is quiet proof of *does it work*.

## The sales run (15:30–17:00) — this is worth as much as the build

The organizers said it outright: **a sale is the biggest bonus; next best is traction and
an LOI.** Budget 90 minutes for this like it's a build phase.

1. **Film the 30-s clip** (good part → green, bad part → red + flick, teach-a-new-object).
   Post it (X/LinkedIn) tagged with the hackathon + Arduino + MagasinX. Ask teammates/
   organizers to reshare. Screenshots of engagement = traction evidence for the jury.
2. **Walk the floor.** MagasinX residents build robots, drones, hardware — every one of
   them has incoming-parts QC and end-of-line checks. Also catch people on the venue tours.
   Pitch: *"Do you visually check parts today? Could I show you 60 seconds?"* → run the
   teach-it-live moment on THEIR part → ask: **"If this were a product, would you sign a
   letter of intent to pilot it?"**
3. **LOI template — have 3 printed copies:**

   > **Letter of Intent — non-binding.** <Company> has seen a working demonstration of
   > InspectorQ, an AI visual quality-inspection cell, on <date> at MagasinX, and is
   > interested in piloting it for <use case> when available.
   > Name / Company / Role / Signature / Contact email

4. **The actual-sale play:** offer the demo unit itself — "€100, as-is, I'll help you set
   it up next week." One taker = the biggest bonus the jury can give. Even a €20 symbolic
   pre-order with a receipt via Swish counts as *a sale*.
5. **Talk to Karl / the Arduino team early** (they're on the jury *and* the floor): show
   the UNO Q + Atech integration specifically. UNO Q vision inspection is Arduino's own
   flagship story — being the team that did it *at their event, integrated with Atech,*
   is jury-relations gold. Ask them what they'd want to see in the demo.

## Q&A prep (likely jury questions)

- *"What does it cost to run?"* — VLM call ≈ €0.001–0.01 per inspection at flash-model
  pricing; on-device Edge Impulse model = €0 and <50 ms for production.
- *"Cloud on a factory floor, really?"* — Demo uses cloud for flexibility; same box runs
  offline models. Low-confidence verdicts route to a human, like every real QA line.
- *"Accuracy?"* — Today's numbers on the dashboard (N inspected / caught / false alarms).
  Honest answer: it's a pilot-grade 80% solution at 0.5% of the price.
- *"Why not just OpenCV?"* — OpenCV needs an engineer per product changeover. This
  reconfigures with a sentence of English by the line operator.
