/* Save / Reject buttons on a job card.
 *
 * One delegated listener on the document rather than a listener per button: the results page
 * renders thirty-odd cards, and the feed re-renders on every visit. Delegation means the
 * handler is attached once and keeps working for markup added later.
 *
 * Plain fetch, no framework — the stack in CLAUDE.md rules out React and Vue, not JavaScript.
 *
 * Why this posts instead of submitting a form: the ranked list only exists in the response
 * that rendered it, so a form POST would either lose the results the user is looking at or
 * re-run the whole search pipeline (a second Groq call) for every click.
 *
 * The body is form-encoded on purpose. The server's check_csrf() reads request.form, so a
 * JSON body would arrive with an empty form and fail the token check on every request.
 */

(function () {
    "use strict";

    var SAVE_LABEL = "Saved";
    var REJECT_LABEL = "Rejected";

    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute("content") : "";
    }

    function setError(group, message) {
        var slot = group.querySelector(".js-decision-error");
        if (!slot) {
            return;
        }
        slot.textContent = message || "";
        slot.classList.toggle("d-none", !message);
    }

    /* Both buttons are disabled together: save and reject are one decision, and leaving the
     * other live would let a user increment a category and decrement it in two clicks. */
    function setBusy(group, busy) {
        group.querySelectorAll(".js-decision").forEach(function (button) {
            button.disabled = busy;
        });
    }

    function settle(button, decision) {
        var group = button.closest(".js-decision-group");
        group.querySelectorAll(".js-decision").forEach(function (other) {
            other.disabled = true;
        });
        button.textContent = decision === "save" ? SAVE_LABEL : REJECT_LABEL;
        button.classList.remove("btn-success", "btn-outline-danger");
        button.classList.add("btn-secondary");
    }

    function body(group, decision) {
        var params = new URLSearchParams();
        params.set("csrf_token", csrfToken());
        params.set("job_id", group.dataset.jobId || "");
        params.set("title", group.dataset.title || "");
        params.set("company", group.dataset.company || "");
        params.set("location", group.dataset.location || "");
        params.set("source", group.dataset.source || "");
        params.set("url", group.dataset.url || "");
        params.set("category", group.dataset.category || "");
        return params;
    }

    document.addEventListener("click", function (event) {
        var button = event.target.closest(".js-decision");
        if (!button) {
            return;
        }

        var group = button.closest(".js-decision-group");
        if (!group) {
            return;
        }

        event.preventDefault();
        var decision = button.dataset.decision;
        setError(group, "");
        setBusy(group, true);

        fetch(decision === "save" ? "/save_job" : "/reject_job", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: body(group, decision).toString(),
            /* The session cookie is what identifies the user to @require_auth. */
            credentials: "same-origin"
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { ok: response.ok, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok || !result.data.ok) {
                    throw new Error(result.data.error || "Something went wrong.");
                }
                /* data.already is true when this job was recorded by an earlier click. That
                 * is a success, not an error — the score moved exactly once (TC-013) — so the
                 * button settles the same way either way. */
                settle(button, decision);
            })
            .catch(function (error) {
                /* Never a silent no-op: re-enable the buttons and say what failed, so a
                 * failure looks different from a click that did not register. */
                setBusy(group, false);
                setError(group, error.message || "Something went wrong.");
            });
    });
})();
