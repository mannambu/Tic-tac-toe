# ASS — Tic-tac-toe AI

## 1. Khởi chạy

Cần **Python 3.10 trở lên có Tkinter**. Không cần cài thêm gói pip. Chạy lệnh trong thư mục chứa `main.py`:

```powershell
python main.py
```

Kiểm tra Tkinter nếu cửa sổ không xuất hiện:

```powershell
python -m tkinter
```

Bản Python dành cho Windows thường có thành phần Tcl/Tk trong trình cài đặt. Nếu Python hiện tại thiếu Tkinter, dùng bản Python đã cài thành phần này. `requirements.txt` chỉ ghi chú môi trường; thư viện `pypdf` trong `tmp/` dùng để đọc đề, không phải phụ thuộc của chương trình.

## 2. Luật và cách chơi

- X đi trước, đặt quân luân phiên vào ô trống.
- Ít nhất **5 quân liên tiếp** ngang, dọc hoặc chéo là thắng.
- Chuỗi từ 6 quân trở lên vẫn thắng; hai đầu bị chặn vẫn thắng.
- Không có luật cấm double-three, double-four hoặc overline.
- Bàn đầy mà chưa có người thắng thì hòa; ván kết thúc ngay khi có kết quả.

Chọn kích thước và chế độ, sau đó bấm **Bắt đầu / Ván mới**:

- **Người vs AI:** chọn quân của bạn. Thuật toán ở ô “AI quân X/O” chỉ dùng nếu bên tương ứng là AI.
- **AI vs AI:** chọn thuật toán riêng cho X và O.
- **Người vs Người:** hai người luân phiên bấm ô trống.

Nút **Tạm dừng / Tiếp tục** hủy lượt suy nghĩ đang chạy; khi tiếp tục, AI tìm lại từ trạng thái hiện tại. Ván mới áp dụng cấu hình mới và loại bỏ kết quả từ tác vụ cũ. Lịch sử ván có thể lưu dưới dạng JSON, gồm cấu hình, tọa độ và thống kê từng nước.

GUI sử dụng tiến trình `multiprocessing` với cơ chế `spawn`. Hãy chạy qua `python main.py`, không gọi `run()` trực tiếp trong notebook. Thời gian hiển thị là thời gian tìm kiếm; khởi tạo tiến trình và cập nhật GUI có thêm chi phí nhỏ.

## 3. Thuật toán

### Backtracking

Minimax dạng Negamax, dùng **đặt quân → đệ quy → gỡ quân**, không cắt nhánh Alpha-beta. Khi đạt độ sâu giới hạn thì dùng heuristic. Với ngân sách thời gian, thuật toán tìm sâu dần từ 1 đến `max_depth`, giữ kết quả của độ sâu đã hoàn thành gần nhất. Nếu chưa hoàn thành độ sâu 1, dùng nước hợp lệ đứng đầu danh sách và ghi `completed_depth = 0`, `score = null`.

### Alpha-beta

Dùng cùng lõi Negamax, cùng nước ứng viên, cùng thứ tự và cùng heuristic với Backtracking; thêm hai biên alpha/beta để bỏ nhánh không ảnh hưởng kết quả. Trong chế độ **cùng độ sâu và không giới hạn thời gian**, hai thuật toán phải cho cùng giá trị Minimax. Cả hai ưu tiên thắng sớm và trì hoãn thua qua điểm `±(1_000_000 - ply)`.

### MCTS

Bốn bước: Selection bằng UCT → Expansion → Simulation → Backpropagation. Một node lưu tổng thưởng theo **người vừa đi đến node đó**, để tại mỗi lượt, lựa chọn UCT tối ưu cho đúng người đang chơi. Thưởng thắng/hòa/thua là 1/0.5/0. Nước cuối cùng lấy theo lượt thăm cao nhất, nếu hòa thì lấy trung bình thưởng cao hơn.

Mô phỏng chọn ngẫu nhiên trong tập ứng viên, có ưu tiên thắng/chặn thắng ngay theo cấu hình chung. Mỗi rollout tối đa 60 nước theo mặc định. Nếu chưa kết thúc ván, dùng xấp xỉ:

```text
value(player) = 0.5 + 0.5 × tanh(evaluate(board, player) / 8192)
```

Đây là **MCTS có heuristic ở mô phỏng cắt ngắn**, không phải mô phỏng ngẫu nhiên thuần túy đến hết mọi ván. Số rollout cắt ngắn được ghi trong `heuristic_rollouts`. Một mô phỏng bị ngắt bởi thời gian không được cập nhật vào cây. Seed cố định cho cùng kết quả nếu cố định số lượt mô phỏng và bỏ giới hạn thời gian; chạy theo thời gian có thể khác kết quả tùy tải máy.

## 4. Heuristic và giảm không gian tìm kiếm

Mọi đoạn 5 ô theo bốn hướng được tính trước. Đoạn có cả X và O cho điểm 0. Đoạn chỉ có quân một bên nhận điểm theo số quân:

| Số quân | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---:|---:|---:|---:|---:|---:|
| Điểm | 0 | 2 | 16 | 128 | 4096 | 1,000,000 |

Điểm toàn bàn là tổng điểm X trừ tổng điểm O; nhân theo bên cần đánh giá. Điểm heuristic được chặn trong ±500,000, thấp hơn điểm thắng chắc chắn. Khi đặt/gỡ quân, chỉ cập nhật những đoạn chứa ô đó.

Các đoạn chồng nhau giúp phản ánh số hướng phát triển, chuỗi mở và chuỗi khuyết. Đây là heuristic theo **cửa sổ 5 ô**, không phải bộ nhận dạng mẫu đầy đủ cho mọi double-threat trong Gomoku.

Cách sinh nước dùng chung cho cả ba thuật toán:

1. Nếu có nước thắng ngay, chỉ giữ các nước đó.
2. Nếu đối phương có nước thắng ngay, chỉ giữ các ô chặn; không loại bớt các ô này vì giới hạn ứng viên. Nếu đối phương có nhiều đe dọa độc lập, việc chặn một ô có thể vẫn không cứu được ván.
3. Nếu bàn trống và dùng bán kính lân cận, đi giữa bàn.
4. Lấy ô trống cách một quân đã đặt tối đa 2 ô theo khoảng cách Chebyshev.
5. Chấm ưu tiên tấn công/phòng thủ, giữ tối đa N ứng viên (GUI mặc định 12; thực nghiệm nhanh 8).

Giới hạn ứng viên và bán kính **có thể bỏ sót nước đi tốt**. Kết quả tìm kiếm sâu là tối ưu trên cây ứng viên được sinh, không phải chứng minh lời giải tối ưu cho toàn bộ trò chơi. Chế độ xét mọi nước trống trong CLI: `--radius 0 --cap 0 --no-forcing`. Đặt `--cap 0` riêng lẻ chỉ bỏ giới hạn số lượng, vẫn giữ bán kính.

## 5. Kiểm thử

```powershell
python -m unittest discover -s tests -v
python -m tests.gui_smoke -v
```

Bộ lõi/AI kiểm tra luật theo mọi hướng và mọi kích thước, chuỗi dài hơn 5, hai đầu bị chặn, hòa, nước bất hợp lệ, phục hồi trạng thái và điểm tăng dần, chặn/thắng ngay, Alpha-beta so với Minimax, timeout/cancel, tính tái lập MCTS, góc nhìn thưởng X/O và replay ván đấu hoàn chỉnh.

Bộ GUI mở cửa sổ Tk thực tế, chạy worker thật, kiểm tra thao tác người chơi, AI đi trước khi người chọn O, pause/resume, reset, bỏ kết quả cũ, cấu hình sai và kích thước vùng thống kê. Cần phiên làm việc có màn hình.

## 6. Thực nghiệm

Chạy bộ nhanh: **12 cặp so sánh độ sâu** và **36 trận**, trên cả ba kích thước, đổi X/O, dùng 2 seed và khai cuộc giống nhau cho mỗi cặp trận:

```powershell
python -m experiments.benchmark --output results/another_run --time 0.04
python -m experiments.verify results/another_run
```

Thư mục `results/quick/` chứa dữ liệu đã chạy thực tế. Ngân sách 0.04 giây/nước phù hợp kiểm tra luồng thực nghiệm; đây là **đợt thử sơ bộ**, không đủ để kết luận sức mạnh tổng quát của ba thuật toán.

Để lấy số liệu với ngân sách lớn hơn và nhiều seed hơn cho báo cáo, ví dụ:

```powershell
python -m experiments.benchmark --output results/extended --time 0.5 --cap 12 --seeds 11 28 37 54 63 80 99 112 --depths 2 3 4
python -m experiments.verify results/extended
```

Lệnh trên chạy 144 trận và 72 cặp độ sâu; có thể mất nhiều thời gian. Nếu chỉ muốn một phần, thêm `--mode compare` hoặc `--mode matches`. `--unordered` bỏ sắp thứ tự duyệt (vẫn xếp hạng để chọn tập khi có cap), `--no-forcing` bỏ lọc thắng/chặn ngay. Xem đầy đủ bằng:

```powershell
python -m experiments.benchmark --help
```

### Điều kiện so sánh

- **Cùng độ sâu:** không giới hạn thời gian, không tìm sâu dần; cùng bàn, ứng viên và thứ tự cho Backtracking/Alpha-beta. Chương trình kiểm tra giá trị Minimax bằng nhau. Thời gian rất ngắn chịu nhiễu đo; số nút là chỉ số ổn định hơn.
- **Cùng thời gian:** cả ba có cùng ngân sách tìm kiếm mỗi lượt; Minimax có trần sâu 20 và MCTS có trần 1,000,000 lượt. Trận có 4 nước khai cuộc ngẫu nhiên được lưu lại, sau đó AI tiếp tục; mỗi seed đổi bên để giảm lợi thế X. Cấu hình này không đảm bảo hai bên tiêu hết thời gian khi đã chứng minh được thắng/thua.
- Thời gian là **giới hạn mềm**: kiểm tra giữa các bước tìm kiếm, nên có thể vượt nhẹ do một bước đang chạy hoặc hệ điều hành. Không tính thời gian tạo tiến trình GUI.
- `nodes` của Minimax là lượt gọi tìm kiếm (gồm gốc mỗi vòng sâu dần); `nodes` của MCTS là số node được cấp trong cây. Hai đơn vị không đại diện cùng khối lượng công việc. Báo cáo thêm `iterations` và `rollout_moves` cho MCTS.

### Các tệp kết quả

| Tệp | Nội dung |
|---|---|
| `metadata.json` | Môi trường, luật, cấu hình, seed, trạng thái hoàn thành và các tệp thuộc lượt chạy |
| `depth_comparison.csv` | Giá trị, nước chọn, nút, cắt tỉa và thời gian ở cùng độ sâu |
| `games.csv` | Một dòng mỗi trận: hai AI, khai cuộc, kết quả, tổng nước |
| `moves.csv` | Một dòng mỗi nước AI: tọa độ và toàn bộ thống kê tìm kiếm |
| `summary.csv` | Thắng/hòa/thua, tỷ lệ điểm, thời gian trung bình, độ sâu/lượt mô phỏng |

Tọa độ hàng/cột bắt đầu từ **1**; trường `move` và các số trong `opening` là chỉ số tuyến tính bắt đầu từ **0** (`row0 × size + col0`). Lượt `ply` tính cả khai cuộc. `score` của Minimax là điểm heuristic/mate, của MCTS là trung bình thưởng [0,1]; không so sánh trực tiếp hai thang này.

Mặc định không ghi đè kết quả. Dùng thư mục mới hoặc `--overwrite` nếu chủ động muốn thay thế. Khi tái sử dụng thư mục với mode khác, chỉ đọc các tệp liệt kê trong `metadata.json.completed_files`.

## 7. Cấu trúc mã

```text
main.py                  Điểm khởi chạy GUI
game/board.py            Luật nền, trạng thái, đặt/gỡ, điểm tăng dần
game/rules.py            Nhãn quân và kết quả
game/candidates.py       Sinh và xếp hạng nước ứng viên
ai/base.py               Cấu hình và kết quả tìm kiếm
ai/evaluation.py         Heuristic, giá trị mô phỏng cắt ngắn
ai/minimax.py            Negamax dùng chung
ai/backtracking.py       Minimax không cắt tỉa
ai/alphabeta.py          Minimax với Alpha-beta
ai/mcts.py               UCT / Monte Carlo Tree Search
ui/app.py                Giao diện Tkinter
ui/worker.py             Worker AI tách tiến trình
experiments/benchmark.py Thực nghiệm và xuất CSV
experiments/verify.py    Replay, đối chiếu kết quả và tổng hợp
tests/                   Kiểm thử lõi, AI và GUI
results/quick/           Dữ liệu thực nghiệm đã chạy
```
