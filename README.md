# Google Authenticator 二维码转密钥工具

这是一个简单的工具，用于将 Google Authenticator 导出的二维码转换为 2FA 密钥格式。

## 功能特点

- 📷 支持上传二维码图片（PNG、JPG、JPEG）
- 🔐 自动解析二维码并提取密钥
- 📋 一键复制密钥
- 🎨 美观简约的界面设计

## 安装步骤

### Windows 用户

1. **卸载旧的 pyzbar 库（如果已安装）**：
```bash
pip uninstall pyzbar -y
```

2. **安装新的依赖**：
```bash
pip install -r requirements.txt
```

或者直接运行安装脚本：
```bash
install.bat
```

3. **运行应用**：
```bash
python app.py
```

4. **在浏览器中打开**：
```
http://localhost:5000
```

### Linux/Mac 用户

1. 安装 Python 依赖：
```bash
pip install -r requirements.txt
```

2. 运行应用：
```bash
python app.py
```

3. 在浏览器中打开：
```
http://localhost:5000
```

## 使用方法

1. 点击上传区域或拖拽二维码图片
2. 预览图片确认无误
3. 点击"转换"按钮
4. 复制提取的密钥

## Docker 部署（推荐用于 Linux 服务器）

### 前置要求

- 已安装 Docker 和 Docker Compose
- Linux 服务器

### 快速开始

1. **克隆或上传项目文件到服务器**

2. **构建并启动容器**：
```bash
docker-compose up -d
```

3. **查看日志**：
```bash
docker-compose logs -f
```

4. **访问应用**：
```
http://服务器IP:5000
```

### Docker 命令

- **启动服务**：`docker-compose up -d`
- **停止服务**：`docker-compose down`
- **重启服务**：`docker-compose restart`
- **查看日志**：`docker-compose logs -f`
- **查看状态**：`docker-compose ps`
- **重新构建**：`docker-compose up -d --build`

### 自定义端口

如果需要修改端口，编辑 `docker-compose.yml` 文件中的端口映射：
```yaml
ports:
  - "8080:5000"  # 将 8080 改为你想要的端口
```

### 仅使用 Dockerfile（不使用 Docker Compose）

```bash
# 构建镜像
docker build -t google-2fa .

# 运行容器
docker run -d -p 5000:5000 --name google-2fa --restart unless-stopped google-2fa
```

## 技术说明

- 使用 **OpenCV** 进行二维码解析（替代 pyzbar，避免 Windows DLL 依赖问题）
- 支持标准的 `otpauth://` URL 格式
- 支持 **Google Authenticator 迁移格式**（protobuf），可解析多个账户
- 自动提取密钥并格式化显示
- 使用 **Protocol Buffers** 解析迁移格式数据

## 注意事项

- 确保二维码图片清晰可见
- 支持 Google Authenticator 导出的标准二维码格式
- 支持 Google Authenticator 迁移格式（包含多个账户）
- 密钥格式为 Base32 编码
- 如果遇到 DLL 错误，请确保已卸载 pyzbar 并重新安装依赖

