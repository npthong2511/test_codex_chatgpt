# Citizen Agent V17.4 — quản lý hội thoại và STT tiếng Việt

Bản này sửa luồng nhận dạng trường hợp, giữ nhu cầu nội dung khi hỏi bổ sung/sửa dữ kiện, giữ trang khi model nhận diện câu không rõ, và phân nhóm nội dung trước khi chia trang. STT dùng `language=vi`, không đưa câu hỏi vào prompt. Model vẫn quyết định nghiệp vụ; engine lưu trạng thái và sắp nhóm hiển thị theo nhãn model cung cấp.

Dữ liệu pháp lý vẫn là Meta 3.1; `data/dialogue_contracts_17_4.json` mô tả yêu cầu nhận dạng và các thành phần cần kiểm tra của từng mục, không tự chứng nhận nguồn đã đầy đủ. Lỗi địa chỉ dữ liệu, quota và thông báo lỗi chung chưa được sửa theo phạm vi đã thống nhất.

Chạy như trước: `python voice_motion_runtime_v17.py` hoặc `python chat.py`. Giữ thư mục `models` và preset đang chạy. Phiên lưu từ V17.3 không khôi phục vào trạng thái V17.4; bắt đầu hội thoại mới. Không cần sửa Unity.

Kiểm thử và giới hạn: [báo cáo V17.4](reports/v17_4/Summary.md), [chi tiết replay](reports/v17_4/Replay_report.md). Công cụ chạy lại bằng WAV: `tools/replay_voice_sessions.py` (có phí API, không kèm WAV người dùng trong source).

---

# Citizen Agent V17.3 — Unity compatible text display

V17.3 sends the information section through the existing Unity `speech_text` protocol. Social speech goes only to TTS; procedure information and question options go only to the screen. The model remains gpt-5.2 with the new Meta 3.1 topic-layer dataset. V17.3 adds model-controlled topic selection and silent page navigation.

## V17.3: chọn nội dung và chuyển trang

Sau khi xác định trường hợp, trợ lý hỏi chọn mục (các bước, hồ sơ, phí, nơi nộp, thời hạn, kết quả, điều kiện theo dữ liệu). Chỉ trả mục được chọn. Câu trả lời đầu của mục vẫn có xã giao + motion; trang đầu được gửi khi audio bắt đầu như V17.2.

Nói “tiếp”, “tiếp theo”, “trang trước”, “mở lại 1/2”, “trang 3” để điều hướng. Một lệnh gọi model ngắn nhận câu nói và số trang; Python gửi lại trang đã lưu qua `speech_text_clear` + `speech_text`, không tạo TTS/motion, không phát preset chờ trong lúc đang duyệt. Nhận giọng nói vẫn cần STT. Ở trang cuối, “tiếp” chuyển sang mục đang chờ hoặc hỏi chọn mục mới. Chọn mục khác/sửa dữ kiện/đổi thủ tục đi vào luồng model nghiệp vụ; không chỉ lật trang.

`config.json`: `display_columns=40`, `display_rows=11` (bao gồm dòng số trang). Đây là mức ước lượng thận trọng từ ảnh, không phải phép đo pixel/font Unity. Nếu Unity tự xuống dòng thêm, giảm `display_columns`; nếu thiếu chiều cao, giảm `display_rows`. Chia theo từ và giữ nguyên mục ngắn trong cùng trang khi có thể; mục quá dài được chia tiếp, không bỏ nội dung. Không cần sửa Unity.

Meta 3.1 bổ sung tầng nội dung dưới từng trường hợp. Runtime ưu tiên `data/kb_meta_tree_3.1.json`, giữ 3.0 để đối chiếu. Khi nhận dạng chỉ tải điều kiện cục bộ; khi chọn mục tải nút `.TOPIC.<mục>` và tham chiếu phù hợp. Các nhánh có điều kiện không được tự động kế thừa. Chuyển trang dùng nội dung đã lưu, không tải lại meta.

Bản này bảo toàn 27 thủ tục / 137 trường hợp, có 7 mục cho mỗi trường hợp; bổ sung thông tin có nguồn và ghi rõ mục chưa xác minh. Xem [báo cáo Meta 3.1](reports/meta_3_1/Bao_cao.md) và [bảng phủ nội dung](reports/meta_3_1/case_coverage.csv). Dùng toàn bộ thư mục bản mới, chép lại `models` và preset đang dùng. Hash dữ liệu thay đổi nên phiên hội thoại cũ không được khôi phục; bắt đầu hội thoại mới.

Giải nén vào đường dẫn ngắn như `D:\VO17_3` để tránh giới hạn đường dẫn CSV trên Windows. Dùng môi trường Python, thư mục `models` và preset đang chạy tốt ở V17.2.

## Files to run

- Text console: `python chat.py`
- Microphone / TTS / avatar: `python voice_motion_runtime_v17.py`

The main filename stays `voice_motion_runtime_v17.py`. `config.json` identifies release 17.3.

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

## Unity packets in V17.3

UTF-8 JSON, one JSON object per line. Immediately after `sd.play` succeeds for social audio, the playback callback clears the previous text, then sends one formatted text message:

```json
{"type":"speech_text_clear"}
{"type":"speech_text","job_id":1,"text":"Hồ sơ cần chuẩn bị\n\nGiấy tờ\n- Tờ khai\n- Giấy tờ theo trường hợp"}
```

The plain text contains the title, section headings, bullet items and A/B/C options. No internal node IDs are included. `job_id` is the response revision. No `information_panel` handler is needed for these V17.3 responses.

For normal topic/question replies, the bridge prepares `response['information']` but does not send it during generation or TTS. It is published once at audio playback start. Only `response['speech_text']` enters the TTS/motion pipeline; naming the display packet `speech_text` does not synthesize its contents. Generated audio playback does not send social text to the display.

A silent finish clears the display without audio. Page navigation sends cached text immediately without audio. Other replies queue one short social utterance as one WAV; if the model leaves social text empty while providing information, a short presentation-only phrase is used. Detected departure sends `speech_text_clear`. Preset greeting/waiting speech text is disabled by default so it cannot overwrite the information on the shared display; preset audio/motion still works. Generated information stays visible after audio ends with the default configuration.

The existing client must already handle `speech_text` and `speech_text_clear`. Clickable choices are not implemented; citizens answer option letters or labels through speech. TCP send success is not a Unity render acknowledgement.

## Diagnostics

Terminal:

```text
[UNITY TEXT] Sent revision=1 turn=... chars=...
```

Normally `[AUDIO START]` appears immediately before `[UNITY TEXT]`. This confirms successful software playback start and TCP send, not physical speaker output or Unity rendering. Send errors log the exception type in `panel_error`; silent page navigation stays silent. Each turn's transcript folder contains:

- `assistant_full_response.v17.json`: model response, including information.
- `assistant_full_response.delivery.json`: revision, TTS readiness/error, audio start/completion/error, audio-only fallback, display send status and character count. The final status is saved after pipeline workers finish.

## Validation and historical reports

```powershell
python -m unittest discover -s tests -v
```

V17.3 validation is recorded in `reports/v17_3_validation.md`. Tests include cached forward/back paging, line/row limits, no-TTS page delivery, source filtering, session restore, cancellation, and the existing V17.2 playback suite. Actual hardware output and Unity rendering were not exercised in the cloud.

Motion generation failure no longer suppresses social speech by default (`play_audio_even_if_motion_failed=True`). The avatar can remain still while the audio plays. The initial readiness buffer is one job. Successful motion still accompanies normal playback. If TTS fails or the audio device cannot start, the new information is not published; inspect `tts_error` / `playback_error` and terminal logs. This release does not fix invalid ElevenLabs credentials, missing local assets, or a muted/incorrect output device.

`reports/Bao_cao.md` and `reports/Hoi_thoai.html` retain historical V17 model API results. References there to `information_panel` describe V17.0, not the current V17.3 transport. `reports/v17_1_transport.md` is the previous transport update; `reports/v17_2_playback.md` records the V17.2 synchronization changes.

The model-only core still uses bounded local windows, correction history and confirmed procedure switching. No new legal/semantic output validator was added.
