/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosGlobalState } from "point_of_sale.models";

let observerStarted = false;

function i18nIncludes(text) {
    const t = (text || "").toLowerCase();
    return (
        t.includes("control de efectivo de apertura") || // ES
        t.includes("opening cash control") ||             // EN (approx)
        t.includes("cash opening")                        // fallback
    );
}

function isCalcPopupTitle(text) {
    const t = (text || "").toLowerCase();
    return (
        t.includes("monedas/billetes") || t.includes("monedas") || t.includes("billetes") || // ES
        t.includes("coins") || t.includes("bills") || t.includes("denominations")            // EN
    );
}

function findPopupRootByTitle(predicate) {
    const dialogs = document.querySelectorAll('.modal-dialog, [role="dialog"]');
    for (const dlg of dialogs) {
        const titleEl = dlg.querySelector('.title');
        if (titleEl && predicate(titleEl.textContent || "")) {
            return dlg;
        }
    }
    return null;
}

function disableManualInputAndAutoOpenCalculator(openingPopup) {
    if (!openingPopup || openingPopup.dataset._forcedDenom === "1") return;

    // 1) Disable manual input
    const amountInput = openingPopup.querySelector('input[type="number"], input');
    if (amountInput) {
        amountInput.readOnly = true;
        amountInput.setAttribute('aria-readonly', 'true');
        amountInput.title = "Use el conteo por denominaciones";
        amountInput.addEventListener('keydown', (ev) => ev.preventDefault(), { passive: false });
        amountInput.addEventListener('paste',  (ev) => ev.preventDefault(), { passive: false });
        amountInput.addEventListener('focus', tryOpenCalculatorOnce, { once: true });
        amountInput.addEventListener('click', tryOpenCalculatorOnce, { once: true });
    }

    // 2) Disable Confirm until denominations confirmed
    const confirmBtn = Array.from(openingPopup.querySelectorAll('button, .button, [role="button"]'))
        .find((b) => /confirmar|confirm|aceptar/i.test((b.textContent || "")));
    if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.dataset._needsDenom = "1";
        confirmBtn.classList.add('o_disabled');
    }

    // 3) Auto-open calculator once
    tryOpenCalculatorOnce();

    openingPopup.dataset._forcedDenom = "1";

    function tryOpenCalculatorOnce() {
        let calcBtn = openingPopup.querySelector('[name="open-cash-denominations"], .fa-calculator, [data-action="cash-denominations"]');
        if (!calcBtn) {
            calcBtn = Array.from(openingPopup.querySelectorAll('button, .button, [role="button"], i'))
                .find((el) => {
                    const t = (el.textContent || el.getAttribute('title') || '').toLowerCase();
                    return t.includes('calculadora') || t.includes('calculator');
                });
        }
        if (calcBtn && !openingPopup.dataset._calcOpenedOnce) {
            openingPopup.dataset._calcOpenedOnce = "1";
            calcBtn.click();
        }
    }
}

function wireCalculatorToOpeningPopup() {
    const openingPopup = findPopupRootByTitle(i18nIncludes);
    const calcPopup   = findPopupRootByTitle(isCalcPopupTitle);
    if (!openingPopup || !calcPopup) return;

    const calcConfirm = Array.from(calcPopup.querySelectorAll('button, .button, [role="button"]'))
        .find((b) => /confirmar|confirm/i.test((b.textContent || "")));
    if (!calcConfirm || calcPopup.dataset._wired === "1") return;
    calcPopup.dataset._wired = "1";

    calcConfirm.addEventListener('click', () => {
        const totalLabel = Array.from(calcPopup.querySelectorAll('div, span, p, b, strong'))
            .find((n) => /total/i.test((n.textContent || "")));
        let total = 0;
        if (totalLabel) {
            const text = (totalLabel.textContent || "") + " " + (totalLabel.parentElement?.textContent || "");
            const m = text.replace(/\s/g,'').match(/(-?\\d+(?:[.,]\\d{1,2})?)/g);
            if (m && m.length) {
                const last = m[m.length - 1].replace(',', '.');
                total = parseFloat(last) || 0;
            }
        }
        const amountInput = openingPopup.querySelector('input[type="number"], input');
        if (amountInput) {
            amountInput.value = Number.isFinite(total) ? String(total) : amountInput.value;
            amountInput.dispatchEvent(new Event('input', { bubbles: true }));
            amountInput.dispatchEvent(new Event('change', { bubbles: true }));
        }
        const confirmBtn = Array.from(openingPopup.querySelectorAll('button, .button, [role="button"]'))
            .find((b) => /confirmar|confirm|aceptar/i.test((b.textContent || "")));
        if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.classList.remove('o_disabled');
            delete confirmBtn.dataset._needsDenom;
        }
    }, { once: true });
}

function bootObserverIfNeeded(pos) {
      console.log("pos: ",!pos?.config?.force_opening_by_denominations );
    if (!pos?.config?.force_opening_by_denominations || observerStarted) return;
    observerStarted = true;

    const obs = new MutationObserver(() => {
        const openingPopup = findPopupRootByTitle(i18nIncludes);
        if (openingPopup) {
           
            disableManualInputAndAutoOpenCalculator(openingPopup);
        }
        wireCalculatorToOpeningPopup();
    });
    obs.observe(document.body, { childList: true, subtree: true });
}

patch(PosGlobalState.prototype, "pos_hide_customer_button.force_opening_by_denominations", {
    async loadServerData(...args) {
        const out = await this._super?.(...args);
        bootObserverIfNeeded(this);
        return out;
    },
    async _processData(...args) {
        const out = await this._super?.(...args);
        bootObserverIfNeeded(this);
        return out;
    },
});
