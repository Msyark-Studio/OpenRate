<div align="center">
<img src="static/favicon.ico" width="15%" alt="OpenRate">
<h1>OpenRate</h1>

<p>收集用户反馈，从未如此简单。</p>

OpenRate 是一个通用的评分数据收集与可视化系统。它提供 RESTful API 用于接收评分数据（1-5 星），并提供一个功能完善的管理面板用于查看统计图表、管理评分记录和用户账户。系统支持**访客模式**、**深色/浅色主题**自动切换，并采用 SQLite 作为数据库，方便部署。

## ✨ 功能特性

- **评分数据收集**  
  - 通过 HTTP POST 请求接收 1-5 整数评分  
  - 自动从请求头获取客户端 IP 地址  
  - 数据存入 SQLite 数据库（`api_data.db`）

- **可视化仪表板**  
  - 总评分数量、平均评分、今日/昨日统计卡片  
  - 评分分布饼图/柱状图  
  - 评分趋势折线图/柱状图（支持日期筛选）  
  - 筛选条件自动记忆（localStorage）

- **用户认证与权限**  
  - 基于 Flask-Login 的登录系统  
  - 管理员/普通用户角色分离  
  - 首次运行需通过 `/setup` 页面创建管理员账户  
  - 管理员可增删用户、修改任意用户密码  
  - 普通用户可修改自己的密码

- **访客模式**  
  - 管理员可在系统设置中开启/关闭访客模式  
  - 开启后未登录用户可查看统计数据与图表，但无法访问详细评分表格及任何写操作

- **系统设置**  
  - 自定义站点标题和左侧图标（FontAwesome）  
  - 一键切换访客模式

- **深色/浅色主题**  
  - 跟随系统主题自动切换  
  - 用户可手动切换，偏好保存至 localStorage

- **响应式设计**  
  - 适配桌面端、平板和手机屏幕
  - 表格在移动端自动调整为可滚动容器

> [!WARNING]
> 请注意，移动端未完全完成适配，可能会出现部分位置显示异常，不影响基本功能使用

## 🛠️ 技术栈

| 组件          | 技术                                 |
| ------------- | ------------------------------------ |
| 后端框架      | Flask 2.3.3                          |
| 用户认证      | Flask-Login, Werkzeug 密码哈希       |
| 数据库        | SQLite3（支持 Python 3.12 日期适配器）|
| 前端图表      | Chart.js 4.3                         |
| 前端图标      | FontAwesome 6                        |
| HTTP 客户端   | Axios                                |
| 容器化        | Docker + Docker Compose              |

## 📦 安装与部署

### 建议方式：1Panel

以1Panel v2.1.13为基准，在开始以下步骤前，你需要先安装1Panel

1. 在上方绿色Code按钮选择`Download ZIP`并解压上传到服务器合适位置
2. 左侧导航栏选择`网站`展开菜单选择`运行环境`，选择上方导航栏的`Python`
3. 点击`创建`，名称自定（如`OpenRate`），目录为刚刚上传的目录（注意此目录中直接包含`app.py`，`api_server.py`），应用选择Python，版本3.14.0，容器名称亦自定
4. 下方端口外部映射端口添加2个，分别设置为两个不同的端口，自定为空闲端口，应用端口分别为2347（收集）及2348（面板）。均勾选`端口外部访问`
5. 启动命令按以下填写
   ```
   pip install -r requirements.txt && python3 api_server.py && python3 app.py
   ```
6. 完成以上所有步骤后点击确认，等待启动，可打开日志观察进度

7. 启动完成后，打开面板，将自动跳转到首次启动的配置界面，根据指引配置管理员用户名与密码等。

## ⚙️ 配置说明

### 环境变量（可选）

|变量名|默认值|说明|
|-----|-----|-----|
|`SECRET_KEY`|随机字符串（开发）|生产环境务必修改|
|`DATABASE_RATINGS`|`api_data.db`|评分数据库文件名|
|`DATABASE_USERS`|`user_data.db`|用户数据库文件名|

### 系统设置（Web界面）

管理员登录后，点击导航栏「系统设置」可修改：

* 站点标题：显示在导航栏左侧
* 站点图标：FontAwesome 类名（例如 fas fa-chart-line）
* 访客模式：是否允许未登录用户查看统计图表

## 🚀 使用指南

### 收集评分数据

请求示例（无需认证）：

```bash
curl -X POST http://localhost:2347/api/record \
  -H "Content-Type: application/json" \
  -d '{"number": 4}'
```

响应：

```json
{
  "status": "success",
  "message": "Data recorded successfully",
  "record_id": 123,
  "timestamp": "2025-01-15T10:30:00",
  "number": 4,
  "ip_address": "192.168.1.100",
  "auto_detected_ip": true
}
```

### 管理面板

| 功能             | 操作路径                     | 权限要求       | 说明                                           |
| ---------------- | ---------------------------- | -------------- | ---------------------------------------------- |
| 查看统计仪表板   | `/`                          | 游客（若开启）或登录用户 | 显示总评分数量、平均分、今日/昨日评分及图表        |
| 查看详细评分记录 | `/` 下方表格                 | 登录用户       | 分页显示所有评分记录，支持日期筛选               |
| 编辑评分         | 表格中的✏️按钮                | 管理员         | 修改已有评分的分数（1-5星）                     |
| 删除评分         | 表格中的🗑️按钮                | 管理员         | 永久删除评分记录                                 |
| 用户管理         | `/admin`                     | 管理员         | 添加/删除用户、修改他人密码、设置管理员角色       |
| 修改个人密码     | `/change-password`           | 登录用户       | 修改当前登录账户的密码                           |
| 系统设置         | `/settings`                  | 管理员         | 修改站点标题、图标、开启/关闭访客模式             |

### 日期筛选与记忆

* 在仪表板选择起止日期，点击「筛选」，表格和图表均会过滤数据
* 刷新页面后筛选条件自动恢复
* 点击「清除」按钮重置筛选

## 📡 API 文档

| 功能         | 方法   | 端点                         | 端口 | 认证要求                                   | 说明                                   |
| ------------ | ------ | ---------------------------- | ---- | ------------------------------------------ | -------------------------------------- |
| 记录评分     | POST   | `/api/record`                | 2347 | 无                                         | 接收 `{"number": 1-5}`，自动记录 IP      |
| 仪表板数据   | GET    | `/api/dashboard`             | 2348 | 登录用户 或 访客模式开启                   | 返回统计卡片、评分分布、趋势数据        |
| 评分列表     | GET    | `/api/ratings`               | 2348 | 必须登录                                   | 分页获取评分记录，支持 `page`, `per_page`, `date_from`, `date_to` |
| 更新评分     | PUT    | `/api/ratings/<id>`          | 2348 | 管理员                                     | 修改指定评分的分数                       |
| 删除评分     | DELETE | `/api/ratings/<id>`          | 2348 | 管理员                                     | 删除指定评分记录                         |

📁 数据库结构

api_data.db（评分库）

```sql
CREATE TABLE api_records (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    number INTEGER NOT NULL,
    ip_address TEXT,
    request_time TEXT DEFAULT CURRENT_TIMESTAMP
);
```

user_data.db（用户库）

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE,
    password_hash TEXT,
    is_admin BOOLEAN,
    created_at TEXT
);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT
);
```

🔧 开发与调试

* 运行模式：设置 FLASK_ENV=development 可启用调试模式
* 日志：控制台会输出 SQL 查询错误和 IP 获取信息
* 图表调试：若图表不显示，检查浏览器控制台是否有 JavaScript 错误

🤝 贡献

欢迎提交 Issue 和 Pull Request。请确保代码风格符合 PEP 8，并更新相关文档。

📄 许可证

GPL v3

🙏 致谢

* 感谢所有开源项目贡献者
* 图标来自 FontAwesome
* 图表库 Chart.js
