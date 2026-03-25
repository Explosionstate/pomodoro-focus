import json
import sqlite3
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from tkinter import messagebox, simpledialog


DB_PATH = Path(__file__).with_name("pomodoro_gui.db")


PALETTE = {
    "bg1": "#f4f0ea",
    "bg2": "#e9eef2",
    "ink": "#1f1f1f",
    "muted": "#6d6a66",
    "card": "#ffffff",
    "line": "#e6dfd7",
    "accent": "#c96c4a",
    "accent2": "#2d7f7e",
    "chip": "#fdfaf6",
    "chip_border": "#eee6dd",
}


@dataclass
class CycleConfig:
    work_minutes: int
    short_break_minutes: int
    long_break_minutes: int
    rounds_before_long_break: int


class PomodoroDB:
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_name TEXT NOT NULL,
                phase TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                duration_minutes REAL NOT NULL,
                completed INTEGER NOT NULL,
                interruptions_json TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        self.conn.commit()

    def add_todo(self, title: str) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "INSERT INTO todos (title, done, created_at, updated_at) VALUES (?, 0, ?, ?)",
            (title.strip(), now, now),
        )
        self.conn.commit()

    def delete_todo(self, todo_id: int) -> None:
        self.conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        self.conn.commit()

    def set_todo_done(self, todo_id: int, done: bool) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            "UPDATE todos SET done = ?, updated_at = ? WHERE id = ?",
            (1 if done else 0, now, todo_id),
        )
        self.conn.commit()

    def get_todos(self):
        return self.conn.execute(
            "SELECT * FROM todos ORDER BY done ASC, created_at DESC"
        ).fetchall()

    def add_session(
        self,
        task_name: str,
        phase: str,
        started_at: datetime,
        ended_at: datetime,
        completed: bool,
        interruptions: list,
    ) -> None:
        minutes = max((ended_at - started_at).total_seconds() / 60.0, 0)
        self.conn.execute(
            """
            INSERT INTO sessions (task_name, phase, started_at, ended_at, duration_minutes, completed, interruptions_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_name.strip() if task_name.strip() else "未命名任务",
                phase,
                started_at.isoformat(timespec="seconds"),
                ended_at.isoformat(timespec="seconds"),
                minutes,
                1 if completed else 0,
                json.dumps(interruptions, ensure_ascii=False),
            ),
        )
        self.conn.commit()

    def get_daily_focus_counts(self, days: int = 365) -> dict:
        today = date.today()
        start_day = today - timedelta(days=days - 1)
        rows = self.conn.execute(
            """
            SELECT substr(started_at, 1, 10) AS d, COUNT(*) AS c
            FROM sessions
            WHERE phase = 'work' AND completed = 1 AND d >= ?
            GROUP BY d
            """,
            (start_day.isoformat(),),
        ).fetchall()
        return {date.fromisoformat(row["d"]): int(row["c"]) for row in rows}

    def get_recent_work_sessions(self, days: int = 56):
        start_day = (date.today() - timedelta(days=days - 1)).isoformat()
        return self.conn.execute(
            """
            SELECT *
            FROM sessions
            WHERE phase = 'work' AND completed = 1 AND substr(started_at, 1, 10) >= ?
            ORDER BY started_at ASC
            """,
            (start_day,),
        ).fetchall()


class PomodoroApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("番茄聚焦")
        self.geometry("1120x780")
        self.minsize(1020, 720)
        self.configure(bg=PALETTE["bg1"])

        self.db = PomodoroDB(DB_PATH)

        self.phase = "work"
        self.work_rounds = 0
        self.is_running = False
        self.is_paused = False
        self.current_task = ""
        self.session_started_at = None
        self.session_end_at = None
        self.pause_buffer_end_at = None
        self.remaining_when_paused = 0
        self.interruptions = []

        self._build_background()
        self._build_shell()
        self.refresh_todos()
        self.refresh_analytics()
        self.update_timer_ui()

    def _build_background(self):
        self.bg = tk.Canvas(self, highlightthickness=0, bg=PALETTE["bg1"])
        self.bg.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.bind("<Configure>", self._paint_gradient)

    def _paint_gradient(self, _event=None):
        w = self.winfo_width()
        h = self.winfo_height()
        self.bg.delete("all")
        self.bg.create_rectangle(0, 0, w, h, fill=PALETTE["bg1"], outline="")
        self.bg.create_oval(-220, -220, w * 0.5, h * 0.55, fill="#f9f6f2", outline="")
        self.bg.create_oval(
            w * 0.55, -180, w + 180, h * 0.5, fill="#d8e4e8", outline=""
        )
        self.bg.create_oval(
            w * 0.6, h * 0.6, w + 220, h + 220, fill="#eef3f4", outline=""
        )

    def _card(self, parent):
        frame = tk.Frame(
            parent,
            bg=PALETTE["card"],
            bd=0,
            highlightthickness=1,
            highlightbackground=PALETTE["line"],
        )
        return frame

    def _btn(self, parent, text, cmd, kind="accent", width=10):
        bg = (
            PALETTE["accent"]
            if kind == "accent"
            else PALETTE["accent2"]
            if kind == "alt"
            else "#ece6e0"
        )
        fg = "#ffffff" if kind in {"accent", "alt"} else "#5e5148"
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=bg,
            fg=fg,
            activebackground=bg,
            activeforeground=fg,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            width=width,
            cursor="hand2",
            padx=8,
            pady=8,
        )

    def _build_shell(self):
        shell = tk.Frame(self, bg=PALETTE["card"], highlightthickness=0)
        shell.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.95, relheight=0.93)

        header = tk.Frame(shell, bg=PALETTE["card"])
        header.pack(fill="x", padx=18, pady=(16, 10))

        tk.Label(
            header,
            text="番茄聚焦",
            bg=PALETTE["card"],
            fg=PALETTE["ink"],
            font=("Times New Roman", 28, "bold"),
        ).pack(side="left")

        self.header_count = tk.Label(
            header,
            text="0 ITEMS",
            bg=PALETTE["card"],
            fg=PALETTE["muted"],
            font=("Consolas", 10, "bold"),
        )
        self.header_count.pack(side="right", pady=8)

        main = tk.Frame(shell, bg=PALETTE["card"])
        main.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left = self._card(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        right = self._card(main)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self._build_todo_panel(left)
        self._build_focus_panel(right)

        bottom = self._card(shell)
        bottom.pack(fill="x", padx=16, pady=(0, 14))
        self._build_analytics_panel(bottom)

    def _build_todo_panel(self, parent):
        tk.Label(
            parent,
            text="今日清单",
            bg=PALETTE["card"],
            fg=PALETTE["ink"],
            font=("Times New Roman", 22, "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 6))

        input_row = tk.Frame(parent, bg=PALETTE["card"])
        input_row.pack(fill="x", padx=16, pady=(2, 10))

        self.todo_entry = tk.Entry(
            input_row,
            font=("Segoe UI", 11),
            bg="#fffefb",
            fg=PALETTE["ink"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=PALETTE["line"],
            highlightcolor=PALETTE["accent"],
        )
        self.todo_entry.pack(side="left", fill="x", expand=True, ipady=8)
        self._btn(input_row, "添加", self.add_todo, "accent", width=8).pack(
            side="left", padx=(8, 0)
        )

        list_wrap = tk.Frame(parent, bg=PALETTE["card"])
        list_wrap.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        self.todo_listbox = tk.Listbox(
            list_wrap,
            activestyle="none",
            bg=PALETTE["chip"],
            fg=PALETTE["ink"],
            selectbackground="#f5e7e0",
            selectforeground="#8a4a30",
            font=("Segoe UI", 11),
            relief="flat",
            highlightthickness=1,
            highlightbackground=PALETTE["chip_border"],
            bd=0,
        )
        self.todo_listbox.pack(side="left", fill="both", expand=True)
        self.todo_listbox.bind("<Double-Button-1>", lambda _e: self.delete_todo())

        scroll = tk.Scrollbar(list_wrap, command=self.todo_listbox.yview)
        self.todo_listbox.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        actions = tk.Frame(parent, bg=PALETTE["card"])
        actions.pack(fill="x", padx=16, pady=(0, 12))
        self._btn(actions, "完成/撤销", self.toggle_todo_done, "alt", width=10).pack(
            side="left"
        )
        self._btn(
            actions, "填入任务", self.use_todo_for_focus, "accent", width=10
        ).pack(side="left", padx=8)
        self._btn(actions, "删除", self.delete_todo, "plain", width=8).pack(side="left")

        tk.Label(
            parent,
            text="点击完成/撤销，双击直接删除。",
            bg=PALETTE["card"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=16, pady=(0, 12))

    def _build_focus_panel(self, parent):
        tk.Label(
            parent,
            text="当前番茄",
            bg=PALETTE["card"],
            fg=PALETTE["ink"],
            font=("Times New Roman", 22, "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 6))

        cfg = tk.Frame(parent, bg=PALETTE["card"])
        cfg.pack(fill="x", padx=16, pady=(0, 10))

        self.work_var = tk.IntVar(value=25)
        self.short_var = tk.IntVar(value=5)
        self.long_var = tk.IntVar(value=15)
        self.rounds_var = tk.IntVar(value=4)

        fields = [
            ("工作", self.work_var),
            ("短休", self.short_var),
            ("长休", self.long_var),
            ("长休轮次", self.rounds_var),
        ]
        for idx, (title, var) in enumerate(fields):
            col = tk.Frame(cfg, bg=PALETTE["card"])
            col.grid(row=0, column=idx, padx=(0, 8), sticky="w")
            tk.Label(
                col,
                text=title,
                bg=PALETTE["card"],
                fg=PALETTE["muted"],
                font=("Segoe UI", 9),
            ).pack(anchor="w")
            spin = tk.Spinbox(
                col,
                from_=1,
                to=180,
                width=5,
                textvariable=var,
                font=("Consolas", 10),
                relief="flat",
            )
            spin.pack(anchor="w")

        self.phase_label = tk.Label(
            parent,
            text="当前阶段: 专注",
            bg=PALETTE["card"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 12),
        )
        self.phase_label.pack(anchor="w", padx=16, pady=(0, 2))

        self.timer_label = tk.Label(
            parent,
            text="25:00",
            bg=PALETTE["card"],
            fg=PALETTE["ink"],
            font=("Consolas", 56, "bold"),
        )
        self.timer_label.pack(anchor="center", pady=(0, 6))

        self.current_task_label = tk.Label(
            parent,
            text="当前任务: (等待开始)",
            bg=PALETTE["card"],
            fg="#145a32",
            font=("Segoe UI", 12, "bold"),
        )
        self.current_task_label.pack(anchor="w", padx=16)

        tk.Label(
            parent,
            text="开始专注前必须输入任务，倒计时界面只显示这一件事。",
            bg=PALETTE["card"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=16, pady=(2, 8))

        self.task_entry = tk.Entry(
            parent,
            font=("Segoe UI", 11),
            bg="#fffefb",
            fg=PALETTE["ink"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=PALETTE["line"],
            highlightcolor=PALETTE["accent"],
        )
        self.task_entry.pack(fill="x", padx=16, ipady=8)

        btns = tk.Frame(parent, bg=PALETTE["card"])
        btns.pack(fill="x", padx=16, pady=12)
        self.start_btn = self._btn(btns, "开始", self.start_or_resume, "accent", 9)
        self.start_btn.pack(side="left")
        self._btn(btns, "柔和打断", self.soft_interrupt, "alt", 9).pack(
            side="left", padx=8
        )
        self._btn(btns, "完成阶段", self.complete_phase_manual, "plain", 9).pack(
            side="left"
        )

        self.buffer_label = tk.Label(
            parent,
            text="",
            bg=PALETTE["card"],
            fg="#8a4b08",
            font=("Segoe UI", 10, "bold"),
        )
        self.buffer_label.pack(anchor="w", padx=16, pady=(0, 12))

    def _build_analytics_panel(self, parent):
        top = tk.Frame(parent, bg=PALETTE["card"])
        top.pack(fill="x", padx=14, pady=(10, 6))
        tk.Label(
            top,
            text="专注热力图与周报",
            bg=PALETTE["card"],
            fg=PALETTE["ink"],
            font=("Times New Roman", 17, "bold"),
        ).pack(side="left")
        self._btn(top, "刷新", self.refresh_analytics, "accent", 7).pack(side="right")

        self.report_label = tk.Label(
            top,
            text="",
            bg=PALETTE["card"],
            fg=PALETTE["muted"],
            font=("Consolas", 10, "bold"),
        )
        self.report_label.pack(side="right", padx=12)

        self.heatmap_canvas = tk.Canvas(
            parent, bg="#ffffff", height=220, highlightthickness=0
        )
        self.heatmap_canvas.pack(fill="x", padx=14, pady=(0, 12))

    def get_config(self) -> CycleConfig:
        return CycleConfig(
            work_minutes=max(1, int(self.work_var.get())),
            short_break_minutes=max(1, int(self.short_var.get())),
            long_break_minutes=max(1, int(self.long_var.get())),
            rounds_before_long_break=max(1, int(self.rounds_var.get())),
        )

    @staticmethod
    def phase_name(phase: str) -> str:
        return {"work": "专注", "short_break": "短休", "long_break": "长休"}.get(
            phase, phase
        )

    def get_phase_seconds(self) -> int:
        cfg = self.get_config()
        if self.phase == "work":
            return cfg.work_minutes * 60
        if self.phase == "short_break":
            return cfg.short_break_minutes * 60
        return cfg.long_break_minutes * 60

    def add_todo(self):
        text = self.todo_entry.get().strip()
        if not text:
            return
        self.db.add_todo(text)
        self.todo_entry.delete(0, tk.END)
        self.refresh_todos()

    def refresh_todos(self):
        self.todo_items = self.db.get_todos()
        self.todo_listbox.delete(0, tk.END)
        active_count = 0
        for row in self.todo_items:
            done = bool(row["done"])
            if not done:
                active_count += 1
            mark = "☑" if done else "☐"
            self.todo_listbox.insert(tk.END, f"{mark}  {row['title']}")
        self.header_count.config(text=f"{active_count} ITEMS")

    def _selected_todo(self):
        sel = self.todo_listbox.curselection()
        if not sel:
            return None
        idx = sel[0]
        return self.todo_items[idx]

    def toggle_todo_done(self):
        row = self._selected_todo()
        if row is None:
            messagebox.showinfo("提示", "请先选择一条待办。")
            return
        self.db.set_todo_done(int(row["id"]), not bool(row["done"]))
        self.refresh_todos()

    def delete_todo(self):
        row = self._selected_todo()
        if row is None:
            return
        self.db.delete_todo(int(row["id"]))
        self.refresh_todos()

    def use_todo_for_focus(self):
        row = self._selected_todo()
        if row is None:
            messagebox.showinfo("提示", "请先选择一条待办。")
            return
        self.task_entry.delete(0, tk.END)
        self.task_entry.insert(0, row["title"])

    def start_or_resume(self):
        if self.is_paused:
            self.resume_from_pause()
            return
        if self.is_running:
            return

        if self.phase == "work":
            task = self.task_entry.get().strip()
            if not task:
                messagebox.showwarning("需要任务", "开始专注前，必须输入本次番茄任务。")
                return
            self.current_task = task
        else:
            self.current_task = "休息恢复"

        self.session_started_at = datetime.now()
        self.session_end_at = self.session_started_at + timedelta(
            seconds=self.get_phase_seconds()
        )
        self.is_running = True
        self.is_paused = False
        self.interruptions = []
        self.update_timer_ui()
        self.tick()

    def soft_interrupt(self):
        if not self.is_running or self.phase != "work":
            return
        reason = (
            simpledialog.askstring("柔和打断", "中断原因(可空):", parent=self)
            or "临时中断"
        )
        buffer_minutes = simpledialog.askinteger(
            "缓冲时长",
            "缓冲几分钟后再恢复专注？(1-15)",
            parent=self,
            minvalue=1,
            maxvalue=15,
            initialvalue=3,
        )
        if buffer_minutes is None:
            return
        now = datetime.now()
        self.remaining_when_paused = max(
            int((self.session_end_at - now).total_seconds()), 0
        )
        self.pause_buffer_end_at = now + timedelta(minutes=buffer_minutes)
        self.is_running = False
        self.is_paused = True
        self.interruptions.append(
            {
                "at": now.isoformat(timespec="seconds"),
                "reason": reason,
                "buffer_minutes": int(buffer_minutes),
            }
        )
        self.update_timer_ui()

    def resume_from_pause(self):
        self.is_paused = False
        self.is_running = True
        self.session_end_at = datetime.now() + timedelta(
            seconds=self.remaining_when_paused
        )
        self.update_timer_ui()
        self.tick()

    def complete_phase_manual(self):
        if not self.is_running and not self.is_paused:
            return
        self.complete_current_phase()

    def complete_current_phase(self):
        ended_at = datetime.now()
        started_at = self.session_started_at or ended_at
        self.db.add_session(
            task_name=self.current_task,
            phase=self.phase,
            started_at=started_at,
            ended_at=ended_at,
            completed=True,
            interruptions=self.interruptions,
        )

        cfg = self.get_config()
        if self.phase == "work":
            self.work_rounds += 1
            if self.work_rounds % cfg.rounds_before_long_break == 0:
                self.phase = "long_break"
                messagebox.showinfo("完成", "本轮专注完成，进入长休。")
            else:
                self.phase = "short_break"
                messagebox.showinfo("完成", "本次番茄完成，进入短休。")
            self.task_entry.delete(0, tk.END)
            self.current_task = ""
        else:
            self.phase = "work"
            messagebox.showinfo("休息结束", "休息结束，回到专注阶段。")

        self.is_running = False
        self.is_paused = False
        self.session_started_at = None
        self.session_end_at = None
        self.pause_buffer_end_at = None
        self.remaining_when_paused = 0
        self.interruptions = []

        self.update_timer_ui()
        self.refresh_analytics()

    def tick(self):
        if self.is_running:
            remain = int((self.session_end_at - datetime.now()).total_seconds())
            if remain <= 0:
                self.complete_current_phase()
                return
            self.update_timer_ui()
        elif self.is_paused:
            self.update_timer_ui()
        self.after(1000, self.tick)

    def update_timer_ui(self):
        if self.is_running:
            remain = max(int((self.session_end_at - datetime.now()).total_seconds()), 0)
        elif self.is_paused:
            remain = self.remaining_when_paused
        else:
            remain = self.get_phase_seconds()

        mm, ss = divmod(remain, 60)
        self.timer_label.config(text=f"{mm:02d}:{ss:02d}")
        self.phase_label.config(text=f"当前阶段: {self.phase_name(self.phase)}")

        if self.phase == "work" and (self.is_running or self.is_paused):
            self.current_task_label.config(text=f"当前任务: {self.current_task}")
        elif self.phase == "work":
            self.current_task_label.config(text="当前任务: (等待开始)")
        else:
            self.current_task_label.config(text="当前任务: 休息恢复")

        if self.is_paused and self.pause_buffer_end_at:
            sec = max(
                int((self.pause_buffer_end_at - datetime.now()).total_seconds()), 0
            )
            bmm, bss = divmod(sec, 60)
            self.buffer_label.config(
                text=f"柔和打断缓冲中，建议等待: {bmm:02d}:{bss:02d}"
            )
            self.start_btn.config(text="恢复")
        else:
            self.buffer_label.config(text="")
            self.start_btn.config(text="开始")

    def refresh_analytics(self):
        counts = self.db.get_daily_focus_counts(365)
        report = self.build_weekly_report(counts)
        self.report_label.config(
            text=(
                f"本周番茄 {report['week_tomatoes']}  |  连续打卡 {report['streak']} 天  |  黄金时间段 {report['best_window']}"
            )
        )
        self.draw_heatmap(counts)

    def build_weekly_report(self, daily_counts: dict):
        sessions = self.db.get_recent_work_sessions(56)
        if not sessions:
            return {"best_window": "暂无数据", "week_tomatoes": 0, "streak": 0}

        slot_minutes = {}
        for row in sessions:
            started = datetime.fromisoformat(row["started_at"])
            slot = started.hour * 2 + (1 if started.minute >= 30 else 0)
            slot_minutes[slot] = slot_minutes.get(slot, 0) + float(
                row["duration_minutes"]
            )

        best_slot = max(slot_minutes, key=slot_minutes.get)
        sh = best_slot // 2
        sm = 30 if best_slot % 2 else 0
        start_dt = datetime.combine(date.today(), dtime(hour=sh, minute=sm))
        end_dt = start_dt + timedelta(minutes=90)

        week_days = [date.today() - timedelta(days=i) for i in range(7)]
        week_tomatoes = sum(daily_counts.get(d, 0) for d in week_days)

        streak = 0
        cur = date.today()
        while daily_counts.get(cur, 0) > 0:
            streak += 1
            cur -= timedelta(days=1)

        return {
            "best_window": f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}",
            "week_tomatoes": week_tomatoes,
            "streak": streak,
        }

    def draw_heatmap(self, counts: dict):
        c = self.heatmap_canvas
        c.delete("all")
        w = c.winfo_width() or 980

        colors = ["#ebedf0", "#c6e48b", "#7bc96f", "#239a3b", "#196127"]

        def color_of(value: int) -> str:
            if value <= 0:
                return colors[0]
            if value <= 2:
                return colors[1]
            if value <= 4:
                return colors[2]
            if value <= 7:
                return colors[3]
            return colors[4]

        today = date.today()
        start_day = today - timedelta(days=364)
        all_days = [start_day + timedelta(days=i) for i in range(365)]

        x0 = 38
        y0 = 40
        cell = 11
        gap = 3

        c.create_text(
            12,
            18,
            text="过去 365 天专注热力图",
            anchor="w",
            fill=PALETTE["muted"],
            font=("Segoe UI", 10, "bold"),
        )

        weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
        for i, name in enumerate(weekday_names):
            y = y0 + i * (cell + gap) + 6
            c.create_text(
                16,
                y,
                text=name,
                anchor="w",
                fill=PALETTE["muted"],
                font=("Segoe UI", 8),
            )

        last_month = None
        for i, d in enumerate(all_days):
            week = i // 7
            weekday = d.weekday()
            x = x0 + week * (cell + gap)
            y = y0 + weekday * (cell + gap)
            if x > w - 14:
                break
            c.create_rectangle(
                x, y, x + cell, y + cell, fill=color_of(counts.get(d, 0)), outline=""
            )
            if d.day <= 7 and d.month != last_month:
                c.create_text(
                    x,
                    y0 - 12,
                    text=f"{d.month}月",
                    anchor="w",
                    fill=PALETTE["muted"],
                    font=("Segoe UI", 8),
                )
                last_month = d.month


if __name__ == "__main__":
    app = PomodoroApp()
    app.mainloop()
