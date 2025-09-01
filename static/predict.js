document.addEventListener("DOMContentLoaded", () => {
    const input = document.querySelector("[data-predict-input]");
    const pillbox = document.querySelector("[data-predict-box]");

    if (!input || !pillbox) return;

    let lastQuery = "";

    input.addEventListener("input", async () => {
        const q = input.value.trim();
        if (q === lastQuery || q.length < 1) {
            pillbox.innerHTML = "";
            return;
        }
        lastQuery = q;

        try {
            const r = await fetch(`/predict?q=${encodeURIComponent(q)}&limit=10`);
            const data = await r.json();
            pillbox.innerHTML = "";
            if (data.items) {
                data.items.forEach(word => {
                    const pill = document.createElement("button");
                    pill.textContent = word;
                    pill.className = "pill";
                    pill.addEventListener("click", () => {
                        input.value = word;
                        pillbox.innerHTML = "";
                        input.focus();
                    });
                    pillbox.appendChild(pill);
                });
            }
        } catch (e) {
            console.error("predict error:", e);
        }
    });
});
