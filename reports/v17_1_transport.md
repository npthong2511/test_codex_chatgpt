# V17.1 — Restore compatibility with the existing Unity text receiver

Problem: V17.0 emitted `information_panel`, while the existing client displays `speech_text`. Sending the new packet alone does not update a client without that handler.

Changes:
- Rename the bridge to `agent17/voice_bridge_v2.py` and TCP sender to `unity_tcp_sender_v7.py`.
- Format information title, sections and choices into plain text. Send `speech_text_clear` then `speech_text` before TTS jobs are queued. Keep social speech audio-only.
- Use `speech_text_clear` on detected departure; an empty information response clears without sending blank text.
- Update main / motion utility / test imports. Keep main entry point `voice_motion_runtime_v17.py`; config release is 17.1.
- Disable preset text by default to prevent greeting/waiting text overwriting the new information on the same UI surface. Preserve preset audio/motion.
- Mark the display-send event and write delivery status beside each turn's response; log send success/failure without claiming Unity render acknowledgement.

Validation: 21 offline tests passed. The suite exercises actual socket framing via socketpair and a simulated legacy append/clear client, plus source-level main wiring checks. No paid API calls, actual Unity client rendering or hardware audio/motion tests were performed for this update. Existing model, KB and historical API reports were preserved.
