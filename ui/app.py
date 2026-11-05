"""Responsive desktop GUI. Search runs in a cancellable spawned process."""

import json
import multiprocessing as mp
import queue
import tkinter as tk
from dataclasses import asdict, replace
from tkinter import filedialog, messagebox, ttk

from ai.base import ALGORITHMS, SearchConfig
from game.board import Board, EMPTY, SIZES, X
from game.rules import symbol
from ui.worker import search_worker

BG = "#eef2f7"
INK = "#172b4d"
BLUE = "#2563eb"
RED = "#e45756"
MODES = ("Người vs AI", "AI vs AI", "Người vs Người")


class GameApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FIVE • Tic-tac-toe AI Lab")
        self.root.geometry("1120x790")
        self.root.minsize(1000, 760)
        self.root.configure(bg=BG)
        self.context = mp.get_context("spawn")
        self.job = None
        self.epoch = 0
        self.request_serial = 0
        self.closed = False
        self.started = False
        self.paused = False
        self.board = Board(7)
        self.records = []
        self.roles = {1: "Human", -1: "Alpha-beta"}
        self.config = SearchConfig()
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._draw()

    def _build(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 23, "bold"))
        style.configure("Heading.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("TButton", padding=(10, 5), font=("Segoe UI", 10))
        style.configure("Accent.TButton", foreground="white", background=BLUE)
        style.map("Accent.TButton", background=[("active", "#1d4ed8")])
        style.configure("Treeview", rowheight=24, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

        outer = ttk.Frame(self.root, padding=20)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="FIVE / AI LAB", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="5 quân liên tiếp để thắng  ·  7×7 / 9×9 / 11×11  ·  X đi trước").pack(anchor="w", pady=(2, 16))
        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body, width=282)
        left.pack(side="left", fill="y", padx=(0, 20))
        left.pack_propagate(False)
        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="THIẾT LẬP VÁN ĐẤU", style="Heading.TLabel").pack(anchor="w", pady=(0, 7))
        self.size_var = tk.StringVar(value="7")
        self.mode_var = tk.StringVar(value=MODES[0])
        self.human_var = tk.StringVar(value="X")
        self.x_var = tk.StringVar(value="Alpha-beta")
        self.o_var = tk.StringVar(value="MCTS")
        self.depth_var = tk.StringVar(value="4")
        self.time_var = tk.StringVar(value="0.75")
        self.iter_var = tk.StringVar(value="1500")
        self.cap_var = tk.StringVar(value="12")
        self.seed_var = tk.StringVar(value="42")
        fields = ttk.Frame(left)
        fields.pack(fill="x")
        fields.columnconfigure(1, weight=1)
        for row, (label, variable, options) in enumerate((
            ("Bàn cờ", self.size_var, tuple(map(str, SIZES))),
            ("Chế độ", self.mode_var, MODES),
            ("Bạn cầm quân", self.human_var, ("X", "O")),
            ("AI quân X", self.x_var, ALGORITHMS),
            ("AI quân O", self.o_var, ALGORITHMS),
        )):
            ttk.Label(fields, text=label).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Combobox(fields, textvariable=variable, values=options, state="readonly", width=17).grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=3)
        for row, (label, variable) in enumerate((
            ("Độ sâu tối đa", self.depth_var),
            ("Giây / nước AI", self.time_var),
            ("Lượt MCTS tối đa", self.iter_var),
            ("Số ứng viên / nút", self.cap_var),
            ("Seed ngẫu nhiên", self.seed_var),
        ), start=5):
            ttk.Label(fields, text=label).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Entry(fields, textvariable=variable, width=19).grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=3)
        ttk.Label(left, text="Thiết lập áp dụng khi bắt đầu ván mới.\nAI tìm quanh quân đã có (bán kính 2).\nGiới hạn ứng viên: 0 = không giới hạn.", wraplength=280, font=("Segoe UI", 9), foreground="#52657f").pack(anchor="w", pady=(6, 6))
        ttk.Button(left, text="Bắt đầu / Ván mới", style="Accent.TButton", command=self.new_game).pack(fill="x", pady=3)
        self.pause_button = ttk.Button(left, text="Tạm dừng", command=self.toggle_pause, state="disabled")
        self.pause_button.pack(fill="x", pady=3)
        ttk.Button(left, text="Lưu lịch sử JSON", command=self.export_game).pack(fill="x", pady=3)
        ttk.Separator(left).pack(fill="x", pady=8)
        ttk.Label(left, text="NƯỚC AI GẦN NHẤT", style="Heading.TLabel").pack(anchor="w")
        self.stats_var = tk.StringVar(value="Chưa có nước đi AI.")
        self.stats_label = ttk.Label(left, textvariable=self.stats_var, justify="left", wraplength=280, font=("Segoe UI", 10))
        self.stats_label.pack(anchor="w", pady=7)

        self.status_var = tk.StringVar(value="Chọn thiết lập rồi bấm Bắt đầu.")
        ttk.Label(right, textvariable=self.status_var, style="Heading.TLabel").pack(anchor="w", pady=(0, 8))
        self.canvas = tk.Canvas(right, bg="white", highlightthickness=1, highlightbackground="#d6dfec")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda event: self._draw())
        self.canvas.bind("<Button-1>", self._click)
        ttk.Label(right, text="X  xanh dương    O  đỏ    •  nước vừa đi", foreground="#52657f").pack(anchor="w", pady=(6, 8))
        log_frame = ttk.Frame(right)
        log_frame.pack(fill="x")
        self.log = ttk.Treeview(log_frame, columns=("turn", "player", "cell", "agent", "time"), show="headings", height=4)
        for name, label, width in (("turn", "Lượt", 45), ("player", "Quân", 45), ("cell", "Ô (hàng, cột)", 110), ("agent", "Người / Thuật toán", 170), ("time", "Thời gian", 90)):
            self.log.heading(name, text=label)
            self.log.column(name, width=width, anchor="center")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="x", expand=True)
        scroll.pack(side="right", fill="y")

    def _read_config(self):
        config = SearchConfig(max_depth=int(self.depth_var.get()), time_limit=float(self.time_var.get()),
                              iterations=int(self.iter_var.get()), max_candidates=int(self.cap_var.get()),
                              seed=int(self.seed_var.get()))
        if not 1 <= config.max_depth <= 20:
            raise ValueError("Độ sâu phải từ 1 đến 20.")
        if not 0.01 <= config.time_limit <= 60:
            raise ValueError("Thời gian mỗi nước phải từ 0.01 đến 60 giây.")
        if config.iterations > 1_000_000 or config.max_candidates > 121:
            raise ValueError("Tối đa 1,000,000 lượt MCTS và 121 ứng viên.")
        return config

    def new_game(self):
        try:
            config = self._read_config()
            board = Board(int(self.size_var.get()))
        except (ValueError, OverflowError) as exc:
            messagebox.showerror("Thiết lập chưa hợp lệ", str(exc), parent=self.root)
            return
        self._cancel_job()
        self.epoch += 1
        self.config, self.board = config, board
        self.roles = {1: self.x_var.get(), -1: self.o_var.get()}
        if self.mode_var.get() == MODES[0]:
            self.roles[1 if self.human_var.get() == "X" else -1] = "Human"
        elif self.mode_var.get() == MODES[2]:
            self.roles = {1: "Human", -1: "Human"}
        self.records = []
        self.log.delete(*self.log.get_children())
        self.started, self.paused = True, False
        self.pause_button.configure(state="normal", text="Tạm dừng")
        self.stats_var.set("Chưa có nước đi AI.")
        self._draw()
        self._advance()

    def _draw(self):
        canvas, board = self.canvas, self.board
        canvas.delete("all")
        width, height = max(200, canvas.winfo_width()), max(200, canvas.winfo_height())
        side = min(width - 44, height - 44)
        step = side / board.size
        x0, y0 = (width - side) / 2, (height - side) / 2
        self.grid_geometry = x0, y0, step
        winners = set(board.winning_line())
        for r in range(board.size):
            canvas.create_text(x0 - 12, y0 + (r + 0.5) * step, text=str(r + 1), fill="#6b7d94", font=("Segoe UI", 9))
            canvas.create_text(x0 + (r + 0.5) * step, y0 - 12, text=str(r + 1), fill="#6b7d94", font=("Segoe UI", 9))
            for c in range(board.size):
                move = r * board.size + c
                x, y = x0 + c * step, y0 + r * step
                fill = "#dcfce7" if move in winners else "#eff6ff" if move == board.last_move else "#ffffff"
                canvas.create_rectangle(x, y, x + step, y + step, fill=fill, outline="#dbe3ee")
                margin = step * 0.27
                if board.cells[move] == X:
                    canvas.create_line(x + margin, y + margin, x + step - margin, y + step - margin, fill=BLUE, width=3)
                    canvas.create_line(x + margin, y + step - margin, x + step - margin, y + margin, fill=BLUE, width=3)
                elif board.cells[move] != EMPTY:
                    canvas.create_oval(x + margin, y + margin, x + step - margin, y + step - margin, outline=RED, width=3)
                if move == board.last_move:
                    canvas.create_oval(x + step - 8, y + 4, x + step - 4, y + 8, fill=INK, outline=INK)

    def _click(self, event):
        if not self.started or self.paused or self.board.terminal or self.job:
            return
        if self.roles[self.board.to_move] != "Human":
            return
        x0, y0, step = self.grid_geometry
        col, row = int((event.x - x0) // step), int((event.y - y0) // step)
        if 0 <= row < self.board.size and 0 <= col < self.board.size:
            move = row * self.board.size + col
            if self.board.cells[move] == EMPTY:
                self._apply_move(move, "Human", None)

    def _apply_move(self, move, agent, stats):
        player = self.board.to_move
        self.board.play(move)
        row, col = divmod(move, self.board.size)
        record = {"turn": self.board.move_count, "player": symbol(player), "row": row + 1,
                  "col": col + 1, "algorithm": agent, "stats": stats}
        self.records.append(record)
        item = self.log.insert("", "end", values=(self.board.move_count, symbol(player), f"{row + 1}, {col + 1}",
                                                   "Người" if agent == "Human" else agent,
                                                   f"{stats['elapsed']:.3f} s" if stats else "—"))
        self.log.see(item)
        if stats:
            if agent == "MCTS":
                detail = f"Lượt mô phỏng: {stats['iterations']:,}\nNút cây: {stats['nodes']:,}\nMô phỏng cắt ngắn: {stats['heuristic_rollouts']:,}"
            else:
                detail = f"Độ sâu hoàn thành: {stats['completed_depth']}\nNút đã xét: {stats['nodes']:,}\nNhánh cắt: {stats['cutoffs']:,}"
            self.stats_var.set(f"{agent} · {stats['elapsed']:.3f} giây\n{detail}" + ("\nĐã chạm giới hạn thời gian." if stats["timed_out"] else ""))
        self._draw()
        self._advance()

    def _advance(self):
        if self.closed or not self.started:
            return
        if self.board.terminal:
            self.status_var.set(f"{symbol(self.board.winner)} thắng!" if self.board.winner else "Hòa — bàn cờ đã đầy.")
            self.pause_button.configure(state="disabled")
            return
        if self.paused:
            self.status_var.set("Đã tạm dừng. Bấm Tiếp tục để chơi.")
            return
        player = symbol(self.board.to_move)
        agent = self.roles[self.board.to_move]
        self.status_var.set(f"Lượt {player} · " + ("Chọn một ô trống." if agent == "Human" else f"{agent} đang suy nghĩ…"))
        if agent != "Human" and self.job is None:
            self._start_job(agent)

    def _start_job(self, agent):
        output = self.context.Queue()
        cancel = self.context.Event()
        self.request_serial += 1
        request_id = (self.epoch, self.request_serial)
        config = replace(self.config, seed=self.config.seed + self.board.move_count)
        process = self.context.Process(target=search_worker,
                                       args=(output, cancel, request_id, self.board.size,
                                             list(self.board.cells), agent, asdict(config)), daemon=True)
        self.job = {"process": process, "queue": output, "cancel": cancel, "id": request_id,
                    "agent": agent, "dead_polls": 0}
        try:
            process.start()
        except Exception as exc:
            self.job = None
            output.close()
            self.paused = True
            self.pause_button.configure(text="Tiếp tục")
            self.status_var.set("Không thể khởi chạy AI.")
            messagebox.showerror("Lỗi AI", str(exc), parent=self.root)
            return
        self.root.after(40, lambda: self._poll(request_id))

    def _poll(self, request_id):
        if self.closed or self.job is None or self.job["id"] != request_id:
            return
        job = self.job
        try:
            message = job["queue"].get_nowait()
        except queue.Empty:
            if not job["process"].is_alive():
                job["dead_polls"] += 1
            if job["dead_polls"] < 15:
                self.root.after(40, lambda: self._poll(request_id))
                return
            message = {"ok": False, "error": f"AI process exited without a result (code {job['process'].exitcode})."}
        agent = job["agent"]
        self._cancel_job()
        if not message["ok"]:
            self.paused = True
            self.pause_button.configure(text="Tiếp tục")
            self._advance()
            messagebox.showerror("Lỗi AI", message["error"], parent=self.root)
            return
        if message["request_id"] != request_id or request_id[0] != self.epoch or self.paused:
            return
        move = message["move"]
        if move not in self.board.legal_moves():
            self.paused = True
            self.pause_button.configure(text="Tiếp tục")
            self._advance()
            messagebox.showerror("Lỗi AI", "AI trả về nước đi không hợp lệ.", parent=self.root)
            return
        self._apply_move(move, agent, message["stats"])

    def _cancel_job(self):
        if self.job is None:
            return
        job, self.job = self.job, None
        job["cancel"].set()
        process = job["process"]
        process.join(timeout=0.04)
        if process.is_alive():
            process.terminate()
            process.join(timeout=0.04)
        job["queue"].cancel_join_thread()
        job["queue"].close()

    def toggle_pause(self):
        if not self.started or self.board.terminal:
            return
        self.paused = not self.paused
        if self.paused:
            self._cancel_job()
        self.pause_button.configure(text="Tiếp tục" if self.paused else "Tạm dừng")
        self._advance()

    def export_game(self):
        path = filedialog.asksaveasfilename(parent=self.root, title="Lưu lịch sử ván đấu", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            data = {"size": self.board.size, "rules": "Five or more; blocked ends allowed; X first",
                    "roles": {symbol(p): a for p, a in self.roles.items()}, "config": asdict(self.config),
                    "finished": self.board.terminal, "winner": symbol(self.board.winner) if self.board.terminal else None,
                    "moves": self.records}
            try:
                with open(path, "w", encoding="utf-8") as stream:
                    json.dump(data, stream, indent=2, ensure_ascii=False)
            except OSError as exc:
                messagebox.showerror("Không lưu được", str(exc), parent=self.root)

    def close(self):
        self.closed = True
        self._cancel_job()
        self.root.destroy()


def run():
    root = tk.Tk()
    GameApp(root)
    root.mainloop()

