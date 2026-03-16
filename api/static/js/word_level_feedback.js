(function (window) {
    function toNumber(value) {
        const n = Number(value);
        return Number.isFinite(n) ? n : null;
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
        };
        const stressWords = [];

        rows.forEach((word) => {
            const status = String(word && word.status || '').toLowerCase();
            if (status === 'correct') counts.correct += 1;
            if (status === 'mispronounced') counts.mispronounced += 1;
            if (status === 'inserted') counts.inserted += 1;
            if (status === 'omitted') counts.omitted += 1;

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
        inferStressIssue,
        summarizeWordLevelFeedback,
        formatWordStatus,
    };
})(window);
