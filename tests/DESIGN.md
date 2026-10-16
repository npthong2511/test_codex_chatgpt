# V17: 10 hội thoại vận hành

Phương pháp: người dân mô phỏng thủ công, trả lời theo câu hỏi thực tế; không dùng API để sinh người dân hoặc chấm điểm. Mỗi hồ sơ dưới đây cố định trước lượt tiếp theo. Mã lựa chọn được chọn theo bảng thực tế. Đây là kiểm chứng vận hành, không phải bao phủ toàn bộ 137 trường hợp nghiệp vụ hay xác nhận cập nhật pháp luật.

| Mã | Hồ sơ / diễn tiến cố định | Kiểm chứng |
|---|---|---|
| D01 | Mẹ làm căn cước lần đầu cho con; nói sắp lớp 1, sau nói 5 tuổi rồi sửa thành vừa đủ 6 | Không suy tuổi; options; mốc tuổi; quay lại nhánh khi sửa |
| D02 | Đang hỏi căn cước, chuyển khai sinh; xác nhận đồng ý; con sinh VN cha mẹ VN có giấy chứng sinh | Xác nhận đổi; reset dữ kiện; danh mục ROOT chỉ sau đổi |
| D03 | Khai sinh; chen câu hộ kinh doanh rồi từ chối đổi; quay về khai sinh | Giữ trạng thái và tiếp tục câu hỏi đang dở |
| D04 | Mất giấy phép xây dựng; sau sửa giấy bị rách vẫn giữ giấy; hỏi hồ sơ và phí | Sửa sau khi trả lời; bỏ kết luận cũ; thiếu dữ liệu phí |
| D05 | Khai sinh lần đầu, sinh ở nhà tại VN, cha mẹ VN, có kết hôn; không giấy chứng sinh, có người làm chứng | Điều kiện ghép và nhánh bổ sung cùng áp dụng; không đòi cam đoan đồng thời |
| D06 | Vợ chồng cùng góp vốn thành lập HKD mới, chọn vợ làm chủ, vợ tự nộp | Không nhầm cá nhân với hộ gia đình; không nhầm ủy quyền chủ và nộp thay |
| D07 | Mẹ mất giấy khuyết tật, mức độ không thay đổi; con chỉ là con, chưa được xác lập đại diện | Không tự cho con có tư cách đại diện; khoảng trống nguồn |
| D08 | Con học THPT công lập chương trình VN, chuyển tỉnh; hỏi hồ sơ rồi thời gian | Hỏi dần; giữ thủ tục khi hỏi topic khác; nạp mục liên quan |
| D09 | Mở đầu 'làm lại thẻ'; căn cước mất; có lúc nói 'trả lời nhầm' nhưng không nêu dữ kiện; sau sửa thành hỏng | Mơ hồ đầu vào; sửa mơ hồ; lựa chọn; không bịa dữ kiện |
| D10 | Hai nhu cầu tạm trú và ATTP; chọn ATTP trước; quán ăn đã đăng ký HKD | Ưu tiên nhu cầu; không đổi sang HKD chỉ vì nhắc giấy đăng ký |

Tiêu chí chung: xã giao âm thanh riêng, bảng thông tin không vào TTS; câu hỏi có lựa chọn lấy từ meta; source windows chỉ node + con trực tiếp + common tổ tiên; không tích lũy toàn cây qua hội thoại. Lưu từng request/response, token API thật và thời gian từng lượt. Đánh giá nội dung thủ công dựa trên nguồn; kiểm tra tự động cấu trúc không thay thế đánh giá nghiệp vụ.
