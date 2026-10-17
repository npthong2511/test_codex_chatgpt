# V17.5 — replay hai phiên qua API

Đầu vào giữ nguyên các transcript đã dùng ở replay V17.4; model gpt-5.2, không chạy lại STT/TTS/Unity. Hai hội thoại có câu trả lời được ghi sẵn: nếu bản mới hỏi khác thì bản ghi không trả lời thích ứng. Không coi số lỗi giảm là chứng nhận đúng toàn bộ nghiệp vụ. Baseline V17.4 là replay đầy đủ trước retest đoạn cuối đã báo cáo, không phải bản ghi người dùng V17.3.

## 20261017_085528_390

```json
{
  "turns": 21,
  "modes": {
    "question": 7,
    "answer": 8,
    "clarification": 3,
    "switch_confirm": 1,
    "no_speech_detected": 2
  },
  "codes": {},
  "calls": 52,
  "usage": {
    "input_tokens": 287603,
    "output_tokens": 12122,
    "total_tokens": 299725
  },
  "actions": {
    "load": 12,
    "respond": 16,
    "continue": 15,
    "open_topic": 5,
    "unclear": 3,
    "restart": 1
  },
  "baseline_modes": {
    "question": 7,
    "answer": 9,
    "clarification": 2,
    "switch_confirm": 1,
    "no_speech_detected": 2
  }
}
```

### turn_001_20261017_085545_067

**Người dân:** tôi muốn làm căn cứ công dân

**Mode cũ → mới:** question → question

**Âm thanh:** Để hướng dẫn đúng, anh/chị cho biết mình làm căn cước thuộc trường hợp nào?

```text
Xác định trường hợp làm căn cước

Cần làm rõ
- Thông tin hướng dẫn/hồ sơ/phí… phụ
thuộc việc anh/chị: cấp lần đầu, cấp đổi
hay cấp lại (mất thẻ).

A. Cấp căn cước lần đầu (chưa từng có
thẻ căn cước)
B. Cấp đổi (đã có thẻ; đổi do đến
Trang 1/2 | Tiếp / Trước
```

### turn_002_20261017_085606_641

**Người dân:** cấp lần đầu

**Mode cũ → mới:** question → question

**Âm thanh:** Để hướng dẫn đúng thủ tục cấp căn cước lần đầu, anh/chị cho biết người đi làm căn cước thuộc nhóm tuổi nào?

```text
Chọn nhóm tuổi khi cấp căn cước lần đầu

Cần làm rõ
- Quy trình/hồ sơ/phí… sẽ khác theo nhóm
tuổi của người được cấp căn cước.

A. Dưới 06 tuổi
B. Từ đủ 06 đến dưới 14 tuổi
C. Từ đủ 14 tuổi
Trang 1/1 | Tiếp / Trước
```

### turn_003_20261017_085627_945

**Người dân:** Hồ sơ cần chuẩn bị là gì?

**Mode cũ → mới:** question → question

**Âm thanh:** Để trả lời đúng “hồ sơ cần chuẩn bị” khi cấp căn cước lần đầu, anh/chị cho biết người đi làm căn cước thuộc nhóm tuổi nào?

```text
Chọn nhóm tuổi để xác định hồ sơ cấp căn
cước lần đầu

Vì sao cần thông tin này
- Hồ sơ cần chuẩn bị phụ thuộc nhóm tuổi
của người được cấp (dưới 06; 06–<14; từ
đủ 14).

A. Dưới 06 tuổi
B. Từ đủ 06 đến dưới 14 tuổi
Trang 1/2 | Tiếp / Trước
```

### turn_004_20261017_085646_982

**Người dân:** Dưới sáu tuổi

**Mode cũ → mới:** answer → answer

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Hồ sơ cấp căn cước lần đầu cho trẻ dưới
06 tuổi

Giấy tờ/nghiệp vụ người đại diện cần
thực hiện
- Kiểm tra thông tin của trẻ trong Cơ sở
dữ liệu quốc gia về dân cư (khi thực
hiện nộp hồ sơ trực tuyến).

Thành phần phát sinh khi dữ liệu chưa
Trang 1/3 | Tiếp / Trước
```

### turn_005_20261017_085723_034

**Người dân:** detail

**Mode cũ → mới:** question → clarification

**Âm thanh:** Anh/chị muốn xem chi tiết nội dung nào (ví dụ: hồ sơ, thủ tục, hoặc phần vừa hiển thị)?

```text
Hồ sơ cấp căn cước lần đầu cho trẻ dưới
06 tuổi

Giấy tờ/nghiệp vụ người đại diện cần
thực hiện
- Kiểm tra thông tin của trẻ trong Cơ sở
dữ liệu quốc gia về dân cư (khi thực
hiện nộp hồ sơ trực tuyến).

Thành phần phát sinh khi dữ liệu chưa
Trang 1/3 | Tiếp / Trước
```

### turn_006_20261017_085756_566

**Người dân:** 那拿後色

**Mode cũ → mới:** clarification → clarification

**Âm thanh:** Anh/chị vui lòng nhập lại rõ hơn (tiếng Việt) hoặc cho biết anh/chị muốn xem trang mấy (1–3)?

```text
Hồ sơ cấp căn cước lần đầu cho trẻ dưới
06 tuổi

Giấy tờ/nghiệp vụ người đại diện cần
thực hiện
- Kiểm tra thông tin của trẻ trong Cơ sở
dữ liệu quốc gia về dân cư (khi thực
hiện nộp hồ sơ trực tuyến).

Thành phần phát sinh khi dữ liệu chưa
Trang 1/3 | Tiếp / Trước
```

### turn_007_20261017_085807_174

**Người dân:** Nơi đọc hồ sơ là gì?

**Mode cũ → mới:** answer → answer

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Nơi nộp hồ sơ (cấp căn cước lần đầu cho
trẻ dưới 06 tuổi)

Kênh/ cách nộp
- Có thể đăng ký lịch qua Cổng dịch vụ
công hoặc ứng dụng VNeID.

Cơ quan/đơn vị tiếp nhận
- Nộp tại cơ quan quản lý căn cước hoặc
điểm thu nhận do Công an cấp xã được
Trang 1/2 | Tiếp / Trước
```

### turn_008_20261017_085842_256

**Người dân:** 接頭

**Mode cũ → mới:** clarification → clarification

**Âm thanh:** Anh/chị muốn tiếp tục xem trang tiếp theo hay muốn hỏi thêm nội dung nào? Vui lòng nói rõ yêu cầu.

```text
Nơi nộp hồ sơ (cấp căn cước lần đầu cho
trẻ dưới 06 tuổi)

Kênh/ cách nộp
- Có thể đăng ký lịch qua Cổng dịch vụ
công hoặc ứng dụng VNeID.

Cơ quan/đơn vị tiếp nhận
- Nộp tại cơ quan quản lý căn cước hoặc
điểm thu nhận do Công an cấp xã được
Trang 1/2 | Tiếp / Trước
```

### turn_009_20261017_085854_192

**Người dân:** Tôi muốn chuyển mục đích sử dụng đất.

**Mode cũ → mới:** switch_confirm → switch_confirm

**Âm thanh:** Anh/chị đang muốn đổi sang thủ tục “chuyển mục đích sử dụng đất” (không phải cấp căn cước) đúng không?

```text
A. Đúng, chuyển sang “chuyển mục đích sử
dụng đất”.
B. Không, tôi vẫn hỏi về cấp căn cước;
cho tôi xem tiếp nội dung.
Trang 1/1 | Tiếp / Trước
```

### turn_010_20261017_085922_411

**Người dân:** Có, tôi muốn chuyển sang thủ tục sử dụng đất.

**Mode cũ → mới:** question → question

**Âm thanh:** Để trả lời đúng thủ tục chuyển mục đích sử dụng đất, anh/chị cho biết mình thuộc trường hợp nào?

```text
Cần làm rõ tình huống chuyển mục đích sử
dụng đất

A. Xin Nhà nước giao đất/cho thuê đất
B. Cần quyết định cho phép chuyển mục
đích/chuyển hình thức sử dụng đất hoặc
gia hạn/điều chỉnh thời hạn sử dụng
C. Đổi mục đích không phải xin phép
nhưng phải đăng ký biến động / tiếp tục
đất nông nghiệp / đã có quyết định thu
Trang 1/2 | Tiếp / Trước
```

### turn_011_20261017_085947_974

**Người dân:** tôi muốn biết về hồ sơ cần chuẩn bị là gì?

**Mode cũ → mới:** question → question

**Âm thanh:** Để cung cấp đúng bộ hồ sơ cần chuẩn bị, anh/chị cho biết mình thuộc trường hợp nào?

```text
Chọn tình huống chuyển mục đích sử dụng
đất

A. Đề nghị Nhà nước giao đất/cho thuê
đất
B. Cần quyết định cho phép chuyển mục
đích/chuyển hình thức sử dụng đất hoặc
gia hạn/điều chỉnh thời hạn sử dụng
C. Đổi mục đích không phải xin phép
nhưng phải đăng ký biến động / tiếp tục
Trang 1/2 | Tiếp / Trước
```

### turn_012_20261017_090013_339

**Người dân:** Chuyển mục đích, chuyển hình thức sử dụng, gia hạn hoặc điều chỉnh thời hạn sử dụng đất.

**Mode cũ → mới:** question → question

**Âm thanh:** Anh/chị cho biết cụ thể anh/chị làm việc nào trong 4 việc dưới đây để mình chốt đúng bộ hồ sơ?

```text
Chọn tiểu trường hợp để lấy đúng bộ hồ
sơ

A. Chuyển mục đích sử dụng đất thuộc
diện phải xin phép
B. Chuyển hình thức sử dụng đất
C. Gia hạn sử dụng đất
D. Điều chỉnh thời hạn sử dụng đất của
dự án
Trang 1/1 | Tiếp / Trước
```

### turn_013_20261017_090034_058

**Người dân:** Chuyển hình thức sử dụng đất

**Mode cũ → mới:** answer → answer

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Hồ sơ – Chuyển hình thức sử dụng đất

Giấy tờ cần chuẩn bị
- Mẫu số 03.
- Giấy tờ về quyền sử dụng đất/quyết
định liên quan.

Phần thông tin chưa thấy trong nguồn
đang mở
- Nguồn hiện có chưa nêu rõ thành phần
Trang 1/2 | Tiếp / Trước
```

### turn_014_20261017_090054_032

**Người dân:** Hồ sơ cần chuẩn bị là gì?

**Mode cũ → mới:** answer → answer

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Hồ sơ – Chuyển hình thức sử dụng đất

Giấy tờ cần chuẩn bị
- Mẫu số 03.
- Giấy tờ về quyền sử dụng đất/quyết
định liên quan.

Phần thông tin chưa thấy trong nguồn
đang mở
- Nguồn hiện có chưa nêu rõ thành phần
Trang 1/2 | Tiếp / Trước
```

### turn_015_20261017_090119_051

**Người dân:** tôi muốn hỏi thêm về thời hạn xử lý.

**Mode cũ → mới:** answer → answer

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Thời hạn xử lý – Chuyển hình thức sử
dụng đất

Thời hạn giải quyết
- Theo nguồn đang có, nhóm thủ tục liên
quan tối đa 15 ngày làm việc (theo công
bố địa phương).

Lưu ý về căn cứ xem xét
- Cơ quan quyết định còn xem xét căn cứ
Trang 1/2 | Tiếp / Trước
```

### turn_016_20261017_090141_676

**Người dân:** thời hạn xử lý

**Mode cũ → mới:** answer → answer

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Thời hạn xử lý – Chuyển hình thức sử
dụng đất

Cách tính thời hạn
- Thời hạn được tính theo ngày làm việc,
kể từ khi hồ sơ đầy đủ và hợp lệ.

Trường hợp có thể kéo dài thời hạn (theo
địa bàn)
- Nếu thuộc xã đảo/địa bàn khó khăn/đặc
Trang 1/3 | Tiếp / Trước
```

### turn_017_20261017_090204_777

**Người dân:** 

**Mode cũ → mới:** no_speech_detected → no_speech_detected

**Âm thanh:** 

```text

```

### turn_018_20261017_090212_932

**Người dân:** Đây nơi nạp hồ sơ là ở đâu?

**Mode cũ → mới:** answer → answer

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Nơi nộp hồ sơ – Chuyển hình thức sử dụng
đất

Kênh nộp hồ sơ
- Có thể nộp trực tuyến qua Cổng Dịch vụ
công quốc gia nếu thủ tục đã được cung
cấp trực tuyến.

Nơi tiếp nhận hồ sơ
- Trung tâm Phục vụ hành chính công các
Trang 1/2 | Tiếp / Trước
```

### turn_019_20261017_090227_844

**Người dân:** 

**Mode cũ → mới:** no_speech_detected → no_speech_detected

**Âm thanh:** 

```text

```

### turn_020_20261017_090230_923

**Người dân:** Thư là ở đâu?

**Mode cũ → mới:** answer → question

**Âm thanh:** Anh/chị cho tôi hỏi “thư” ở đây là thư/giấy nào ạ?

```text
Làm rõ nội dung “thư”

- Anh/chị đang hỏi về: (A) nơi nộp hồ
sơ; (B) giấy hẹn/phiếu tiếp nhận trả ở
đâu; (C) thư/thông báo nghĩa vụ tài
chính nhận ở đâu; hay (D) loại “thư”
khác (nêu tên giúp tôi).

A. noi_nop
B. ket_qua
Trang 1/2 | Tiếp / Trước
```

### turn_021_20261017_090251_024

**Người dân:** nơi nộp hồ sơ là ở đâu?

**Mode cũ → mới:** answer → answer

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Nơi nộp hồ sơ (chuyển hình thức sử dụng
đất)

Nơi tiếp nhận hồ sơ
- Trung tâm Phục vụ hành chính công các
cấp hoặc Chi nhánh Văn phòng đăng ký đất
đai (tùy thủ tục).

Kênh nộp
- Có thể nộp trực tuyến qua Cổng Dịch vụ
Trang 1/2 | Tiếp / Trước
```

## 20261017_092026_995

```json
{
  "turns": 29,
  "modes": {
    "question": 12,
    "answer": 5,
    "clarification": 5,
    "page": 6,
    "switch_confirm": 1
  },
  "codes": {},
  "calls": 62,
  "usage": {
    "input_tokens": 271905,
    "output_tokens": 12114,
    "total_tokens": 284019
  },
  "actions": {
    "load": 9,
    "respond": 18,
    "continue": 17,
    "open_topic": 4,
    "restart": 3,
    "unclear": 5,
    "page": 6
  },
  "baseline_modes": {
    "question": 18,
    "clarification": 6,
    "page": 2,
    "switch_confirm": 3
  }
}
```

### turn_001_20261017_092047_406

**Người dân:** Tôi muốn chuyển trường cho con tôi.

**Mode cũ → mới:** question → question

**Âm thanh:** Anh/chị cho biết con anh/chị thuộc trường hợp nào dưới đây để tôi hướng dẫn đúng thủ tục chuyển trường?

```text
A. Học sinh đang học trong nước; chuyển
trường thông thường
B. Học sinh Việt Nam từ nước ngoài về
C. Chuyển từ THPT tư thục sang công lập
hoặc trường chuyên biệt
D. Tuyển sinh đầu cấp, xin học lại sau
nghỉ hoặc học sinh nước ngoài
Trang 1/1 | Tiếp / Trước
```

### turn_002_20261017_092123_265

**Người dân:** học sinh Việt Nam chuyển từ nước ngoài về

**Mode cũ → mới:** question → question

**Âm thanh:** Anh/chị muốn hỏi nội dung nào về trường hợp học sinh Việt Nam từ nước ngoài về?

```text
A. Hướng dẫn (các bước thực hiện)
B. Hồ sơ cần chuẩn bị
D. Nơi nộp hồ sơ
E. Thời hạn
F. Kết quả
Trang 1/1 | Tiếp / Trước
```

### turn_003_20261017_092146_407

**Người dân:** Hồ sơ cần chuẩn bị là gì?

**Mode cũ → mới:** question → answer

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Hồ sơ cần chuẩn bị (học sinh Việt Nam từ
nước ngoài về)

Giấy tờ/Thông tin đang có trong nguồn hồ
sơ
- (Nguồn đang mở chưa liệt kê danh mục
giấy tờ cụ thể cần nộp; hiện chỉ có các
nội dung về xử lý hồ sơ và lưu ý kèm
theo.)

Trang 1/2 | Tiếp / Trước
```

### turn_004_20261017_092215_287

**Người dân:** à tôi nhầm là chỉ trường bình thường ở Việt Nam.

**Mode cũ → mới:** question → question

**Âm thanh:** Anh/chị xác nhận giúp: mình muốn chuyển sang trường hợp chuyển trường thông thường trong nước (không phải từ nước ngoài về) đúng không?

```text
A. Đúng, chuyển trường trong nước
(trường hợp thông thường)
B. Không, vẫn là học sinh từ nước ngoài
về
C. Khác (mô tả ngắn giúp tôi: chuyển
cấp/đầu cấp, tư thục sang công lập, hoặc
trường hợp khác)
Trang 1/1 | Tiếp / Trước
```

### turn_005_20261017_092246_189

**Người dân:** Có đổi sang chuyển trường bình thường trong Việt Nam.

**Mode cũ → mới:** question → question

**Âm thanh:** Anh/chị muốn xem nội dung nào của trường hợp P22.C01?

```text
Chọn mục cần tra cứu

A. Các bước thực hiện
B. Hồ sơ
C. Phí, lệ phí
D. Nơi nộp hồ sơ
E. Thời hạn
F. Kết quả
G. Điều kiện
Trang 1/1 | Tiếp / Trước
```

### turn_006_20261017_092311_516

**Người dân:** cách book được tiền như thế nào?

**Mode cũ → mới:** question → answer

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Phí/tiền khi làm thủ tục chuyển trường
(P22.C01)

Mức thu/lưu ý về tiền
- Không thu lệ phí hành chính đối với
thủ tục chuyển trường.
- Học phí và các khoản dịch vụ giáo dục
(nếu có phát sinh) là các khoản khác,
không phải lệ phí hành chính của thủ tục
chuyển trường.
Trang 1/1 | Tiếp / Trước
```

### turn_007_20261017_092348_165

**Người dân:** 네.

**Mode cũ → mới:** clarification → clarification

**Âm thanh:** Anh/chị vui lòng nói rõ muốn hỏi thêm nội dung nào về chi phí (ví dụ: lệ phí, chi phí phát sinh, hoặc cách thanh toán)?

```text
Phí/tiền khi làm thủ tục chuyển trường
(P22.C01)

Mức thu/lưu ý về tiền
- Không thu lệ phí hành chính đối với
thủ tục chuyển trường.
- Học phí và các khoản dịch vụ giáo dục
(nếu có phát sinh) là các khoản khác,
không phải lệ phí hành chính của thủ tục
chuyển trường.
Trang 1/1 | Tiếp / Trước
```

### turn_008_20261017_092357_425

**Người dân:** tiếp theo

**Mode cũ → mới:** question → question

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn xem tiếp mục nào?

```text
Chọn nội dung cần xem tiếp (P22.C01)

A. Các bước thực hiện
B. Hồ sơ
D. Nơi nộp hồ sơ
E. Thời hạn
F. Kết quả
G. Điều kiện
Trang 1/1 | Tiếp / Trước
```

### turn_009_20261017_092405_420

**Người dân:** Trước đó

**Mode cũ → mới:** page → page

**Âm thanh:** 

```text
Chọn nội dung cần xem tiếp (P22.C01)

A. Các bước thực hiện
B. Hồ sơ
D. Nơi nộp hồ sơ
E. Thời hạn
F. Kết quả
G. Điều kiện
Trang 1/1 | Tiếp / Trước
```

### turn_010_20261017_092413_865

**Người dân:** 接著

**Mode cũ → mới:** clarification → question

**Âm thanh:** Anh/chị muốn xem tiếp mục nào của thủ tục chuyển trường này?

```text
Chọn nội dung cần xem tiếp (P22.C01)

A. Các bước thực hiện
B. Hồ sơ
D. Nơi nộp hồ sơ
E. Thời hạn
F. Kết quả
G. Điều kiện
Trang 1/1 | Tiếp / Trước
```

### turn_011_20261017_092420_968

**Người dân:** 디테일

**Mode cũ → mới:** clarification → clarification

**Âm thanh:** Anh/chị muốn xem mục nào: các bước, hồ sơ, nơi nộp, thời hạn, kết quả hay điều kiện?

```text
Chọn nội dung cần xem tiếp (P22.C01)

A. Các bước thực hiện
B. Hồ sơ
D. Nơi nộp hồ sơ
E. Thời hạn
F. Kết quả
G. Điều kiện
Trang 1/1 | Tiếp / Trước
```

### turn_012_20261017_092430_031

**Người dân:** 深體

**Mode cũ → mới:** clarification → clarification

**Âm thanh:** Anh/chị muốn xem mục nào: A Các bước, B Hồ sơ, D Nơi nộp, E Thời hạn, F Kết quả, hay G Điều kiện?

```text
Chọn nội dung cần xem tiếp (P22.C01)

A. Các bước thực hiện
B. Hồ sơ
D. Nơi nộp hồ sơ
E. Thời hạn
F. Kết quả
G. Điều kiện
Trang 1/1 | Tiếp / Trước
```

### turn_013_20261017_092451_322

**Người dân:** hồ sơ cần chuẩn bị là gì?

**Mode cũ → mới:** question → answer

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Hồ sơ cần chuẩn bị (chuyển trường thông
thường – học sinh đang học trong nước)

Giấy tờ người dân chuẩn bị
- Đơn chuyển trường/đơn xin chuyển
trường của cha/mẹ hoặc người giám hộ (có
thể nộp bản điện tử hoặc bản giấy; trong
đơn kê khai đầy đủ thông tin cần thiết
của học sinh).
- Bảng tổng hợp kết quả đánh giá giáo
Trang 1/3 | Tiếp / Trước
```

### turn_014_20261017_092516_057

**Người dân:** DeepL

**Mode cũ → mới:** clarification → clarification

**Âm thanh:** Anh/chị muốn tra cứu hay dịch nội dung gì với “DeepL”?

```text
Hồ sơ cần chuẩn bị (chuyển trường thông
thường – học sinh đang học trong nước)

Giấy tờ người dân chuẩn bị
- Đơn chuyển trường/đơn xin chuyển
trường của cha/mẹ hoặc người giám hộ (có
thể nộp bản điện tử hoặc bản giấy; trong
đơn kê khai đầy đủ thông tin cần thiết
của học sinh).
- Bảng tổng hợp kết quả đánh giá giáo
Trang 1/3 | Tiếp / Trước
```

### turn_015_20261017_092532_873

**Người dân:** tôi muốn làm căn cước công dân.

**Mode cũ → mới:** switch_confirm → switch_confirm

**Âm thanh:** Anh/chị muốn chuyển sang hỏi thủ tục làm Căn cước công dân (thay vì hồ sơ chuyển trường) đúng không?

```text
A. Đúng, chuyển sang làm Căn cước công
dân
B. Không, tiếp tục nội dung chuyển
trường (đang xem Hồ sơ/Phí)
Trang 1/1 | Tiếp / Trước
```

### turn_016_20261017_092557_841

**Người dân:** Có chuyển sang thủ tục căn cứ công dân cho tôi.

**Mode cũ → mới:** switch_confirm → question

**Âm thanh:** Anh/chị đang làm căn cước thuộc trường hợp nào?

```text
Chọn trường hợp thực hiện

A. Cấp lần đầu (chưa từng có thẻ căn
cước)
B. Đổi thẻ (đã có thẻ; đến tuổi/thay đổi
thông tin/hư hỏng...)
C. Cấp lại (đã có thẻ nhưng bị mất/thuộc
diện cấp lại)
Trang 1/1 | Tiếp / Trước
```

### turn_017_20261017_092618_591

**Người dân:** cấp căn cước công dân lần đầu

**Mode cũ → mới:** switch_confirm → question

**Âm thanh:** Để hướng dẫn đúng trường hợp cấp căn cước lần đầu, anh/chị cho biết người làm căn cước hiện thuộc nhóm tuổi nào?

```text
Chọn nhóm tuổi (cấp lần đầu)

A. Dưới 06 tuổi
B. Từ đủ 06 đến dưới 14 tuổi
C. Từ đủ 14 tuổi trở lên
Trang 1/1 | Tiếp / Trước
```

### turn_018_20261017_092638_221

**Người dân:** Hồ sơ cần chuẩn bị là gì?

**Mode cũ → mới:** question → question

**Âm thanh:** Để trả đúng “hồ sơ cần chuẩn bị” khi cấp căn cước lần đầu, anh/chị cho biết người làm căn cước thuộc nhóm tuổi nào?

```text
Chọn nhóm tuổi (cấp lần đầu)

A. Dưới 06 tuổi
B. Từ đủ 06 đến dưới 14 tuổi
C. Từ đủ 14 tuổi trở lên
Trang 1/1 | Tiếp / Trước
```

### turn_019_20261017_092654_816

**Người dân:** The

**Mode cũ → mới:** clarification → clarification

**Âm thanh:** Anh/chị chọn nhóm tuổi nào: A (dưới 06), B (06 đến dưới 14) hay C (từ 14 trở lên)?

```text
Chọn nhóm tuổi (cấp lần đầu)

A. Dưới 06 tuổi
B. Từ đủ 06 đến dưới 14 tuổi
C. Từ đủ 14 tuổi trở lên
Trang 1/1 | Tiếp / Trước
```

### turn_020_20261017_092713_888

**Người dân:** Từ sáu tới mười bốn tuổi

**Mode cũ → mới:** question → answer

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Hồ sơ cần chuẩn bị (cấp căn cước lần
đầu; từ đủ 06 đến dưới 14 tuổi)

Giấy tờ/người dân chuẩn bị
- Người đại diện hợp pháp kiểm tra thông
tin và ký xác nhận trên Phiếu thu nhận
thông tin căn cước (CC01) khi cơ quan
thu nhận in ra để đối chiếu.

Giấy tờ chỉ cần khi có điều kiện phát
Trang 1/4 | Tiếp / Trước
```

### turn_021_20261017_092738_387

**Người dân:** Có xem hồ sơ cần chuẩn bị.

**Mode cũ → mới:** question → answer

**Âm thanh:** Tôi xin cung cấp thông tin trên màn hình. Anh/chị muốn hỏi thêm nội dung nào?

```text
Hồ sơ cần chuẩn bị (cấp căn cước lần
đầu; từ đủ 06 đến dưới 14 tuổi)

Giấy tờ/người dân chuẩn bị
- Người đại diện hợp pháp kiểm tra thông
tin và ký xác nhận trên Phiếu thu nhận
thông tin căn cước (CC01) khi cơ quan
thu nhận in ra để đối chiếu.

Giấy tờ chỉ cần khi có điều kiện phát
Trang 1/4 | Tiếp / Trước
```

### turn_022_20261017_092801_927

**Người dân:** tiếp theo cho tôi

**Mode cũ → mới:** question → page

**Âm thanh:** 

```text
sinh
- Giấy tờ chứng minh người đại diện hợp
pháp: chỉ yêu cầu khi dữ liệu hiện có
không chứng minh được quan hệ đại diện;
không mặc định phải nộp trong mọi trường
hợp.

Biểu mẫu/phiếu do cơ quan lập khi tiếp
nhận (nộp trực tiếp)
- Phiếu thu nhận thông tin căn cước
Trang 2/4 | Tiếp / Trước
```

### turn_023_20261017_092812_154

**Người dân:** tiếp theo cho tôi

**Mode cũ → mới:** question → page

**Âm thanh:** 

```text
(CC01) do cơ quan thu nhận in để công
dân/người đại diện kiểm tra, ký xác
nhận.
- Phiếu thu thập thông tin dân cư (DC01)
(nếu có) do cơ quan thu nhận in kèm để
kiểm tra, ký xác nhận.

Số lượng
- 01 bộ hồ sơ (thành phần cụ thể có thể
thay đổi theo hình thức nộp và tình
Trang 3/4 | Tiếp / Trước
```

### turn_024_20261017_092820_946

**Người dân:** tiếp theo cho tôi.

**Mode cũ → mới:** question → page

**Âm thanh:** 

```text
trạng dữ liệu của từng trường hợp).

Lưu ý
- Thông tin người đại diện hợp pháp được
khai thác từ CSDLQG về dân cư và CSDL
căn cước; nếu không khai thác được thì
cơ quan tiếp nhận sẽ hướng dẫn cập
nhật/thu thập thông tin phù hợp.
Trang 4/4 | Tiếp / Trước
```

### turn_025_20261017_092828_520

**Người dân:** Trước đó cho tôi

**Mode cũ → mới:** page → page

**Âm thanh:** 

```text
(CC01) do cơ quan thu nhận in để công
dân/người đại diện kiểm tra, ký xác
nhận.
- Phiếu thu thập thông tin dân cư (DC01)
(nếu có) do cơ quan thu nhận in kèm để
kiểm tra, ký xác nhận.

Số lượng
- 01 bộ hồ sơ (thành phần cụ thể có thể
thay đổi theo hình thức nộp và tình
Trang 3/4 | Tiếp / Trước
```

### turn_026_20261017_092844_199

**Người dân:** tiếp theo cho tôi.

**Mode cũ → mới:** question → page

**Âm thanh:** 

```text
trạng dữ liệu của từng trường hợp).

Lưu ý
- Thông tin người đại diện hợp pháp được
khai thác từ CSDLQG về dân cư và CSDL
căn cước; nếu không khai thác được thì
cơ quan tiếp nhận sẽ hướng dẫn cập
nhật/thu thập thông tin phù hợp.
Trang 4/4 | Tiếp / Trước
```

### turn_027_20261017_092856_922

**Người dân:** Tôi muốn đăng ký khai sinh.

**Mode cũ → mới:** question → question

**Âm thanh:** Anh/chị đang muốn chuyển sang thủ tục Đăng ký khai sinh (thay vì cấp căn cước lần đầu) đúng không?

```text
A. Có, chuyển sang Đăng ký khai sinh
B. Không, tôi vẫn hỏi về cấp căn cước
lần đầu
Trang 1/1 | Tiếp / Trước
```

### turn_028_20261017_092929_105

**Người dân:** Có chuyển sang thủ tục đăng ký khai sinh

**Mode cũ → mới:** question → question

**Âm thanh:** Anh/chị cho tôi biết mình làm “đăng ký khai sinh lần đầu” hay thuộc nhóm “đã có khai sinh rồi (xin bản sao/trích lục, đăng ký lại, cải chính/bổ sung/ghi chú...)”?

```text
Cần xác định đúng trường hợp trước khi
tra hồ sơ/quy trình

- A. Đăng ký khai sinh lần đầu (chưa
từng đăng ký khai sinh)
- B. Đã có khai sinh rồi: xin bản
sao/trích lục, đăng ký lại, cải chính/bổ
sung/ghi chú...
- C. Chưa chắc/khác (mô tả ngắn tình
huống của anh/chị)
Trang 1/2 | Tiếp / Trước
```

### turn_029_20261017_092949_678

**Người dân:** Hướng dẫn

**Mode cũ → mới:** question → question

**Âm thanh:** Để hướng dẫn đúng quy trình, anh/chị cho biết mình làm “đăng ký khai sinh lần đầu” hay là “đã có khai sinh rồi (xin bản sao/trích lục, đăng ký lại, cải chính/bổ sung/ghi chú...)”?

```text
Chọn đúng trường hợp để xem mục Hướng
dẫn

- A. Đăng ký khai sinh lần đầu (chưa
từng đăng ký khai sinh)
- B. Đã có khai sinh rồi: xin bản
sao/trích lục, đăng ký lại, cải chính/bổ
sung/ghi chú...
- C. Chưa chắc/khác (mô tả ngắn tình
huống của anh/chị)
Trang 1/2 | Tiếp / Trước
```

