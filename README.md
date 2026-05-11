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

---

## 阿里云部署（国内访问更顺畅）

适合：**管理员在大陆**，希望打开后台快、少遇到国际链路问题。代价是 **轻量服务器通常按年/按月少量付费**（常有新用户试用或特价），需要你会 **SSH 登录 + 复制几条命令**（仍比从零配 Linux 网站简单得多）。

### 1. 买什么

- 打开 [阿里云轻量应用服务器](https://www.aliyun.com/product/swas)（或搜「轻量应用服务器」）。  
- 选 **内地地域**（离你最近）。  
- 镜像建议：**Ubuntu 22.04**（或带 **Docker** 的应用镜像，可跳过下面安装 Docker）。  
- 套餐：**最低档**一般足够一名管理员使用。

### 2. 放行端口

在轻量控制台 → 你的实例 → **防火墙 / 安全组**：放行 **TCP `8000`**（先快速用起来）。  
以后若要 **80 / 443 + 域名**，再考虑配 Nginx 与 HTTPS（可选）。

### 3. 登录服务器并安装 Docker（Ubuntu 示例）

SSH 登录后执行（若镜像已预装 Docker 可跳过安装步骤）：

```bash
sudo apt update && sudo apt install -y docker.io git
sudo systemctl enable --now docker
```

把代码放到机器上（二选一）：

- **Git**：`git clone <你的仓库地址>`，再 `cd Dota2-Competition`  
- **本地上传**：用 SFTP 工具把项目文件夹传到服务器

### 4. 构建并运行（本仓库根目录有 Dockerfile）

**推荐：一键脚本**（密码写在单独文件里，避免在终端历史里留下明文）

在 **`Dota2-Competition` 仓库根目录**执行：

```bash
cp scripts/deploy-aliyun.example.env scripts/deploy-aliyun.env
nano scripts/deploy-aliyun.env
```

改好 `ADMIN_PASSWORD`、`SECRET_KEY` 后保存，再执行：

```bash
chmod +x scripts/deploy-aliyun.sh
bash scripts/deploy-aliyun.sh
```

可选环境变量（脚本默认值已够用）：

- **`HOST_PORT`**：宿主机映射端口，默认 `8000`（与轻量防火墙放行一致）。  
  例：`HOST_PORT=8080 bash scripts/deploy-aliyun.sh`  
- **`DATA_HOST_PATH`**：数据库目录在宿主机路径，默认 `/root/dota2-data`。

**手写 `docker run`（与脚本等价）**：

```bash
sudo docker build -t dota2-competition .
sudo mkdir -p /root/dota2-data
sudo docker run -d --restart unless-stopped --name dota2-competition \
  -p 8000:8000 \
  -e PORT=8000 \
  -e ADMIN_PASSWORD='在这里改成强密码' \
  -e SECRET_KEY='在这里改成一长串随机字符' \
  -e DATABASE_URL='sqlite:////data/competition.db' \
  -e TIMEZONE=Asia/Shanghai \
  -v /root/dota2-data:/data \
  dota2-competition
```

说明：

- **`DATABASE_URL`** 使用主机目录 **`/root/dota2-data`** 映射到容器内 `/data`，数据库文件会持久保存；重装容器只要不删宿主机目录，数据仍在。  
- 若改用 **阿里云 RDS PostgreSQL**，把 `DATABASE_URL` 换成 `postgresql+psycopg://...` 即可（需与安全组/白名单放行匹配）。

### 5. 访问

浏览器打开：`http://服务器公网IP:8000/`  
（登录页 → 使用你在 `ADMIN_PASSWORD` 里设的密码。）

### 6. 域名与备案（可选）

- **只用 IP + 端口**：一般 **不要求备案**，适合内部自用。  
- **要备案域名、默认 80 端口对外网站**：按阿里云要求完成 **ICP 备案**，再配 **Nginx 反向代理 + HTTPS**（可参考阿里云文档或以后再迭代）。

### 和 Render 对比（帮你下决心）

| | 阿里云轻量 | Render 免费档 |
|--|------------|----------------|
| 国内访问 | 通常更快、更稳 | 可能慢或不稳定 |
| 费用 | 多为低价包年/包月 | 常有免费额度 |
| 运维量 | 需要 SSH + 几条命令 | 几乎全图形界面 |

两者都用同一套 **`Dockerfile`**，应用本身不用改。
