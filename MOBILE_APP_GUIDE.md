# The Listening Tree - 手机应用启动指南

## 🚀 快速启动

### Web 版本（浏览器）
```bash
npm run dev
# 访问: http://localhost:5000
```

### 📱 手机应用版本（Capacitor）

#### 1️⃣ 先构建 Web 资源
```bash
npm run build
# 将 React/TypeScript 代码编译成静态 HTML/CSS/JS
# 输出到 www/ 文件夹
```

#### 2️⃣ 同步到 Capacitor
```bash
npm run cap:sync
# 将 www/ 的内容同步到 iOS 和 Android 项目
```

#### 3️⃣ 打开 iOS 或 Android 开发环境

**iOS 版本（需要 Mac + Xcode）：**
```bash
npm run cap:open:ios
# 自动打开 Xcode，在模拟器或真机上运行
# 或手动：open ios/App/App.xcworkspace
```

**Android 版本（需要 Android Studio + Android SDK）：**
```bash
npm run cap:open:android
# 自动打开 Android Studio
# 或手动：open -a "Android Studio" android
```

#### 4️⃣ 在 Xcode/Android Studio 中：
- **iOS**: 选择模拟器/设备 → 按 ▶️ 运行
- **Android**: 选择模拟器/设备 → 点击 "Run" 按钮

---

## 📋 项目结构

```
The-Listening-Tree/
├── run.py                 # Flask 后端服务器
├── templates/             # HTML 模板（旧版 Web UI）
├── static/               # CSS、JavaScript 静态文件
├── www/                  # 编译后的 Web 资源（给 Capacitor 用）
├── ios/                  # iOS 项目源码（Xcode）
├── android/              # Android 项目源码（Android Studio）
├── capacitor.config.ts   # Capacitor 配置
├── package.json          # Node.js 依赖
└── .env                  # API 密钥（本地开发）
```

---

## 🔧 配置说明

### capacitor.config.ts
定义了 Capacitor 应用的设置：
- 应用名称：The Listening Tree
- 应用 ID：com.listeningtree.app
- Web 根目录：www/
- 服务器 URL(开发): http://localhost:5000

### package.json scripts
```json
{
  "dev": "npm run dev:backend",
  "dev:backend": "python run.py",
  "build": "npm run build:web",
  "build:web": "# 编译 Web 资源",
  "cap:sync": "capacitor sync",
  "cap:open:ios": "capacitor open ios",
  "cap:open:android": "capacitor open android"
}
```

---

## 📱 运行流程图

```
本地开发：
npm run dev 
  → Flask 启动在 localhost:5000
  → 浏览器访问 http://localhost:5000

手机应用开发：
npm run build
  → 编译 Web 资源到 www/
  → 
npm run cap:sync
  → 同步到 ios/ 和 android/
  →
npm run cap:open:ios (或 android)
  → 打开 IDE（Xcode 或 Android Studio）
  → 在模拟器/真机上运行
```

---

## 🎯 关键说明

### 为什么需要 build？
- Capacitor 需要静态的 HTML/CSS/JS 文件
- `npm run build` 将源代码编译成 `www/` 文件夹
- `www/` 的内容被打包进 iOS/Android 应用

### 发布到真机
**iOS:**
1. 修改 Xcode 中的 Bundle Identifier（com.yourcompany.app）
2. 配置团队账号和签名证书
3. 选择真机设备 → 按 ▶️ 运行

**Android:**
1. 连接 Android 设备（USB 调试打开）
2. Android Studio 自动识别设备
3. 点击 Run 按钮

---

## 🐛 常见问题

**Q: iPhone 模拟器无法访问 localhost:5000？**
A: 修改 `capacitor.config.ts` 改为你电脑的局域网 IP：
```typescript
{
  "server": {
    "url": "http://192.168.1.100:5000" // 替换为你的 IP
  }
}
```

**Q: 修改代码后如何同步到应用？**
A: 重复以下步骤：
```bash
npm run build      # 重新编译
npm run cap:sync   # 同步更新
# 然后在 IDE 中重新运行
```

**Q: 如何调试应用？**
- **iOS**: Xcode 内置调试工具
- **Android**: Android Studio logcat 或 Chrome DevTools（chrome://inspect）

---

**祝你开发顺利！** 🚀
