(function (window) {
    const EMOJI_RE = /[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu;

    const FEMALE_HINTS = [
        'female',
        'samantha',
        'anna',
        'zira',
        'google',
        'moira',
        'karen',
        'serena',
        'microsoft',
        'mei',
        'yuna',
    ];

    function cleanSpeechText(text) {
        return String(text || '').replace(EMOJI_RE, '').trim();
    }

    function hasChineseText(text) {
        return /[\u3400-\u9FFF]/.test(String(text || ''));
    }

    function prefersCantonese(currentLang, text) {
        const normalizedLang = String(currentLang || '').toLowerCase();
        return normalizedLang === 'zh-hk' || normalizedLang === 'zh' || hasChineseText(text);
    }

    function preferredLanguage(currentLang, text) {
        return prefersCantonese(currentLang, text) ? 'yue-HK' : 'en-US';
    }

    function scoreVoice(voice, currentLang, text) {
        const lang = String(voice.lang || '').toLowerCase();
        const name = String(voice.name || '').toLowerCase();
        let score = 0;
        const useCantonese = prefersCantonese(currentLang, text);

        if (useCantonese) {
            if (lang === 'yue-hk') score += 120;
            if (lang.startsWith('yue')) score += 110;
            if (name.includes('cantonese') || name.includes('廣東') || name.includes('粵語')) score += 105;
            if (name.includes('hong kong') || name.includes('hk')) score += 90;
            if (lang === 'zh-hk') score += 85;
            if (lang.startsWith('zh')) score += 50;
            if (name.includes('sin-ji') || name.includes('ting-ting') || name.includes('mei')) score += 40;
        } else {
            if (lang === 'en-us') score += 120;
            if (lang.startsWith('en')) score += 100;
        }

        if (FEMALE_HINTS.some((hint) => name.includes(hint))) score += 8;
        return score;
    }

    function pickVoice(voices, currentLang) {
        if (!Array.isArray(voices) || voices.length === 0) return null;

        const ranked = voices
            .map((voice) => ({ voice, score: scoreVoice(voice, currentLang, '') }))
            .sort((a, b) => b.score - a.score);

        const best = ranked[0];
        return best && best.score > 0 ? best.voice : voices[0];
    }

    function speak(text, currentLang, options = {}) {
        if (!window.speechSynthesis || options.enabled === false) return;

        const clean = cleanSpeechText(text);
        if (!clean) return;

        window.speechSynthesis.cancel();

        const utterance = new SpeechSynthesisUtterance(clean);
        const useCantonese = prefersCantonese(currentLang, clean);
        utterance.lang = preferredLanguage(currentLang, clean);
        utterance.rate = useCantonese ? 0.92 : 0.88;
        utterance.pitch = useCantonese ? 1.06 : 1.15;
        utterance.volume = 1.0;

        const speakNow = () => {
            const voices = window.speechSynthesis.getVoices();
            const voice = voices
                .map((v) => ({ voice: v, score: scoreVoice(v, currentLang, clean) }))
                .sort((a, b) => b.score - a.score)[0]?.voice || null;

            if (voice) {
                utterance.voice = voice;
                if (!useCantonese && voice.lang) {
                    utterance.lang = voice.lang;
                }
            }

            window.speechSynthesis.speak(utterance);
        };

        const voices = window.speechSynthesis.getVoices();
        if (voices.length > 0) {
            speakNow();
            return;
        }

        const handleVoicesChanged = () => {
            const loadedVoices = window.speechSynthesis.getVoices();
            if (!loadedVoices.length) return;
            window.speechSynthesis.onvoiceschanged = null;
            speakNow();
        };

        window.speechSynthesis.onvoiceschanged = handleVoicesChanged;
        window.speechSynthesis.getVoices();

        setTimeout(() => {
            if (window.speechSynthesis.getVoices().length === 0) {
                speakNow();
            }
        }, 250);
    }

    window.TLTSpeech = {
        cleanSpeechText,
        pickVoice,
        speak,
    };
})(window);