import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.listeningtree.app',
  appName: 'The Listening Tree',
  // webDir points to the local fallback page.
  // The app loads from the remote server URL so backend routes work.
  webDir: 'www',
  server: {
    // ───────────────────────────────────────────────────────────────
    // IMPORTANT: Change this URL to your deployed server address.
    //
    // For LOCAL development:
    //   url: 'http://<YOUR_LOCAL_IP>:5000'
    //   (Find your IP with `ifconfig | grep inet`)
    //
    // For PRODUCTION (Vercel / Render / etc.):
    //   url: 'https://your-app.vercel.app'
    //
    // When `url` is set, Capacitor loads the remote web app inside
    // the native WebView — backend routes, sessions, and JS work
    // exactly as in a browser.
    // ───────────────────────────────────────────────────────────────
    url: 'https://the-listening-tree.vercel.app',
    cleartext: true,   // Allow HTTP (non-HTTPS) for local dev
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      launchAutoHide: true,
      backgroundColor: '#5B9A7D',
      androidSplashResourceName: 'splash',
      androidScaleType: 'CENTER_CROP',
      showSpinner: true,
      spinnerColor: '#FFFFFF',
      splashFullScreen: true,
      splashImmersive: true,
    },
    Keyboard: {
      resize: 'body',
      resizeOnFullScreen: true,
    },
    StatusBar: {
      style: 'LIGHT',
      backgroundColor: '#5B9A7D',
    },
  },
  // iOS specific configuration
  ios: {
    contentInset: 'automatic',
    allowsLinkPreview: true,
    scrollEnabled: true,
    // Allow microphone access for voice input
    // (configured in Info.plist via Xcode after `cap add ios`)
  },
  // Android specific configuration
  android: {
    allowMixedContent: true,
    captureInput: true,
    webContentsDebuggingEnabled: true,  // Disable in production
  },
};

export default config;
