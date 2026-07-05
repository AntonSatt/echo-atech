# InspectorQ — VLM prompts (OpenRouter)

The whole product is "QA inspection configured by a prompt instead of a trained model."
These prompts ARE the product. Keep them versioned here; the demo pitch literally shows
editing this file to reconfigure the inspection cell.

## API call shape

`POST https://openrouter.ai/api/v1/chat/completions` with the frame as a base64 data-URL
image part. Ask for JSON only. Downscale frames to ~512–768 px on the long edge before
sending (faster upload, cheaper, plenty for defects).

Force JSON with `response_format: {"type": "json_object"}` (supported by most OpenRouter
models); still parse defensively (strip code fences, retry once on bad JSON).

## Model shortlist (pick by speed on the day)

| Priority | Model (OpenRouter id) | Why |
|---|---|---|
| 1st | `google/gemini-2.5-flash` | fast, cheap, strong vision — likely the demo default |
| 2nd | `anthropic/claude-haiku-4.5` | fast, good instruction-following for strict JSON |
| 3rd | `openai/gpt-4o-mini` | reliable fallback |
| Quality ref | `anthropic/claude-sonnet-5` / `openai/gpt-4o` | if flash models misjudge defects, trade speed for accuracy |

Benchmark all of them in phase 1 with 3 test photos; hardcode the winner, keep the list as
runtime fallbacks (OpenRouter also supports the `models: [...]` fallback array — use it).

## System prompt — generic inspection (v1, demo default)

```
You are InspectorQ, an automated visual quality-control inspector on a factory line.
You will be shown one photo of a single product in the inspection zone.

Decide if the product passes visual quality control. FAIL it for defects such as:
damage, cracks, dents, scratches, missing or crooked labels, missing parts, wrong
color, loose or unseated caps/connectors, dirt or contamination, deformation.

Judge only what is clearly visible. Minor lighting variation, shadows, or camera
angle are NOT defects. If no product is visible in the inspection zone, verdict
is "EMPTY".

Respond with ONLY this JSON, no other text:
{"verdict": "PASS" | "FAIL" | "EMPTY",
 "reason": "<max 8 words, plain language, names the defect or says 'no defects found'>",
 "confidence": <0.0-1.0>}
```

User message per frame: `Inspect this product.` + image.

**The `reason` string is what shows on the Atech TFT and gets spoken/displayed — the
8-word cap is load-bearing (TFT is small).**

## System prompt — golden-sample comparison (v2, the upgrade)

Stronger and the better *sales* story: "show it one good part, it inspects against that."
Send TWO images: reference first, candidate second.

```
You are InspectorQ, an automated visual quality-control inspector.

Image 1 is the GOLDEN SAMPLE: a verified good unit of the product.
Image 2 is the CANDIDATE currently in the inspection zone.

Compare the candidate to the golden sample. FAIL the candidate for any meaningful
deviation: damage, missing/extra/misplaced components, label differences, color
mismatch, deformation, contamination. Ignore differences in lighting, shadows,
background, exact position and rotation.

Respond with ONLY this JSON, no other text:
{"verdict": "PASS" | "FAIL" | "EMPTY",
 "reason": "<max 8 words: the deviation, or 'matches golden sample'>",
 "confidence": <0.0-1.0>}
```

Workflow: press-and-hold the Atech button 2 s → current frame saved as golden sample →
NeoPixel flashes white to confirm. This makes the demo interactive: a judge can hand us
ANY object, we "teach" it in one press, then damage/occlude it and watch it FAIL.
**This is the money moment of the demo.**

## Product-specific override (v3, for the LOI conversation)

When pitching a resident company, duplicate v1 and replace the defect list with THEIR
product's failure modes, live, in front of them, in 60 seconds. Template:

```
The product is: <THEIR PRODUCT>.
FAIL it specifically for: <their top 3-5 defect types>.
Additionally apply general visual defect checks.
<same JSON contract as v1>
```

## Verdict handling rules (main.py contract)

- `PASS` → green + chirp + counter++
- `FAIL` → red + buzz + reason on TFT + save frame to `failures/` + servo `reject()` + counter++
- `EMPTY` → idle blue "watching" state, no counters
- `confidence < 0.6` → treat as FAIL for the reject arm but tag "CHECK" amber on the TFT
  (real QA lines route low-confidence to a human — say this to the judges, it lands)
- API error/timeout (>8 s) → amber blink + retry once → then "OFFLINE" state. Never crash the loop.
