# V17.2 — Publish information when social audio starts

Code findings: V17.1 sent information before TTS. The playback worker skipped audio completely on motion-generation failure, regardless of the configurable fallback flag. TTS/device errors could also leave a visible answer without audible social speech. The user's exact local failure is not established without their machine logs.

Implementation:
- Bridge v3 retains formatted information in the per-turn delivery token; queues the social utterance as one audio job. It does not send the answer while generating/queuing it.
- Both audio+motion and audio-only functions call the display hook immediately AFTER sounddevice.play returns successfully. Information uses the existing speech_text_clear + speech_text packets, once per response. Physical device and render latency are outside this software guarantee.
- Motion failure defaults to audio-only playback. A motion error before audio starts can also use fallback; errors after audio has started never replay the speech.
- A display send error cannot suppress or replace already-started social audio. Audio waits to finish even if sending motion frames fails.
- Nonempty information with empty model speech receives a short presentation-only utterance. Silent finish remains a clear-only operation.
- One initial motion-buffer job is sufficient. Waiting presets still complete before the generated reply begins. Preset text remains disabled to avoid overwriting information.
- TTS/audio failures and start/completion states are recorded in assistant_full_response.delivery.json; the main thread saves final status after workers finish. Model/KB unchanged; no extra model call.

Entry point: voice_motion_runtime_v17.py. Renamed bridge v2 -> v3 and motion utility v2 -> v3; updated active imports. Unity sender remains v7.

Validation: 35 unique offline tests passed. Actual Python playback function bodies and the playback worker were exercised with mocked media dependencies; TCP framing uses socketpair. Tested motion fallback, play failure without display, deferred sending, once-only display, no replay after a post-start error, display failure while audio completes, empty social speech, and TTS failure without playback job. No paid OpenAI/ElevenLabs calls or local hardware/Unity rendering were performed.
