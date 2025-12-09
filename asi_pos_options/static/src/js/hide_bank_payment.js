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

function hideBankPaymentButtons(root = document) {
    let found = false;
    // Enfocarse en la pantalla de pagos
    const paymentScreen = root.querySelector('.payment-screen');
    if (!paymentScreen) return false;

    // Selectores para botones de métodos de pago
    const paymentButtons = paymentScreen.querySelectorAll(
        '.paymentmethod, .button.payment-method, .payment-button, button.payment, .payment-item'
    );

    paymentButtons.forEach(btn => {
        // Verificar si es "Banco" en diferentes idiomas/variaciones
        const isBankPayment = byText(btn, "Banco") || 
                             byText(btn, "Bank") || 
                             byText(btn, "Transferencia bancaria") || 
                             byText(btn, "Bank transfer") ||
                             btn.getAttribute('data-payment-method')?.toLowerCase().includes('bank') ||
                             btn.dataset.paymentMethod?.toLowerCase().includes('bank');

        if (isBankPayment) {
            btn.style.display = "none";
            btn.style.pointerEvents = "none";
            btn.setAttribute("data-hidden-bank-payment", "1");
            found = true;
            console.debug("[asi_pos_options] Ocultando botón de pago Banco:", btn);
        }
    });

    return found;
}

function startBankPaymentObserver(ctx) {
    if (window.__POS_HIDE_BANK_PAYMENT_OBS__) return;
    try {
        const enabled = !!(ctx && ctx.config && ctx.config.hide_bank_payment);
        if (!enabled) return;

        const obs = new MutationObserver(() => {
            hideBankPaymentButtons(document);
        });
        obs.observe(document.body, { childList: true, subtree: true });
        window.__POS_HIDE_BANK_PAYMENT_OBS__ = obs;
        console.debug("[asi_pos_options] Observer de ocultación de pago Banco iniciado.");
    } catch (e) {
        console.error("[asi_pos_options] Error al iniciar observer de pago Banco:", e);
    }
}

async function runBankPaymentInit(ctx) {
    try {
        const enabled = !!(ctx && ctx.config && ctx.config.hide_bank_payment);
        if (!enabled) return;

        await domReady();
        
        let found = false;
        for (let i = 0; i < 60; i++) { 
            found = hideBankPaymentButtons(document) || found;
            await new Promise(r => setTimeout(r, 100));
        }
        startBankPaymentObserver(ctx);
        if (!found) {
            console.warn("[asi_pos_options] No se encontró el botón de pago 'Banco' en pantalla de pagos; observer activo. Verifica el texto exacto del botón.");
            // Depuración: listar todos los botones de pago
            const paymentScreen = document.querySelector('.payment-screen');
            if (paymentScreen) {
                const allButtons = paymentScreen.querySelectorAll('.paymentmethod, .button, button');
                allButtons.forEach(btn => {
                    console.debug("[asi_pos_options] Botón de pago encontrado:", btn.textContent.trim(), btn.className, btn.dataset);
                });
            }
        }
    } catch (e) {
        console.error("[asi_pos_options] Error en inicialización de ocultación de pago Banco:", e);
    }
}

patch(PosGlobalState.prototype, "asi_pos_options.hide_bank_payment", {
    async loadServerData(...args) {
        const out = await this._super?.(...args);
        runBankPaymentInit(this);
        return out;
    },
    async _processData(...args) {
        const out = await this._super?.(...args);
        runBankPaymentInit(this);
        return out;
    },
});