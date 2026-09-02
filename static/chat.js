    (function() {
        if (window.Capacitor) {
            document.body.classList.add('capacitor-app');
            document.documentElement.classList.add('capacitor-app');
            // Hardware back button (Android)
            import('@capacitor/app').then(({ App }) => {
                App.addListener('backButton', ({ canGoBack }) => {
                    const guidePanel = document.querySelector('.guide-panel.show');
                    if (guidePanel) { guidePanel.classList.remove('show'); return; }
                    if (canGoBack) window.history.back();
                    else App.exitApp();
                });
            }).catch(() => {});
            // Keyboard handling
            import('@capacitor/keyboard').then(({ Keyboard }) => {
                Keyboard.addListener('keyboardWillShow', (info) => {
                    document.body.style.setProperty('--keyboard-height', info.keyboardHeight + 'px');
                    document.body.classList.add('keyboard-open');
                    const cb = document.getElementById('messageFormeight');
                    if (cb) setTimeout(() => cb.scrollTop = cb.scrollHeight, 100);
                });
                Keyboard.addListener('keyboardWillHide', () => {
                    document.body.style.setProperty('--keyboard-height', '0px');
                    document.body.classList.remove('keyboard-open');
                });
            }).catch(() => {});
            // Haptic feedback
            import('@capacitor/haptics').then(({ Haptics, ImpactStyle }) => {
                document.addEventListener('click', (e) => {
                    if (e.target.closest('.send_btn, .chat-nav-btn, .reminder-delete'))
                        Haptics.impact({ style: ImpactStyle.Light }).catch(() => {});
                });
            }).catch(() => {});
            // Hide splash
            import('@capacitor/splash-screen').then(({ SplashScreen }) => {
                SplashScreen.hide();
            }).catch(() => {});
            // Status bar theme sync
            import('@capacitor/status-bar').then(({ StatusBar }) => {
                const t = document.body.getAttribute('data-theme') || 'light';
                StatusBar.setStyle({ style: t === 'dark' ? 'DARK' : 'LIGHT' }).catch(() => {});
                StatusBar.setBackgroundColor({ color: t === 'dark' ? '#0F1923' : '#5B9A7D' }).catch(() => {});
                new MutationObserver(() => {
                    const th = document.body.getAttribute('data-theme');
                    StatusBar.setStyle({ style: th === 'dark' ? 'DARK' : 'LIGHT' }).catch(() => {});
                    StatusBar.setBackgroundColor({ color: th === 'dark' ? '#0F1923' : '#5B9A7D' }).catch(() => {});
                }).observe(document.body, { attributes: true, attributeFilter: ['data-theme'] });
            }).catch(() => {});
            // Native reminder alarms — fire even if the app is backgrounded/closed
            import('@capacitor/local-notifications').then(({ LocalNotifications }) => {
                window.__localNotifications = LocalNotifications;
                LocalNotifications.requestPermissions().catch(() => {});
            }).catch(() => {});
        }
    })();

    // Reschedule native OS notifications to match the current active reminder list.
    // Called from checkReminders() (chat.js below) after every /get_reminders fetch.
    window.syncNativeReminders = function(reminders) {
        const LocalNotifications = window.__localNotifications;
        if (!LocalNotifications) return;
        LocalNotifications.getPending().then(({ notifications }) => {
            if (notifications.length) {
                return LocalNotifications.cancel({ notifications: notifications.map(n => ({ id: n.id })) });
            }
        }).then(() => {
            const active = (reminders || []).filter(r => r.active && /^\d{1,2}:\d{2}$/.test(r.time));
            if (!active.length) return;
            const toSchedule = active.map((r, i) => {
                const [h, m] = r.time.split(':').map(Number);
                const when = new Date();
                when.setHours(h, m, 0, 0);
                if (when <= new Date()) when.setDate(when.getDate() + 1);
                return {
                    id: i + 1,
                    title: currentLang === 'zh-HK' ? '⏰ 提醒' : '⏰ Reminder',
                    body: r.label,
                    schedule: { at: when },
                    sound: 'notification.mp3',
                };
            });
            LocalNotifications.schedule({ notifications: toSchedule }).catch(() => {});
        }).catch(() => {});
    };

    $(document).ready(function() {
        const currentLang = window.CHAT_I18N.currentLang;
        let ttsEnabled = true;

        // ========== Theme Toggle ==========
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.body.setAttribute('data-theme', savedTheme);
        updateThemeIcon(savedTheme);

        $('#themeToggle').on('click', function() {
            const current = document.body.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            document.body.setAttribute('data-theme', next);
            localStorage.setItem('theme', next);
            updateThemeIcon(next);
        });

        function updateThemeIcon(theme) {
            $('#themeIcon').attr('class', theme === 'dark' ? 'fas fa-moon' : 'fas fa-sun');
        }

        // ========== Mobile Sidebar Toggle ==========
        $('#sidebarToggleHeader').on('click', function() {
            $('#sidebarColumn').toggleClass('hidden-mobile');
        });

        // ========== Guide Helper ==========
        $('#guideFab').on('click', function() { $('#guidePanel').toggleClass('show'); });
        $('#guideClose').on('click', function() { $('#guidePanel').removeClass('show'); });
        // ========== TTS ==========
        // Prefer a young / gentle female voice when available. Note: available voices
        // depend on the browser and OS. We use heuristics to pick a female-sounding voice
        // for the current language, and slightly increase pitch for a younger tone.
        function speakText(text) {
            window.TLTSpeech && window.TLTSpeech.speak(text, currentLang, { enabled: ttsEnabled });
        }

        $('#ttsToggle').on('click', function() {
            ttsEnabled = !ttsEnabled;
            if (!ttsEnabled) window.speechSynthesis.cancel();
            const onLabel = window.CHAT_I18N.voiceOn;
            const offLabel = window.CHAT_I18N.voiceOff;
            if (ttsEnabled) {
                $('#ttsIcon').attr('class', 'fas fa-volume-up');
                $('#ttsLabel').text(onLabel);
                $('#ttsToggle').removeClass('tts-off').addClass('tts-on');
            } else {
                $('#ttsIcon').attr('class', 'fas fa-volume-mute');
                $('#ttsLabel').text(offLabel);
                $('#ttsToggle').removeClass('tts-on').addClass('tts-off');
            }
        });

        if ('speechSynthesis' in window) {
            window.speechSynthesis.getVoices();
            window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
        }

        // ========== Chat Messages ==========
        function appendMessage(sender, message, time) {
            const html = UI.MessageBubble(sender, message, time);
            $('#messageFormeight').append(html);
            $('#messageFormeight').scrollTop($('#messageFormeight')[0].scrollHeight);
        }

        // ========== Conversations ==========
        let currentConversationId = null;

        function renderMessages(history) {
            $('#messageFormeight').empty();
            if (history && history.length > 0) {
                history.forEach(item => {
                    const time = item.timestamp.split(' ')[1].substring(0, 5);
                    appendMessage(item.sender, item.message, time);
                });
            } else {
                const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                const welcomeMsg = window.CHAT_I18N.welcomeChat;
                appendMessage('bot', welcomeMsg, time);
            }
        }

        function loadConversationMessages(conversationId) {
            currentConversationId = conversationId;
            $.get(`/conversations/${conversationId}/messages`, function(data) {
                renderMessages(data.history);
            }).fail(function(xhr) {
                console.error('Failed to load conversation messages:', xhr.status, xhr.responseText);
                renderMessages([]);
            });
        }

        function loadConversationList(onDone) {
            $.get('/conversations', function(data) {
                if (onDone) onDone(data.conversations);
            });
        }

        $('#newConversationBtn').on('click', function() {
            $.post('/conversations/new', function(data) {
                loadConversationMessages(data.conversation_id);
            });
        });

        // Load chat history: honor a `?conversation_id=` deep link (used by
        // the /history page's "open this conversation" cards), otherwise
        // start on the most recent conversation, or create the user's first
        // one if they have none yet.
        function loadChatHistory() {
            const requestedId = new URLSearchParams(location.search).get('conversation_id');
            if (requestedId) {
                loadConversationMessages(parseInt(requestedId, 10));
                return;
            }
            loadConversationList(function(conversations) {
                if (conversations && conversations.length > 0) {
                    loadConversationMessages(conversations[0].id);
                } else {
                    $.post('/conversations/new', function(data) {
                        loadConversationMessages(data.conversation_id);
                    });
                }
            });
        }
        loadChatHistory();

        // Network/Backend Status Support
        async function updateNetworkStatus() {
            // If browser is clearly offline, show banner immediately.
            if (!navigator.onLine) {
                $('#offlineBanner').removeClass('d-none');
                return;
            }

            // Verify backend health to avoid false "online" when API/DB is unreachable.
            try {
                const controller = new AbortController();
                const timer = setTimeout(() => controller.abort(), 2500);
                const resp = await fetch('/health/db', { method: 'GET', cache: 'no-store', signal: controller.signal });
                clearTimeout(timer);
                if (resp.ok) $('#offlineBanner').addClass('d-none');
                else $('#offlineBanner').removeClass('d-none');
            } catch (_) {
                $('#offlineBanner').removeClass('d-none');
            }
        }
        window.addEventListener('online', () => { updateNetworkStatus(); });
        window.addEventListener('offline', () => { updateNetworkStatus(); });
        updateNetworkStatus();
        setInterval(updateNetworkStatus, 30000);

        // Handle message submit
        $('#messageArea').on('submit', function(event) {
            event.preventDefault();
            const text = $('#text').val().trim();
            if (!text) return;
            
            const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            appendMessage('user', text, time);
            $('#text').val('');

            $.ajax({
                type: 'POST',
                url: '/get_response',
                data: { msg: text, conversation_id: currentConversationId },
                dataType: 'json',
                success: function(data) {
                    appendMessage('bot', data.response, time);
                    speakText(data.response);
                    if (text.toLowerCase().includes('reminder') || text.includes('提醒')) checkReminders();
                },
                error: function(xhr) {
                    console.error('Error:', xhr);
                    appendMessage('bot', window.CHAT_I18N.errorGeneric, time);
                }
            });
        });

        // ================================================================
        // Voice Recording (STT) — Browser Web Speech API only
        // ================================================================

        let _recognition = null;
        let _isRecording = false;
        let _recordingMode = null; // 'webspeech' | 'fallback'
        let _discardRecording = false; // true = user hit trash; drop result, don't transcribe/populate
        let _fallbackStream = null;
        let _fallbackRecorder = null;
        let _fallbackChunks = [];
        let _fallbackMimeType = '';

        // Localised placeholder strings (set by Jinja)
        const PLACEHOLDER_IDLE    = window.CHAT_I18N.placeholderIdle;
        const PLACEHOLDER_LISTEN  = window.CHAT_I18N.placeholderListen;
        const PLACEHOLDER_PROCESS = window.CHAT_I18N.placeholderProcess;

        // ----------------------------------------------------------------
        // Live voice waveform (ECG-style amplitude bars while recording)
        // ----------------------------------------------------------------
        let _waveformState = null; // { audioCtx, analyser, dataArray, rafId, stream, ownsStream }
        // Bar pitch (px) — a new history sample is appended roughly every
        // SAMPLE_INTERVAL_MS, and one bar is drawn per sample, scrolling
        // left as new ones arrive (like WhatsApp/iMessage voice notes) —
        // this is what actually produces the varying-height "ECG strip"
        // look, as opposed to redrawing one live snapshot every frame
        // (which just shows a near-constant band for a steady tone).
        const BAR_PITCH_PX = 4;
        const SAMPLE_INTERVAL_MS = 70;
        const _prefersReducedMotion = window.matchMedia
            && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        function initWaveformAnalyser(stream, ownsStream) {
            try {
                const AudioCtx = window.AudioContext || window.webkitAudioContext;
                if (!AudioCtx) return;
                const audioCtx = new AudioCtx();
                const source = audioCtx.createMediaStreamSource(stream);
                const analyser = audioCtx.createAnalyser();
                analyser.fftSize = 256;
                source.connect(analyser); // never connect to destination — avoids echo

                const canvasEl = document.getElementById('voiceWaveform');
                $(canvasEl).removeClass('d-none');
                // CSS stretches this element responsively (flex:1); sync the
                // canvas's drawing-buffer resolution to its actual rendered
                // size so bars aren't stretched/blurry.
                if (canvasEl && canvasEl.clientWidth) {
                    canvasEl.width = canvasEl.clientWidth;
                    canvasEl.height = canvasEl.clientHeight;
                }

                _waveformState = {
                    audioCtx,
                    analyser,
                    dataArray: new Uint8Array(analyser.frequencyBinCount),
                    history: [], // amplitude samples, 0..1, oldest first
                    maxBars: Math.max(1, Math.floor(canvasEl.width / BAR_PITCH_PX)),
                    rafId: null,
                    lastSampleTime: 0,
                    stream,
                    ownsStream,
                };
                drawWaveform();
            } catch (e) {
                console.warn('[Waveform] init failed:', e);
            }
        }

        /**
         * Web Speech API exposes no raw audio, so its waveform can't reflect
         * real amplitude. A synthetic breathing pulse conveys "listening"
         * without a second getUserMedia() call — see startRecording() for
         * why that call was removed (multi-second contention delay).
         */
        function initSyntheticWaveform() {
            const canvasEl = document.getElementById('voiceWaveform');
            $(canvasEl).removeClass('d-none');
            if (canvasEl && canvasEl.clientWidth) {
                canvasEl.width = canvasEl.clientWidth;
                canvasEl.height = canvasEl.clientHeight;
            }
            _waveformState = {
                synthetic: true,
                history: [],
                maxBars: Math.max(1, Math.floor(canvasEl.width / BAR_PITCH_PX)),
                rafId: null,
                lastSampleTime: 0,
                startTime: performance.now(),
            };
            drawWaveform();
        }

        function drawWaveform(ts) {
            if (!_waveformState) return;
            const s = _waveformState;
            const interval = _prefersReducedMotion ? SAMPLE_INTERVAL_MS * 4 : SAMPLE_INTERVAL_MS;

            if (!ts || ts - s.lastSampleTime >= interval) {
                s.lastSampleTime = ts || 0;
                let amp;
                if (s.synthetic) {
                    const t = (performance.now() - s.startTime) / 1000;
                    amp = 0.35 + 0.25 * Math.abs(Math.sin(t * 2.2)) + Math.random() * 0.1;
                } else {
                    s.analyser.getByteTimeDomainData(s.dataArray);
                    // RMS amplitude of this window, 0..1 — gives a natural,
                    // speech-like envelope rather than a flat average.
                    let sumSquares = 0;
                    for (let i = 0; i < s.dataArray.length; i++) {
                        const v = (s.dataArray[i] - 128) / 128;
                        sumSquares += v * v;
                    }
                    const rms = Math.sqrt(sumSquares / s.dataArray.length);
                    amp = Math.min(1, rms * 4); // small gain so normal speech reaches good height
                }
                s.history.push(amp);
                if (s.history.length > s.maxBars) s.history.shift();
            }

            const canvas = document.getElementById('voiceWaveform');
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            const { width, height } = canvas;
            ctx.clearRect(0, 0, width, height);

            const minBarHeight = 3;
            ctx.fillStyle = '#5B9A7D';
            // Right-align the strip so the newest sample sits at the right
            // edge, oldest ones scroll off to the left (WhatsApp-style).
            const startX = width - s.history.length * BAR_PITCH_PX;
            for (let i = 0; i < s.history.length; i++) {
                const amp = s.history[i];
                const barHeight = Math.max(minBarHeight, amp * height * 0.9);
                const x = startX + i * BAR_PITCH_PX;
                const y = (height - barHeight) / 2;
                ctx.beginPath();
                if (ctx.roundRect) ctx.roundRect(x, y, BAR_PITCH_PX - 1.5, barHeight, 2);
                else ctx.rect(x, y, BAR_PITCH_PX - 1.5, barHeight);
                ctx.fill();
            }

            s.rafId = requestAnimationFrame(drawWaveform);
        }

        function teardownWaveform() {
            if (!_waveformState) {
                $('#voiceWaveform').addClass('d-none');
                return;
            }
            if (_waveformState.rafId) cancelAnimationFrame(_waveformState.rafId);
            if (_waveformState.ownsStream && _waveformState.stream) {
                _waveformState.stream.getTracks().forEach(track => track.stop());
            }
            try {
                if (_waveformState.audioCtx && _waveformState.audioCtx.state !== 'closed') {
                    _waveformState.audioCtx.close();
                }
            } catch (e) { /* already closed */ }
            _waveformState = null;
            $('#voiceWaveform').addClass('d-none');
        }

        /**
         * Gracefully stop any active recording session.
         * Resets the mic button state and placeholder text.
         */
        function resetMicUi() {
            _isRecording = false;
            _recordingMode = null;
            _discardRecording = false;
            teardownWaveform();
            $('#micBtn')
                .removeClass('recording-active pulse-recording')
                .find('i').removeClass('fa-stop fa-play').addClass('fa-microphone');
            $('#micDeleteBtn').addClass('d-none');
            $('#text').removeClass('d-none').attr('placeholder', PLACEHOLDER_IDLE);
        }

        function stopRecording() {
            $('#micDeleteBtn').addClass('d-none');

            if (_recordingMode === 'fallback' && _fallbackRecorder && _fallbackRecorder.state !== 'inactive') {
                _isRecording = false;
                teardownWaveform();
                $('#micBtn')
                    .removeClass('recording-active pulse-recording')
                    .find('i').removeClass('fa-stop').addClass('fa-play');
                $('#text').removeClass('d-none').attr('placeholder', PLACEHOLDER_PROCESS);
                try { _fallbackRecorder.stop(); } catch (e) { /* already stopped */ }
                return;
            }

            // Only a live recognizer means we're genuinely awaiting a result
            // (its 'end' event will call resetMicUi()). If there's nothing to
            // wait on — unsupported browser, permission denied, start failed —
            // reset straight to idle instead of getting stuck on the play icon.
            const awaitingResult = !!_recognition;

            if (_recognition) {
                try { _recognition.stop(); } catch (e) { /* already stopped */ }
                _recognition = null;
            }
            if (_fallbackStream) {
                _fallbackStream.getTracks().forEach(track => track.stop());
                _fallbackStream = null;
            }
            _fallbackRecorder = null;
            _fallbackChunks = [];
            _fallbackMimeType = '';

            if (!awaitingResult) {
                resetMicUi();
                return;
            }

            teardownWaveform();
            $('#micBtn')
                .removeClass('recording-active pulse-recording')
                .find('i').removeClass('fa-stop').addClass('fa-play');
            $('#text').removeClass('d-none').attr('placeholder', PLACEHOLDER_PROCESS);
        }

        /**
         * Discard the in-progress recording — like WhatsApp's trash icon.
         * Stops capture and drops whatever was said so far without
         * transcribing (fallback engine) or populating the input
         * (Web Speech engine).
         */
        function discardRecording() {
            $('#text').val('');
            $('#micDeleteBtn').addClass('d-none');

            if (_recordingMode === 'fallback' && _fallbackRecorder && _fallbackRecorder.state !== 'inactive') {
                _discardRecording = true;
                try { _fallbackRecorder.stop(); } catch (e) { /* already stopped */ }
                return; // onstop handler finishes cleanup, sees the flag, skips transcribing
            }

            if (_recognition) {
                _discardRecording = true;
                try {
                    if (typeof _recognition.abort === 'function') _recognition.abort();
                    else _recognition.stop();
                } catch (e) { /* already stopped */ }
                return; // 'end' handler finishes cleanup, sees the flag, skips populating text
            }

            resetMicUi();
        }

        function encodeWavFromAudioBuffer(audioBuffer) {
            const channelCount = audioBuffer.numberOfChannels;
            const sampleRate = audioBuffer.sampleRate;
            const length = audioBuffer.length;
            const mixed = new Float32Array(length);

            for (let c = 0; c < channelCount; c++) {
                const channel = audioBuffer.getChannelData(c);
                for (let i = 0; i < length; i++) mixed[i] += channel[i] / channelCount;
            }

            const bytesPerSample = 2;
            const blockAlign = bytesPerSample;
            const byteRate = sampleRate * blockAlign;
            const dataSize = mixed.length * bytesPerSample;
            const buffer = new ArrayBuffer(44 + dataSize);
            const view = new DataView(buffer);

            let offset = 0;
            const writeString = (s) => { for (let i = 0; i < s.length; i++) view.setUint8(offset++, s.charCodeAt(i)); };

            writeString('RIFF');
            view.setUint32(offset, 36 + dataSize, true); offset += 4;
            writeString('WAVE');
            writeString('fmt ');
            view.setUint32(offset, 16, true); offset += 4;
            view.setUint16(offset, 1, true); offset += 2; // PCM
            view.setUint16(offset, 1, true); offset += 2; // mono
            view.setUint32(offset, sampleRate, true); offset += 4;
            view.setUint32(offset, byteRate, true); offset += 4;
            view.setUint16(offset, blockAlign, true); offset += 2;
            view.setUint16(offset, 16, true); offset += 2;
            writeString('data');
            view.setUint32(offset, dataSize, true); offset += 4;

            for (let i = 0; i < mixed.length; i++, offset += 2) {
                const s = Math.max(-1, Math.min(1, mixed[i]));
                view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
            }
            return new Blob([buffer], { type: 'audio/wav' });
        }

        async function convertRecordedBlobToWav(blob) {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (!AudioCtx) throw new Error('AudioContext not available');
            const ctx = new AudioCtx();
            try {
                const arr = await blob.arrayBuffer();
                const decoded = await ctx.decodeAudioData(arr.slice(0));
                return encodeWavFromAudioBuffer(decoded);
            } finally {
                try { await ctx.close(); } catch (_) {}
            }
        }

        async function transcribeFallbackChunks() {
            if (!_fallbackChunks.length) {
                showVoiceToast(currentLang === 'zh-HK' ? '🎤 聽唔到語音。請再試一次。' : '🎤 No speech captured. Please try again.');
                return;
            }

            try {
                $('#text').attr('placeholder', PLACEHOLDER_PROCESS);
                const recordedBlob = new Blob(_fallbackChunks, { type: _fallbackMimeType || 'audio/webm' });
                const wavBlob = await convertRecordedBlobToWav(recordedBlob);
                const form = new FormData();
                form.append('audio', wavBlob, 'speech.wav');
                form.append('lang', currentLang);

                const resp = await fetch('/transcribe', { method: 'POST', body: form });
                const data = await resp.json();
                if (!resp.ok) {
                    throw new Error(data.error || 'STT request failed');
                }

                const text = (data.text || '').trim();
                if (!text) {
                    showVoiceToast(currentLang === 'zh-HK' ? '🎤 聽唔到語音。請講得清楚啲。' : '🎤 No speech recognized. Please speak clearly.');
                    return;
                }

                // Populate the input with the transcript but let the user
                // review/edit it and press Send themselves — don't auto-submit.
                $('#text').val(text).trigger('focus');
            } catch (e) {
                console.error('[STT fallback] error:', e);
                showVoiceToast(currentLang === 'zh-HK'
                    ? '⚠️ 語音轉文字暫時失敗，請檢查網絡後再試。'
                    : '⚠️ Speech-to-text failed. Please check your network and try again.');
            }
        }

        async function startFallbackRecording() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                showVoiceToast(currentLang === 'zh-HK'
                    ? '你嘅瀏覽器唔支援錄音。請用 Chrome、Edge 或 Safari。'
                    : 'Your browser does not support recording. Please use Chrome, Edge, or Safari.');
                stopRecording();
                return;
            }

            const mimeCandidates = [
                'audio/webm;codecs=opus',
                'audio/webm',
                'audio/mp4',
                'audio/ogg;codecs=opus'
            ];

            try {
                _fallbackStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                initWaveformAnalyser(_fallbackStream, false);
                $('#text').addClass('d-none');
                _fallbackMimeType = '';
                if (window.MediaRecorder && MediaRecorder.isTypeSupported) {
                    _fallbackMimeType = mimeCandidates.find(t => MediaRecorder.isTypeSupported(t)) || '';
                }
                _fallbackRecorder = _fallbackMimeType
                    ? new MediaRecorder(_fallbackStream, { mimeType: _fallbackMimeType })
                    : new MediaRecorder(_fallbackStream);

                _fallbackChunks = [];
                _recordingMode = 'fallback';

                _fallbackRecorder.ondataavailable = (e) => {
                    if (e.data && e.data.size > 0) _fallbackChunks.push(e.data);
                };

                _fallbackRecorder.onstop = async () => {
                    if (_fallbackStream) {
                        _fallbackStream.getTracks().forEach(track => track.stop());
                        _fallbackStream = null;
                    }
                    if (!_discardRecording) {
                        await transcribeFallbackChunks();
                    }
                    _fallbackRecorder = null;
                    _fallbackChunks = [];
                    _fallbackMimeType = '';
                    resetMicUi();
                };

                _fallbackRecorder.start(200);
                console.log('[STT fallback] recording started');
            } catch (e) {
                console.error('[STT fallback] start error:', e);
                showVoiceToast(currentLang === 'zh-HK'
                    ? '❌ 無法啟動麥克風，請檢查權限。'
                    : '❌ Unable to start microphone. Please check permissions.');
                stopRecording();
            }
        }

        /**
         * Show a friendly, non-blocking toast instead of a browser alert().
         * Auto-dismisses after 4 seconds.
         */
        function showVoiceToast(message) {
            // Remove any existing toast
            $('.voice-toast').remove();
            const toast = $('<div class="voice-toast">' + message + '</div>');
            $('body').append(toast);
            setTimeout(() => toast.addClass('show'), 10);
            setTimeout(() => { toast.removeClass('show'); setTimeout(() => toast.remove(), 300); }, 4000);
        }

        /**
         * Start recording using browser Web Speech API.
         */
        async function startRecording() {
            _isRecording = true;
            _discardRecording = false;
            $('#micBtn')
                .addClass('recording-active pulse-recording')
                .find('i').removeClass('fa-microphone').addClass('fa-stop');
            $('#micDeleteBtn').removeClass('d-none');
            $('#text').val('').attr('placeholder', PLACEHOLDER_LISTEN);

            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (SpeechRecognition) {
                _recordingMode = 'webspeech';
                // Web Speech API gives no raw audio access. A second,
                // visualization-only getUserMedia() call used to run here,
                // but on the same physical mic device it can take several
                // seconds to resolve while the recognizer already holds the
                // mic (OS-level capture arbitration) — the waveform would
                // stay hidden for that whole window. Use a synthetic pulse
                // instead: same WhatsApp-style visual, no real audio needed,
                // shows instantly with no contention.
                initSyntheticWaveform();
                $('#text').addClass('d-none');
                _recognition = new SpeechRecognition();
                _recognition.lang = (currentLang === 'zh-HK') ? 'zh-HK' : 'en-US';
                _recognition.interimResults = true;
                _recognition.continuous = false;
                _recognition.maxAlternatives = 1;

                _recognition.addEventListener('result', function (event) {
                    let interim = '', final = '';
                    for (let i = event.resultIndex; i < event.results.length; i++) {
                        const t = event.results[i][0].transcript;
                        if (event.results[i].isFinal) final += t;
                        else interim += t;
                    }
                    // Show interim results live in the text field
                    $('#text').val(final || interim);
                });

                _recognition.addEventListener('error', function (event) {
                    console.warn('[STT] error:', event.error);
                    // Stop current recognition session but keep graceful fallback available.
                    stopRecording();
                    
                    // Friendly error messages for elderly users
                    switch(event.error) {
                        case 'not-allowed':
                            showVoiceToast(currentLang === 'zh-HK'
                                ? '❌ 咪高峰權限被拒絕。請檢查瀏覽器設定，允許存取麥克風。'
                                : '❌ Microphone access denied. Please allow in browser settings.');
                            break;
                        case 'no-speech':
                            showVoiceToast(currentLang === 'zh-HK'
                                ? '🎤 聽唔到語音。請講得大聲啲！'
                                : '🎤 No speech detected. Please speak louder!');
                            break;
                        case 'network':
                            showVoiceToast(currentLang === 'zh-HK'
                                ? '⚠️ 網路連接有問題，請檢查網絡。'
                                : '⚠️ Network connection issue. Please check your network.');
                            break;
                        case 'aborted':
                            // User cancelled — silent
                            break;
                        default:
                            showVoiceToast(currentLang === 'zh-HK'
                                ? '⚠️ 語音轉文字失敗，請再試一次。'
                                : '⚠️ Voice recognition failed. Please try again.');
                    }
                });

                _recognition.addEventListener('end', function () {
                    const discarded = _discardRecording;
                    resetMicUi();
                    _recognition = null;
                    if (discarded) {
                        $('#text').val('');
                        return;
                    }
                    // Leave the transcript in the input for the user to
                    // review/edit and press Send themselves — don't auto-submit.
                    const transcript = $('#text').val().trim();
                    if (transcript) $('#text').trigger('focus');
                });

                try {
                    _recognition.start();
                    console.log('[STT] started Web Speech API');
                } catch (e) {
                    console.error('[STT] failed to start:', e);
                    // start() threw synchronously — no 'end' event will ever
                    // fire for this instance, so clear it before stopRecording()
                    // or the mic would get stuck showing the play icon forever.
                    _recognition = null;
                    stopRecording();
                    showVoiceToast(currentLang === 'zh-HK'
                        ? '⚠️ 語音功能啟動失敗。'
                        : '⚠️ Failed to start voice recognition.');
                }
                return;  // done — Web Speech API handles everything
            }
            // Browser has no Web Speech API: switch to recorder + server fallback.
            await startFallbackRecording();
        }

        // Mic button: toggle recording on/off
        $('#micBtn').on('click', function () {
            if (_isRecording) stopRecording();
            else startRecording();
        });

        // Trash button: discard the in-progress recording without sending
        $('#micDeleteBtn').on('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            discardRecording();
        });

        // Stop button: cancel recording (same action as mic button when recording)
        $('#stopBtn').on('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            stopRecording();
        });

        // ========== Reminder Management ==========
        function checkReminders() {
            $.get('/get_reminders', function(data) {
                if (window.syncNativeReminders) window.syncNativeReminders(data.reminders);
                $('#reminderList').empty();
                if (!data.reminders || data.reminders.length === 0) {
                    const noReminders = window.CHAT_I18N.noReminders;
                    $('#reminderList').append('<p style="text-align:center;color:var(--text-muted);font-size:0.85rem;padding:8px 0;">' + noReminders + '</p>');
                    return;
                }
                data.reminders.forEach(r => {
                    const deleteLabel = currentLang === 'zh-HK' ? '刪除' : 'Delete';
                    const html = `<div class="reminder-item ${r.active ? '' : 'inactive'} fade-in">
                        <div class="reminder-icon"><i class="fas fa-bell"></i></div>
                        <div class="reminder-info">
                            <div class="reminder-label">${r.label}</div>
                            <div class="reminder-time-badge"><i class="fas fa-clock"></i> ${r.time}</div>
                        </div>
                        ${r.active ? `<button class="reminder-delete delete-reminder" data-label="${r.label}" title="${deleteLabel}"><i class="fas fa-times"></i></button>` : ''}
                    </div>`;
                    $('#reminderList').append(html);
                });
                $('.delete-reminder').off('click').on('click', function() {
                    const label = $(this).data('label');
                    $.post('/get_response', { msg: 'delete reminder ' + label }, function() { checkReminders(); });
                });
            });
        }
        checkReminders();
        setInterval(checkReminders, 60000);

        // Reminder alarm check
        function checkForRemindersNow() {
            $.get('/get_reminders', function(data) {
                const currentTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
                data.reminders.forEach(r => {
                    if (r.time === currentTime && r.active) {
                        const audio = new Audio("/static/notification.mp3");
                        audio.loop = true;
                        audio.play().catch(() => {});
                        setTimeout(() => {
                            const alertMsg = currentLang === 'zh-HK'
                                ? '⏰ 提醒：' + r.label + '！\n\n係時候' + r.label + '喇！'
                                : '⏰ Reminder: ' + r.label + '!\n\nIt\'s time to ' + r.label.toLowerCase() + '!';
                            alert(alertMsg);
                            audio.pause(); audio.currentTime = 0;
                            $.post('/deactivate_reminder', { label: r.label }, function() { checkReminders(); });
                        }, 300);
                    }
                });
            });
        }
        const now = new Date();
        setTimeout(() => { checkForRemindersNow(); setInterval(checkForRemindersNow, 60000); }, (60 - now.getSeconds()) * 1000);

        // Add reminder form
        $('#reminderForm').on('submit', function(e) {
            e.preventDefault();
            const label = $('#reminderLabel').val().trim();
            const time = $('#reminderTime').val();
            if (label && time) {
                const cmd = currentLang === 'zh-HK' ? '設置提醒 ' + label + ' ' + time : 'set reminder ' + label + ' ' + time;
                $.post('/get_response', { msg: cmd }, function(data) {
                    // Show confirmation in chat
                    const t = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                    appendMessage('bot', data.response, t);
                    speakText(data.response);
                    $('#reminderLabel').val(''); $('#reminderTime').val('');
                    checkReminders();
                });
            }
        });

        // ========== FullCalendar with HK Holidays ==========
        const calendarEl = document.getElementById('miniCalendar');
        const calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            locale: currentLang === 'zh-HK' ? 'zh-hk' : 'en',
            headerToolbar: {
                left: 'prev',
                center: 'title',
                right: 'next'
            },
            height: 'auto',
            fixedWeekCount: false,
            dayMaxEvents: 1,
            dayCellContent: function(arg) {
                // Custom date display: unified format (no "日" character for Chinese)
                const dayNum = arg.date.getDate();
                return { html: dayNum.toString() };
            },
            dayCellClassNames: function(arg) {
                // Include 'fc-daygrid-day-today' for today styling, no border circle
                const classes = [];
                if (arg.isToday) {
                    classes.push('fc-daygrid-day-today');
                }
                return classes;
            },
            events: function(fetchInfo, successCallback, failureCallback) {
                $.get('/get_hk_holidays', function(data) {
                    successCallback(data.holidays || []);
                }).fail(function() { successCallback([]); });
            },
            eventClick: function(info) {
                // Read holiday name aloud
                speakText(info.event.title);
            },
            dateClick: function(info) {
                // Announce the date
                const d = new Date(info.dateStr);
                const dateText = currentLang === 'zh-HK'
                    ? `${d.getFullYear()}年${d.getMonth()+1}月${d.getDate()}日`
                    : d.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
                speakText(dateText);
            }
        });
        calendar.render();

        // ========== HK News ==========
        function loadNews() {
            $('#newsContainer').html('<div class="news-loading"><i class="fas fa-spinner"></i> ' + window.CHAT_I18N.loadingNews + '</div>');
            $.get('/get_news', function(data) {
                $('#newsContainer').empty();
                if (!data.articles || data.articles.length === 0) {
                    $('#newsContainer').html('<p style="text-align:center;color:var(--text-muted);padding:20px;font-size:0.9rem;">' + window.CHAT_I18N.noNews + '</p>');
                    return;
                }
                data.articles.forEach(article => {
                    const html = `<div class="news-item fade-in" onclick="window.open('${article.url}', '_blank')">
                        <div class="news-title">${article.title}</div>
                        <div class="news-desc">${article.description || ''}</div>
                        <div class="news-meta">
                            <span class="news-source">${article.source}</span>
                            <button class="news-voice-btn" onclick="event.stopPropagation(); speakNewsItem('${article.title.replace(/'/g, "\\'")}', '${(article.description || '').replace(/'/g, "\\'")}')" title="${window.CHAT_I18N.voiceRead}">
                                <i class="fas fa-volume-up"></i>
                            </button>
                        </div>
                    </div>`;
                    $('#newsContainer').append(html);
                });
            }).fail(function() {
                $('#newsContainer').html('<p style="text-align:center;color:var(--text-muted);padding:20px;font-size:0.9rem;">' + window.CHAT_I18N.noNews + '</p>');
            });
        }

        // Global function for news voice button
        window.speakNewsItem = function(title, desc) {
            speakText(title + '. ' + desc);
        };

        loadNews();
        $('#refreshNews').on('click', loadNews);

    });
