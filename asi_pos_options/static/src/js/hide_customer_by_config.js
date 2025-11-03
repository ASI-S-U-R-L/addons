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
    return t === text.toLowerCase() || t.includes(text.toLowerCase());
}

function collectTargets(root = document) {
    const list = [
        ".pos .button.set-partner",
        '.pos button[aria-label="Cliente"]',
        '.pos button[title="Cliente"]',
    ];
    const nodes = new Set();
    list.forEach(sel => root.querySelectorAll(sel).forEach(n => nodes.add(n)));
    root.querySelectorAll(".pos button").forEach(btn => {
        const hasIcon = !!btn.querySelector(".fa-user");
        if (hasIcon || byText(btn, "Cliente")) nodes.add(btn);
    });
    return Array.from(nodes);
}

function hideButtons(root = document) {
    let found = false;

    // Obtener el contenedor del numpad
    const numpad = root.querySelector('.numpad');
    if (!numpad) return false;


    // Ocultar completamente Presupuesto/Pedido
    const presupuestoButton = root.querySelector('.o_sale_order_button');
    if (presupuestoButton && byText(presupuestoButton, "Presupuesto/Pedido")) {
        presupuestoButton.style.display = "none";
        presupuestoButton.style.pointerEvents = "none";
        presupuestoButton.setAttribute("data-hidden-presupuesto", "1");
        found = true;
    }


    // Ocultar completamente Nota de cliente
    const noteButton = root.querySelector('.control-button:has(.fa-sticky-note)');
    if (noteButton && byText(noteButton, "Nota de cliente")) {
        noteButton.style.display = "none";
        noteButton.style.pointerEvents = "none";
        noteButton.setAttribute("data-hidden-customer-note", "1");
        found = true;
    }

    // Ocultar completamente Reembolso
    const refundButton = root.querySelector('.control-button:has(.fa-undo)');
    if (refundButton && byText(refundButton, "Reembolso")) {
        refundButton.style.display = "none";
        refundButton.style.pointerEvents = "none";
        refundButton.setAttribute("data-hidden-refund", "1");
        found = true;
    }

    // Ocultar completamente Información
    const infoButton = root.querySelector('.control-button:has(.fa-info-circle)');
    if (infoButton && byText(infoButton, "Información")) {
        infoButton.style.display = "none";
        infoButton.style.pointerEvents = "none";
        infoButton.setAttribute("data-hidden-info", "1");
        found = true;
    }

    // Ocultar completamente Cliente
    const clientButtons = collectTargets(root);
    if (clientButtons.length) {
        clientButtons.forEach(el => {
            el.style.display = "none";
            el.style.pointerEvents = "none";
            el.setAttribute("data-hidden-customer", "1");
        });
        found = true;
    }

    // No ocultar el botón de Pago
    // El botón de Pago queda intacto

    // Ocultar % Desc preservando espacio
    const discountButtons = numpad.querySelectorAll('.mode-button:not(.selected-mode)');
    discountButtons.forEach(btn => {
        if (byText(btn, "% Desc")) {
            btn.style.visibility = "hidden";
            btn.style.pointerEvents = "none";
            btn.setAttribute("data-hidden-discount", "1");
            found = true;
        }
    });

    // Ocultar Precio preservando espacio
    const priceButtons = numpad.querySelectorAll('.mode-button:not(.selected-mode)');
    priceButtons.forEach(btn => {
        if (byText(btn, "Precio")) {
            btn.style.visibility = "hidden";
            btn.style.pointerEvents = "none";
            btn.setAttribute("data-hidden-price", "1");
            found = true;
        }
    });

    return found;
}

function startObserver() {
    if (window.__POS_HIDE_BUTTONS_OBS__) return;
    try {
        const obs = new MutationObserver(() => hideButtons(document));
        obs.observe(document.body, { childList: true, subtree: true });
        window.__POS_HIDE_BUTTONS_OBS__ = obs;
    } catch (_) {}
}

async function runAfterInit(ctx) {
    try {
        const enabled = !!(ctx && ctx.config && ctx.config.hide_customer_button);
        if (!enabled) return;
        await domReady();
        
        let found = false;
        for (let i = 0; i < 60; i++) { 
            found = hideButtons(document) || found;
            await new Promise(r => setTimeout(r, 100));
        }
        startObserver();
        if (!found) console.warn("[asi_pos_options] no se encontraron los botones aún; observer activo.");
    } catch (e) {
        console.warn("[asi_pos_options] post-init failed:", e);
    }
}

// Función para ocultar el botón "Cliente" en la pantalla de pago
function hideCustomerButtonInPaymentScreen(root = document) {
    const paymentScreen = root.querySelector('.payment-screen');
    if (!paymentScreen) return false;

    const clientButton = paymentScreen.querySelector('.partner-button .button');
    if (clientButton && (clientButton.querySelector('.fa-user') || byText(clientButton, "Cliente"))) {
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
        const obs = new MutationObserver(() => {
            hideCustomerButtonInPaymentScreen(document);
        });
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
        if (!found) console.warn("[asi_pos_options] no se encontró el botón 'Cliente' en pantalla de pago aún; observer activo.");
    } catch (e) {
        console.warn("[asi_pos_options] post-init payment screen failed:", e);
    }
}

const _orig = {
    loadServerData: PosGlobalState.prototype.loadServerData,
    _processData: PosGlobalState.prototype._processData,
};

patch(PosGlobalState.prototype, "asi_pos_options.selective_hiding_fixed", {
    async loadServerData(...args) {
        let res;
        if (typeof _orig.loadServerData === "function") {
            res = await _orig.loadServerData.apply(this, args);
        }
        runAfterInit(this);
        runPaymentScreenInit(this);
        return res;
    },
    async _processData(...args) {
        let res;
        if (typeof _orig._processData === "function") {
            res = await _orig._processData.apply(this, args);
        }
        runAfterInit(this);
        runPaymentScreenInit(this);
        return res;
    },
});