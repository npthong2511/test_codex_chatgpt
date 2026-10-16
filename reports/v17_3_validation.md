# V17.3 validation

## Offline

47 tests passed (`python -m unittest discover -s tests -v`); see v17_3_tests.txt.
Includes legacy audio/motion synchronization, direct cached page publication with an empty TTS queue, forward/back/absolute page commands, dimensions and content preservation, snapshot restore, cancellation, error preservation, topic filtering and invalidation on new answers.

## Live OpenAI smoke test

Model: gpt-5.2, reasoning none. One seven-turn conversation plus six isolated routing phrases, not a broad legal-accuracy benchmark. No ElevenLabs, microphone STT, motion model weights or Unity hardware were invoked.

- First-time ID for child age 5, mother speaking: asks topic before providing information.
- Select documents: only document requirements; two pages.
- Repeat confirmation: document response remains scoped to documents.
- “tiếp”: cached page 2/2, display_only=true, empty speech.
- “mở lại 1/2”: cached page 1/2, display_only=true, empty speech.
- Ask fees: new fee content replaces document pages.
- Correct age to 8: returns to topic selection for corrected case.
- Six independent phrases: next/back/absolute page all routed correctly; mixed next+age correction and return-to-topic-menu routed to business model.

All 7 conversation turns completed without transport_error. 19 model calls total, 32,073 input tokens and 2,929 output tokens. 12 lightweight router calls (including routing before topic changes) used 3,629 input and 228 output tokens, approximately 302 input/19 output per call. Router durations 0.96–1.56 seconds in this run; excludes STT and network/render time on the user's device.

Raw results and usage: v17_3_api_smoke.json. The run preceded a small per-turn call-budget accounting adjustment; final offline suite validates the packaged code.

## Limits and operation

40 characters × 11 lines is an estimate from the supplied image, not a pixel/font measurement. Includes page footer. Unity proportional font, line spacing and automatic wrapping must be checked locally; adjust display_columns/display_rows in config.json if necessary.

Every page navigation goes through the model. Cached text is sent immediately after the navigation decision with no TTS/motion jobs. Existing waiting presets are skipped on browsing turns, including turns that change topics. Initial topic answers retain audio-start synchronized text. STT is still needed for microphone input. At last page, “next” goes to pending topics or topic selection and may produce a new social utterance.

Topic selection and correction are model decisions, with no semantic validation engine. Block-level filtering preserves conditions and untagged blocks; mixed-topic blocks remain intact. Small smoke coverage is not proof of all legal cases. Motion/Unity physical behavior was not exercised here. Keep local installation path short to avoid the known Windows CSV path-length problem; V17.3 does not change the working V17.2 motion generation code.
