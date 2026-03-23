
(function () {
    function initTextType() {
        // CSS Injection for Cursor (Once globally)
        if (!document.getElementById('text-type-styles')) {
            const style = document.createElement('style');
            style.id = 'text-type-styles';
            style.innerHTML = `
                .text-type-container {
                    display: inline-block;
                    white-space: pre-wrap; /* Preserve spaces/newlines */
                }
                .text-type__content {
                    /* Inherit font/color */
                }
                .text-type__cursor {
                    margin-left: 2px;
                    display: inline-block;
                    font-weight: 100;
                    color: inherit;
                    animation: text-type-blink 1s step-end infinite;
                }
                @keyframes text-type-blink {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0; }
                }
            `;
            document.head.appendChild(style);
        }

        const containers = document.querySelectorAll('.text-type-container'); // Find all instances
        containers.forEach(container => {
            if (container.dataset.initialized) return;
            startTyping(container);
            container.dataset.initialized = 'true';
        });
    }

    function startTyping(container) {
        // --- Parse Attributes ---
        // data-text can be "['Text 1', 'Text 2']" or just "Hello World"
        let texts = [];
        const rawText = container.getAttribute('data-text');

        if (!rawText) return;

        try {
            // Replace single quotes with double for strict JSON parse.
            // Edge case: Text contains quotes. 
            // Simple approach: Check if it looks like an array start
            if (rawText.trim().startsWith('[')) {
                // Try simple replace
                let jsonString = rawText.replace(/'/g, '"');
                texts = JSON.parse(jsonString);
            } else {
                texts = [rawText];
            }
        } catch (e) {
            // Fallback: Treat entire string as one item
            texts = [rawText];
        }

        const typingSpeed = parseInt(container.getAttribute('data-speed') || '50');
        const deletingSpeed = parseInt(container.getAttribute('data-delete-speed') || '30');
        const pauseDuration = parseInt(container.getAttribute('data-pause') || '2000');
        const loop = container.getAttribute('data-loop') !== 'false';

        // --- Setup DOM ---
        container.innerHTML = '';
        const contentSpan = document.createElement('span');
        contentSpan.className = 'text-type__content';
        // Inherit color from parent (or allow override via CSS)

        container.appendChild(contentSpan);

        const cursorSpan = document.createElement('span');
        cursorSpan.className = 'text-type__cursor';
        cursorSpan.textContent = '|';
        container.appendChild(cursorSpan);

        // --- Logic ---
        let textIndex = 0;      // Index of current string in array
        let charIndex = 0;      // Current character position
        let isDeleting = false; // Mode
        let isPaused = false;   // Pause state

        // Logic Function
        function type() {
            const currentFullText = texts[textIndex];

            // Determine text to show
            if (isDeleting) {
                // Removing char
                contentSpan.textContent = currentFullText.substring(0, charIndex - 1);
                charIndex--;
            } else {
                // Adding char
                contentSpan.textContent = currentFullText.substring(0, charIndex + 1);
                charIndex++;
            }

            // Determine Speed
            let delta = typingSpeed;
            if (isDeleting) delta = deletingSpeed;

            // --- State Transitions ---

            // 1. Finished Typing Sentence
            if (!isDeleting && charIndex === currentFullText.length) {
                // Pause at end
                delta = pauseDuration;
                isDeleting = true; // Switch mode

                // Check End of Queue
                // If loop is false and this is the last item: Stop.
                if (!loop && textIndex === texts.length - 1) {
                    // Stop animation completely
                    // Maybe hide cursor?
                    // cursorSpan.style.display = 'none';
                    return;
                }
            }
            // 2. Finished Deleting Sentence
            else if (isDeleting && charIndex === 0) {
                isDeleting = false;
                textIndex++; // Move to next string
                delta = 500; // Small pause before typing next

                // Wrap around
                if (textIndex >= texts.length) {
                    textIndex = 0;
                }
            }

            setTimeout(type, delta);
        }

        // Start
        setTimeout(type, typingSpeed); // Initial delay
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTextType);
    } else {
        initTextType();
    }
})();
