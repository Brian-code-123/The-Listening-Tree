/**
 * prepare-www.js — Pre-build script for Capacitor mobile builds.
 *
 * This script ensures the www/ directory has:
 *   1. The fallback index.html (already exists)
 *   2. A copy of capacitor-bridge.js that detects the Capacitor
 *      environment and initializes mobile-specific features.
 *
 * Run via: npm run build:mobile
 */

const fs = require('fs');
const path = require('path');

const wwwDir = path.join(__dirname, '..', 'www');

// Ensure www/ exists
if (!fs.existsSync(wwwDir)) {
    fs.mkdirSync(wwwDir, { recursive: true });
}

// Create the capacitor-bridge.js that gets injected into the Flask templates
const bridgeJS = `
/**
 * Capacitor Bridge — Mobile-specific enhancements for The Listening Tree.
 *
 * This script is loaded by the Flask templates when running inside a
 * Capacitor WebView.  It handles:
 *   - Safe area padding for notch / home indicator
 *   - Hardware back button (Android)
 *   - Status bar styling
 *   - Keyboard handling for chat input
 *   - Haptic feedback on interactions
 */
(function() {
    'use strict';

    // Only run inside Capacitor
    if (!window.Capacitor) return;

    // Add body class for CSS targeting
    document.body.classList.add('capacitor-app');
    document.documentElement.classList.add('capacitor-app');

    console.log('[Capacitor] Running inside native WebView');

    // ---- Status Bar ----
    async function setupStatusBar() {
        try {
            const { StatusBar } = await import('@capacitor/status-bar');
            const theme = document.body.getAttribute('data-theme') || 'light';
            await StatusBar.setStyle({ style: theme === 'dark' ? 'DARK' : 'LIGHT' });
            await StatusBar.setBackgroundColor({
                color: theme === 'dark' ? '#0F1923' : '#5B9A7D'
            });

            // Watch for theme changes
            const observer = new MutationObserver(async (mutations) => {
                for (const m of mutations) {
                    if (m.attributeName === 'data-theme') {
                        const t = document.body.getAttribute('data-theme');
                        await StatusBar.setStyle({ style: t === 'dark' ? 'DARK' : 'LIGHT' });
                        await StatusBar.setBackgroundColor({
                            color: t === 'dark' ? '#0F1923' : '#5B9A7D'
                        });
                    }
                }
            });
            observer.observe(document.body, { attributes: true });
        } catch (e) { /* StatusBar plugin not available */ }
    }

    // ---- Hardware Back Button (Android) ----
    async function setupBackButton() {
        try {
            const { App } = await import('@capacitor/app');
            App.addListener('backButton', ({ canGoBack }) => {
                // If modal is open, close it
                const modal = document.querySelector('.hk-guide-modal.show');
                if (modal) {
                    modal.classList.remove('show');
                    return;
                }
                const guidePanel = document.querySelector('.guide-panel.show');
                if (guidePanel) {
                    guidePanel.classList.remove('show');
                    return;
                }
                if (canGoBack) {
                    window.history.back();
                } else {
                    App.exitApp();
                }
            });
        } catch (e) { /* App plugin not available */ }
    }

    // ---- Keyboard Handling ----
    async function setupKeyboard() {
        try {
            const { Keyboard } = await import('@capacitor/keyboard');
            Keyboard.addListener('keyboardWillShow', (info) => {
                document.body.style.setProperty('--keyboard-height', info.keyboardHeight + 'px');
                document.body.classList.add('keyboard-open');
                // Scroll chat to bottom when keyboard opens
                const chatBody = document.getElementById('messageFormeight');
                if (chatBody) {
                    setTimeout(() => chatBody.scrollTop = chatBody.scrollHeight, 100);
                }
            });
            Keyboard.addListener('keyboardWillHide', () => {
                document.body.style.setProperty('--keyboard-height', '0px');
                document.body.classList.remove('keyboard-open');
            });
        } catch (e) { /* Keyboard plugin not available */ }
    }

    // ---- Haptic Feedback ----
    async function setupHaptics() {
        try {
            const { Haptics, ImpactStyle } = await import('@capacitor/haptics');
            // Add haptic feedback to send button and mic button
            document.addEventListener('click', (e) => {
                const btn = e.target.closest('.send_btn, .hk-tab, .hk-card-detail, .reminder-delete');
                if (btn) {
                    Haptics.impact({ style: ImpactStyle.Light }).catch(() => {});
                }
            });
        } catch (e) { /* Haptics plugin not available */ }
    }

    // ---- Splash Screen ----
    async function hideSplash() {
        try {
            const { SplashScreen } = await import('@capacitor/splash-screen');
            await SplashScreen.hide();
        } catch (e) { /* SplashScreen plugin not available */ }
    }

    // Initialize all
    setupStatusBar();
    setupBackButton();
    setupKeyboard();
    setupHaptics();

    // Hide splash after content is loaded
    if (document.readyState === 'complete') {
        hideSplash();
    } else {
        window.addEventListener('load', hideSplash);
    }
})();
`;

const bridgePath = path.join(wwwDir, 'capacitor-bridge.js');
fs.writeFileSync(bridgePath, bridgeJS.trim());
console.log('✅ capacitor-bridge.js written to www/');

console.log('✅ www/ directory ready for Capacitor sync');
