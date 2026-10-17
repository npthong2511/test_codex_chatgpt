# Meta 3.2 và giao thức V17.5

Đầu vào là `data/kb_meta_tree_3.1.json` trong ZIP Meta Updated của người dùng. Nội dung, điều kiện và nguồn được giữ nguyên khi tạo `kb_meta_tree_3.2.json`; builder chỉ thêm định tuyến và phiên bản. Không sao chép văn bản sang mọi nhánh và không tạo địa chỉ giả.

Mọi nút cấu trúc trừ ROOT có 7 entry `topic_routes`. Mỗi entry tham chiếu một topic node tồn tại trong catalog của chính nó hoặc tổ tiên gần nhất có nguồn/tham chiếu. Quan hệ tổ tiên chỉ là ứng viên cần xét điều kiện. `local_source` nghĩa có văn bản tại nút, không đồng nghĩa đầy đủ pháp lý. `conditional_sources` cần model xét phạm vi và các supporting_topics. Nếu không tìm được nguồn thì `unconfirmed`; không mặc định miễn phí hay không cần hồ sơ.

Tổng: 1.620 vị trí × 7 = 11.340 entry, gồm 2.369 local_source và 8.971 conditional_sources trong bản dữ liệu này. Không có entry unconfirmed vì tổ tiên có các nguồn ứng viên; điều này KHÔNG có nghĩa mọi mục đã có nội dung áp dụng cho từng trường hợp.

Ví dụ:

```text
P09.C07.N002.N002 (Chuyển hình thức sử dụng đất)
  ho_so     -> P09.C07.N002.N002.TOPIC.ho_so (local)
  thoi_gian -> P09.C07.N002.TOPIC.thoi_gian (ancestor_candidate)
  noi_nop   -> P09.C07.TOPIC.noi_nop (ancestor_candidate)
```

Nguồn tổ tiên có thể chỉ chứa liên kết. Model đọc điều kiện của supporting_topics và chỉ dùng nhánh phù hợp; không kế thừa tất cả anh em. Nếu không xác định được nguồn áp dụng thì hỏi điều kiện hoặc báo thiếu, không ép trả lời.

Model gọi `open_topic` với `case_id` và `topic`, engine dùng cùng bản đồ đang cung cấp cho menu để chọn địa chỉ tải. Trường hợp gốc được giữ trong topic_context khi đọc nguồn chung. Nguồn cục bộ vẫn chỉ là cửa sổ hiện tại, tổ tiên và con trực tiếp; toàn bộ 11.340 route không được gửi trong mỗi call.

Sau một lần open_topic trong lượt, schema API chỉ cho load/respond/restart. Model đọc nguồn đã tải hoặc load tham chiếu hợp lệ. Việc này ngăn lặp open_topic; engine vẫn giữ chốt chống lặp cho provider không tuân schema. Không phải bộ kiểm tra ngữ nghĩa câu trả lời.

Yêu cầu load sai địa chỉ/open_topic sai case hoặc topic: rollback trạng thái tạm của hành động, trả navigation_error và menu địa chỉ hợp lệ cho model sửa tối đa hai lần trong ngân sách lượt. Nếu vẫn lỗi hoặc hết ngân sách phục hồi, trả navigation_error với preserve_display, không thay facts/pages. Lỗi nguồn thiếu có mã NO_CONFIRMED_SOURCE, khác địa chỉ sai. Lỗi quota và lỗi API khác không thay đổi.

Trạng thái pending_switch do model tạo là dấu hiệu đang chờ xác nhận đổi thủ tục; chấp nhận câu hỏi trước ở mode question hoặc switch_confirm khi đã có dấu hiệu này. Không cho restart khi không có pending_switch.

Tái tạo: `python tools/build_topic_routes.py`. Kiểm tra: `python -m unittest discover -s tests`.
