# Dota2 个人积分赛管理后台

业务规则见 `产品方案2.md`，界面与部署思路见 `产品方案3.md`。

## 本地运行（开发）

**后端**（默认 SQLite `backend/dota2_competition.db`，管理密码默认 `666`）：

```powershell
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**前端**（需安装 Node.js）：

```powershell
cd frontend
npm install
npm run dev
```

浏览器访问 Vite 提示的地址（一般为 `http://127.0.0.1:5173`），API 通过开发代理转发到 `8000`。

## 生产构建（单服务）

```powershell
cd frontend
npm install
npm run build
cd ..\backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

构建产物输出到 `backend/static`，由 FastAPI 托管前端与 `/api`。

## 环境变量（可选）

| 变量 | 说明 |
|------|------|
| `ADMIN_PASSWORD` | 管理员密码（默认 `666`，生产请务必修改） |
| `SECRET_KEY` | 签发登录令牌的密钥（生产请务必随机设置） |
| `DATABASE_URL` | 数据库连接串；默认 SQLite |
| `TIMEZONE` | 比赛日与时钟，默认 `Asia/Shanghai` |

## 导入初始积分

```powershell
cd backend
python scripts/import_scores.py .\initial_scores.csv
```

CSV 列：`name`, `score`（重名覆盖当前积分）。

---

## 免费云端部署（仅一名管理员、几乎零运维）

适合：**不想买服务器、不想配 Nginx** → 用国外 PaaS **免费档**，连 GitHub，自动构建 Docker 镜像并给一个 **https://…** 链接。

### 你该选哪种？

| 方式 | 费用感观 | 特点 | 适合 |
|------|-----------|------|------|
| **[Render](https://render.com)** | 有免费 Web Service | 连仓库即用；免费实例**一段时间不用会休眠**，第一次打开要等十几秒～几十秒唤醒 | 最不折腾、一步步跟界面即可 |
| **[Railway](https://railway.app)** | 常按月赠额度 | 体验接近「点一下就部署」；额度用完后需付费或停服 | 能接受偶尔看一眼用量 |
| **国内轻量云**（阿里云/腾讯云「轻量」） | 常有小额包年 | 访问稳定、延迟低；要自己去控制台买实例、装 Docker 或用镜像 | 管理员主要在大陆、介意海外网速时 |

下面以 **Render + 本仓库自带 `Dockerfile`** 为例（**无需你自己懂运维**，会点网页即可）。

### 部署前准备（5 分钟）

1. 代码推到 **[GitHub](https://github.com)** 私有或公开仓库均可。  
2. 打开 [render.com](https://render.com) 注册（可用 GitHub 登录）。  
3. 想好三个值（自己记在备忘录里）：  
   - **`ADMIN_PASSWORD`**：管理员登录密码（不要用 `666`）。  
   - **`SECRET_KEY`**：任意一长串随机字符（可搜索「random string generator」生成）。  
   - **`DATABASE_URL`**（**强烈建议**）：不要用容器内 SQLite 长期存数据（重装/休眠可能丢文件）。在 Render 里新建 **PostgreSQL**，把控制台里的 **Internal Database URL** 改成 SQLAlchemy 形式即可，例如：  
     `postgresql+psycopg://用户:密码@主机:5432/数据库名`  
     （把官方给的 `postgres://...` 前缀改成 `postgresql+psycopg://` 即可。）

### 在 Render 上创建服务

1. Dashboard → **New +** → **Web Service**。  
2. Connect 你的 GitHub 仓库，分支选 `main`（或你用的分支）。  
3. **Runtime**：选 **Docker**（会自动用根目录 `Dockerfile`）。  
4. **Instance type**：选免费档即可（单管理员够用）。  
5. **Environment** 里添加变量：  
   - `ADMIN_PASSWORD` = 你的密码  
   - `SECRET_KEY` = 你的随机串  
   - `DATABASE_URL` = 上一步 PostgreSQL 连接串（若暂未配库，可先不配，仅用 SQLite **试用**，数据可能不持久）。  
   - （可选）`TIMEZONE` = `Asia/Shanghai`  
6. 保存并 **Deploy**。首次构建约几分钟；成功后页面会显示 **URL**，那就是管理员访问地址。

### 你会遇到的正常现象

- **第一次打开很慢**：免费档休眠唤醒，等一会儿再刷新即可。  
- **只有一个人用**：免费档通常足够；若将来变慢再考虑付费档。  
- **在大陆访问 Render 有时偏慢或被干扰**：若体验不好，可换 **Railway** 或上面说的 **国内轻量云 + Docker**。

### 容器说明

- 根目录 **`Dockerfile`**：先在镜像里执行 `npm run build`，再把静态文件放进 `backend/static`，最后只跑 **`uvicorn`**，与本地「单服务」一致。  
- 平台注入的 **`PORT`** 已由启动命令读取，无需改代码。

### Railway（简述）

新建 Project → Deploy from GitHub → 选仓库 → 变量同样设置 `ADMIN_PASSWORD`、`SECRET_KEY`、`DATABASE_URL` → Railway 识别 `Dockerfile` 构建即可。具体菜单名可能微调，逻辑与 Render 相同。
