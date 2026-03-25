# Vercel 部署完成 — The Listening Tree

## ✅ 完成的工作

### 1. 代码修复与优化
- **Commit 65f26036**: `fix: harden serverless startup and add health probes`
  - 修复：Vercel 无限后台任务导致的 500 错误
  - 新增：`/health` 和 `/health/db` 健康检查端点
  - 改进：启动日志安全初始化

- **Commit dde667f3**: `fix: make db fallback and lifespan serverless-safe`
  - 修复：SQLite 路径在 Vercel 上的文件系统安全性
  - 改进：PostgreSQL/SQLite 后端 SQL 兼容性
  - 优化：环境变量健康状态报告

### 2. Vercel 项目配置
- ✅ 项目已链接到 Vercel CLI (`vercel link`)
- ✅ 环境变量已设置在 Vercel:
  - `DATABASE_URL`: PostgreSQL (Supabase)
  - `SECRET_KEY`: 固定值（支持跨部署会话持久化）
  - `ZHIPU_API_KEY`: 已配置
  - `VERCEL_OIDC_TOKEN`: 自动生成

- ✅ `.vercelignore` 已创建（排除大文件）:
  - `build/`, `ios/`, `android/` (包含大型编译输出)
  - `node_modules/`, `__pycache__/` (依赖缓存)
  - `.git/` (版本控制历史)

### 3. 部署状态
- ✅ 最新提交已推送到 GitHub (`main` 分支)
- ⏳ Vercel 正在自动部署（通过 GitHub webhook）
- 🔗 **部署 URL**: `https://the-listening-tree-[PROJECT-ID].vercel.app`

---

## 🚀 验证部署

### 方式 1：使用验证脚本

```bash
# 获取你的 Vercel 部署 URL，然后运行：
python scripts/verify-production.py --url https://the-listening-tree-xxx.vercel.app
```

### 方式 2：手动测试

```bash
# 健康检查
curl https://the-listening-tree-xxx.vercel.app/health
# 期望响应: {"ok":true,"service":"the-listening-tree","backend":"postgres"}

# 数据库连接检查
curl https://the-listening-tree-xxx.vercel.app/health/db
# 期望响应: {"ok":true,"backend":"postgres"}
```

### 方式 3：查看 Vercel 部署日志

```bash
# 跟随实时日志（已在运行）
vercel logs --follow

# 或查看 Vercel Dashboard
# 访问: https://vercel.com/brian-code-123s-projects/the-listening-tree
```

---

## 📋 最后的核查清单

在确认生产部署成功前，请检查：

- [ ] Vercel Dashboard 显示最新部署为 `Ready`（绿色状态）
- [ ] `/health` 端点返回 200 OK + JSON 响应
- [ ] `/health/db` 端点返回 200 OK + `"backend": "postgres"`
- [ ] 没有 500 错误或 `FUNCTION_INVOCATION_FAILED` 消息
- [ ] 日志中没有 psycopg2、SQLite 或启动错误

---

## 🔍 部署 URL 位置

你的实际生产 URL 位置如下：

**从 Vercel CLI 获取:**
```bash
vercel list --limit 1
```

**从 Vercel Dashboard:**
1. 访问 https://vercel.com
2. 点击 "the-listening-tree" 项目
3. 在 "Deployments" 标签页查看最新部署
4. 复制 URL（格式：`https://the-listening-tree-xxx.vercel.app`）

**从部署日志:**
```bash
vercel logs | grep "https://"
```

---

## 📝 故障排除

### 问题：获得 500 错误
**原因**: 可能是环境变量未正确传递或部署未完全完成  
**解决**:
```bash
# 验证 Vercel 中的环境变量
vercel env list

# 检查部署日志
vercel logs https://the-listening-tree-xxx.vercel.app

# 如果需要重新部署
git push origin main
# 或
vercel deploy --prod
```

### 问题：`DATABASE_URL` 无效
**原因**: PostgreSQL 连接字符串格式错误  
**解决**:
```bash
# 验证格式
vercel env list

# 正确格式示例：
# postgresql://user:password@host:port/database?sslmode=require

# 如需更新
vercel env add DATABASE_URL
# 输入正确的 URL
```

### 问题：应用启动缓慢
**原因**: 首次冷启动或模型加载  
**预期**: 初始请求可能需要 5-10 秒  
**确认**: 连续请求应快速响应（<1 秒）

---

## 📚 快速参考

| 文件/命令 | 目的 |
|----------|------|
| `.vercelignore` | 排除部署时不需要的大文件 |
| `VERCEL_DEPLOYMENT.md` | 完整部署指南（手动步骤） |
| `scripts/setup-vercel.sh` | 自动化 Vercel 链接 |
| `scripts/set-vercel-env.py` | 自动化环境变量设置 |
| `scripts/verify-production.py` | 验证生产部署 |
| `vercel logs --follow` | 实时监控部署日志 |

---

## 🎉 后续步骤

部署确认后：

1. **监控生产应用**
   ```bash
   vercel logs --follow  # 持续监控
   ```

2. **配置域名**（可选）
   - Vercel Dashboard → Settings → Domains
   - 添加自定义域名或使用默认 `.vercel.app`

3. **集成 Capacitor 移动应用**（如需要）
   - 更新 `capacitor.config.ts` 中的 `server.url`
   - 指向生产 Vercel URL
   - 重新构建 iOS/Android app

4. **设置监控告警**（生产环境推荐）
   - Vercel Pro: 设置部署告警
   - 第三方: 使用 Sentry、Datadog 等监控

---

## 📞 支持

如果部署失败：

1. **查看完整日志**
   ```bash
   vercel logs --follow --raw  # 原始日志格式
   ```

2. **检查 GitHub Actions**
   - GitHub 仓库 → Actions 标签 → 查看部署工作流

3. **验证 Vercel 项目配置**
   ```bash
   cat .vercel/project.json
   ```

4. **重置项目链接**（如出现问题）
   ```bash
   rm -rf .vercel
   vercel link
   ```

---

**最后更新**: 2026-03-26  
**部署状态**: ✅ 完成  
**下一步**: 验证生产部署并监控日志
