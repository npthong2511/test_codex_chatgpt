# V17.4 — kết quả sửa và kiểm tra

Đây là bản có thay đổi và bằng chứng kiểm thử, chưa thể kết luận cả hai hội thoại đều tốt hơn toàn diện. Giữ bản V17.3 ở nhánh cũ để đối chiếu.

## Phạm vi đã sửa

- STT chỉ định tiếng Việt; thử lại cùng WAV tối đa một lần khi rỗng/không có chữ Latin. Không đưa câu hỏi vào prompt STT: thử nghiệm cho thấy audio yếu có thể bị chép thành chính câu hỏi.
- Transcript chữ Hàn/Trung không còn bị coi mặc định là im lặng. Model phân loại ý định; khi `unclear`, giữ nguyên dữ kiện, câu hỏi đang chờ và bộ trang, chỉ hỏi lại. Không có bảng thay thế từ nghe sai.
- Lưu riêng `requested_topics`, `pending_question`, `case_resolution` và facts. Model phân biệt sửa dữ kiện cùng thủ tục với đổi thủ tục, giữ nhu cầu khi hỏi bổ sung.
- Cung cấp điều kiện nhánh cục bộ và dấu hiệu cùng điều kiện với nút cha. Các nhánh chia nội dung không mặc định là các trường hợp cần chọn. Thêm schema giới hạn mã topic hợp lệ.
- Nội dung có các nhóm do model gán: chuẩn bị, có điều kiện, cơ quan lập, số lượng, lưu ý, bước thực hiện, nội dung, phần thiếu. Engine chỉ sắp nhóm theo nhãn và chia trang, không xác thực hay tự sửa nghiệp vụ.
- Giữ Meta 3.1. Không sửa phần xử lý lỗi địa chỉ/quota/thông báo lỗi chung (phần 5 đã hoãn).

## Kiểm thử

64 kiểm thử offline đạt; 4/4 probe API đạt: câu vô nghĩa -> unclear, lựa chọn A -> tiếp tục nghiệp vụ, câu vừa nói tiếp vừa sửa tuổi -> nghiệp vụ, trước đó -> chuyển trang. Xem `offline_tests.txt`, `route_probes.json`.

Đã phát lại 21 + 29 lượt có transcript từ hai ZIP; có một bản ghi cuối phiên 2 không có transcript gốc nên không nằm trong so sánh 50 lượt. STT dùng WAV thật, không tự sửa transcript thành lời mong muốn. Baseline là log người dùng, không gọi API lại cho bản cũ. Các câu đã ghi âm là cố định: khi bản mới hỏi điều kiện khác, bản ghi không có câu trả lời tương ứng. Vì vậy replay đánh giá được lỗi/trạng thái nhưng không thay thế một cuộc hội thoại thích ứng với người thật.

## So sánh replay đầy đủ

| Chỉ số | Phiên 1 cũ → mới | Phiên 2 cũ → mới |
|---|---|---|
| Lượt trả nội dung answer | 4 → 9 | 4 → 0 |
| Lượt lỗi transport_error | 3 → 0 | 1 → 0 |
| Lượt chuyển trang page | 0 → 0 | 7 → 2 |
| Lượt hỏi lại vì không rõ, giữ trang | Không có mode riêng → 2 | Không có mode riêng → 6 |

Không dùng việc giảm lỗi transport để kết luận chất lượng hội thoại đã tốt: phiên 2 chưa tiến tới trả nội dung trong replay đầy đủ, do hỏi thêm điều kiện và lặp xác nhận đổi thủ tục. Phần quota/địa chỉ chưa được sửa; không có lỗi trong một lượt chạy không bảo đảm lỗi đã hết.

Phiên 1: hỏi tuổi trước menu; giữ nhu cầu hồ sơ khi hỏi tuổi; tại lượt 13 đã trả hồ sơ sau khi xác định chuyển hình thức sử dụng đất, không bắt chọn lại mục. Các câu hỏi tiếp về thời hạn/nơi nộp được trả. Hồ sơ căn cước 5 trang ở bản cũ còn 4 trang trong lần này.

Phiên 2: sửa từ nước ngoài về sang trong nước không reset thủ tục, vẫn giữ nhu cầu hồ sơ. Tuy nhiên model hỏi thêm cấp học/chương trình; câu ghi âm không trả lời các điều kiện mới nên hội thoại bị kéo dài. Có câu STT nhận thành hỏi “tiền” và model giữ thêm mục phí; đây là rủi ro còn lại. Model từng hỏi lại xác nhận sau câu “có chuyển sang căn cước”. Đã làm rõ quy tắc xác nhận và kiểm tra lại riêng lượt 16–29 trong `session2_tail_retest.json`; kết quả này không thay thế hoặc che mất replay đầy đủ trước sửa cuối.

## Token và chi phí

Replay đầy đủ phiên 1: 47 calls hội thoại, 252.796 input + 9.771 output = 262.567 token.
Replay đầy đủ phiên 2: 54 calls hội thoại, 215.414 input + 10.932 output = 226.346 token.

Các số trên chưa gồm STT, các lượt thử bị dừng, probe và retest đoạn cuối. Log các lượt thử ở initial_attempt/second_attempt/third_attempt được giữ lại. Không có token baseline trong ZIP nên không khẳng định tiết kiệm so với V17.3. Không đưa ra tổng USD khi chưa đối chiếu hóa đơn API.

## Giới hạn cần biết khi dùng

- Chưa chứng minh cải thiện toàn diện cả hai phiên; phiên 2 còn vấn đề hỏi dư và hiểu sai câu nhận dạng lỗi.
- Chỉ định tiếng Việt không bảo đảm STT đúng. Một số WAV vẫn ra chữ nước ngoài sau lần thử lại; model hỏi lại thay vì tự dịch/đoán.
- Nhóm nội dung và chia trang đã có cấu trúc nhưng vẫn phụ thuộc model gán ý đúng; không phải kiểm chứng đầy đủ pháp lý.
- Không chạy Unity, TTS hoặc motion thật trong cloud. Luồng media giữ nguyên; cần kiểm tra trên máy local với assets hiện có.

## Chạy local

Giải nén vào thư mục mới, chép `models` và preset đang dùng, cấu hình key như trước; chạy `python voice_motion_runtime_v17.py`. File chạy giữ tên cũ, `config.json` xác định V17.4. Không cần sửa Unity. Phiên V17.3 không khôi phục vào trạng thái V17.4. Text console: `python chat.py`.

## Retest cuối sau sửa xác nhận đổi thủ tục

Đã chạy đủ lượt 16–29: {'question': 9, 'clarification': 1, 'answer': 2, 'page': 1, 'switch_confirm': 1}. 34 API calls; token {'input_tokens': 148125, 'output_tokens': 7528, 'total_tokens': 155653}.

Lượt 16 chuyển được sang căn cước, lượt 20 trả hồ sơ sau khi nhận nhóm tuổi, lượt 28 chuyển được sang khai sinh. Vẫn còn các lượt hỏi lại mục sau khi đã trả lời; chưa đạt độ ổn định mong muốn. Đây là retest đoạn cuối, không phải lần replay đầy đủ thứ hai trên bản sửa cuối.
