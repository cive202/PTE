(function (window) {
    const PAUSE_PUNCTUATION = new Set([',', '.', ';', ':', '!', '?']);
    const BASE_PAUSE_THRESHOLDS = {
        ',': [0.25, 0.50],
        ';': [0.35, 0.65],
        ':': [0.35, 0.65],
        '.': [0.60, 1.00],
        '!': [0.60, 1.00],
        '?': [0.60, 1.00],
    };
    const BASE_WORD_GAP_RANGE = [0.08, 0.25];

    function toNumber(value) {
        const n = Number(value);
        return Number.isFinite(n) ? n : null;
    }

    function roundTo(value, digits) {
        const n = toNumber(value);
        if (n === null) return null;
        const factor = 10 ** (digits || 2);
        return Math.round(n * factor) / factor;
    }

    function isPauseToken(word) {
        const token = String(word && word.word || '').trim();
        const status = String(word && word.status || '').trim().toLowerCase();
        return PAUSE_PUNCTUATION.has(token) || status.endsWith('_pause');
    }

    function isGapMarker(word) {
        return Boolean(word && word.kind === 'gap_marker');
    }

    function hasFiniteTiming(word) {
        if (!word || typeof word !== 'object') {
            return false;
        }
        const start = toNumber(word.start);
        const end = toNumber(word.end);
        return start !== null && end !== null && end >= start;
    }

    function canOpenWordModal(word) {
        if (!word || typeof word !== 'object') {
            return false;
        }
        if (isGapMarker(word)) {
            return true;
        }
        if (isPauseToken(word) && (word.pause_eval || Array.isArray(word.expected_range))) {
            return true;
        }
        return hasFiniteTiming(word);
    }

    function punctuationLabel(token) {
        const value = String(token || '').trim();
        return {
            ',': 'Comma',
            '.': 'Full stop',
            ';': 'Semicolon',
            ':': 'Colon',
            '!': 'Exclamation mark',
            '?': 'Question mark',
        }[value] || value || 'Punctuation';
    }

    function getPauseRange(word, speechRateScale) {
        if (word && word.pause_eval && Array.isArray(word.pause_eval.expected_range) && word.pause_eval.expected_range.length === 2) {
            const minValue = toNumber(word.pause_eval.expected_range[0]);
            const maxValue = toNumber(word.pause_eval.expected_range[1]);
            if (minValue !== null && maxValue !== null) {
                return [minValue, maxValue];
            }
        }

        const token = String(word && word.word || '').trim();
        const base = BASE_PAUSE_THRESHOLDS[token];
        const scale = toNumber(speechRateScale) || 1;
        if (!base) {
            return null;
        }
        return [roundTo(base[0] * scale, 2), roundTo(base[1] * scale, 2)];
    }

    function getWordGapRange(speechRateScale) {
        const scale = toNumber(speechRateScale) || 1;
        return [
            roundTo(BASE_WORD_GAP_RANGE[0] * scale, 2),
            roundTo(BASE_WORD_GAP_RANGE[1] * scale, 2),
        ];
    }

    function formatSeconds(value) {
        const n = toNumber(value);
        return n === null ? 'N/A' : `${n.toFixed(2)}s`;
    }

    function formatRange(range) {
        if (!Array.isArray(range) || range.length !== 2) {
            return 'N/A';
        }
        const minValue = toNumber(range[0]);
        const maxValue = toNumber(range[1]);
        if (minValue === null || maxValue === null) {
            return 'N/A';
        }
        return `${minValue.toFixed(2)}s - ${maxValue.toFixed(2)}s`;
    }

    function pauseStatusVariant(word) {
        const status = String(word && word.status || '').trim().toLowerCase();
        if (status === 'correct_pause') return 'pause-correct';
        if (status === 'short_pause' || status === 'long_pause') return 'pause-warn';
        if (status === 'missed_pause') return 'pause-error';
        return '';
    }

    function buildGapMarker(prevWord, nextWord, speechRateScale) {
        if (!prevWord || !nextWord || isPauseToken(prevWord) || isPauseToken(nextWord)) {
            return null;
        }
        const prevEnd = toNumber(prevWord.end);
        const nextStart = toNumber(nextWord.start);
        if (prevEnd === null || nextStart === null || nextStart <= prevEnd) {
            return null;
        }

        const expectedRange = getWordGapRange(speechRateScale);
        const maxGap = expectedRange[1];
        const gapDuration = roundTo(nextStart - prevEnd, 3);
        if (gapDuration === null || gapDuration <= maxGap) {
            return null;
        }

        return {
            word: '  ',
            display_word: '  ',
            kind: 'gap_marker',
            status: 'extra_gap',
            start: prevEnd,
            end: nextStart,
            duration: gapDuration,
            expected_range: expectedRange,
            prev_word: String(prevWord.word || '').trim(),
            next_word: String(nextWord.word || '').trim(),
            gap_feedback: `Gap is longer than ideal: ${formatSeconds(gapDuration)} vs ${formatRange(expectedRange)}.`,
        };
    }

    function buildDisplayRowsWithGapMarkers(words, speechRateScale) {
        const rows = Array.isArray(words) ? words : [];
        if (!rows.length) {
            return [];
        }

        const displayRows = [];
        for (let index = 0; index < rows.length; index += 1) {
            const current = rows[index];
            const previous = index > 0 ? rows[index - 1] : null;
            const gapMarker = buildGapMarker(previous, current, speechRateScale);
            if (gapMarker) {
                displayRows.push(gapMarker);
            }
            displayRows.push(current);
        }
        return displayRows;
    }

    function inferStressIssue(word) {
        if (!word || typeof word !== 'object') {
            return false;
        }
        if (word.stress_error === true) {
            return true;
        }
        const score = toNumber(word.stress_score);
        if (score !== null && score < 0.85) {
            return true;
        }
        const details = word.stress_details || {};
        const info = String(details.match_info || '').toLowerCase();
        if (!info) {
            return false;
        }
        if (info.includes('perfect match') || info.includes('acceptable variation')) {
            return false;
        }
        return info.includes('mismatch') || info.includes('no vowels');
    }

    function summarizeWordLevelFeedback(words, backendFeedback) {
        const rows = Array.isArray(words) ? words : [];
        const counts = {
            total_words: rows.length,
            correct: 0,
            mispronounced: 0,
            inserted: 0,
            omitted: 0,
            stress_issues: 0,
            pause_issues: 0,
            long_gaps: 0,
        };
        const stressWords = [];

        rows.forEach((word) => {
            const status = String(word && word.status || '').toLowerCase();
            if (status === 'correct') counts.correct += 1;
            if (status === 'mispronounced') counts.mispronounced += 1;
            if (status === 'inserted') counts.inserted += 1;
            if (status === 'omitted') counts.omitted += 1;
            if (status === 'short_pause' || status === 'long_pause' || status === 'missed_pause') counts.pause_issues += 1;
            if (status === 'extra_gap' || isGapMarker(word)) counts.long_gaps += 1;

            if (inferStressIssue(word)) {
                counts.stress_issues += 1;
                const token = String(word && word.word || '').trim();
                if (token) {
                    const exists = stressWords.some((item) => item.toLowerCase() === token.toLowerCase());
                    if (!exists) {
                        stressWords.push(token);
                    }
                }
            }
        });

        const highlights = [];
        if (counts.stress_issues > 0) {
            const focus = stressWords.slice(0, 3).join(', ');
            highlights.push(
                focus
                    ? `Stress issues on ${counts.stress_issues} word(s): ${focus}.`
                    : `Stress issues on ${counts.stress_issues} word(s).`
            );
        }
        if (counts.mispronounced > 0) {
            highlights.push(`${counts.mispronounced} word(s) need clearer pronunciation.`);
        }
        if (counts.omitted > 0 || counts.inserted > 0) {
            highlights.push(`Alignment issues: ${counts.omitted} omitted, ${counts.inserted} inserted.`);
        }
        if (counts.pause_issues > 0) {
            highlights.push(`${counts.pause_issues} punctuation pause(s) need better timing.`);
        }
        if (counts.long_gaps > 0) {
            highlights.push(`${counts.long_gaps} extra gap(s) were longer than the ideal word-to-word limit.`);
        }
        if (!highlights.length) {
            highlights.push('Word-level pronunciation and stress look consistent.');
        }

        const backendMessage = backendFeedback && typeof backendFeedback === 'object'
            ? String(backendFeedback.message || '').trim()
            : '';

        return {
            counts,
            highlights,
            message: backendMessage || highlights.join(' '),
        };
    }

    function formatWordStatus(status) {
        const normalized = String(status || '').trim().toLowerCase();
        if (!normalized) return 'unknown';
        return normalized.replace(/_/g, ' ');
    }

    window.WordLevelFeedback = {
        buildDisplayRowsWithGapMarkers,
        canOpenWordModal,
        formatRange,
        formatSeconds,
        inferStressIssue,
        isGapMarker,
        isPauseToken,
        pauseStatusVariant,
        punctuationLabel,
        summarizeWordLevelFeedback,
        formatWordStatus,
    };
})(window);
