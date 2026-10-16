# Citizen Agent V17.2 — Unity compatible text display

V17.2 sends the information section through the existing Unity `speech_text` protocol. Social speech goes only to TTS; procedure information and question options go only to the screen. The conversation model and source data are unchanged from V17.

## Files to run

- Text console: `python chat.py`
- Microphone / TTS / avatar: `python voice_motion_runtime_v17.py`

The main filename stays `voice_motion_runtime_v17.py`. `config.json` identifies release 17.2.

Renamed modules and all active imports:

- `agent17/voice_bridge_v2.py` → `agent17/voice_bridge_v3.py`
- `motion_pipeline_utils_v2.py` → `motion_pipeline_utils_v3.py`
- `agent17/playback.py`: coordinates playback, fallback and start notification
- `unity_tcp_sender_v6.py` → `unity_tcp_sender_v7.py`
- Main runtime, `motion_pipeline_utils_v3.py` and tests import the new filenames.

Use the complete release folder. When migrating, copy your existing model/scaler assets and preset assets into the locations below. API keys and motion weights are not included.

## Text console

Python 3.12 and OpenAI SDK 3.31.0 were used for testing. In Windows PowerShell:

```powershell
cd "D:\Citizen_Agent_V17"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:Open_AI = "YOUR_OPENAI_KEY"
.\.venv\Scripts\python.exe chat.py
```

`chat.py` prints speech and screen content; it does not connect to Unity or synthesize speech. Type `exit` to quit. Console conversations call the OpenAI API.

## Voice / avatar

Use the existing Python environment that already runs your media/motion pipeline. `requirements.txt` installs the conversation dependency only, not all media libraries. The voice environment needs the compatible existing versions of MediaPipe (including mp.solutions), OpenCV, NumPy, pandas, sounddevice, soundfile, librosa, PyTorch and ElevenLabs.

Place assets relative to the main Python file:

```text
models/
  outputs_transformer_local_window/
    best_model.pt
    audio_scaler.pkl
    y_scaler.pkl
  outputs_lip_mlp_local_window/
    best_model.pt
    audio_scaler.pkl
    y_scaler.pkl
out_audio/preset_audios/
  greeting_audios/
  waiting_audios/
```

Each preset WAV must have a matching `.motion.csv`. The preset directories may be empty. Set `Open_AI` and `ELEVENLABS_API_KEY`, or use `openai_keys.txt` / `elevenlabs_keys.txt` beside the main file. The text console specifically reads `Open_AI` from the environment. Check `TTS_VOICE_ID` in the main file against the desired ElevenLabs voice.

Run Python, then start the Unity TCP client on `127.0.0.1:5005`. Python logs `Waiting Unity connection` until the client connects. Default camera index is 0. Ctrl+C stops the runtime.

## Unity packets in V17.2

UTF-8 JSON, one JSON object per line. Immediately after `sd.play` succeeds for social audio, the playback callback clears the previous text, then sends one formatted text message:

```json
{"type":"speech_text_clear"}
{"type":"speech_text","job_id":1,"text":"Hồ sơ cần chuẩn bị\n\nGiấy tờ\n- Tờ khai\n- Giấy tờ theo trường hợp"}
```

The plain text contains the title, section headings, bullet items and A/B/C options. No internal node IDs are included. `job_id` is the response revision. No `information_panel` handler is needed for these V17.2 responses.

The bridge prepares `response['information']` but does not send it during generation or TTS. It is published once at audio playback start. Only `response['speech_text']` enters the TTS/motion pipeline; naming the display packet `speech_text` does not synthesize its contents. Generated audio playback does not send social text to the display.

A silent finish clears the display without audio. Other replies queue one short social utterance as one WAV; if the model leaves social text empty while providing information, a short presentation-only phrase is used. Detected departure sends `speech_text_clear`. Preset greeting/waiting speech text is disabled by default so it cannot overwrite the information on the shared display; preset audio/motion still works. Generated information stays visible after audio ends with the default configuration.

The existing client must already handle `speech_text` and `speech_text_clear`. Clickable choices are not implemented; citizens answer option letters or labels through speech. TCP send success is not a Unity render acknowledgement.

## Diagnostics

Terminal:

```text
[UNITY TEXT] Sent revision=1 turn=... chars=...
```

Normally `[AUDIO START]` appears immediately before `[UNITY TEXT]`. This confirms successful software playback start and TCP send, not physical speaker output or Unity rendering. Send errors log the exception type and use an audio error message. Each turn's transcript folder contains:

- `assistant_full_response.v17.json`: model response, including information.
- `assistant_full_response.delivery.json`: revision, TTS readiness/error, audio start/completion/error, audio-only fallback, display send status and character count. The final status is saved after pipeline workers finish.

## Validation and historical reports

```powershell
python -m unittest discover -s tests -v
```

V17.2: 35 offline tests passed. Tests include actual playback function bodies with mocked audio devices, the actual playback worker on motion failure, socketpair display packets, delayed publishing, single-WAV social speech, missing social text, TTS failure, audio-device failure, and not replaying already-started speech. No paid API calls were made for this change. Actual hardware output and Unity rendering were not exercised in the cloud.

Motion generation failure no longer suppresses social speech by default (`play_audio_even_if_motion_failed=True`). The avatar can remain still while the audio plays. The initial readiness buffer is one job. Successful motion still accompanies normal playback. If TTS fails or the audio device cannot start, the new information is not published; inspect `tts_error` / `playback_error` and terminal logs. This release does not fix invalid ElevenLabs credentials, missing local assets, or a muted/incorrect output device.

`reports/Bao_cao.md` and `reports/Hoi_thoai.html` retain historical V17 model API results. References there to `information_panel` describe V17.0, not the current V17.2 transport. `reports/v17_1_transport.md` is the previous transport update; `reports/v17_2_playback.md` records current synchronization changes.

The model-only core still uses bounded local windows, correction history and confirmed procedure switching. No new legal/semantic output validator was added.
