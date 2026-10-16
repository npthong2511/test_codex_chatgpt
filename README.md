# Citizen Agent V17 — Model-only Local

## Chạy lõi hội thoại

Python 3.12 đã kiểm tra, OpenAI SDK 3.31.0. Đặt secret `Open_AI` trong môi trường.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python run_dialogues.py tests/round1.json --output reports/new_run
```

Lệnh cuối gọi API có phí và ghi vào reports. Không chạy lại vào báo cáo đã tồn tại trừ khi muốn nối thêm lượt. Dùng các file round tiếp theo theo thứ tự để tái hiện hội thoại đã ghi.

## Kiến trúc

`agent17/runtime.py`: một model gpt-5.2, reasoning none. Model chọn load/respond/restart và cập nhật dữ kiện. Python chỉ quản lý trạng thái, tra mã node, giới hạn số cửa sổ/call, xử lý lỗi vận chuyển. Không có engine phán xét đúng/sai nghiệp vụ hoặc câu trả lời.

Mỗi API call nhận tối đa 4 cửa sổ: node được chọn, common tổ tiên, con trực tiếp. Không nạp đệ quy hậu duệ, không tích lũy source cache toàn cuộc hội thoại. Tại ROOT chỉ có danh mục tóm tắt. Các nhánh all_applicable vẫn có thể đồng thời áp dụng. Nguồn nguyên bản meta3.0 được giữ nguyên.

`agent17/voice_bridge.py`: gửi information riêng trước TTS, chỉ speech_text vào hàng đợi âm thanh. Persist dữ kiện theo session và hash meta. Hủy lượt đang xử lý không commit trạng thái.

`voice_motion_runtime_v17.py`: kế thừa main V16 trong ZIP và nối bridge V17. Các module ghi âm, motion, head/lip do người dùng gửi được đi kèm; rag_core/local_hashing lưu để tương thích nhưng lõi V17 không gọi chúng. Không gọi API tóm tắt hội thoại legacy. Có thể dùng Open_AI / ELEVENLABS_API_KEY hoặc các file key riêng như triển khai cũ; không có key trong gói.

Chạy toàn bộ giọng nói cần môi trường desktop cũ: camera, mic, loa, các model/scaler motion trong models/, thư viện media/ML và ElevenLabs, Unity client. Những tài nguyên này không nằm trong file đính kèm. requirements.txt chỉ dành cho lõi API; giữ môi trường media đang hoạt động để chạy main. Không tuyên bố đã kiểm tra phần cứng/TTS/Unity thật trong cloud.

## Giao thức Unity

UTF-8 JSON, mỗi gói một dòng, TCP server Python cổng 5005 như trước.

```json
{"type":"information_panel","protocol_version":17,"session_id":"s1","turn_id":"t1","revision":1,"action":"replace","mode":"question","payload":{"title":"Độ tuổi","sections":[],"options":[{"id":"A","label":"Chưa đủ 6 tuổi","node_ids":[]}]}}
```

`payload` chỉ chứa thông tin hiển thị. Xã giao không có trong packet. Sections có title/items; options có id/label/node_ids. node_ids là metadata nội bộ, không hiển thị cho người dân. `action=clear` khi phát hiện người rời đi. `replace` thay toàn bảng, tránh giữ câu trả lời của nhánh cũ. Client cần xử lý packet mới và bỏ packet phiên/lượt cũ. Không cung cấp C# theo yêu cầu người dùng. Chưa có ACK xác nhận render.

Bản TCP hiện tại là chiều gửi, chưa có đường nhận sự kiện bấm nút. Options hiện hỗ trợ người dân nói A/B hoặc tên lựa chọn qua STT; nếu muốn bấm trên Unity cần bổ sung receiver. Không quảng cáo nút bấm hoạt động sẵn.

Câu xã giao tạo TTS/motion như cũ, bỏ gửi speech_text cho các câu do model sinh. Preset chào/chờ giữ luồng cũ; bảng information không bị xóa khi hết âm thanh. Tệp .v17.json trong thư mục lượt lưu cả hai phần.

## Kết quả và phạm vi kiểm chứng

Xem reports/Bao_cao.md và reports/Hoi_thoai.html. Bộ chính gồm 10 hội thoại / 41 lượt; sau phát hiện lỗi đã sửa rồi chạy hồi quy có mục tiêu, không chạy lại toàn bộ 41 lượt trên bản cuối. Source snapshots và hash runtime nằm trong reports để phân biệt các lần chạy. Dữ liệu API gốc và cả kết quả thất bại được giữ nguyên.

Giới hạn địa chỉ điều hướng: load chỉ truy cập trong thủ tục hiện tại; muốn sang thủ tục khác, model phải đưa switch_confirm trước, sau đó nhận xác nhận của người dân và chọn restart. Python kiểm tra thứ tự thao tác và phạm vi địa chỉ, không xét đúng/sai nghiệp vụ hoặc phán quyết nội dung câu trả lời. Phản hồi lỗi điều hướng được gửi về model để chọn lại thao tác.

Sau restart, lượt nội bộ tiếp theo nhận nhu cầu mới thay cho câu xác nhận 'Có', tránh khởi động lại lặp. Mã các cửa sổ đã đọc gần đây được gửi dạng nhật ký ngắn, không chứa nội dung nguồn; model có thể yêu cầu nhiều cửa sổ liên quan trong cùng call để tránh nạp luân phiên.

Tái chạy hội thoại dùng --output với một thư mục mới; chạy các round theo thứ tự vào cùng thư mục đó. API không bảo đảm câu hỏi giống hệt lần trước, nên bộ replies này là bản lưu cuộc hội thoại thực tế, không phải bài test tự động có thể chấm đúng chỉ bằng mã A/B.

Ngoại lệ nguồn bổ trợ: có thể đọc node ngoài thủ tục nếu meta hiện tại liên kết rõ tới node đó và cùng giữ node thủ tục chính trong tập cửa sổ. Đây là đọc nguồn tham chiếu, không reset hoặc đổi quy trình. Không cho phép dùng ngoại lệ để tự mở node thủ tục khác.
