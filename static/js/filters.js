/* Result filter chips — TC-015 / FR-021.
 *
 * Client-side by design. The ranked list only exists in the response that rendered it, so a
 * server-side filter would have to re-run the whole pipeline -- a second Groq call and fresh
 * Adzuna quota -- to hide cards the browser is already holding. The SRS specifies these as
 * chips applied to the current results, which is the same conclusion.
 *
 * Plain JS, no framework, matching static/js/decisions.js. If JS is off the chips do nothing
 * and every result stays visible, which is the correct degradation: the user sees more than
 * they asked for, never less.
 *
 * Scoped to #js-results on purpose, so the AI Recommendations band above is never filtered.
 * Those three are the answer to the question the user asked; hiding them because of a chip
 * would make the panel look broken.
 */

(function () {
    "use strict";

    var active = {};

    function cards() {
        var results = document.getElementById("js-results");
        return results ? results.querySelectorAll(".js-job-card") : [];
    }

    /* One predicate per chip. A card must satisfy EVERY active filter, so the chips narrow
     * together rather than each replacing the last. */
    var RULES = {
        remote: function (card) {
            return card.dataset.remote === "yes";
        },
        eligible: function (card) {
            /* "unknown" counts as eligible and that is deliberate: the listing did not say
             * it excludes this user, and hiding it would be acting on a guess. The card
             * still carries its "Location terms unclear" badge so the user can judge. */
            var e = card.dataset.eligibility;
            return e === "open" || e === "unknown";
        }
    };

    function apply() {
        var shown = 0;
        var total = 0;

        cards().forEach(function (card) {
            total += 1;
            var visible = Object.keys(active).every(function (name) {
                return !active[name] || RULES[name](card);
            });
            card.classList.toggle("d-none", !visible);
            if (visible) {
                shown += 1;
            }
        });

        var count = document.querySelector(".js-filter-count");
        if (count) {
            count.textContent = shown === total ? "" : "showing " + shown + " of " + total;
        }

        /* Never let a filter leave a silently blank page -- the same rule the agent's error
         * banners follow. */
        var empty = document.getElementById("js-filter-empty");
        if (empty) {
            empty.classList.toggle("d-none", shown > 0 || total === 0);
        }
    }

    document.addEventListener("click", function (event) {
        var chip = event.target.closest(".js-filter");
        if (!chip) {
            return;
        }
        var name = chip.dataset.filter;
        if (!RULES[name]) {
            return;
        }

        active[name] = !active[name];
        chip.setAttribute("aria-pressed", active[name] ? "true" : "false");
        chip.classList.toggle("btn-secondary", active[name]);
        chip.classList.toggle("btn-outline-secondary", !active[name]);
        apply();
    });
}());
