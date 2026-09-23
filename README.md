# DataScr Universal

Khung Python cho thu thập dữ liệu có cấu hình, thay được model và truy ngược bằng chứng.
Module mục đích đầu tiên là **warships**: thông số tàu chiến/lớp tàu từ Wikipedia đa ngôn ngữ,
lấy định hướng từ [minhtuluc/DataScraping](https://github.com/minhtuluc/DataScraping).

Đây là bộ khung CLI chạy được, chưa phải crawler mọi website hay dịch vụ production.
Python 3.11+, không có dependency runtime. Demo không cần mạng, API key hay model.

## Chạy ngay

Tại thư mục repo:

```powershell
python -m datascr check examples/warships-demo.toml
python -m datascr run examples/warships-demo.toml --output output/demo
python -m datascr run examples/custom-demo.toml --output output/catalog
python -m unittest discover -s tests -v
```

Nếu muốn lệnh `datascr` độc lập, cài `python -m pip install -e .` trong virtualenv.
Đường dẫn fixture tính từ file TOML; `--output` tính từ thư mục chạy lệnh.

Demo tàu dùng **dữ liệu giả lập**, cố ý cho tốc độ 30 và 31 kn để minh họa `conflict`.
Chiều dài 100 m và 0.1 km được chuẩn hóa thành cùng giá trị; khoảng thủy thủ được giữ nguyên.
Mỗi lần chạy tạo JSON riêng và một bản ghi trong `runs.sqlite3`.

## Cấu trúc

```text
datascr/
  contracts.py       Document, Field, giao diện Source và Model
  config.py          Đọc và kiểm tra schema cấu hình TOML
  access.py          Quyền truy cập, robots, pacing, dừng khi bị chặn
  sources.py         Fixture, HTML tĩnh, Wikipedia qua API
  models.py          Rules, Ollama, endpoint Chat Completions tương thích
  numbers.py         Parser số theo ngôn ngữ, dấu phân cách và khoảng
  validation.py      Kiểm tra bằng chứng/kiểu, đổi đơn vị, giữ mâu thuẫn
  pipeline.py        Điều phối, giới hạn tài liệu/model call, trạng thái chạy
  storage.py         JSON + SQLite
  cli.py             check / run
examples/
  warships-demo.toml       Module warships, demo offline đa ngôn ngữ
  warships-wikipedia.toml  Module warships, cấu hình nguồn/model thật
  custom-demo.toml         Module catalog để minh họa thêm miền dữ liệu
tests/                    Kiểm thử offline, mock các ranh giới HTTP
docs/                     Kiến trúc, quyết định thiết kế, hướng mở rộng
```

Module mục đích ở phiên bản này là một **profile TOML**: entity + nguồn + bộ trường + model.
Không cần thêm class Python chỉ để đổi loại thông tin cần lấy.

## Tùy chỉnh thông tin

Copy một TOML, thay `entity`, các `[[sources]]`, `[[fields]]` và `[[models]]`.
Ví dụ thêm trường:

```toml
[[fields]]
name = "manufacturer"
description = "Manufacturer explicitly named for this entity"
kind = "string"
aliases = ["Manufacturer", "Nhà sản xuất"]
```

`kind`: `number` (mặc định), `string`, `boolean`; số hỗ trợ cả `{min,max}`.
`unit` là đơn vị đích; `description` hướng dẫn LLM. `aliases` dùng cho bộ rules đọc
dòng `nhãn: giá trị`. Rules chỉ là baseline xác định được, không đọc hiểu bài Wikipedia.
Một job xử lý **một entity**, tránh trộn thông số của các tàu/sản phẩm khác nhau.

Trường `string` dạng danh sách có thể khai báo `list_separator` và `exclude_terms` để
lọc từng mục theo nội dung. Ví dụ [profile Asahi](examples/asahi-mimo.toml)
giữ súng/bệ phóng ở `armament` và tách radar, sonar khỏi giá trị chuẩn hóa.
Kết quả luôn giữ `raw_value` và `excluded_segments` để kiểm tra lại; bộ lọc này
chỉ là quy tắc do profile chỉ định, chưa phân loại thiết bị tự động cho mọi ngôn ngữ.

## Model

- `rules`: baseline offline cho dữ liệu có nhãn; không gọi LLM.
- `ollama`: API `/api/chat`, model do người dùng cài sẵn, mặc định localhost.
- `chat_completions`: endpoint hỗ trợ `/chat/completions`, JSON mode và `max_tokens`.
  Có thể là model cloud hoặc local server tương thích; không mặc định mọi provider đều hỗ trợ.

Thêm nhiều `[[models]]` để chạy từng model trên cùng tài liệu. Kết quả giữ nhãn model riêng;
không coi số model đồng ý là bằng chứng độc lập hay xác suất đúng.

```toml
[[models]]
provider = "chat_completions"
base_url = "https://your-provider.example/v1"
model = "your-model-id"
api_key_env = "DATASCR_MODEL_KEY"
```

Đặt key bằng biến môi trường, ví dụ `$env:DATASCR_MODEL_KEY = '...'`; không đặt trong TOML.
Không tự tải `.env`. Khi chọn cloud endpoint, văn bản nguồn và schema được gửi đến endpoint đó.
Giới hạn tài liệu, số lượt gọi, ký tự đầu vào và token đầu ra có thể cấu hình trong `[limits]`;
đây **không phải** hạn mức chi phí tiền tệ hay bộ đếm token đầu vào chính xác.

## Nguồn thật và nguyên tắc truy cập

Sửa `examples/warships-wikipedia.toml`: chọn model, contact User-Agent thật và các ngôn ngữ.
Sau khi tự kiểm tra điều khoản/quyền thu thập của nguồn, ghi `permission_note` và đặt `approved = true`.
Đây là thông tin cấu hình do người vận hành xác nhận, không phải chương trình tự chứng minh quyền truy cập.

```powershell
python -m datascr check examples/warships-wikipedia.toml
python -m datascr run examples/warships-wikipedia.toml --output output/warships
```

Thêm HTML tĩnh bằng `[[sources]]` với `kind = "html"`, `url = "https://..."`, `language = "vi"`;
thêm chính xác hostname vào `access.allowed_hosts`. Không crawl liên kết tùy ý.

Mọi GET web đi qua cùng cổng kiểm soát: HTTPS, host cho phép, kiểm tra IP public,
robots.txt, khoảng nghỉ ít nhất 1 giây/host và Crawl-delay/Request-rate nếu có.
HTTP lỗi (kể cả 403, 429), challenge nhận diện được hoặc robots không tải được thì dừng host
trong lần chạy đó. Không retry, không xoay proxy/User-Agent, không giải CAPTCHA, không đăng nhập,
không theo HTTP redirect. Với 429, không gửi tiếp nên không gọi lại trước Retry-After.

Chính sách thận trọng: robots 404 cũng dừng; robots áp dụng cả URL API Wikipedia.
Nếu `/w/api.php` bị robots cấm, module sẽ báo lỗi và dừng, **không chuyển endpoint để né**.
Muốn nguồn khác, bổ sung connector dùng kênh được nguồn cho phép rõ ràng.
Robots không đồng nghĩa với giấy phép; người vận hành vẫn cần đánh giá điều khoản và quyền dữ liệu.
Không có cơ chế nào ở đây tự bảo đảm mọi mục đích sử dụng đều hợp lệ.

## Đọc kết quả

- `documents`: văn bản đã đưa vào xử lý, URL, ngôn ngữ, revision (Wikipedia), SHA-256.
- `attempts`: model, tài liệu, các claim model trả về hoặc lỗi.
- `fields`: `observed`, `missing`, `conflict`; giữ mọi candidate với quote và nguồn.
- `issues`: lỗi nguồn/model/validation, hoặc giới hạn bị chạm.
- `status`: `completed` (có claim, không lỗi), `partial` (có claim và lỗi), `failed` (không claim hợp lệ).
- `needs_review`: có trường thiếu hoặc mâu thuẫn. `completed` không có nghĩa dữ liệu đã được xác minh.

Exit code: 0 chạy hoàn tất/check hợp lệ; 2 partial/failed; 1 lỗi config/output.
Không có dữ liệu không được thay bằng 0. Có mâu thuẫn thì giá trị tổng hợp là null, không lấy trung bình.
Quote được kiểm tra có tồn tại trong nguồn; điều đó **chưa chứng minh** model đã diễn giải đúng quote.
Đơn vị chưa biết hoặc mơ hồ (ví dụ `tons`) bị từ chối thay vì đoán.

Validator còn kiểm tra số và đơn vị xuất hiện trong quote, trước khi chuyển đơn vị.
Số chuỗi được đọc theo `source.language`: ví dụ `1,234.5` (en), `1.234,5` (vi/de),
`1 234,5` (fr). Nếu không biết ngôn ngữ, các dạng mơ hồ như `1,234` bị từ chối.
Hỗ trợ khoảng nối bằng `-`, `–`, `—`, số âm và ký hiệu khoa học. Alias đơn vị gồm
`mét`, `feet`, `kts`, `tấn`, `người` và một số dạng số ít/số nhiều.
Không làm tròn cố định về 9 chữ số thập phân nữa; so sánh số chỉ dung sai tương đối `1e-12`
để bỏ nhiễu phép đổi đơn vị, không hợp nhất các giá trị thực sự khác nhau.
Những cách viết giới hạn/xấp xỉ nhận diện được (`>30`, `30+`, `over 30`, `hơn 30`, `khoảng 30`)
bị từ chối vì schema hiện chưa biểu diễn được điều kiện đó.

HTML giữ nhãn và giá trị cùng hàng bảng, không tự xuống dòng khi đóng thẻ inline.
Lỗi một bản dịch Wikipedia được ghi trong `issues`, các bài tải được vẫn đi tiếp và run là `partial`.
Cấu hình source trùng hệt nhau chỉ được tải một lần mỗi run.
Chi tiết phạm vi và ca kiểm thử: [cải thiện chất lượng dữ liệu](docs/data-quality.md).

## Phạm vi hiện tại

Đã có đường chạy thực: nguồn → model → kiểm tra → chuẩn hóa → tổng hợp → JSON/SQLite.
Adapter đã qua kiểm thử mock và live extraction nhỏ trên Command Code với MiMo V2.6 Flash,
DeepSeek V4 Flash và GLM-5.3 Flash; xem [báo cáo](docs/commandcode-test.md).
Chưa xác nhận end-to-end từ Wikipedia đến model.
Chưa có UI, tìm kiếm web diện rộng, PDF/OCR, browser rendering, cache/resume, phân mảnh bài dài,
API native cho mọi hãng model, lập lịch hoặc hàng đợi phân tán. Bài dài bị báo skip thay vì cắt âm thầm.
Khung HTTP dùng trong CLI tin cậy; chưa đủ để mở thành dịch vụ nhận URL tùy ý từ Internet
(cần bảo vệ DNS rebinding và egress ở tầng mạng). Nhận diện challenge chỉ là heuristic.

Xem [kiến trúc và hướng phát triển](docs/architecture.md), [đối chiếu repo cũ](docs/legacy-review.md).
