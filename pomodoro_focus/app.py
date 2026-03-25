import json
import math
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
import streamlit as st
from streamlit_autorefresh import st_autorefresh


DB_PATH = Path(__file__).with_name("pomodoro.db")


@dataclass
class CycleConfig:
    work_minutes: int
    short_break_minutes: int
    long_break_minutes: int
    rounds_before_long_break: int


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
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
    conn.execute(
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
    conn.commit()


def add_todo(conn: sqlite3.Connection, title: str) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO todos (title, done, created_at, updated_at) VALUES (?, 0, ?, ?)",
        (title.strip(), now, now),
    )
    conn.commit()


def set_todo_status(conn: sqlite3.Connection, todo_id: int, done: bool) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE todos SET done = ?, updated_at = ? WHERE id = ?",
        (1 if done else 0, now, todo_id),
    )
    conn.commit()


def get_todos(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM todos ORDER BY done ASC, created_at DESC"))


def add_session(
    conn: sqlite3.Connection,
    task_name: str,
    phase: str,
    started_at: datetime,
    ended_at: datetime,
    completed: bool,
    interruptions: list[dict],
) -> None:
    minutes = max((ended_at - started_at).total_seconds() / 60.0, 0)
    conn.execute(
        """
        INSERT INTO sessions (
            task_name,
            phase,
            started_at,
            ended_at,
            duration_minutes,
            completed,
            interruptions_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
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
    conn.commit()


def get_daily_focus_counts(
    conn: sqlite3.Connection, days: int = 365
) -> dict[date, int]:
    today = date.today()
    start_day = today - timedelta(days=days - 1)
    rows = conn.execute(
        """
        SELECT substr(started_at, 1, 10) AS d, COUNT(*) AS c
        FROM sessions
        WHERE phase = 'work' AND completed = 1 AND d >= ?
        GROUP BY d
        """,
        (start_day.isoformat(),),
    ).fetchall()
    result: dict[date, int] = {}
    for row in rows:
        result[date.fromisoformat(row["d"])] = int(row["c"])
    return result


def get_work_sessions(
    conn: sqlite3.Connection, recent_days: int = 56
) -> list[sqlite3.Row]:
    start_day = (date.today() - timedelta(days=recent_days - 1)).isoformat()
    return list(
        conn.execute(
            """
            SELECT *
            FROM sessions
            WHERE phase = 'work' AND completed = 1 AND substr(started_at, 1, 10) >= ?
            ORDER BY started_at ASC
            """,
            (start_day,),
        )
    )


def init_state() -> None:
    defaults = {
        "phase": "work",
        "is_running": False,
        "is_paused": False,
        "pause_buffer_until": 0.0,
        "remaining_when_paused": 0,
        "current_task": "",
        "selected_todo": "",
        "session_started_at": None,
        "session_end_ts": 0.0,
        "session_interruptions": [],
        "work_rounds": 0,
        "toast_msg": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_phase_seconds(cfg: CycleConfig, phase: str) -> int:
    if phase == "work":
        return cfg.work_minutes * 60
    if phase == "short_break":
        return cfg.short_break_minutes * 60
    return cfg.long_break_minutes * 60


def phase_name(phase: str) -> str:
    names = {
        "work": "专注",
        "short_break": "短休",
        "long_break": "长休",
    }
    return names.get(phase, phase)


def advance_phase(cfg: CycleConfig) -> None:
    now = datetime.now()
    started_at = st.session_state["session_started_at"]
    if started_at is None:
        started_at = now

    current_task = st.session_state["current_task"] or "休息"
    add_session(
        st.session_state["conn"],
        task_name=current_task,
        phase=st.session_state["phase"],
        started_at=started_at,
        ended_at=now,
        completed=True,
        interruptions=st.session_state["session_interruptions"],
    )

    if st.session_state["phase"] == "work":
        st.session_state["work_rounds"] += 1
        if st.session_state["work_rounds"] % cfg.rounds_before_long_break == 0:
            st.session_state["phase"] = "long_break"
            st.session_state["toast_msg"] = "完成一轮大循环，进入长休。"
        else:
            st.session_state["phase"] = "short_break"
            st.session_state["toast_msg"] = "番茄完成，先短休一下。"
        st.session_state["current_task"] = ""
        st.session_state["selected_todo"] = ""
    else:
        st.session_state["phase"] = "work"
        st.session_state["toast_msg"] = "休息结束，准备开始下一次专注。"

    st.session_state["is_running"] = False
    st.session_state["is_paused"] = False
    st.session_state["session_started_at"] = None
    st.session_state["session_end_ts"] = 0.0
    st.session_state["session_interruptions"] = []


def start_session(cfg: CycleConfig) -> None:
    if st.session_state["phase"] == "work":
        task = st.session_state.get("input_task", "").strip()
        if not task:
            st.warning("开始专注前，请先输入本次番茄任务。")
            return
        st.session_state["current_task"] = task

    duration = get_phase_seconds(cfg, st.session_state["phase"])
    st.session_state["session_started_at"] = datetime.now()
    st.session_state["session_end_ts"] = time.time() + duration
    st.session_state["is_running"] = True
    st.session_state["is_paused"] = False
    st.session_state["session_interruptions"] = []


def pause_with_buffer(reason: str, buffer_minutes: int) -> None:
    now_ts = time.time()
    remaining = max(int(st.session_state["session_end_ts"] - now_ts), 0)
    st.session_state["is_running"] = False
    st.session_state["is_paused"] = True
    st.session_state["remaining_when_paused"] = remaining
    st.session_state["pause_buffer_until"] = now_ts + buffer_minutes * 60
    st.session_state["session_interruptions"].append(
        {
            "at": datetime.now().isoformat(timespec="seconds"),
            "reason": reason.strip() if reason.strip() else "临时中断",
            "buffer_minutes": buffer_minutes,
        }
    )


def resume_after_pause() -> None:
    st.session_state["is_paused"] = False
    st.session_state["is_running"] = True
    st.session_state["session_end_ts"] = (
        time.time() + st.session_state["remaining_when_paused"]
    )


def build_heatmap(counts: dict[date, int]):
    today = date.today()
    start_day = today - timedelta(days=364)
    all_days = [start_day + timedelta(days=i) for i in range(365)]
    weeks = math.ceil(len(all_days) / 7)
    matrix = [[0 for _ in range(weeks)] for _ in range(7)]

    for i, day in enumerate(all_days):
        week_idx = i // 7
        weekday_idx = day.weekday()
        matrix[weekday_idx][week_idx] = counts.get(day, 0)

    fig, ax = plt.subplots(figsize=(12, 2.8))
    cmap = ListedColormap(["#ebedf0", "#c6e48b", "#7bc96f", "#239a3b", "#196127"])
    norm = BoundaryNorm([0, 1, 3, 5, 8, 999], cmap.N)
    ax.imshow(matrix, cmap=cmap, norm=norm, aspect="auto")

    ax.set_yticks(range(7))
    ax.set_yticklabels(["周一", "周二", "周三", "周四", "周五", "周六", "周日"])

    month_ticks = []
    month_labels = []
    prev_month = None
    for i, day in enumerate(all_days):
        if day.day <= 7 and day.month != prev_month:
            month_ticks.append(i // 7)
            month_labels.append(f"{day.month}月")
            prev_month = day.month
    ax.set_xticks(month_ticks)
    ax.set_xticklabels(month_labels)

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)
    ax.set_title("过去 365 天专注热力图", loc="left", pad=10)
    return fig


def get_weekly_report(conn: sqlite3.Connection) -> dict:
    sessions = get_work_sessions(conn, recent_days=56)
    if not sessions:
        return {
            "best_window": "暂无数据",
            "week_tomatoes": 0,
            "current_streak": 0,
        }

    slot_minutes: dict[int, float] = {}
    for row in sessions:
        started = datetime.fromisoformat(row["started_at"])
        slot = started.hour * 2 + (1 if started.minute >= 30 else 0)
        slot_minutes[slot] = slot_minutes.get(slot, 0.0) + float(
            row["duration_minutes"]
        )

    best_slot = max(slot_minutes, key=slot_minutes.get)
    start_hour = best_slot // 2
    start_minute = 30 if best_slot % 2 else 0
    start_dt = datetime.combine(
        date.today(), dt_time(hour=start_hour, minute=start_minute)
    )
    end_dt = start_dt + timedelta(minutes=90)
    best_window = f"{start_dt.strftime('%H:%M')} - {end_dt.strftime('%H:%M')}"

    daily_counts = get_daily_focus_counts(conn, days=365)
    last_7_days = [date.today() - timedelta(days=i) for i in range(7)]
    week_tomatoes = sum(daily_counts.get(d, 0) for d in last_7_days)

    streak = 0
    cursor_day = date.today()
    while daily_counts.get(cursor_day, 0) > 0:
        streak += 1
        cursor_day -= timedelta(days=1)

    return {
        "best_window": best_window,
        "week_tomatoes": week_tomatoes,
        "current_streak": streak,
    }


def render_todo_panel(conn: sqlite3.Connection) -> None:
    st.subheader("待办任务列表")
    with st.form("add_todo", clear_on_submit=True):
        title = st.text_input("新增待办", placeholder="例如：复习操作系统第三章")
        submitted = st.form_submit_button("添加")
        if submitted and title.strip():
            add_todo(conn, title)
            st.rerun()

    todos = get_todos(conn)
    if not todos:
        st.info("还没有待办，先添加一个任务再开始番茄钟。")
        return

    for todo in todos:
        checked = st.checkbox(
            todo["title"],
            value=bool(todo["done"]),
            key=f"todo_{todo['id']}",
        )
        if checked != bool(todo["done"]):
            set_todo_status(conn, todo["id"], checked)
            st.rerun()


def render_focus_panel(cfg: CycleConfig) -> None:
    st.subheader("当前番茄钟")

    if st.session_state["toast_msg"]:
        st.success(st.session_state["toast_msg"])
        st.session_state["toast_msg"] = ""

    if st.session_state["phase"] == "work" and not st.session_state["is_running"]:
        todos = [
            r["title"]
            for r in get_todos(st.session_state["conn"])
            if not bool(r["done"])
        ]
        quick_select = st.selectbox(
            "从待办中选择（可选）",
            options=["", *todos],
            key="selected_todo",
            help="选中后会自动填入本次任务",
        )
        if quick_select:
            st.session_state["input_task"] = quick_select

        st.text_input(
            "本次专注任务（必填）",
            key="input_task",
            placeholder="例如：复习操作系统第三章",
        )

    if st.session_state["is_running"]:
        now_ts = time.time()
        remaining = max(int(st.session_state["session_end_ts"] - now_ts), 0)
        if remaining == 0:
            advance_phase(cfg)
            st.rerun()

        st_autorefresh(interval=1000, key="timer_refresh")
        mins, secs = divmod(remaining, 60)
        st.markdown(
            f"### {phase_name(st.session_state['phase'])}中：`{mins:02d}:{secs:02d}`"
        )

        if st.session_state["phase"] == "work":
            st.write(f"专注任务：**{st.session_state['current_task']}**")

            with st.expander("柔和打断（尽量减少破窗）"):
                reason = st.text_input("中断原因（可选）", key="pause_reason")
                buffer_minutes = st.slider(
                    "缓冲分钟", min_value=1, max_value=10, value=3
                )
                if st.button("记录并暂停"):
                    pause_with_buffer(reason, buffer_minutes)
                    st.rerun()
    elif st.session_state["is_paused"]:
        now_ts = time.time()
        wait_seconds = max(int(st.session_state["pause_buffer_until"] - now_ts), 0)
        st.warning("已进入柔和打断缓冲期，先处理紧急事项，再回来继续。")
        st.write(f"建议缓冲剩余：`{wait_seconds // 60:02d}:{wait_seconds % 60:02d}`")
        if st.button("我准备好了，恢复专注"):
            resume_after_pause()
            st.rerun()
    else:
        st.markdown(f"### 当前阶段：{phase_name(st.session_state['phase'])}")
        if st.session_state["phase"] == "work":
            st.caption("开始前必须定义本次专注任务，倒计时时仅显示这一件事。")
        if st.button("开始"):
            start_session(cfg)
            st.rerun()


def render_analytics(conn: sqlite3.Connection) -> None:
    st.subheader("专注分析")
    counts = get_daily_focus_counts(conn, days=365)
    st.pyplot(build_heatmap(counts), use_container_width=True)

    report = get_weekly_report(conn)
    col1, col2, col3 = st.columns(3)
    col1.metric("本周番茄", f"{report['week_tomatoes']} 个")
    col2.metric("连续打卡", f"{report['current_streak']} 天")
    col3.metric("黄金时间段", report["best_window"])


def main() -> None:
    st.set_page_config(page_title="番茄聚焦", page_icon="🍅", layout="wide")
    st.title("🍅 番茄聚焦：清晰规划，专注执行")
    st.caption("每次只做一件事，用可见进度维持连续性。")

    conn = get_conn()
    init_db(conn)
    init_state()
    st.session_state["conn"] = conn

    with st.sidebar:
        st.header("循环设置")
        cfg = CycleConfig(
            work_minutes=st.number_input(
                "工作时长（分钟）", min_value=1, max_value=120, value=25
            ),
            short_break_minutes=st.number_input(
                "短休时长（分钟）", min_value=1, max_value=60, value=5
            ),
            long_break_minutes=st.number_input(
                "长休时长（分钟）", min_value=1, max_value=120, value=15
            ),
            rounds_before_long_break=st.number_input(
                "几轮后长休", min_value=1, max_value=12, value=4
            ),
        )
        st.divider()
        st.write(
            "当前循环："
            f"`{cfg.work_minutes}m 专注 -> {cfg.short_break_minutes}m 短休`，"
            f"每 `{cfg.rounds_before_long_break}` 轮进入 `{cfg.long_break_minutes}m` 长休"
        )

    left, right = st.columns([1.15, 1.35])
    with left:
        render_todo_panel(conn)
        st.divider()
        render_focus_panel(cfg)
    with right:
        render_analytics(conn)


if __name__ == "__main__":
    main()
