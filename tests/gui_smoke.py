"""Real Tk + spawned-worker lifecycle checks. Run explicitly on a desktop.

    python -m tests.gui_smoke
"""

import multiprocessing
import time
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ui.app import GameApp, MODES


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.app = GameApp(self.root)
        self.root.update()

    def tearDown(self):
        self.app.close()

    def pump_until(self, condition, timeout=12):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertTrue(condition(), "Timed out waiting for the GUI / AI worker.")

    def test_human_clicks_sizes_and_win(self):
        for size in (7, 9, 11):
            self.app.size_var.set(str(size))
            self.app.mode_var.set(MODES[2])
            self.app.new_game()
            self.root.update()
            sequence = [0, size * 2, 1, size * 2 + 2, 2, size * 2 + 4, 3, size * 2 + 6, 4]
            for move in sequence:
                x0, y0, step = self.app.grid_geometry
                row, col = divmod(move, size)
                event = SimpleNamespace(x=x0 + (col + 0.5) * step, y=y0 + (row + 0.5) * step)
                self.app._click(event)
            self.assertEqual(self.app.board.winner, 1)
            self.assertIn("thắng", self.app.status_var.get())

    def test_real_worker_pause_reset_resume_and_stale_result(self):
        self.app.mode_var.set(MODES[1])
        self.app.time_var.set("0.10")
        self.app.new_game()
        previous = self.app.job["id"]
        self.app.toggle_pause()
        self.assertIsNone(self.app.job)
        self.app._poll(previous)
        self.assertEqual(self.app.board.move_count, 0)
        self.app.toggle_pause()
        self.pump_until(lambda: self.app.board.move_count >= 2)
        self.app.toggle_pause()
        count = self.app.board.move_count
        self.root.update()
        self.assertEqual(count, self.app.board.move_count)
        self.app.mode_var.set(MODES[2])
        self.app.size_var.set("11")
        self.app.new_game()
        self.assertEqual(self.app.board.size, 11)
        self.assertEqual(self.app.board.move_count, 0)
        self.assertIsNone(self.app.job)
        self.app._poll(previous)
        self.assertEqual(self.app.board.move_count, 0)

    def test_human_o_starts_with_ai_x(self):
        self.app.human_var.set("O")
        self.app.time_var.set("0.05")
        self.app.new_game()
        self.pump_until(lambda: self.app.board.move_count == 1)
        self.assertEqual(self.app.roles[self.app.board.to_move], "Human")
        self.assertIsNone(self.app.job)

    def test_bad_input_does_not_reset_game(self):
        self.app.mode_var.set(MODES[2])
        self.app.new_game()
        self.app.board.play(0)
        self.app.time_var.set("nan")
        with patch("ui.app.messagebox.showerror") as error:
            self.app.new_game()
            error.assert_called_once()
        self.assertEqual(self.app.board.move_count, 1)

    def test_stats_fit_at_minimum_window_size(self):
        self.root.geometry("1000x760")
        self.app.stats_var.set("Alpha-beta · 0.750 giây\nĐộ sâu hoàn thành: 4\nNút đã xét: 123,456\nNhánh cắt: 2,345\nĐã chạm giới hạn thời gian.")
        self.root.update()
        label = self.app.stats_label
        self.assertGreaterEqual(label.winfo_height(), label.winfo_reqheight())
        self.assertLessEqual(label.winfo_y() + label.winfo_height(), label.master.winfo_height())


if __name__ == "__main__":
    multiprocessing.freeze_support()
    unittest.main()

