# V17.5 — kết quả kiểm chứng

Đã xây trên code V17.4 và đúng file Meta 3.1 bổ sung trong Citizen_Agent_V17_4_Meta_Updated_20261017.zip. Hash đầu vào được ghi ở meta_input.json. Meta 3.2 giữ nội dung, thêm bản đồ định tuyến cho 1.620 vị trí cấu trúc (11.340 mục). Không tự thêm hay sửa quy định pháp lý.

## Thay đổi

- Menu và open_topic(case_id, topic) dùng chung topic_routes; chương trình tra địa chỉ có thật thay vì model tự ghép .TOPIC.
- Nguồn ở tổ tiên/nhánh tham chiếu vẫn có điều kiện, không tự kế thừa mọi nhánh anh em. Các trạng thái có nguồn không chứng nhận đầy đủ nghiệp vụ.
- Địa chỉ sai được phản hồi cho model sửa tối đa hai lần trong ngân sách lượt. Khi thất bại giữ trạng thái và trang cũ. Thiếu nguồn được phân biệt với sai địa chỉ.
- Khi đã mở một mục trong lượt, schema API bỏ open_topic, chỉ cho đọc tham chiếu/trả lời/đổi thủ tục. Có thêm chốt chống lặp cho provider không tuân schema.
- Xác nhận đổi thủ tục dùng pending_switch đã lưu; chấp nhận câu hỏi xác nhận được model gắn mode question hoặc switch_confirm. Không cho restart nếu chưa có pending_switch.
- STT, TTS, motion và giao thức Unity giữ như V17.4. Lỗi quota và lỗi API khác chưa thay đổi.

## Kiểm thử offline và API

75 kiểm thử offline đạt. Bao gồm: đường dẫn hợp lệ trên toàn bộ cây, giữ nguyên nội dung bổ sung, nguồn có điều kiện, thiếu nguồn, phục hồi địa chỉ sai, giới hạn phục hồi, bảo toàn trạng thái/trang và chống mở lặp.

Hai bài thử API có chủ đích chèn lệnh tải sai địa chỉ thời hạn/nơi nộp của P09.C07.N002.N002 đều phục hồi: model chuyển sang open_topic và trả lời trong cùng lượt. Lệnh sai là lỗi được chèn để kiểm tra, không phải lỗi model tự sinh; xem recovery_probes.json. Các probe chạy trước chốt schema chống mở lặp; mỗi probe chỉ mở một mục nên không đi qua nhánh chốt mới. Chốt mới có kiểm thử offline riêng và replay đầy đủ trên bản chốt.

Replay bản chốt dùng đúng 50 đầu vào text đã được STT trong lần kiểm tra V17.4 (21 + 29 lượt), gpt-5.2 qua API thật. Không gọi lại STT để tránh thay đổi đầu vào. Không chạy Unity/TTS/motion thật. Không sửa transcript sai thành câu mong muốn. Câu nói là bản ghi cố định, không đáp ứng thích ứng khi model mới hỏi khác.

| Chỉ số | Phiên 1: V17.4 → V17.5 | Phiên 2: V17.4 → V17.5 |
|---|---:|---:|
| Lượt có transcript | 21 → 21 | 29 → 29 |
| Trả nội dung answer | 9 → 8 | 0 → 5 |
| Chuyển trang page | 0 → 0 | 2 → 6 |
| Lỗi runtime/API trong lượt chạy | 0 → 0 | 0 → 0 |
| API calls hội thoại | 47 → 52 | 54 → 62 |
| Input token | 252.796 → 287.603 | 215.414 → 271.905 |
| Output token | 9.771 → 12.122 | 10.932 → 12.114 |
| Tổng token | 262.567 → 299.725 | 226.346 → 284.019 |

Baseline là replay đầy đủ V17.4 đã lưu, trước retest đoạn cuối của bản đó. Nó khác với log local V17.3 ban đầu: log local có INVALID_NODE_ADDRESS ở lượt 15/18/21. Không trình bày baseline khác nhau thành cùng một thí nghiệm.

## Những điểm đã xác nhận

- Phiên 1 lượt 15/18/21 trên V17.5 đều trả answer, không INVALID_NODE_ADDRESS. Thời hạn trả theo nguồn hiện có, đồng thời ghi thiếu mốc bắt đầu/cách loại trừ nếu chưa xác nhận; nơi nộp theo nguồn có điều kiện.
- Phiên 2 có trả hồ sơ, sửa trường hợp trong cùng thủ tục và chuyển trang. Đoạn cuối chuyển được sang khai sinh rồi hỏi lần đầu hay đã đăng ký; bản ghi không trả lời điều kiện đó nên chưa có hướng dẫn khai sinh cuối cùng.
- Không có transport_error hoặc navigation_error trong 50 lượt replay cuối. Đây là kết quả một lượt chạy, không bảo đảm model luôn đúng.

## Hạn chế và chi phí

- Không khẳng định toàn bộ hội thoại tốt hơn: số answer phiên 1 giảm một lượt vì câu STT “Thơ/Thư là ở đâu” được hỏi làm rõ. Một số câu nghe sai/mơ hồ vẫn phải hỏi lại.
- Nội dung hồ sơ/nơi nộp có thể còn chung hoặc thiếu chi tiết; định tuyến đúng không chứng nhận đầy đủ/hiệu lực pháp lý của nguồn.
- 11.340 route có đường tới nguồn ứng viên không đồng nghĩa mọi nguồn đều áp dụng cho trường hợp. 8.971 route là conditional_sources, cần model xét điều kiện.
- Tổng token replay cuối: 583.744, cao hơn khoảng 19,4% so với 488.913 của baseline V17.4. Đây là bản sửa độ tin cậy định tuyến, chưa phải bản tối ưu chi phí.
- Số token trên không bao gồm initial_replay, second_attempt, hai probe và các lượt phát triển khác; không phải tổng chi phí phiên làm việc. Các lần thử chưa đạt được giữ nguyên để kiểm tra. Các lần đầu có vòng lặp open_topic/TURN_CALL_BUDGET, đã sửa và chạy lại cả hai phiên.
- Không công bố tổng USD khi chưa đối chiếu hóa đơn. Không có lần gọi STT/TTS/ElevenLabs mới trong bài kiểm tra V17.5 này.

## Tệp và chạy local

Chi tiết từng lượt: Replay_report.md và hai file JSON phiên. Giao thức: ../../docs/topic_routes_17_5.md. Bộ tái hiện: ../../tools/replay_text_sessions.py (có phí API, cần --live).

Tải toàn bộ nhánh v17.5, chép models/preset đang dùng, giữ key như trước; chạy python voice_motion_runtime_v17.py. Không cần sửa Unity. Bắt đầu phiên mới vì dữ liệu và phiên bản trạng thái thay đổi. File chạy giữ tên cũ, config.json xác định V17.5.
