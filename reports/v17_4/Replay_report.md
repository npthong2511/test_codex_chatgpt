# Kiểm tra V17.4 trên hai phiên thực tế

## Phương pháp

Nhận dạng lại WAV của cả hai phiên, lưu transcript mới rồi phát lại vào engine. Phát lại WAV của cả hai phiên qua gpt-4o-mini-transcribe với language=vi, tối đa một lần nhận dạng lại khi rỗng/không có chữ Latin. Không đưa câu hỏi vào prompt STT để tránh chép lại prompt khi audio yếu. Chạy các câu nhận dạng được theo thứ tự trên engine V17.4 với gpt-5.2. Baseline là kết quả thực tế trong ZIP của người dùng; không chạy lại baseline mất phí. Đây là replay câu nói cố định: khi câu hỏi mới thay đổi, câu trả lời đã ghi âm có thể không còn khớp. Không giả vờ đây là người dùng tương tác thích ứng.

Không chạy Unity/TTS/motion thật trong cloud. Kiểm thử offline kiểm tra giao thức và dữ liệu hiển thị. Không sửa xử lý lỗi quota/địa chỉ (phần 5 đã hoãn). Giữ dữ liệu pháp lý Meta 3.1; thêm hợp đồng nhận dạng/nội dung và trạng thái hội thoại, không bổ sung quy định mới.

## 20261017_085528_390

21 lượt; {'question': 7, 'answer': 9, 'clarification': 2, 'switch_confirm': 1, 'no_speech_detected': 2}; 47 calls xử lý hội thoại; token {'input_tokens': 252796, 'output_tokens': 9771, 'total_tokens': 262567}. Token này không bao gồm STT, lượt thử ban đầu và các kiểm tra riêng.

### turn_001_20261017_085545_067

- STT cũ: Tôi muốn làm căn cứ công dân.
- STT mới: tôi muốn làm căn cứ công dân
- Mode cũ: question
- Mode mới: question
- Âm thanh: Anh/chị đang làm căn cước trong trường hợp nào?

```text
A. Chưa có thẻ, làm lần đầu
B. Đã có thẻ, cần đổi (đến tuổi/thay đổi
thông tin/hư hỏng...)
C. Đã có thẻ, bị mất hoặc cần cấp lại
Trang 1/1 | Tiếp / Trước
```

### turn_002_20261017_085606_641

- STT cũ: Gấp lần đầu
- STT mới: cấp lần đầu
- Mode cũ: question
- Mode mới: question
- Âm thanh: Anh/chị cho biết người được cấp căn cước lần đầu thuộc nhóm tuổi nào?

```text
A. Dưới 06 tuổi
B. Từ đủ 06 đến dưới 14 tuổi
C. Từ đủ 14 tuổi
Trang 1/1 | Tiếp / Trước
```

### turn_003_20261017_085627_945

- STT cũ: Hồ sơ cần chuẩn bị là gì?
- STT mới: Hồ sơ cần chuẩn bị là gì?
- Mode cũ: question
- Mode mới: question
- Âm thanh: Để trả lời đúng “hồ sơ cần chuẩn bị” khi cấp căn cước lần đầu, anh/chị cho biết người được cấp thuộc nhóm tuổi nào?

```text
A. Dưới 06 tuổi
B. Từ đủ 06 đến dưới 14 tuổi
C. Từ đủ 14 tuổi
Trang 1/1 | Tiếp / Trước
```

### turn_004_20261017_085646_982

- STT cũ: Dưới sáu tuổi
- STT mới: Dưới sáu tuổi
- Mode cũ: answer
- Mode mới: answer
- Âm thanh: Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Hồ sơ cần chuẩn bị (cấp căn cước lần đầu
cho trẻ dưới 06 tuổi)

Giấy tờ/phiếu bổ sung (chỉ khi hệ thống
không có/không khai thác được dữ liệu)
- Nếu công dân chưa có thông tin trong
Cơ sở dữ liệu quốc gia về dân cư: có
thêm Phiếu thu thập thông tin dân cư
(DC01) và giấy tờ pháp lý chứa thông tin
công dân.
Trang 1/4 | Tiếp / Trước
```

### turn_005_20261017_085723_034

- STT cũ: detail
- STT mới: detail
- Mode cũ: question
- Mode mới: question
- Âm thanh: Anh/chị muốn xem chi tiết mục nào tiếp theo?

```text
A. Các bước thực hiện
B. Hồ sơ cần chuẩn bị
C. Phí và chi phí
D. Nơi nộp hồ sơ
E. Thời hạn
F. Kết quả
G. Điều kiện và lưu ý
Trang 1/1 | Tiếp / Trước
```

### turn_006_20261017_085756_566

- STT cũ: 那拿俠素
- STT mới: 那拿後色
- Mode cũ: no_speech_detected
- Mode mới: clarification
- Âm thanh: Anh/chị muốn xem mục nào tiếp theo: A Các bước, B Hồ sơ, C Phí, D Nơi nộp, E Thời hạn, F Kết quả, hay G Điều kiện?

```text
A. Các bước thực hiện
B. Hồ sơ cần chuẩn bị
C. Phí và chi phí
D. Nơi nộp hồ sơ
E. Thời hạn
F. Kết quả
G. Điều kiện và lưu ý
Trang 1/1 | Tiếp / Trước
```

### turn_007_20261017_085807_174

- STT cũ: nơi đọc hồ sơ là gì?
- STT mới: Nơi đọc hồ sơ là gì?
- Mode cũ: answer
- Mode mới: answer
- Âm thanh: Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Nơi nộp hồ sơ

Kênh đăng ký lịch (nếu cần)
- Đăng ký lịch qua Cổng dịch vụ
công/VNeID.

Cơ quan/điểm tiếp nhận
- Nộp tại cơ quan quản lý căn cước hoặc
điểm thu nhận Công an cấp xã được triển
khai.
Trang 1/1 | Tiếp / Trước
```

### turn_008_20261017_085842_256

- STT cũ: 接下來
- STT mới: 接頭
- Mode cũ: no_speech_detected
- Mode mới: clarification
- Âm thanh: Anh/chị muốn hỏi nội dung gì tiếp theo (ví dụ: nơi nộp, hồ sơ, lệ phí, thời gian xử lý)?

```text
Nơi nộp hồ sơ

Kênh đăng ký lịch (nếu cần)
- Đăng ký lịch qua Cổng dịch vụ
công/VNeID.

Cơ quan/điểm tiếp nhận
- Nộp tại cơ quan quản lý căn cước hoặc
điểm thu nhận Công an cấp xã được triển
khai.
Trang 1/1 | Tiếp / Trước
```

### turn_009_20261017_085854_192

- STT cũ: Tôi muốn chuyển mục đích sử dụng đất.
- STT mới: Tôi muốn chuyển mục đích sử dụng đất.
- Mode cũ: switch_confirm
- Mode mới: switch_confirm
- Âm thanh: Anh/chị muốn chuyển sang thủ tục “chuyển mục đích sử dụng đất” (thay cho nội dung cấp căn cước đang tra cứu) đúng không?

```text
A. Đúng, chuyển sang thủ tục chuyển mục
đích sử dụng đất
B. Không, tôi vẫn hỏi thủ tục cấp căn
cước
Trang 1/1 | Tiếp / Trước
```

### turn_010_20261017_085922_411

- STT cũ: Có, tôi muốn chuyển sang thủ tục sử dụng đất.
- STT mới: Có, tôi muốn chuyển sang thủ tục sử dụng đất.
- Mode cũ: question
- Mode mới: question
- Âm thanh: Để hướng dẫn đúng trường hợp, anh/chị cho biết mình thuộc tình huống nào?

```text
A. Đề nghị Nhà nước giao đất/cho thuê
đất
B. Cần quyết định về mục đích/hình
thức/thời hạn sử dụng (có chuyển mục
đích)
C. Đổi mục đích không phải xin phép,
tiếp tục đất nông nghiệp hoặc đã có
quyết định thu hồi
Trang 1/1 | Tiếp / Trước
```

### turn_011_20261017_085947_974

- STT cũ: tôi muốn biết về hồ sơ cần chuẩn bị là gì?
- STT mới: tôi muốn biết về hồ sơ cần chuẩn bị là gì?
- Mode cũ: question
- Mode mới: question
- Âm thanh: Để trả lời đúng hồ sơ cần chuẩn bị, anh/chị cho biết mình thuộc trường hợp nào trong nhóm này?

```text
A. Đề nghị Nhà nước giao đất/cho thuê
đất
B. Cần quyết định về mục đích/hình
thức/thời hạn sử dụng (có chuyển mục
đích)
C. Đổi mục đích không phải xin phép,
tiếp tục đất nông nghiệp hoặc đã có
quyết định thu hồi
Trang 1/1 | Tiếp / Trước
```

### turn_012_20261017_090013_339

- STT cũ: Chuyển mục đích, chuyển hình thức sử dụng, gia hạn hoặc điều chỉnh thời hạn sử dụng đất
- STT mới: Chuyển mục đích, chuyển hình thức sử dụng, gia hạn hoặc điều chỉnh thời hạn sử dụng đất.
- Mode cũ: question
- Mode mới: question
- Âm thanh: Để chốt đúng bộ hồ sơ, anh/chị đang làm theo trường hợp nào?

```text
A. Chuyển mục đích sử dụng đất thuộc
diện phải xin phép
B. Chuyển hình thức sử dụng đất
C. Xin gia hạn thời hạn sử dụng đất
D. Dự án được điều chỉnh thời hạn sử
dụng đất
Trang 1/1 | Tiếp / Trước
```

### turn_013_20261017_090034_058

- STT cũ: chuyển hình thức sử dụng đất
- STT mới: Chuyển hình thức sử dụng đất
- Mode cũ: question
- Mode mới: answer
- Âm thanh: Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Hồ sơ chuyển hình thức sử dụng đất

Giấy tờ/biểu mẫu cần chuẩn bị
- Mẫu 03.
- Giấy tờ quyền/quyết định.
Trang 1/1 | Tiếp / Trước
```

### turn_014_20261017_090054_032

- STT cũ: Hồ sơ cần chuẩn bị là gì?
- STT mới: Hồ sơ cần chuẩn bị là gì?
- Mode cũ: answer
- Mode mới: answer
- Âm thanh: Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Hồ sơ chuyển hình thức sử dụng đất

Giấy tờ/biểu mẫu cần chuẩn bị
- Mẫu 03.
- Giấy tờ quyền/quyết định.
Trang 1/1 | Tiếp / Trước
```

### turn_015_20261017_090119_051

- STT cũ: Tôi muốn hỏi thêm về thời hạn xử lý.
- STT mới: tôi muốn hỏi thêm về thời hạn xử lý.
- Mode cũ: transport_error
- Mode mới: answer
- Âm thanh: Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Thời hạn xử lý (cách tính) — Đăng ký
biến động đất đai

Cách tính thời hạn
- Thời hạn được tính theo ngày làm việc,
kể từ khi nhận đủ hồ sơ đầy đủ, hợp lệ.

Các khoảng thời gian không tính vào thời
hạn
- Không tính: thời gian xác định nghĩa
Trang 1/2 | Tiếp / Trước
```

### turn_016_20261017_090141_676

- STT cũ: thời hạn xử lý
- STT mới: thời hạn xử lý
- Mode cũ: answer
- Mode mới: answer
- Âm thanh: Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Thời hạn xử lý — Đăng ký biến động đất
đai (chuyển hình thức sử dụng đất)

Cách tính thời hạn
- Thời hạn được tính theo ngày làm việc,
kể từ khi nhận đủ hồ sơ đầy đủ, hợp lệ.

Các khoảng thời gian không tính vào thời
hạn
- Không tính: thời gian xác định nghĩa
Trang 1/2 | Tiếp / Trước
```

### turn_017_20261017_090204_777

- STT cũ: 
- STT mới: 
- Mode cũ: no_speech_detected
- Mode mới: no_speech_detected
- Âm thanh: 

```text

```

### turn_018_20261017_090212_932

- STT cũ: Đây nơi nạp hồ sơ là ở đâu?
- STT mới: Đây nơi nạp hồ sơ là ở đâu?
- Mode cũ: transport_error
- Mode mới: answer
- Âm thanh: Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Nơi nộp hồ sơ — Đăng ký biến động đất
đai (chuyển hình thức sử dụng đất)

Kênh nộp trực tuyến (nếu có cung cấp)
- Nộp trực tuyến qua Cổng dịch vụ công
quốc gia nếu thủ tục được cung cấp.

Nơi tiếp nhận hồ sơ
- Trung tâm phục vụ hành chính công các
cấp; hoặc Chi nhánh Văn phòng đăng ký
Trang 1/2 | Tiếp / Trước
```

### turn_019_20261017_090227_844

- STT cũ: 
- STT mới: 
- Mode cũ: no_speech_detected
- Mode mới: no_speech_detected
- Âm thanh: 

```text

```

### turn_020_20261017_090230_923

- STT cũ: Thơ là ở đâu?
- STT mới: Thư là ở đâu?
- Mode cũ: question
- Mode mới: answer
- Âm thanh: Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Nơi nộp hồ sơ — Đăng ký biến động đất
đai (chuyển hình thức sử dụng đất)

Kênh nộp trực tuyến (nếu có cung cấp)
- Nộp trực tuyến qua Cổng dịch vụ công
quốc gia nếu thủ tục được cung cấp.

Nơi tiếp nhận hồ sơ
- Trung tâm phục vụ hành chính công các
cấp; hoặc Chi nhánh Văn phòng đăng ký
Trang 1/2 | Tiếp / Trước
```

### turn_021_20261017_090251_024

- STT cũ: Nơi nộp hồ sơ là ở đâu?
- STT mới: nơi nộp hồ sơ là ở đâu?
- Mode cũ: transport_error
- Mode mới: answer
- Âm thanh: Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Nơi nộp hồ sơ — Đăng ký biến động đất
đai (chuyển hình thức sử dụng đất)

Kênh nộp trực tuyến (nếu thủ tục có cung
cấp)
- Nộp trực tuyến qua Cổng dịch vụ công
quốc gia (nếu thủ tục được cung cấp).

Nơi tiếp nhận hồ sơ
- Trung tâm phục vụ hành chính công các
Trang 1/2 | Tiếp / Trước
```

## 20261017_092026_995

29 lượt; {'question': 18, 'clarification': 6, 'page': 2, 'switch_confirm': 3}; 54 calls xử lý hội thoại; token {'input_tokens': 215414, 'output_tokens': 10932, 'total_tokens': 226346}. Token này không bao gồm STT, lượt thử ban đầu và các kiểm tra riêng.

### turn_001_20261017_092047_406

- STT cũ: Tôi muốn chuyển trường cho con tôi.
- STT mới: Tôi muốn chuyển trường cho con tôi.
- Mode cũ: question
- Mode mới: question
- Âm thanh: Để tra đúng thủ tục, anh/chị cho biết trường hợp của con thuộc nhóm nào?

```text
A. Học sinh đang học trong nước; chuyển
trường thông thường
B. Học sinh Việt Nam từ nước ngoài về
C. Chuyển từ THPT tư thục sang công lập
hoặc trường chuyên biệt
Trang 1/1 | Tiếp / Trước
```

### turn_002_20261017_092123_265

- STT cũ: ờ Học sinh Việt Nam chuyển từ nước ngoài về
- STT mới: học sinh Việt Nam chuyển từ nước ngoài về
- Mode cũ: question
- Mode mới: question
- Âm thanh: Để áp đúng quy trình/giấy tờ cho trường hợp học sinh Việt Nam từ nước ngoài về, anh/chị cho biết 3 ý: quốc tịch của học sinh; chương trình đang học; và học ở trường nước ngoài hay trường tại Việt Nam dạy chương trình nước ngoài/quốc tế?

```text
A. Học sinh quốc tịch Việt Nam (vui lòng
nói thêm chương trình đang học và học ở
nước ngoài hay ở VN dạy CT nước
ngoài/quốc tế)
B. Học sinh có song tịch/khác quốc tịch
Việt Nam (vui lòng nói thêm chương trình
đang học và học ở nước ngoài hay ở VN
dạy CT nước ngoài/quốc tế)
C. Không rõ/Chưa có đủ thông tin 3 ý
trên
Trang 1/1 | Tiếp / Trước
```

### turn_003_20261017_092146_407

- STT cũ: hồ sơ cần chuẩn bị là gì?
- STT mới: Hồ sơ cần chuẩn bị là gì?
- Mode cũ: answer
- Mode mới: question
- Âm thanh: Để trả lời đúng “hồ sơ cần chuẩn bị” cho trường hợp học sinh Việt Nam từ nước ngoài về, anh/chị vui lòng cho biết 3 thông tin: (1) quốc tịch của học sinh; (2) chương trình đang học; (3) học ở trường nước ngoài hay trường tại Việt Nam dạy chương trình nước ngoài/quốc tế?

```text
A. Học sinh quốc tịch Việt Nam
B. Học sinh song tịch/khác quốc tịch
Việt Nam
C. Chưa rõ/chưa có đủ 3 thông tin trên
Trang 1/1 | Tiếp / Trước
```

### turn_004_20261017_092215_287

- STT cũ: à tôi nhầm là chỉ trường bình thường ở Việt Nam
- STT mới: à tôi nhầm là chỉ trường bình thường ở Việt Nam.
- Mode cũ: switch_confirm
- Mode mới: question
- Âm thanh: Anh/chị xác nhận giúp: chuyển trường trong nước giữa các trường phổ thông bình thường, hay là đang từ trường tại Việt Nam dạy chương trình nước ngoài/quốc tế chuyển sang chương trình Việt Nam?

```text
A. Chuyển trường thông thường trong nước
(trường phổ thông bình thường)
B. Từ trường tại Việt Nam dạy chương
trình nước ngoài/quốc tế chuyển sang
chương trình Việt Nam
C. Khác/Chưa rõ
Trang 1/1 | Tiếp / Trước
```

### turn_005_20261017_092246_189

- STT cũ: Có đổi sang chuyển trường bình thường trong Việt Nam.
- STT mới: Có đổi sang chuyển trường bình thường trong Việt Nam.
- Mode cũ: question
- Mode mới: question
- Âm thanh: Anh/chị cho biết học sinh đang học cấp nào để mình cung cấp đúng hồ sơ chuyển trường trong nước?

```text
A. Tiểu học
B. THCS
C. THPT
Trang 1/1 | Tiếp / Trước
```

### turn_006_20261017_092311_516

- STT cũ: Cách bước được kỳ như thế nào?
- STT mới: cách book được tiền như thế nào?
- Mode cũ: answer
- Mode mới: question
- Âm thanh: Anh/chị cho biết học sinh đang học cấp nào (tiểu học/THCS/THPT) để mình tra đúng phần chi phí chuyển trường?

```text
A. Tiểu học
B. THCS
C. THPT
Trang 1/1 | Tiếp / Trước
```

### turn_007_20261017_092348_165

- STT cũ: 뱁
- STT mới: 네.
- Mode cũ: no_speech_detected
- Mode mới: clarification
- Âm thanh: Anh/chị chọn cấp học nào: Tiểu học, THCS hay THPT?

```text
A. Tiểu học
B. THCS
C. THPT
Trang 1/1 | Tiếp / Trước
```

### turn_008_20261017_092357_425

- STT cũ: tiếp theo
- STT mới: tiếp theo
- Mode cũ: page
- Mode mới: question
- Âm thanh: Anh/chị cho biết học sinh đang học cấp nào (tiểu học/THCS/THPT) để mình tra đúng phần hồ sơ và chi phí chuyển trường?

```text
A. Tiểu học
B. THCS
C. THPT
Trang 1/1 | Tiếp / Trước
```

### turn_009_20261017_092405_420

- STT cũ: trước đó
- STT mới: Trước đó
- Mode cũ: page
- Mode mới: page
- Âm thanh: 

```text
A. Tiểu học
B. THCS
C. THPT
Trang 1/1 | Tiếp / Trước
```

### turn_010_20261017_092413_865

- STT cũ: 跌頭
- STT mới: 接著
- Mode cũ: no_speech_detected
- Mode mới: clarification
- Âm thanh: Bạn muốn chọn cấp học nào để tiếp tục (Tiểu học/THCS/THPT)?

```text
A. Tiểu học
B. THCS
C. THPT
Trang 1/1 | Tiếp / Trước
```

### turn_011_20261017_092420_968

- STT cũ: 디테일
- STT mới: 디테일
- Mode cũ: no_speech_detected
- Mode mới: clarification
- Âm thanh: Anh/chị muốn xem “chi tiết” phần nào, hay vui lòng chọn cấp học của học sinh: Tiểu học, THCS hay THPT?

```text
A. Tiểu học
B. THCS
C. THPT
Trang 1/1 | Tiếp / Trước
```

### turn_012_20261017_092430_031

- STT cũ: dip-tail
- STT mới: 深體
- Mode cũ: question
- Mode mới: clarification
- Âm thanh: Anh/chị muốn chọn cấp học nào cho học sinh: Tiểu học, THCS hay THPT?

```text
A. Tiểu học
B. THCS
C. THPT
Trang 1/1 | Tiếp / Trước
```

### turn_013_20261017_092451_322

- STT cũ: hồ sơ cần chuẩn bị là gì?
- STT mới: hồ sơ cần chuẩn bị là gì?
- Mode cũ: answer
- Mode mới: question
- Âm thanh: Anh/chị cho biết học sinh đang học cấp nào (tiểu học/THCS/THPT) để mình tra đúng hồ sơ chuyển trường?

```text
A. Tiểu học
B. THCS
C. THPT
Trang 1/1 | Tiếp / Trước
```

### turn_014_20261017_092516_057

- STT cũ: DeepL
- STT mới: DeepL
- Mode cũ: question
- Mode mới: clarification
- Âm thanh: Anh/chị vui lòng chọn cấp học của học sinh: Tiểu học, THCS hay THPT?

```text
A. Tiểu học
B. THCS
C. THPT
Trang 1/1 | Tiếp / Trước
```

### turn_015_20261017_092532_873

- STT cũ: Tôi muốn làm căn cước công dân.
- STT mới: tôi muốn làm căn cước công dân.
- Mode cũ: switch_confirm
- Mode mới: switch_confirm
- Âm thanh: Anh/chị xác nhận giúp: mình chuyển sang hỏi thủ tục làm căn cước công dân (thay vì thủ tục chuyển trường) đúng không?

```text
A. Đúng, chuyển sang làm căn cước công
dân
B. Không, vẫn hỏi thủ tục chuyển trường
Trang 1/1 | Tiếp / Trước
```

### turn_016_20261017_092557_841

- STT cũ: Có, chuyển sang thủ tục căn cứ công dân cho tôi.
- STT mới: Có chuyển sang thủ tục căn cứ công dân cho tôi.
- Mode cũ: question
- Mode mới: switch_confirm
- Âm thanh: Anh/chị xác nhận giúp: mình chuyển sang hỏi thủ tục làm căn cước công dân (thay vì thủ tục chuyển trường) đúng không?

```text
A. Đúng, chuyển sang làm căn cước công
dân
B. Không, vẫn hỏi thủ tục chuyển trường
Trang 1/1 | Tiếp / Trước
```

### turn_017_20261017_092618_591

- STT cũ: Cấp căn cước công dân lần đầu
- STT mới: cấp căn cước công dân lần đầu
- Mode cũ: question
- Mode mới: switch_confirm
- Âm thanh: Anh/chị xác nhận giúp: mình chuyển sang hỏi thủ tục cấp căn cước công dân lần đầu (thay vì thủ tục chuyển trường) đúng không?

```text
A. Đúng, chuyển sang cấp căn cước công
dân lần đầu
B. Không, vẫn hỏi thủ tục chuyển trường
Trang 1/1 | Tiếp / Trước
```

### turn_018_20261017_092638_221

- STT cũ: Hồ sơ cần chuẩn bị là gì?
- STT mới: Hồ sơ cần chuẩn bị là gì?
- Mode cũ: question
- Mode mới: question
- Âm thanh: Để em trả đúng “hồ sơ cần chuẩn bị”, anh/chị xác nhận giúp mình muốn hỏi hồ sơ của thủ tục nào ạ?

```text
A. Đúng, chuyển sang cấp căn cước công
dân lần đầu
B. Không, vẫn hỏi hồ sơ thủ tục chuyển
trường
Trang 1/1 | Tiếp / Trước
```

### turn_019_20261017_092654_816

- STT cũ: de
- STT mới: The
- Mode cũ: question
- Mode mới: clarification
- Âm thanh: Anh/chị muốn chọn A hay B ạ?

```text
A. Đúng, chuyển sang cấp căn cước công
dân lần đầu
B. Không, vẫn hỏi hồ sơ thủ tục chuyển
trường
Trang 1/1 | Tiếp / Trước
```

### turn_020_20261017_092713_888

- STT cũ: từ sáu tới mười bốn tuổi
- STT mới: Từ sáu tới mười bốn tuổi
- Mode cũ: question
- Mode mới: question
- Âm thanh: Anh/chị đang muốn hỏi cho thủ tục nào: chuyển trường hay chuyển sang cấp căn cước công dân lần đầu?

```text
A. Đúng, chuyển sang cấp căn cước công
dân lần đầu
B. Không, vẫn hỏi thủ tục chuyển trường
(nhóm tuổi 6–14)
Trang 1/1 | Tiếp / Trước
```

### turn_021_20261017_092738_387

- STT cũ: Có, xem hồ sơ cần chuẩn bị.
- STT mới: Có xem hồ sơ cần chuẩn bị.
- Mode cũ: answer
- Mode mới: question
- Âm thanh: Anh/chị muốn xem hồ sơ cần chuẩn bị cho thủ tục nào?

```text
A. Cấp căn cước công dân lần đầu
B. Chuyển trường thông thường trong nước
(nhóm tuổi 6–14)
Trang 1/1 | Tiếp / Trước
```

### turn_022_20261017_092801_927

- STT cũ: tiếp theo cho tôi.
- STT mới: tiếp theo cho tôi
- Mode cũ: page
- Mode mới: question
- Âm thanh: Anh/chị muốn xem tiếp (hồ sơ, phí) cho thủ tục nào?

```text
A. Cấp căn cước công dân lần đầu
B. Chuyển trường thông thường trong nước
(nhóm tuổi 6–14)
Trang 1/1 | Tiếp / Trước
```

### turn_023_20261017_092812_154

- STT cũ: Tiếp theo cho tôi.
- STT mới: tiếp theo cho tôi
- Mode cũ: page
- Mode mới: question
- Âm thanh: Để tôi hiển thị đúng phần “hồ sơ” và “phí”, anh/chị đang muốn xem cho thủ tục nào?

```text
A. Cấp căn cước công dân lần đầu
B. Chuyển trường thông thường trong nước
(nhóm tuổi 6–14)
Trang 1/1 | Tiếp / Trước
```

### turn_024_20261017_092820_946

- STT cũ: Tiếp theo cho tôi.
- STT mới: tiếp theo cho tôi.
- Mode cũ: page
- Mode mới: question
- Âm thanh: Anh/chị muốn “tiếp theo” cho thủ tục nào: chuyển trường (6–14 tuổi) hay cấp căn cước công dân lần đầu?

```text
A. Cấp căn cước công dân lần đầu
B. Chuyển trường thông thường trong nước
(nhóm tuổi 6–14)
Trang 1/1 | Tiếp / Trước
```

### turn_025_20261017_092828_520

- STT cũ: Trước đó cho tôi
- STT mới: Trước đó cho tôi
- Mode cũ: page
- Mode mới: page
- Âm thanh: 

```text
A. Cấp căn cước công dân lần đầu
B. Chuyển trường thông thường trong nước
(nhóm tuổi 6–14)
Trang 1/1 | Tiếp / Trước
```

### turn_026_20261017_092844_199

- STT cũ: Tiếp theo cho tôi.
- STT mới: tiếp theo cho tôi.
- Mode cũ: page
- Mode mới: question
- Âm thanh: Anh/chị muốn “tiếp theo” cho thủ tục nào?

```text
A. Cấp căn cước công dân lần đầu
B. Chuyển trường thông thường trong nước
(nhóm tuổi 6–14)
Trang 1/1 | Tiếp / Trước
```

### turn_027_20261017_092856_922

- STT cũ: Tôi muốn đăng ký khai sinh.
- STT mới: Tôi muốn đăng ký khai sinh.
- Mode cũ: switch_confirm
- Mode mới: question
- Âm thanh: Anh/chị đang muốn chuyển sang thủ tục “đăng ký khai sinh” đúng không?

```text
A. Đúng, chuyển sang đăng ký khai sinh
B. Không, tôi muốn tiếp tục thủ tục
trước đó (chuyển trường/CCCD lần đầu)
C. Tôi muốn nói rõ lại nhu cầu khác
Trang 1/1 | Tiếp / Trước
```

### turn_028_20261017_092929_105

- STT cũ: Có chuyển sang thủ tục đăng ký khai sinh.
- STT mới: Có chuyển sang thủ tục đăng ký khai sinh
- Mode cũ: question
- Mode mới: question
- Âm thanh: Anh/chị có muốn chuyển sang thủ tục “đăng ký khai sinh” không?

```text
A. Đúng, chuyển sang đăng ký khai sinh
B. Không, tôi muốn tiếp tục thủ tục
trước đó (chuyển trường/CCCD lần đầu)
C. Tôi muốn nói rõ lại nhu cầu khác
Trang 1/1 | Tiếp / Trước
```

### turn_029_20261017_092949_678

- STT cũ: hướng dẫn
- STT mới: Hướng dẫn
- Mode cũ: transport_error
- Mode mới: question
- Âm thanh: Để hướng dẫn đúng thủ tục, anh/chị xác nhận giúp: có chuyển sang “đăng ký khai sinh” không?

```text
A. Đúng, chuyển sang đăng ký khai sinh
B. Không, tôi muốn hướng dẫn thủ tục
chuyển trường trong nước
C. Tôi muốn nói rõ lại nhu cầu khác
Trang 1/1 | Tiếp / Trước
```

