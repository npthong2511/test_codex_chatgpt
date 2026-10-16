# V17.3 — Meta 3.1

## Thay đổi

- 27 thủ tục, 137 trường hợp; giữ 1.621 nút gốc và điều kiện rẽ nhánh.
- Mỗi trường hợp có 7 mục: các bước, hồ sơ, phí, nơi nộp, thời hạn, kết quả, điều kiện.
- 2.086 đoạn nguồn được phân loại; 149 bổ sung được chấp nhận, đặt tại 235 vị trí; 3 sửa tên biểu mẫu có lưu nguyên văn cũ.
- 4.122 nút nội dung; loader chọn Meta 3.1, chỉ gửi điều kiện và nội dung cục bộ phù hợp. Không thêm engine quyết định pháp lý.
- Audio/motion/Unity giữ luồng V17.3; điều hướng trang dùng nội dung lưu và không tạo audio/motion.

## Mức độ hoàn thiện

959 mục thuộc 137 trường hợp: {'local_content': 196, 'inherited_content': 61, 'conditional_sources': 652, 'unconfirmed': 50}.

`conditional_sources` nghĩa cần xét điều kiện rồi đọc nhánh tham chiếu; không đồng nghĩa tất cả nội dung đã đủ. 50 mục `unconfirmed` vẫn chưa có nguồn phù hợp để bổ sung chắc chắn. Runtime phải nói rõ thiếu dữ liệu, không suy ra miễn phí hoặc không cần hồ sơ. Nội dung gốc được bảo toàn nhưng chưa được chứng nhận toàn bộ còn hiệu lực.

Bảng chi tiết: [case_coverage.csv](case_coverage.csv). Các phát hiện nghiên cứu tại [unresolved_checks.json](unresolved_checks.json) gồm 186 điểm cần kiểm tra và 18 nghi vấn xung đột; đây là nhận định sơ bộ từ tìm kiếm, có thể trùng hoặc chỉ là lỗi truy cập, không phải 204 lỗi pháp lý đã xác nhận.

## Nguồn và khả năng kiểm tra

Đã tìm nguồn cho cả 27 thủ tục qua web search. Ưu tiên Cổng Dịch vụ công, Chính phủ, cơ quan chuyên ngành và cơ quan TP.HCM; một số văn bản được tra qua bản đăng lại. Truy cập HTTP trực tiếp bị proxy 403 nên dùng công cụ web search; chứng cứ URL/trích đoạn được lưu trong data/migration/reviewed_supplements.json và web_evidence.json. Không tự điền những ứng viên lệch địa bàn, sai thủ tục hoặc chưa rõ hiệu lực.

Ví dụ căn cước: [hướng dẫn Cổng Chính phủ](https://xaydungchinhsach.chinhphu.vn/huong-dan-thu-tuc-cap-cap-doi-cap-lai-the-can-cuoc-tai-cong-an-cap-xa-119260828113820605.htm). Tách DC02 điện tử khi đề nghị; CC01 do cơ quan thu nhận in để kiểm tra/ký; DC01 chỉ phát sinh theo điều kiện thiếu dữ liệu. Không mặc định giấy đại diện bắt buộc trong mọi trường hợp. Chi tiết tại [id_detail.md](id_detail.md).

## Kiểm thử

56 kiểm thử offline đạt (offline_tests.txt): bảo toàn nguồn/điều kiện, đủ mục, tham chiếu hợp lệ, không kế thừa nhánh anh em, tải cục bộ và các kiểm thử runtime/hiển thị hiện có.

API smoke dưới đây chỉ kiểm tra text, không chạy Unity, ElevenLabs hoặc thiết bị motion. Kết hôn và hộ kinh doanh chạy trước đợt bổ sung cuối; căn cước chạy sau bản dữ liệu cuối. Không phải kiểm định toàn bộ 137 trường hợp.

### id_child

5 lượt; 12 API calls; token: {'input_tokens': 64699, 'output_tokens': 3438, 'total_tokens': 68137}.

**Người dân:** Tôi làm căn cước lần đầu cho con 5 tuổi, tôi là mẹ ruột. Tôi muốn biết hồ sơ.

**Kết quả:** question

**Âm thanh:** Anh/chị muốn xem đúng mục “Hồ sơ cần chuẩn bị” cho trường hợp cấp căn cước lần đầu cho trẻ dưới 06 tuổi phải không?

```text
Chọn nội dung cần xem

B. Hồ sơ cần chuẩn bị
A. Các bước thực hiện
C. Phí, lệ phí
D. Nơi nộp hồ sơ
E. Thời hạn trả kết quả
F. Kết quả
G. Điều kiện
Trang 1/1 | Tiếp / Trước
```

**Người dân:** Đúng rồi, tôi muốn xem hồ sơ cần chuẩn bị.

**Kết quả:** answer

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Hồ sơ cần chuẩn bị (cấp căn cước lần đầu
cho trẻ dưới 06 tuổi)

Thành phần hồ sơ/biểu mẫu
- Phiếu đề nghị giải quyết thủ tục về
căn cước (DC02) (kê khai dưới dạng biểu
mẫu điện tử khi nộp hồ sơ trực tuyến cho
trẻ dưới 6 tuổi).
Trang 1/5 | Tiếp / Trước
```

**Người dân:** tiếp

**Kết quả:** page

**Âm thanh:** (không tạo)

```text
- Trường hợp dữ liệu công dân chưa có
trong Cơ sở dữ liệu quốc gia về dân cư:
hồ sơ có thể cần thêm Phiếu thu thập
thông tin dân cư (DC01) và giấy tờ pháp
lý chứa thông tin công dân (chỉ áp dụng
khi chưa có dữ liệu, không phải mọi
trường hợp).

Số lượng hồ sơ
Trang 2/5 | Tiếp / Trước
```

**Người dân:** mở lại trang 1

**Kết quả:** page

**Âm thanh:** (không tạo)

```text
Hồ sơ cần chuẩn bị (cấp căn cước lần đầu
cho trẻ dưới 06 tuổi)

Thành phần hồ sơ/biểu mẫu
- Phiếu đề nghị giải quyết thủ tục về
căn cước (DC02) (kê khai dưới dạng biểu
mẫu điện tử khi nộp hồ sơ trực tuyến cho
trẻ dưới 6 tuổi).
Trang 1/5 | Tiếp / Trước
```

**Người dân:** Tôi muốn biết phí.

**Kết quả:** answer

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Phí và chi phí (cấp căn cước lần đầu cho
trẻ dưới 06 tuổi)

Phí/lệ phí thủ tục
- Cấp căn cước lần đầu: không thu phí.

Chi phí có thể phát sinh (nếu chọn)
- Nếu đăng ký chuyển phát kết quả: phí
chuyển phát là dịch vụ riêng (không nằm
trong phí/lệ phí của thủ tục).
Trang 1/1 | Tiếp / Trước
```

### marriage

3 lượt; 8 API calls; token: {'input_tokens': 41397, 'output_tokens': 2536, 'total_tokens': 43933}.

**Người dân:** Tôi và bạn gái đều là công dân Việt Nam, sống trong nước, chưa kết hôn với ai và muốn đăng ký kết hôn lần đầu.

**Kết quả:** question

**Âm thanh:** Anh/chị muốn xem nội dung nào về thủ tục đăng ký kết hôn lần đầu?

```text
Chọn nội dung cần xem

A. Hướng dẫn (các bước thực hiện)
B. Hồ sơ cần chuẩn bị
C. Phí và chi phí
D. Nơi nộp hồ sơ
E. Thời hạn
F. Kết quả
G. Điều kiện và lưu ý
Trang 1/1 | Tiếp / Trước
```

**Người dân:** Tôi 28 tuổi, bạn gái 26 tuổi. Cả hai tự nguyện, không có quan hệ họ hàng.

**Kết quả:** question

**Âm thanh:** Anh/chị muốn xem nội dung nào về thủ tục đăng ký kết hôn lần đầu?

```text
Chọn nội dung cần xem

A. Hướng dẫn (các bước thực hiện)
B. Hồ sơ cần chuẩn bị
C. Phí và chi phí
D. Nơi nộp hồ sơ
E. Thời hạn
F. Kết quả
G. Điều kiện và lưu ý
Trang 1/1 | Tiếp / Trước
```

**Người dân:** Tôi muốn xem hồ sơ cần chuẩn bị.

**Kết quả:** answer

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Hồ sơ cần chuẩn bị (đăng ký kết hôn lần
đầu, không có yếu tố nước ngoài)

Giấy tờ/Thông tin cần có
- Tờ khai đăng ký kết hôn theo mẫu, có
đủ thông tin của hai bên nam, nữ (khi
nộp trực tiếp, hai bên có thể khai chung
vào một tờ khai).
- Thông tin định danh để cơ quan đăng ký
khai thác/xác thực nhân thân.
Trang 1/2 | Tiếp / Trước
```

### business

2 lượt; 7 API calls; token: {'input_tokens': 37773, 'output_tokens': 1669, 'total_tokens': 39442}.

**Người dân:** Tôi muốn đăng ký hộ kinh doanh mới, một mình tôi thành lập.

**Kết quả:** question

**Âm thanh:** Anh/chị muốn xem nội dung nào về thủ tục đăng ký hộ kinh doanh mới (một mình thành lập)?

```text
Chọn nội dung cần xem

A. Hướng dẫn/Các bước thực hiện
B. Hồ sơ cần chuẩn bị
C. Phí và chi phí
D. Nơi nộp hồ sơ
E. Thời hạn
F. Kết quả
G. Điều kiện và lưu ý
Trang 1/1 | Tiếp / Trước
```

**Người dân:** Hồ sơ cần những gì?

**Kết quả:** answer

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Hồ sơ đăng ký hộ kinh doanh mới (một cá
nhân thành lập)

Thành phần hồ sơ
- Giấy đề nghị đăng ký hộ kinh doanh (do
cá nhân thành lập ký).

Lưu ý theo quy định áp dụng (khi đăng ký
mới)
Trang 1/3 | Tiếp / Trước
```

## Hạn chế còn lại

- Các lần thử ban đầu có JSON nối hai object; đã làm rõ giao thức một object/một action. Log thất bại được giữ ở initial_api, second_api, third_api. Không khẳng định lỗi model sẽ không tái diễn.
- Lượt kiểm tra trước bản cuối có chọn nhầm nhánh phí cấp đổi/cấp lại khi hỏi cấp lần đầu; đã điều chỉnh hướng dẫn chọn tham chiếu và giữ topic trường hợp khi đọc thêm nguồn. Xem log cuối ở trên để đánh giá kết quả thực tế.
- Câu trả lời hồ sơ có thể dài thành 4 trang ở cấu hình 40 ký tự × 11 dòng; không cắt bỏ điều kiện để ép một trang.
- Dữ liệu nhạy với thay đổi pháp luật/địa bàn. Các mục còn thiếu và các đoạn gốc chưa tái kiểm chứng cần được người phụ trách nghiệp vụ rà soát.
- research_usage.json chỉ thống kê các batch nghiên cứu có raw log, không phải tổng chi phí: không bao gồm phân loại, nghiên cứu căn cước riêng, API smoke và phí công cụ tìm kiếm. Không dùng số đó để suy ra chi phí một hội thoại.

## Chạy local

Dùng toàn bộ thư mục release, giữ models/preset của bản đang chạy; đặt Open_AI trong môi trường. Chạy `python voice_motion_runtime_v17.py` như cũ, hoặc `python chat.py` để thử text. Meta đổi hash nên bắt đầu phiên hội thoại mới. Không cần sửa Unity.
