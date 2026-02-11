# PostgreSQL 连接失败 - 诊断和解决方案

## 🔴 问题诊断

你的 PostgreSQL 连接失败，诊断结果显示：

```
✗ 主机名无法解析: db.kgmyhukvyygudsllypgv.supabase.co
可能原因: DNS 问题或主机名拼写错误
```

这意味着你的系统无法将主机名 `db.kgmyhukvyygudsllypgv.supabase.co` 转换为 IP 地址。

---

## 🔧 可能原因和解决方案

### 1️⃣ **网络连接问题** (最常见)

#### 症状:
- 无法连接到互联网
- WiFi 连接不稳定
- VPN 影响 DNS 解析

#### 解决方案:

```bash
# 检查网络连接
ping google.com

# 测试 DNS 解析
nslookup db.kgmyhukvyygudsllypgv.supabase.co

# 或使用 dig
dig db.kgmyhukvyygudsllypgv.supabase.co

# macOS 上刷新 DNS 缓存
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
```

### 2️⃣ **DNS 服务器问题**

#### 症状:
- 某些域名无法解析
- 其他网站可以访问，但 Supabase 不行

#### 解决方案:

改用公共 DNS 服务器（macOS）:

```bash
# 方案 A: 使用 Google DNS
# 系统偏好设置 → 网络 → Wi-Fi → 高级 → DNS
# 添加: 8.8.8.8 和 8.8.4.4

# 方案 B: 使用 Cloudflare DNS
# 添加: 1.1.1.1 和 1.0.0.1

# 方案 C: 命令行方式 (需要 sudo)
sudo nano /etc/resolv.conf
# 添加:
# nameserver 8.8.8.8
# nameserver 8.8.4.4
```

### 3️⃣ **防火墙/代理阻止**

#### 症状:
- 企业网络或公司 WiFi
- 使用了代理服务器
- VPN 有限制

#### 解决方案:

```bash
# 检查是否有代理设置
echo $http_proxy
echo $https_proxy

# 清除代理 (如果需要)
unset http_proxy
unset https_proxy

# 使用 traceroute 追踪路径
traceroute db.kgmyhukvyygudsllypgv.supabase.co
```

### 4️⃣ **PostgreSQL 连接字符串拼写错误**

检查 `.env` 文件中的配置:

```bash
# 查看当前配置
cat .env | grep SUPABASE_DB

# 应该看到:
# SUPABASE_DB_HOST=db.kgmyhukvyygudsllypgv.supabase.co
# SUPABASE_DB_NAME=postgres
# SUPABASE_DB_USER=postgres
# SUPABASE_DB_PASSWORD=你的密码
```

---

## ✅ 完整解决步骤

### 步骤 1: 测试网络

```bash
# 1. 测试互联网连接
ping -c 3 8.8.8.8
# 应该看到 "icmp_seq=1 time=XX ms"

# 2. 测试 DNS
dig db.kgmyhukvyygudsllypgv.supabase.co
# 应该看到一个 IP 地址
```

### 步骤 2: 刷新 DNS 缓存 (macOS)

```bash
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
sudo killall mDNSResponderHelper

# 稍等 3 秒后重试
sleep 3
nslookup db.kgmyhukvyygudsllypgv.supabase.co
```

### 步骤 3: 切换 DNS 服务器

**方案 A: 临时切换 (仅限当前会话)**

```bash
# 在 Python 中使用公共 DNS
cat > ~/.dns_config.py << 'EOF'
import socket

# 使用 Google DNS
socket.setdefaulttimeout(5)
# Python 会自动使用系统 DNS，但可以强制使用特定 DNS：

import dns.resolver
resolver = dns.resolver.Resolver()
resolver.nameservers = ['8.8.8.8', '8.8.4.4']

answer = resolver.resolve('db.kgmyhukvyygudsllypgv.supabase.co', 'A')
print(answer)
EOF

python ~/.dns_config.py
```

**方案 B: 永久切换 (通过系统设置)**

1. 打开 System Preferences
2. 点击 Network
3. 选择你的网络连接
4. 点击 Advanced
5. 选择 DNS 标签
6. 添加 `8.8.8.8` 和 `1.1.1.1`

### 步骤 4: 重试连接

```bash
cd /Users/fupeggy/NL2SQL

# 再次运行诊断
source .venv/bin/activate
python diagnose_postgres_connection.py

# 如果仍然失败，运行完整工具
python find_all_tables_comprehensive.py
```

---

## 🛠️ 使用 SSH 隧道 (备选方案)

如果网络问题无法解决，可以使用 SSH 隧道：

```bash
# 1. 创建 SSH 隧道 (使用 Supabase SSH 密钥)
ssh -L 5432:db.kgmyhukvyygudsllypgv.supabase.co:5432 user@your_supabase_machine

# 2. 在另一个终端中连接到本地端口
export SUPABASE_DB_HOST=localhost
python find_all_tables_comprehensive.py
```

---

## 📝 快速检查清单

- [ ] 网络连接正常 (`ping google.com` 成功)
- [ ] DNS 正常 (`nslookup db.kgmyhukvyygudsllypgv.supabase.co` 返回 IP)
- [ ] `.env` 文件配置正确
- [ ] psycopg2 已安装 (`pip list | grep psycopg2`)
- [ ] 防火墙/VPN 没有阻止 PostgreSQL 端口 5432
- [ ] 账户和密码正确

---

## 📞 需要进一步帮助?

1. **获取 Supabase 连接信息:**
   - 访问 https://app.supabase.com
   - 选择你的项目
   - 点击 Database → Connection String
   - 复制连接信息

2. **测试连接:**
   ```bash
   # 使用 psql 客户端直接测试
   psql -h db.kgmyhukvyygudsllypgv.supabase.co \
        -U postgres \
        -d postgres
   ```

3. **查看详细错误:**
   ```bash
   python -c "
   import socket
   import sys
   
   host = 'db.kgmyhukvyygudsllypgv.supabase.co'
   port = 5432
   
   try:
       socket.create_connection((host, port), timeout=5)
       print(f'✓ 可以连接到 {host}:{port}')
   except Exception as e:
       print(f'✗ 连接失败: {e}')
       sys.exit(1)
   "
   ```
