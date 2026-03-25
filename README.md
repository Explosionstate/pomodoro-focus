# 番茄聚焦（Pomodoro Focus）

一个开箱即用的 Python 番茄钟项目，目标是让用户快速进入专注状态，并通过数据反馈形成持续习惯。

## 功能覆盖

- 自定义循环流
  - 工作时长
  - 短休时长
  - 长休时长
  - 几轮后进入长休
- 任务绑定与聚焦
  - 开始专注前强制输入本次任务
  - 倒计时只显示当前单一任务
- 柔和打断机制
  - 遇到临时事项可记录原因
  - 自动进入缓冲暂停，再恢复专注
- 待办任务列表
  - 快速添加/勾选完成
  - 可从待办一键填入当前专注任务
- GitHub 式热力图
  - 展示过去 365 天每日番茄数量
  - 颜色越深代表专注越多
- 黄金时间段分析
  - 基于近期专注记录给出高效时间窗口
  - 同时展示本周番茄数与连续打卡天数

## 运行方式

### 方式 A：直接点绿色三角运行（推荐）

- 打开 `run_pomodoro.py`
- 在 IDE（如 PyCharm / VS Code Python）点击运行按钮（绿色三角）即可
- 无需命令行

### 方式 A2：纯 HTML 页面（无需命令行）

- 直接双击打开 `index.html`
- 页面内已包含待办、番茄计时、柔和打断、热力图、黄金时间段分析
- 所有数据保存在浏览器本地 `localStorage`

### 打包成双击即开的 EXE

- 打开 `build_exe.py`
- 点击 IDE 运行按钮（绿色三角）
- 打包完成后，生成文件在：`dist/番茄聚焦.exe`

### HTML 桌面壳 EXE（推荐）

- 打开 `build_web_exe.py`
- 点击 IDE 运行按钮（绿色三角）
- 打包完成后，生成文件在：`dist/PomodoroFocusWeb.exe`
- 此版本使用 `index.html` 作为操作页面，并支持系统右下角提醒

### Edge 启动器 EXE（点击后自动 Edge 打开）

- 打开 `build_edge_exe.py`
- 点击 IDE 运行按钮（绿色三角）
- 打包完成后，生成文件在：`dist/PomodoroFocusEdge.exe`
- 双击后会自动用 Edge 打开 `index.html`（本地服务地址）

### 方式 B：Streamlit Web 版（可选）

```bash
pip install -r requirements.txt
streamlit run pomodoro_focus/app.py
```

运行后浏览器会自动打开界面。

## 数据存储

- 本地 SQLite：`pomodoro_focus/pomodoro.db`
- 不依赖云端，默认离线可用。
