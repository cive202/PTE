(function (window) {
    const RANDOM_VOICE_ID = '__random__';

    const CURATED_VOICES = [
        { id: 'en-US-GuyNeural', label: 'Blake (US)', gender: 'male' },
        { id: 'en-IN-PrabhatNeural', label: 'Amir (IN)', gender: 'male' },
        { id: 'en-AU-NatashaNeural', label: 'Anna (AU)', gender: 'female' },
        { id: 'en-GB-SoniaNeural', label: 'Helen (UK)', gender: 'female' },
    ];

    const FALLBACK_SPEED_OPTIONS = [
        { id: 'x0.85', label: 'x0.85' },
        { id: 'x1.0', label: 'x1.0' },
        { id: 'x1.15', label: 'x1.15' },
    ];

    function createTtsPresetController(config) {
        const feature = String(config.feature || 'listening').trim();
        const storagePrefix = String(config.storagePrefix || feature).trim();
        const voiceSelect = config.voiceSelect;
        const speedSelect = config.speedSelect;
        const metaLabel = config.metaLabel;
        const replayButton = config.replayButton || null;
        const audioElement = config.audioElement || null;
        const onSelectionChange = typeof config.onSelectionChange === 'function'
            ? config.onSelectionChange
            : function () { };

        if (!voiceSelect || !speedSelect) {
            throw new Error('voiceSelect and speedSelect elements are required.');
        }

        const voiceStorageKey = `${storagePrefix}Voice`;
        const speedStorageKey = `${storagePrefix}Speed`;

        let provider = 'edge';
        let availableVoiceMap = new Map();
        let resolvedRandomVoiceId = null;

        function setMeta(text) {
            if (metaLabel) {
                metaLabel.textContent = text || '';
            }
        }

        function formatVoiceLabel(voice) {
            if (voice && voice.label) {
                return String(voice.label);
            }
            const shortName = String((voice && (voice.short_name || voice.shortName)) || '').trim();
            const locale = String((voice && voice.locale) || '').trim();
            const friendly = String((voice && (voice.display_name || voice.friendly_name || shortName)) || '').trim();
            if (locale && friendly && !friendly.includes('(')) {
                return `${friendly} (${locale})`;
            }
            return friendly || shortName;
        }

        function voiceLabelById(voiceId) {
            const voice = availableVoiceMap.get(String(voiceId || '').trim());
            return voice ? formatVoiceLabel(voice) : String(voiceId || '').trim();
        }

        function randomVoiceId() {
            const pick = CURATED_VOICES[Math.floor(Math.random() * CURATED_VOICES.length)];
            return pick ? pick.id : CURATED_VOICES[0].id;
        }

        function ensureVoiceOption(voiceName) {
            const normalized = String(voiceName || '').trim();
            if (!normalized) {
                return CURATED_VOICES[0].id;
            }
            if (normalized === RANDOM_VOICE_ID) {
                return RANDOM_VOICE_ID;
            }
            if (availableVoiceMap.has(normalized)) {
                return normalized;
            }
            return CURATED_VOICES[0].id;
        }

        function currentVoiceLabel() {
            const selected = ensureVoiceOption(voiceSelect.value);
            if (selected !== RANDOM_VOICE_ID) {
                return voiceLabelById(selected);
            }
            if (resolvedRandomVoiceId) {
                return `Random (${voiceLabelById(resolvedRandomVoiceId)})`;
            }
            return 'Random';
        }

        function resolveVoice(forceRepickRandom) {
            const selected = ensureVoiceOption(voiceSelect.value);
            if (selected !== RANDOM_VOICE_ID) {
                resolvedRandomVoiceId = selected;
                return selected;
            }
            if (!forceRepickRandom && resolvedRandomVoiceId && availableVoiceMap.has(resolvedRandomVoiceId)) {
                return resolvedRandomVoiceId;
            }
            resolvedRandomVoiceId = randomVoiceId();
            return resolvedRandomVoiceId;
        }

        function refreshMeta() {
            setMeta(`Voice: ${currentVoiceLabel()} • Speed: ${speedSelect.value || 'x1.0'}`);
        }

        function populateVoiceOptions(preferredVoice) {
            voiceSelect.innerHTML = '';
            availableVoiceMap = new Map();

            CURATED_VOICES.forEach((voice) => {
                const option = document.createElement('option');
                option.value = voice.id;
                option.textContent = formatVoiceLabel(voice);
                voiceSelect.appendChild(option);
                availableVoiceMap.set(voice.id, voice);
            });

            const randomOption = document.createElement('option');
            randomOption.value = RANDOM_VOICE_ID;
            randomOption.textContent = 'Random';
            voiceSelect.appendChild(randomOption);

            const savedVoice = window.localStorage.getItem(voiceStorageKey);
            const selected = ensureVoiceOption(preferredVoice || savedVoice || CURATED_VOICES[2].id);
            voiceSelect.value = selected;
            window.localStorage.setItem(voiceStorageKey, selected);
            resolvedRandomVoiceId = selected === RANDOM_VOICE_ID ? null : selected;
        }

        function populateSpeedOptions(speedOptions, preferredSpeed) {
            speedSelect.innerHTML = '';
            const options = Array.isArray(speedOptions) && speedOptions.length
                ? speedOptions
                : FALLBACK_SPEED_OPTIONS;

            options.forEach((speed) => {
                const id = String(speed.id || '').trim();
                if (!id) {
                    return;
                }
                const option = document.createElement('option');
                option.value = id;
                option.textContent = String(speed.label || id);
                speedSelect.appendChild(option);
            });

            const savedSpeed = window.localStorage.getItem(speedStorageKey);
            const selectedSpeed = preferredSpeed || savedSpeed || 'x1.0';
            speedSelect.value = selectedSpeed;
            if (!speedSelect.value) {
                speedSelect.value = 'x1.0';
            }
            window.localStorage.setItem(speedStorageKey, speedSelect.value);
        }

        function buildQuery(forceRepickRandom) {
            const params = new URLSearchParams();
            params.set('provider', provider || 'edge');
            params.set('voice', resolveVoice(Boolean(forceRepickRandom)));
            if (speedSelect.value) {
                params.set('speed', speedSelect.value);
            }
            return params;
        }

        function buildAudioUrl(basePath, forceRepickRandom) {
            const params = buildQuery(forceRepickRandom);
            return `${basePath}?${params.toString()}`;
        }

        function handleVoiceChange() {
            const selected = ensureVoiceOption(voiceSelect.value);
            voiceSelect.value = selected;
            window.localStorage.setItem(voiceStorageKey, selected);
            resolvedRandomVoiceId = selected === RANDOM_VOICE_ID ? null : selected;
            refreshMeta();
            onSelectionChange({
                type: 'voice',
                selected,
                random: selected === RANDOM_VOICE_ID,
            });
        }

        function handleSpeedChange() {
            window.localStorage.setItem(speedStorageKey, speedSelect.value || 'x1.0');
            refreshMeta();
            onSelectionChange({
                type: 'speed',
                speed: speedSelect.value || 'x1.0',
            });
        }

        async function init(forceRefresh) {
            const params = new URLSearchParams({
                feature,
                locale: 'en',
            });
            if (forceRefresh) {
                params.set('refresh', '1');
            }

            try {
                const response = await window.fetch(`/api/tts/options?${params.toString()}`);
                const data = await response.json();
                if (!response.ok || data.error) {
                    throw new Error(data.error || 'Failed to load TTS options.');
                }

                const capabilities = data.capabilities || {};
                provider = String(data.provider || capabilities.default_provider || 'edge').trim().toLowerCase();
                populateVoiceOptions(capabilities.default_voice);
                populateSpeedOptions(capabilities.speed_options, capabilities.default_speed);
            } catch (_error) {
                provider = 'edge';
                populateVoiceOptions(CURATED_VOICES[2].id);
                populateSpeedOptions(FALLBACK_SPEED_OPTIONS, 'x1.0');
            }

            if (replayButton && audioElement) {
                replayButton.addEventListener('click', () => {
                    if (!audioElement.src) {
                        return;
                    }
                    audioElement.currentTime = 0;
                    audioElement.play().catch(() => { });
                });
            }

            voiceSelect.addEventListener('change', handleVoiceChange);
            speedSelect.addEventListener('change', handleSpeedChange);
            refreshMeta();
        }

        return {
            init,
            refreshMeta,
            buildQuery,
            buildAudioUrl,
            getProvider: () => provider || 'edge',
            getSpeed: () => speedSelect.value || 'x1.0',
            getCurrentVoiceLabel: () => currentVoiceLabel(),
            getCurrentVoiceId: () => ensureVoiceOption(voiceSelect.value),
            shouldRepickRandom: () => ensureVoiceOption(voiceSelect.value) === RANDOM_VOICE_ID,
        };
    }

    window.createTtsPresetController = createTtsPresetController;
    window.TTS_RANDOM_VOICE_ID = RANDOM_VOICE_ID;
})(window);
