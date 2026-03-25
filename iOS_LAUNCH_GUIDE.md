# iOS Launch Guide — The Listening Tree

## Overview
This guide walks you through launching **The Listening Tree** on iOS Simulator or a physical iOS device. The app is a **Capacitor + FastAPI** hybrid app: the native iOS shell loads a web backend served by Python.

---

## Prerequisites

Before starting, ensure you have:
- **Xcode 15+** installed (with iOS SDK 17+)
- **Node.js 18+** and **npm 9+** installed
- **Python 3.11+** with required packages (FastAPI, Uvicorn, etc.)
- **Git** for version control

Verify installations:
```bash
npm --version         # Should be 9.0+
node --version        # Should be 18+
python --version      # Should be 3.11+
xcode-select -p       # Should return Xcode path
```

---

## Step 1: Start the FastAPI Backend Server

The iOS app connects to your local FastAPI server on **port 5000**. This MUST be running before launching the app.

### Option A: Direct Python Execution
```bash
cd /Users/lochunman/Desktop/個人項目/The-Listening-Tree
python run.py
```

You should see:
```
Server running: http://localhost:5000
```

### Option B: Using Uvicorn Directly (if run.py fails)
```bash
uvicorn run:app --reload --host 0.0.0.0 --port 5000
```

**Keep this terminal open** — the backend must remain running while you use the app.

---

## Step 2: Build Web Assets (Production Mode)

In a **new terminal**, build the static web files that will be bundled into the iOS app:

```bash
cd /Users/lochunman/Desktop/個人項目/The-Listening-Tree
npm run build
```

This generates files in the `www/` directory that Capacitor will copy into the iOS app bundle.

---

## Step 3: Sync Web Assets to iOS

Synchronize the built web assets and Capacitor configuration to the native iOS project:

```bash
npx cap sync ios
```

This command:
- Copies `www/` contents to `ios/App/App/public/`
- Updates `capacitor.config.json` in the iOS project
- Runs `pod install` to ensure all dependencies are up-to-date

---

## Step 4: Open Xcode and Build for Simulator

Open the iOS workspace in Xcode:

```bash
npx cap open ios
```

This launches Xcode with the workspace file `ios/App/App.xcworkspace`.

### In Xcode:

1. **Select Build Target**: In the top toolbar, ensure the target is `App` (left dropdown)
2. **Select Simulator**: Click the device selector (middle dropdown) and choose an iPhone simulator (e.g., "iPhone 17 Pro")
   - If no simulator is available, create one:
     - Xcode > Window > Devices and Simulators
     - Click the "+" button under Simulators
     - Choose iPhone 17 Pro, iOS 26.3, give it a name, click Create

3. **Build and Run**: Press **Cmd + R** (or Product > Run)
   - Xcode will:
     - Compile the native Swift code
     - Copy synchronized web assets
     - Install the app on the selected simulator
     - Launch and attach the debugger

4. **Check the Simulator**:
   - The app should load the login page (or redirect to chat if already logged in)
   - The app connects to `http://localhost:5000` (FastAPI server) to fetch the web UI
   - If you see a loading spinner and it hangs, check:
     - Python backend is running (Step 1)
     - No build errors in Xcode console
     - Network connectivity between simulator and `localhost:5000`

---

## Step 5: Debug and Inspect

### View Console Logs in Xcode
- In Xcode, open **View > Debug Area > Activate Console** (or Cmd+Shift+Y)
- Logs from the native code and web bridge appear here
- Look for any `ERROR`, `Exception`, or `crashed` messages

### Inspect the WebView (Safari Web Inspector)
The most powerful tool for debugging the app's web content:

1. **On Mac**: Open **Safari** (not Xcode)
2. **In Safari menu**: Develop > Simulator > [Your App Name]
3. **Web Inspector opens** — you'll see:
   - **Console**: JavaScript errors, warnings, and logs
   - **Network**: HTTP requests and responses
   - **Elements**: HTML/CSS inspection
   - **Storage**: LocalStorage, SessionStorage

### Common Issues and Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| **White screen** | Backend not reachable, or wrong port | Ensure `python run.py` is running on port 5000. Check `capacitor.config.ts` has `url: 'http://localhost:5000'` |
| **Login page not loading** | FastAPI server down | Restart `python run.py` in terminal |
| **App crashes on startup** | Dependency missing or permission denied | Check Xcode console for error. Run `npx cap sync ios` again. |
| **Simulator black screen** | Build failed silently | Press Cmd+B to clean build, then Cmd+R to rebuild |
| **Network timeout (ECONNREFUSED)** | Simulator can't reach localhost | Ensure backend listens on `0.0.0.0:5000` (check run.py uses `--host 0.0.0.0`) |

---

## Step 6 (Optional): Launch on Physical iPhone

To test on a real device:

1. **Connect iPhone** via USB to Mac
2. **Trust the Mac** on your iPhone (unlock device, tap Trust)
3. **In Xcode**:
   - Change the device selector from Simulator to your iPhone
   - Ensure "Team" is set (Xcode Project > Signing & Capabilities)
   - Press Cmd+R to build and run

4. **Important**: On a real device, `localhost:5000` is not reachable. Instead:
   - Find your Mac's local IP: `ifconfig | grep inet` (look for `192.168.x.x`)
   - Update `capacitor.config.ts` to use your IP:
     ```typescript
     url: 'http://192.168.1.100:5000'  // Replace with your actual IP
     ```
   - Re-run `npx cap sync ios` and rebuild

---

## Complete Workflow (All Steps Combined)

For a quick full deployment:

```bash
# Terminal 1: Start backend (keep running)
cd /Users/lochunman/Desktop/個人項目/The-Listening-Tree
python run.py

# Terminal 2: Build, sync, and open in Xcode
cd /Users/lochunman/Desktop/個人項目/The-Listening-Tree
npm run build && npx cap sync ios && npx cap open ios
```

In Xcode: **Press Cmd+R** to build and run on the selected simulator.

---

## Environment Variables

The FastAPI backend loads secrets from a `.env` file. Required variables:

```
ZHIPU_API_KEY=<your-api-key>    # Optional; fallback responses used if missing
SECRET_KEY=<session-secret>      # Optional; random key generated if missing
```

Create/update `.env` in the project root:
```bash
echo 'ZHIPU_API_KEY=sk_test_....' > .env
echo 'SECRET_KEY=my-secret-key' >> .env
```

---

## Troubleshooting Checklist

- [ ] Python backend running on `0.0.0.0:5000`? (`python run.py`)
- [ ] Web assets built? (`npm run build`)
- [ ] iOS synced? (`npx cap sync ios`)
- [ ] Xcode target is "App", device is a simulator or connected iPhone?
- [ ] Pressed Cmd+R in Xcode to build and run?
- [ ] Checked Safari Web Inspector for JS errors (Develop > Simulator)?
- [ ] No firewall blocking localhost on port 5000?
- [ ] Simulator has network access (Apple menu > Settings > Network)?

---

## Quick Reference

| Action | Command |
|--------|---------|
| Start backend | `python run.py` |
| Build web | `npm run build` |
| Sync to iOS | `npx cap sync ios` |
| Open Xcode | `npx cap open ios` |
| Run in Xcode | Cmd+R (when Xcode is focused) |
| Build only | Cmd+B |
| Stop running app | Cmd+. (period key) |
| Open console | Cmd+Shift+Y |
| Rebuild clean | Cmd+Shift+K, then Cmd+B |

---

## Architecture Summary

```
┌─────────────────────────────────────┐
│  iOS Native App (Swift/Capacitor)   │
│  ├─ UIWebView/WKWebView             │
│  │   └─ Loads http://localhost:5000 │
│  └─ Capacitor Plugins               │
│      (Audio, Permissions, etc.)     │
└───────────────┬─────────────────────┘
                │ HTTP
                ▼
        ┌─────────────────┐
        │  FastAPI Server │
        │  localhost:5000 │
        │                 │
        │ Routes:         │
        │ - /login        │
        │ - /get_response │
        │ - /transcribe   │
        │ - /...          │
        │                 │
        │ Database:       │
        │ reminders.db    │
        └─────────────────┘
```

When the iOS app starts:
1. Native code initializes (`AppDelegate.swift`)
2. `capacitor.js` bridge is loaded
3. Web content loads from `server.url` (typically `http://localhost:5000`)
4. Backend serves web UI and API endpoints
5. App is fully interactive

---

## Performance Tips

- **Slow app startup?** Check if backend is slow to respond. Profile with Safari Web Inspector (Network tab).
- **High memory usage?** Restart the simulator (Device menu > Erase All Content and Settings) or rebuild Xcode project (Cmd+Shift+K).
- **Hot reload not working?** This is expected — iOS app doesn't support hot reload. Rebuild with Cmd+R each time you change code.

---

## Additional Resources

- [Capacitor Documentation](https://capacitorjs.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Xcode Help](https://help.apple.com/xcode)
- [iOS Simulator Guide](https://developer.apple.com/documentation/xcode/running-your-app-in-simulator-or-on-a-device)

---

**Last Updated**: March 2026  
**Version**: 2.0 (Capacitor 6.0, FastAPI 0.128+)
