/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosGlobalState } from "point_of_sale.models";

function domReady() {
    if (document.readyState === "complete" || document.readyState === "interactive") {
        return Promise.resolve();
    }
    return new Promise((resolve) => {
        document.addEventListener("DOMContentLoaded", () => resolve(), { once: true });
    });
}

function byText(el, text) {
    const t = (el.textContent || "").trim().toLowerCase();
    return t.includes(text);
}

function collectCustomerTargets(root = document) {
    const list = [
        ".pos .button.set-partner",
        '.pos button[aria-label="Cliente"]',
        '.pos button[title="Cliente"]',
    ];
    const nodes = new Set();
    list.forEach(sel => root.querySelectorAll(sel).forEach(n => nodes.add(n)));

    // Fallback: por icono y texto
    root.querySelectorAll(".pos button").forEach(btn => {
        const hasIcon = !!btn.querySelector(".fa-user");
        if (hasIcon || byText(btn, "cliente")) nodes.add(btn);
    });
    return Array.from(nodes);
}

function collectCustomerNoteTargets(root = document) {
    const nodes = new Set();

    // Buscar por estructura exacta: .control-button con .fa-sticky-note y texto "Nota de cliente"
    root.querySelectorAll('.control-button').forEach(btn => {
        const hasIcon = !!btn.querySelector('.fa-sticky-note');
        const hasText = byText(btn, "nota de cliente");
        if (hasIcon && hasText) {
            nodes.add(btn);
        }
    });

    return Array.from(nodes);
}

function hideElements(nodes) {
    if (!nodes.length) return false;
    nodes.forEach(el => {
        el.style.display = "none";
        el.style.pointerEvents = "none";
        el.setAttribute("data-hidden-pos-restriction", "1");
    });
    return true;
}

function hideCustomerButtons(root = document) {
    const nodes = collectCustomerTargets(root);
    return hideElements(nodes);
}

function hideCustomerNoteButtons(root = document) {
    const nodes = collectCustomerNoteTargets(root);
    return hideElements(nodes);
}

function startObserver() {
    if (window.__POS_HIDE_RESTRICTIONS_OBS__) return;
    try {
        const obs = new MutationObserver(() => {
            hideCustomerButtons(document);
            hideCustomerNoteButtons(document);
        });
        obs.observe(document.body, { childList: true, subtree: true });
        window.__POS_HIDE_RESTRICTIONS_OBS__ = obs;
    } catch (_) {}
}

async function runAfterInit(ctx) {
    try {
        const enabled = !!(ctx && ctx.config && ctx.config.hide_customer_button);
        if (!enabled) return;

        await domReady();

        let found = false;
        for (let i = 0; i < 60; i++) {
            found = hideCustomerButtons(document) || found;
            found = hideCustomerNoteButtons(document) || found;
            await new Promise(r => setTimeout(r, 100));
        }

        startObserver();

        if (!found) {
            console.warn("[pos_hide_customer_button] No se encontraron botones 'Cliente' o 'Nota de cliente'. Observer activo.");
        }
    } catch (e) {
        console.warn("[pos_hide_customer_button] post-init failed:", e);
    }
}

// === Pantalla de Pago: ocultar botón Cliente ===
function hideCustomerButtonInPaymentScreen(root = document) {
    const paymentScreen = root.querySelector('.payment-screen');
    if (!paymentScreen) return false;

    const clientButton = paymentScreen.querySelector('.partner-button .button');
    if (clientButton && (clientButton.querySelector('.fa-user') || byText(clientButton, "cliente"))) {
        clientButton.style.display = "none";
        clientButton.style.pointerEvents = "none";
        clientButton.setAttribute("data-hidden-customer", "1");
        return true;
    }
    return false;
}

function startPaymentScreenObserver() {
    if (window.__POS_HIDE_CUSTOMER_PAYMENT_OBS__) return;
    try {
        const obs = new MutationObserver(() => hideCustomerButtonInPaymentScreen(document));
        obs.observe(document.body, { childList: true, subtree: true });
        window.__POS_HIDE_CUSTOMER_PAYMENT_OBS__ = obs;
    } catch (_) {}
}

async function runPaymentScreenInit(ctx) {
    try {
        const enabled = !!(ctx && ctx.config && ctx.config.hide_customer_button);
        if (!enabled) return;
        await domReady();

        let found = false;
        for (let i = 0; i < 60; i++) {
            found = hideCustomerButtonInPaymentScreen(document) || found;
            await new Promise(r => setTimeout(r, 100));
        }
        startPaymentScreenObserver();
    } catch (e) {
        console.warn("[pos_hide_customer_button] payment screen init failed:", e);
    }
}

// === Patch ===
const _orig = {
    loadServerData: PosGlobalState.prototype.loadServerData,
    _processData: PosGlobalState.prototype._processData,
};

patch(PosGlobalState.prototype, "pos_hide_customer_button.restrictions", {
    async loadServerData(...args) {
        const res = await (_orig.loadServerData?.apply(this, args) || this._super?.(...args));
        runAfterInit(this);
        runPaymentScreenInit(this);
        return res;
    },
    async _processData(...args) {
        const res = await (_orig._processData?.apply(this, args) || this._super?.(...args));
        runAfterInit(this);
        runPaymentScreenInit(this);
        return res;
    },
});