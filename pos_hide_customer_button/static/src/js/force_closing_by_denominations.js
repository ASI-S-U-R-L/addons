/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosGlobalState } from "point_of_sale.models";

let observerStartedClosing = false;
let closingFlowArmed = false; // se arma SOLO cuando se hace click en Cerrar

// === Helpers específicos para el DOM que nos diste ===
function getClosingPopup() {
    // Popup de cierre: <div class="popup close-pos-popup">
    const dlg = document.querySelector('.modal-dialog .popup.close-pos-popup');
    return dlg || null;
}

function getClosingAmountInput(root) {
    // Input del contado: <input class="pos-input">
    return root?.querySelector('input.pos-input') || null;
}

function getCalculatorButton(root) {
    // Botón calculadora: <div class="button icon"><i class="fa fa-calculator"></i></div>
    // Haremos click en el contenedor .button.icon
    const container = root?.querySelector('.button.icon');
    return container || null;
}

function getConfirmCloseButton(root) {
    // Botón confirmar cierre: <footer class="footer"><div class="button highlight">Cerrar sesión</div>
    return root?.querySelector('.footer .button.highlight') || null;
}

function disableManualInputAndAutoOpenCalculator_Closing(closingPopup) {
    if (!closingPopup || closingPopup.dataset._forcedDenomClosing === "1") return;

    // 1) Deshabilitar input manual
    const amountInput = getClosingAmountInput(closingPopup);
    if (amountInput) {
        amountInput.readOnly = true;
        amountInput.setAttribute('aria-readonly', 'true');
        amountInput.title = "Use el conteo por denominaciones";
        amountInput.addEventListener('keydown', (ev) => ev.preventDefault(), { passive: false });
        amountInput.addEventListener('paste',  (ev) => ev.preventDefault(), { passive: false });
        amountInput.addEventListener('focus', tryOpenCalculatorOnce, { once: true });
        amountInput.addEventListener('click', tryOpenCalculatorOnce, { once: true });
    }

    // 2) Bloquear Confirmar/Cerrar
    const confirmBtn = getConfirmCloseButton(closingPopup);
    if (confirmBtn) {
        confirmBtn.classList.add('o_disabled');
        confirmBtn.dataset._needsDenomClosing = "1";
        confirmBtn.setAttribute('aria-disabled', 'true');
        confirmBtn.addEventListener('click', (ev) => {
            if (confirmBtn.dataset._needsDenomClosing === "1") {
                ev.stopImmediatePropagation();
                ev.preventDefault();
            }
        }, true);
    }

    // 3) Intentar abrir la calculadora una vez
    tryOpenCalculatorOnce();

    closingPopup.dataset._forcedDenomClosing = "1";

    function tryOpenCalculatorOnce() {
        const calcBtn = getCalculatorButton(closingPopup);
        if (calcBtn && !closingPopup.dataset._calcOpenedOnceClosing) {
            closingPopup.dataset._calcOpenedOnceClosing = "1";
            calcBtn.click();
        }
    }
}

// Heurística para detectar el popup de Money Details (no tenemos su HTML exacto).
function isMoneyDetailsPopup(node) {
    if (!node) return false;
    const txt = (node.textContent || "").toLowerCase();
    return (
        /monedas|billetes|denominaciones|coins|bills|denominations|detalles monetarios/.test(txt)
    );
}

// Cuando el usuario confirma el popup de denominaciones:
// - Traemos el total y lo aplicamos al input .pos-input
// - Habilitamos el botón "Cerrar sesión"
function wireCalculatorToClosingPopup() {
    const closingPopup = getClosingPopup();
    if (!closingPopup) return;

    // Buscar un posible popup de Money Details activo
    const dialogs = Array.from(document.querySelectorAll('.modal-dialog .popup'));
    const calcPopup = dialogs.find((p) => p !== closingPopup && isMoneyDetailsPopup(p));
    if (!calcPopup || calcPopup.dataset._wiredClosing === "1") return;
    calcPopup.dataset._wiredClosing = "1";

    // Confirmación del conteo: probamos con botones que tengan texto confirm-ish
    const calcConfirm = Array.from(calcPopup.querySelectorAll('button, .button, [role="button"], .footer .button'))
        .find((b) => /confirmar|aceptar|ok|confirm/i.test((b.textContent || "")));

    if (!calcConfirm) return;

    calcConfirm.addEventListener('click', () => {
        // 1) extraer total visible (heurística robusta)
        let total = 0;
        const amountHints = Array.from(calcPopup.querySelectorAll('div, span, p, b, strong'));
        const totalNode = amountHints.find((n) => /total/i.test((n.textContent || "")));
        if (totalNode) {
            const text = ((totalNode.textContent || "") + " " + (totalNode.parentElement?.textContent || "")).replace(/\s/g, '');
            const matches = text.match(/-?\d+(?:[.,]\d{1,2})?/g);
            if (matches && matches.length) {
                const last = matches[matches.length - 1].replace(',', '.');
                const parsed = parseFloat(last);
                if (!Number.isNaN(parsed)) total = parsed;
            }
        }

        // 2) setear input
        const amountInput = getClosingAmountInput(closingPopup);
        if (amountInput) {
            amountInput.value = Number.isFinite(total) ? String(total) : amountInput.value;
            amountInput.dispatchEvent(new Event('input', { bubbles: true }));
            amountInput.dispatchEvent(new Event('change', { bubbles: true }));
        }

        // 3) habilitar cierre
        const confirmBtn = getConfirmCloseButton(closingPopup);
        if (confirmBtn) {
            confirmBtn.classList.remove('o_disabled');
            confirmBtn.removeAttribute('aria-disabled');
            delete confirmBtn.dataset._needsDenomClosing;
        }
    }, { once: true });
}

// Arranca el observer SOLO cuando el usuario pulsa el botón de cerrar sesión en la vista principal.
function startClosingObserver() {
    if (observerStartedClosing) return;
    observerStartedClosing = true;

    const obs = new MutationObserver(() => {
        const closingPopup = getClosingPopup();
        if (closingPopup) {
            disableManualInputAndAutoOpenCalculator_Closing(closingPopup);
        }
        wireCalculatorToClosingPopup();
    });
    obs.observe(document.body, { childList: true, subtree: true });
}

// Armar el hook en el botón que dispara el popup de cierre.
function armOnCloseButtonClick() {
    if (closingFlowArmed) return;
    closingFlowArmed = true;

    document.addEventListener("click", (ev) => {
        const target = ev.target instanceof HTMLElement ? ev.target : null;
        if (!target) return;

       const btn = target.closest('.header-button');
        if (!btn) return;

        // Buscamos el botón externo que abre el popup de cierre
        const txt = (btn.textContent || "").toLowerCase();
        const classes = (btn.className || "").toLowerCase();
        const nameAttr = (btn.getAttribute("name") || "").toLowerCase();
        const dataAction = (btn.getAttribute("data-action") || "").toLowerCase();

       const looksLikeCloseAction =true;

        if (looksLikeCloseAction) {
            startClosingObserver();
        }
    }, true);
}

patch(PosGlobalState.prototype, "pos_hide_customer_button.force_closing_by_denominations_dom_specific", {
    async loadServerData(...args) {
        const out = await this._super?.(...args);
        // NO iniciamos el observer en boot; solo armamos el listener de "Cerrar"
        armOnCloseButtonClick();
        return out;
    },
    async _processData(...args) {
        const out = await this._super?.(...args);
        armOnCloseButtonClick();
        return out;
    },
});
