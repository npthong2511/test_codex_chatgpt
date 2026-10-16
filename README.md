# Citizen Agent V17.1 — Unity compatible text display

V17.1 sends the information section through the existing Unity `speech_text` protocol. Social speech goes only to TTS; procedure information and question options go only to the screen. The conversation model and source data are unchanged from V17.

## Files to run

- Text console: `python chat.py`
- Microphone / TTS / avatar: `python voice_motion_runtime_v17.py`

The main filename stays `voice_motion_runtime_v17.py`. `config.json` identifies release 17.1.

Renamed modules and all active imports:

- `agent17/voice_bridge.py` → `agent17/voice_bridge_v2.py`
- `unity_tcp_sender_v6.py` → `unity_tcp_sender_v7.py`
- Main runtime, `motion_pipeline_utils_v2.py` and tests import the new filenames.

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

## Unity packets in V17.1

UTF-8 JSON, one JSON object per line. The sender clears the previous text, then sends one formatted text message:

```json
{"type":"speech_text_clear"}
{"type":"speech_text","job_id":1,"text":"Hồ sơ cần chuẩn bị\n\nGiấy tờ\n- Tờ khai\n- Giấy tờ theo trường hợp"}
```

The plain text contains the title, section headings, bullet items and A/B/C options. No internal node IDs are included. `job_id` is the response revision. No `information_panel` handler is needed for these V17.1 responses.

Only `response['information']` is formatted and sent to Unity. Only `response['speech_text']` enters the TTS/motion pipeline; naming the display packet `speech_text` does not synthesize its contents. Generated audio playback does not send social text to the display.

Empty information (e.g. finish) clears the display without sending a blank text item. Detected departure sends `speech_text_clear`. Preset greeting/waiting speech text is disabled by default so it cannot overwrite the information on the shared display; preset audio/motion still works. Generated information stays visible after audio ends with the default configuration.

The existing client must already handle `speech_text` and `speech_text_clear`. Clickable choices are not implemented; citizens answer option letters or labels through speech. TCP send success is not a Unity render acknowledgement.

## Diagnostics

Terminal:

```text
[UNITY TEXT] Sent revision=1 turn=... chars=...
```

This confirms the send operation, not rendering. Send errors log the exception type and use an audio error message. Each turn's transcript folder contains:

- `assistant_full_response.v17.json`: model response, including information.
- `assistant_full_response.delivery.json`: revision, send status / error and displayed character count.

## Validation and historical reports

```powershell
python -m unittest discover -s tests -v
```

V17.1: 21 offline tests passed, including socketpair UTF-8 framing, legacy clear/text packets, question formatting, replacement across turns, departure clearing, finish clearing, cancellation, send failure and information/audio separation. No paid API calls were needed for this transport change. Actual Unity rendering, microphones, cameras, ElevenLabs and motion execution were not run in the cloud.

`reports/Bao_cao.md` and `reports/Hoi_thoai.html` retain historical V17 model API results. References there to `information_panel` describe V17.0, not the current V17.1 transport. `reports/v17_1_transport.md` records this update.

The model-only core still uses bounded local windows, correction history and confirmed procedure switching. No new legal/semantic output validator was added.
