# Rà soát lấy dữ liệu và chuẩn hóa — 2026-09-23

Đã tái hiện lỗi bằng các kiểm thử thất bại trước sửa, sau đó sửa và chạy toàn bộ suite.

| Vấn đề cũ | Hành vi hiện tại |
|---|---|
| Đóng thẻ `b/span` làm tách số và đơn vị; bảng bị mất quan hệ nhãn–giá trị | Giữ inline text; hàng hai ô thành `nhãn: giá trị`, ô sau phân cách bằng `|` |
| Một bản dịch lỗi làm mất toàn bộ kết quả Wikipedia source | Giữ bài thành công, báo lỗi từng ngôn ngữ và trạng thái partial |
| Source cấu hình trùng vẫn tải lại | Loại cấu hình trùng trước bước lấy dữ liệu |
| Không đọc số có phân cách hàng nghìn/decimal theo locale | Parser xác định theo language, kiểm tra nhóm ba chữ số, không đoán dạng mơ hồ |
| Chỉ nhận khoảng en/em dash | Nhận thêm hyphen, khoảng số âm, ký hiệu khoa học |
| Quote tồn tại nhưng model có thể trả số/đơn vị khác | Kiểm tra số và đơn vị trong quote trước chuẩn hóa |
| Làm tròn cố định khiến số nhỏ thành 0 | Giữ độ chính xác float, kiểm tra overflow; dung sai tương đối rất nhỏ khi đối chiếu |
| Giá trị “over 30” có thể thành 30 chính xác | Từ chối một số dạng bound/approximation phổ biến chưa biểu diễn được |

## Kiểm chứng

- `python -m unittest discover -s tests -v`: 38 tests đạt.
- Ca dữ liệu Anh, Việt, Pháp; comma/dot/NBSP/narrow NBSP; range và scientific notation.
- Kiểm thử giữ kết quả khi bản dịch lỗi và truyền issue lên pipeline.
- Kiểm thử quote thật nhưng số sai, đơn vị sai; không biến missing thành 0.
- Các kiểm thử policy nguồn, pacing, robots, HTTP 403/429 vẫn đạt.
- Các thay đổi này được kiểm thử offline/mock; không tuyên bố đã chạy Wikipedia live trong đợt này.

## Giới hạn còn lại

Đây là kiểm chứng cú pháp/bằng chứng, chưa chứng minh đầy đủ ý nghĩa. Quote chứa nhiều số,
đơn vị, biến thể hoặc thời điểm vẫn có thể bị model gán nhầm; cần người dùng review.
Việc nhận diện từ chỉ giới hạn/xấp xỉ chưa bao phủ mọi ngôn ngữ.
Nguồn dùng định dạng số khác quy ước `language` có thể bị từ chối; không tự đổi locale để đoán.
HTML parser không triển khai đầy đủ rowspan/colspan hoặc bảng lồng nhau.
Không tự hợp nhất ước lượng, trung bình số mâu thuẫn, hay coi nhiều model là nhiều nguồn độc lập.
Chưa thêm chunking, nhận diện entity/variant tự động, hoặc crawl liên kết diện rộng.
