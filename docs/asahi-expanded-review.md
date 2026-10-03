# Đánh giá Asahi mở rộng

Ngày chạy: 2026-09-23. Model: xiaomi/mimo-v2.6-flash, CommandCode.
29 lời gọi: 21 cho nguồn chính, 6 cho nguồn đối chiếu, 2 để kiểm chứng bản sửa PS/inch.
Không dùng model khác. Không đo được giá tiền thực tế của nhà cung cấp.

## Kết quả và cách đọc

Mẫu tăng từ một tài liệu sang 9 tài liệu, gồm HTML và trang PDF chọn trước.
31 trường cấu hình, 27 trường có ít nhất một claim vượt validator;
100 claim được giữ, 26 claim/thuộc tính bị loại. Đây là coverage, không phải độ chính xác.
Các lượt dùng hai phiên bản prompt; raw attempts giữ nguyên để kiểm tra lại.
JMSDF và Japan Ministry of Defense là cùng hệ thống cơ quan, không phải hai xác nhận độc lập.
Sáu nhãn publisher không được hiểu là sáu nguồn độc lập cho từng con số.

File gộp: `output/asahi-final/e28e9603d6ae466a947014ed12e8bca7.json`.
Bản đọc: cùng đường dẫn, đuôi `.md`.

- Động lực: nguồn GE ghi hai LM2500 và hai động cơ điện; danh mục GE ghi COGLAG.
- Công suất nguồn JMSDF ghi 62.500 PS, chuẩn hóa 45,968671875 MW. MHI ghi
  64.000 PS, chuẩn hóa 47,07192 MW. Giữ conflict, không chọn trung bình.
- Thủy thủ đoàn: khoảng 220 người ở PDF dành riêng DD-119; giữ qualifier và scope.
- Vũ khí: có tên, số lượng và cỡ nòng; nguồn đối chiếu bổ sung Mk 45, Phalanx,
  Type 90 theo 2x4, HOS-303 theo 2x3 và các mô tả VLS.
- Cảm biến: giữ cả tên chức năng từ JMSDF và model từ nguồn đối chiếu;
  dữ liệu radar/sonar không còn bị bỏ đi khi lọc khỏi danh sách vũ khí.
- Chưa có bằng chứng được chấp nhận cho range_nm, range_at_speed_kn,
  endurance_days, fuel_capacity.

## Lỗi thực tế đã sửa

1. Trang JMSDF cũ dùng Shift-JIS với ký tự mở rộng Windows; dùng cp932 đúng encoding,
   không thay user-agent hoặc vượt chặn.
2. Prompt khiến model bỏ công suất PS vì schema đặt đơn vị đích MW. Làm rõ số và đơn vị
   đầu vào phải giữ nguyên; validator mới đổi đơn vị. Hai lời gọi kiểm chứng đã lấy được PS.
3. Đơn vị ở tiêu đề bảng như `Length, m: 151.0` từng bị từ chối.
4. Ký hiệu `2x3` từng mất số thứ hai. Hỗ trợ dấu nhân mà không tự tính tổng đạn.
5. Model tạo khoảng 16–32 từ câu nói 16 ô hiện hữu, có thể mở rộng 32. Validator giờ
   yêu cầu ký hiệu khoảng thực sự liền nhau; đã loại claim sai này khi tái xử lý.
6. Phạm vi class và DD-119 từng che mâu thuẫn bên trong cùng phạm vi; giờ phân nhóm
   rồi kiểm tra conflict trong từng nhóm.

## Giới hạn cần review

Tên khác nhau của cùng thiết bị chưa được hợp nhất về mã định danh: `HOS-303` và
`HOS-303 TT`, hoặc tên Nhật và Anh có thể còn trùng. Bộ phát hiện conflict chỉ so
record cùng tên/context/scope; khác tên có thể che xung đột 16/32 ô VLS.
Chuỗi tên/operator khác ngôn ngữ bị báo conflict bảo thủ, không đồng nghĩa nguồn bất đồng thực tế.

Nguồn WeaponSystems viết `5.100`, `6.800` trong trang tiếng Anh nhưng cũng dùng
`18.3`: formatter không nhất quán. Các claim 5100/6800 này bị loại thay vì đoán locale.
Một số claim crew tự thêm đơn vị persons, record propulsion sai cấu trúc và role
không nằm trong quote của record cũng bị loại. Giữ raw để sửa prompt/tái trích xuất sau.
Trường count ở mô tả tổ hợp phải đọc cùng tubes_per_mount và quote; không diễn giải
count=2 của hệ thống 2x4 thành chỉ có hai tên lửa.

Wikipedia bị robots từ chối. URL pamphlet ash.pdf trả nội dung không có chữ ký PDF
trong lượt thu này nên bị loại. Không dùng mirror hoặc endpoint khác để né chặn.
PDF ảnh chưa có OCR. Discovery chỉ duyệt link cùng host đã duyệt, chưa có search-engine adapter.

## Nguồn

- [JMSDF class](https://www.mod.go.jp/msdf/equipment/ships/dd/asahi/)
- [JMSDF ship PDF, trang 6](https://www.mod.go.jp/msdf/asd/IMAGE/CONTENTS/PDF/TOPICS/kantei.pdf)
- [GE catalog, trang 14](https://www.geaerospace.com/sites/default/files/2022-03/LM500-Experience-List.pdf)
- [GE press release](https://www.geaerospace.com/news/press-releases/marine-industrial-engines/ge-lm2500-marine-gas-turbines-power-japans-new-js-asahi)
- [MHI class](https://www.mhi.com/jp/business/products-services/space-defense/surface-ships/destroyer-asahi-class)
- [Kyushu Defense Bureau commissioning](https://www.mod.go.jp/rdb/kyushu/topics/300307asahi/index.htm)
- [JMSDF fleet group](https://www.mod.go.jp/msdf/wg2hq/)
- [WeaponSystems](https://weaponsystems.net/system/1167-Asahi%20class)
- [Navypedia](https://navypedia.org/ships/japan/jap_dd_asahi.htm)
