# V17 — Code, 10 hội thoại API và kết quả kiểm chứng

Đã xây dựng V17 dựa trên main V16 trong ZIP và 8 module Python người dùng gửi. Bản cuối có lõi model-only, meta cục bộ, hỏi bằng lựa chọn, sửa dữ kiện, xác nhận đổi thủ tục, hai kênh âm thanh/hiển thị và tích hợp phía Python của voice runtime.

## Những gì đã chạy

- 10 hội thoại chính, 41 lượt người dân, 95 lần gọi OpenAI thật.
- Người dân được mô phỏng thủ công theo hồ sơ cố định trong tests/DESIGN.md, trả lời theo câu hỏi thực tế. Không gọi model để sinh người dân hoặc làm giám khảo.
- Trước bộ chính: 10 lượt mở đầu thăm dò để sửa prompt.
- Sau bộ chính: 8 lượt kiểm tra sửa lần 1 và 4 lượt kiểm tra bản cuối, dùng lại các tình huống/phần trạng thái của bộ chính.
- 16 kiểm tra offline đều đạt: cửa sổ cục bộ, thay thế nguồn, phạm vi điều hướng, restart, hủy lượt, cách ly phiên, ACK cũ, TCP thực bằng socketpair, tách panel/TTS và lỗi gửi panel.
- Không chạy ElevenLabs, camera/mic/loa, model motion hay Unity thật. Luồng Python được nối và kiểm tra cấu trúc + bridge/socket giả lập. Unity cần nhận packet information_panel mới; không có C# trong gói theo yêu cầu.

**Không coi toàn bộ 10 hội thoại đều đạt hoàn toàn.** Có lỗi nội dung và một lượt chạm giới hạn gọi model. Bản cuối đã sửa các lỗi trọng tâm và được kiểm tra có mục tiêu; chưa chạy lại toàn bộ 41 lượt trên bản cuối. Các snapshot source/hashes phân biệt rõ phiên bản đã chạy.

## Số liệu API

| Lần chạy | Lượt người dân | API calls | Input tokens | Output tokens | Tổng tokens | Trung vị giây/lượt |
|---|---:|---:|---:|---:|---:|---:|
| Thăm dò đầu | 10 | 23 | 54.603 | 4.804 | 59.407 | 9,54 |
| 10 hội thoại chính | 41 | 95 | 295.692 | 23.070 | 318.762 | 7,66 |
| Kiểm tra sửa lần 1 | 8 | 16 | 58.171 | 3.835 | 62.006 | 5,74 |
| Kiểm tra bản cuối | 4 | 10 | 43.356 | 2.320 | 45.676 | 8,52 |
| **Tổng toàn công việc** | **63** | **144** | **451.822** | **34.029** | **485.851** | — |

92.032 input tokens được API ghi nhận cached (nằm trong tổng input, không cộng thêm). Không có lỗi HTTP/API trong 144 calls. Có 2 lỗi xử lý ở tầng hội thoại: một TURN_CALL_BUDGET trong bộ chính và một RESTART_LOOP ở kiểm tra sửa lần 1; cả hai tình huống đã chạy lại thành công ở bản cuối. Không ghi nhận lỗi xử lý trong 4 lượt hồi quy cuối, không suy rộng thành bảo đảm mọi hội thoại đều hết lỗi.

Độ trễ là từ gửi một câu người dân đến nhận phản hồi văn bản hoàn chỉnh, gồm các call nạp nguồn cần thiết; chưa gồm STT/TTS/motion/thời gian người đọc. Lượt chậm nhất bộ chính 32,08 giây là lượt lặp nạp nguồn thất bại. Các hội thoại độc lập chạy tối đa 2 luồng, mỗi hội thoại tuần tự.

Tham chiếu V16.2 bộ hội thoại tự nhiên trước: 22 lượt, 405.075 tokens, trung vị 9,62 giây/lượt; trung bình 18.412 tokens/lượt. V17 bộ chính: khoảng 7.775 tokens/lượt, thấp hơn khoảng 57,8%. **Hai bộ hội thoại khác nhau, đây không phải phép A/B kiểm soát và không phải cam kết mức tiết kiệm cố định.** Không gọi lại V16.2 để tránh phát sinh chi phí thêm. Không suy chi phí USD chính xác từ token khi chưa đối chiếu biểu giá/tài khoản thanh toán.

## Kết quả từng hội thoại

| Mã | Kiểm chứng chính | Quan sát và kết luận |
|---|---|---|
| D01 | Căn cước trẻ; không suy tuổi từ lớp học; sửa 5 → vừa đủ 6 | Hỏi nhóm tuổi đúng; sửa tuổi chuyển nội dung sang nhánh 6–<14. Bảng vẫn đưa thêm phí/thời hạn khi hỏi chuẩn bị; lúc kết thúc không phát lời chào. |
| D02 | Đổi căn cước → khai sinh | Bộ chính tự chuyển thiếu xác nhận. Đã sửa giao thức phạm vi node và reset; bản cuối hỏi Có/Không, nhận Có rồi mở khai sinh, bỏ trạng thái cũ. |
| D03 | Đề cập thủ tục khác rồi từ chối đổi | Hỏi xác nhận, từ chối thì tiếp tục khai sinh. Có lúc trả danh sách chung trước khi hỏi đủ chi tiết giấy chứng sinh và tình trạng cha mẹ; chưa cá thể hóa hoàn toàn. |
| D04 | Giấy phép mất → rách còn giữ; thiếu phí trực tiếp; xem riêng hồ sơ | Cập nhật đúng giấy phép cũ phải kèm; không bịa phí chưa có nguồn. Yêu cầu xem riêng giấy tờ được đáp ứng. Có câu về phí dùng từ kỹ thuật “node/dữ liệu đang mở” không phù hợp người dân. |
| D05 | Khai sinh tại nhà, không chứng sinh, có người làm chứng | Kết quả cuối chọn văn bản người làm chứng, không đòi cam đoan đồng thời. Nhưng bỏ sót “Ở Việt Nam” trong câu trả lời và hỏi lại nơi sinh. Kiểm tra sửa lần 1 vẫn lặp; lỗi này còn tồn tại. |
| D06 | Vợ chồng cùng thành lập, vợ làm chủ, tự nộp; phí/thời hạn | Sau đính chính rõ, hồ sơ phân biệt đúng ủy quyền làm chủ và nộp thay. Bộ chính báo thiếu phí dù meta có. Bản cuối đã trả phí trực tiếp 100.000 đồng theo địa bàn nguồn, trực tuyến 0 đồng, cùng thời hạn 3 ngày làm việc. |
| D07 | Con làm giúp mẹ mất giấy khuyết tật, chưa có tư cách đại diện | Không tự khẳng định con là đại diện hợp pháp; cuối cùng nêu đúng khoảng trống dữ liệu về nộp thay. Hỏi tư cách nhiều lần dù người dân đã nói chỉ đi giúp; câu hỏi chưa đủ hiệu quả. |
| D08 | Chuyển THPT công lập khác tỉnh; hỏi thêm giữa năm | Đi được nhánh phù hợp và trả phần hỏi tiếp trong cùng thủ tục. Một câu hỏi vẫn nhắc khả năng xuất phát tư thục dù đã nói công lập; có thể rút ngắn. |
| D09 | “Làm lại thẻ” mơ hồ; sửa thông tin chưa rõ; mất → hỏng | Bộ chính tự đoán căn cước; sửa mơ hồ có options; sau đó hỏi miễn phí dù chỉ hỏi giấy tờ và lặp nạp nguồn tới giới hạn. Lượt thăm dò lại đã hỏi loại thẻ; bản cuối chạy lại điểm lỗi trả được giấy tờ cho thẻ hỏng. |
| D10 | Hai nhu cầu; chọn ATTP; đã có đăng ký HKD | Bộ chính tự ưu tiên tạm trú. Kiểm tra sửa lần 1 đã hỏi ưu tiên trước; sau chọn ATTP không chuyển nhầm sang HKD. Bảng hồ sơ ATTP cuối vẫn dài và kèm thẩm định/kết quả ngoài mục hỏi. |

## Kiểm chứng hai kênh và meta cục bộ

Bộ chính có 21 question, 2 switch_confirm, 14 answer, 2 data_gap, 1 finish và 1 transport_error. Tất cả 23 câu hỏi/xác nhận có options. Tất cả 16 answer/data_gap dùng đúng 2 câu xã giao riêng, không đọc thông tin nghiệp vụ:

> Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

Trong 95 call bộ chính, không call nào vượt 4 cửa sổ; không node con nào mang theo toàn bộ hậu duệ. Các cửa sổ gồm node, con trực tiếp, common tổ tiên và các tham chiếu ngắn tới quy định bổ sung. Source không tích lũy cả cây theo hội thoại. ROOT chỉ dùng danh mục tóm tắt. Đây là kết quả kiểm tra payload thật, không chỉ kiểm tra lời hứa trong prompt.

Bridge gửi packet information_panel chỉ chứa information, rồi đưa speech_text vào TTS. Kiểm tra socketpair xác nhận phần giấy tờ có trong packet nhưng không trong hàng đợi âm thanh, và xã giao không trong packet. Audio/motion thực chưa chạy. Preset chào/chờ thuộc luồng cũ, độc lập các câu model sinh.

Ví dụ bản cuối D06, bảng hiển thị:

- Lệ phí trực tiếp: 100.000 đồng/lần, điều kiện địa bàn Bình Dương trước sắp xếp.
- Trực tuyến: 0 đồng.
- Trong 3 ngày làm việc: cấp khi đủ điều kiện hoặc thông báo lý do/nội dung bổ sung.

Đây là nội dung theo meta được cung cấp; đợt xây dựng này không tra cứu lại hiệu lực pháp luật.

## Những thay đổi sau phát hiện lỗi

1. load không thể đi tắt sang mã thủ tục khác. Phải có switch_confirm, rồi model nhận xác nhận và chọn restart. Đây là kiểm tra trình tự/phạm vi địa chỉ, không phải engine kiểm tra nội dung pháp lý.
2. Sau restart, call tiếp theo nhận nhu cầu mới thay cho câu “Có”, tránh lặp restart.
3. Gửi nhật ký ngắn các địa chỉ vừa nạp; cảnh báo thao tác nạp lặp để model yêu cầu các cửa sổ cần ghép cùng một lần, vẫn giới hạn 4.
4. Nhấn mạnh trong prompt: không đoán loại thẻ, hỏi ưu tiên khi nhiều nhu cầu, đọc nhánh phí chung trước khi tuyên bố thiếu dữ liệu, ghép nguồn phí và thời hạn.

## Vấn đề còn lại và bước tiếp theo

- Cập nhật dữ kiện chưa ổn định: câu trả lời tự nhiên có nhiều ý vẫn có thể bị bỏ sót và hỏi lại (D05 rõ nhất). Không tăng giới hạn call để che lỗi này.
- Câu hỏi đôi lúc dư hoặc gộp nhiều điều kiện, lựa chọn “không thuộc/không chắc” có thể nhập nhằng. Cần kiểm tra thêm việc người dân không biết/không hiểu lựa chọn.
- Bảng thông tin chưa luôn ngắn đúng mục hỏi; đôi lúc lộ mã thủ tục hoặc thuật ngữ nội bộ. Không có bộ lọc ngữ nghĩa sửa lại câu trả lời vì giữ yêu cầu model-only.
- Phí và thời hạn đúng trong lượt hồi quy cụ thể không chứng minh mọi nhánh đều truy xuất đúng; cần hồi quy rộng hơn sau thay đổi prompt tiếp theo.
- Chưa kiểm tra toàn bộ 27 thủ tục/137 trường hợp. Bộ này ưu tiên hành vi vận hành và 7 nhóm thủ tục được hỏi chuyên biệt, cùng tạm trú ở bước chọn nhu cầu.
- Packet mới cần được Unity xử lý. TCP hiện chỉ gửi, options hỗ trợ trả lời bằng giọng nói; thao tác bấm lựa chọn cần thêm đường nhận sự kiện. Chưa có ACK xác nhận Unity đã render.

Gói đủ để tiếp tục tích hợp và thử nghiệm trên máy đang chạy avatar; chưa có bằng chứng phần cứng/Unity end-to-end hoạt động với packet mới trong cloud.

Bổ sung cuối khi đóng gói: thao tác load được phép ghép một nguồn bổ trợ ngoài thủ tục nếu có liên kết rõ trong meta đang mở, giữ cửa sổ thủ tục chính và tối đa 4 cửa sổ. Điều này tránh coi đọc quy định nộp thay ở P25 là đổi khỏi thủ tục thành lập HKD ở P24. Thay đổi phạm vi địa chỉ này được kiểm tra offline bằng test riêng; các log API cuối dùng snapshot runtime_api_final.py trước bổ sung này. Không phát sinh thêm API cho thay đổi địa chỉ thuần túy.
