# Pomodoro Focus

一个专注执行导向的番茄钟应用。  
核心目标：让用户“无脑上手”，清晰规划、持续执行当前任务。

---

## 功能概览

- 自定义循环流
  - 工作时长（如 25 分钟）
  - 短休时长（如 5 分钟）
  - 长休时长（如 15 分钟）
  - 几轮后进入长休
  - 长休可开关（可禁用）

- 任务绑定与视觉聚焦
  - 开始专注前必须输入“本次要做什么”
  - 倒计时阶段只展示当前任务，降低分心

- 柔和打断机制
  - 专注中可记录中断原因
  - 缓冲暂停后可恢复原进度继续专注

- 清单体系
  - 今日清单：当天任务管理
  - 长期清单：每日都要做，按天自动重置完成状态
  - 历史清单：昨日未完成的今日任务自动归档

- 数据分析
  - GitHub 风格 365 天专注热力图（绿点矩阵）
  - 每周黄金时间段分析（高专注时段）
  - 本周番茄数、连续打卡天数

- 通知提醒
  - 番茄结束与休息结束支持系统提醒
  - 支持桌面壳通知桥接（更稳定）

---

## 项目结构

- `index.html`  
  主操作页面（UI + 业务逻辑 + 本地数据存储）

- `web_shell.py`  
  桌面壳（pywebview）入口，支持系统通知桥接

- `edge_launcher.py`  
  Edge 启动器入口（启动后自动用 Edge 打开页面）

- `build_web_exe.py`  
  打包桌面壳 EXE

- `build_edge_exe.py`  
  打包 Edge 启动器 EXE

- `run_pomodoro.py`  
  Tk 桌面版入口（历史版本保留）

- `pomodoro_focus/app.py`  
  Streamlit 版本入口（历史版本保留）

---

## 快速开始

### 方式 1：直接打开 HTML

双击打开 `index.html` 即可使用。  
说明：数据默认保存到浏览器 `localStorage`。

### 方式 2：打包桌面壳 EXE（推荐）

运行 `build_web_exe.py`（IDE 点绿色三角即可）后，生成：

- `dist/PomodoroFocusWeb.exe`

### 方式 3：打包 Edge 启动器 EXE

运行 `build_edge_exe.py` 后，生成：

- `dist/PomodoroFocusEdge.exe`

双击后自动启动本地服务并用 Edge 打开页面。

如果 `dist/tomato.jpeg` 存在，打包时会自动转换为 `dist/tomato.ico` 并作为 exe 图标。

---

## 依赖安装

```bash
pip install -r requirements.txt
```
