# Định hướng lấy từ repo cũ

Nguồn: [minhtuluc/DataScraping](https://github.com/minhtuluc/DataScraping), nhánh `master`,
commit được kiểm tra `6c1b60a8cd24dd4092b9ba5693fe2005ba64fb4b`.
Đã đọc README, pipeline main, model dữ liệu, prompts và Wikipedia fetcher qua GitHub connector.
Không import DB/debug outputs, không sao chép toàn bộ implementation cũ.

## Giữ lại

- Entity là tàu/lớp tàu và các thông số length, beam, draft, displacement, speed, crew, armament.
- Wikipedia là nguồn đầu tiên, lấy thêm bản ngôn ngữ qua language links.
- Model trích xuất dữ liệu, giữ đơn vị thô, chuẩn hóa ở bước độc lập.
- Cần revision/source và kết quả theo từng trường để đối chiếu.

## Thay đổi nền tảng

| Repo cũ | Khung mới |
|---|---|
| Pipeline gắn chặt warship và schema DB | Profile tùy chỉnh, core không biết domain |
| Nhiều phiên bản prompt/schema đặc thù | Contract claim thống nhất và prompt có phiên bản |
| Semaphore giới hạn đồng thời, sleep 60s giữa extraction | Pacing nguồn theo host, giới hạn model call cấu hình |
| Retry HTTP errors chung | Dừng nguồn bị chặn/rate-limit, không retry tự động |
| Lấy infobox hoặc body | Lấy HTML API đã render, giữ toàn văn text để trích xuất |
| Tổng hợp thành một giá trị theo scoring | Giữ candidates, đánh dấu conflict, không suy confidence |
| Mục tiêu duy nhất | Warships là profile đầu, catalog demo chứng minh đổi domain |

## Giới hạn cần nhớ

Khung chưa thay thế toàn bộ tính năng dự kiến trong spec cũ: chưa chọn ngôn ngữ theo quốc gia,
chưa tách loại nguồn infobox/body, chưa có unit parser ngôn ngữ tự nhiên toàn diện.
Rules hiện đọc dấu phân cách theo ngôn ngữ, khoảng nối bằng hyphen/en/em dash;
LLM có thể diễn giải văn bản đa ngôn ngữ nhưng kết quả vẫn cần review.
Không đổi `30+` hoặc `over 30` thành số chính xác; chưa có kiểu lower-bound.
Lỗi bản dịch đã được cô lập: bài gốc và các bản dịch thành công được giữ lại,
ngôn ngữ lỗi hoặc không có bản dịch được báo trong `issues`.
