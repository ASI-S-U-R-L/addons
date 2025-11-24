/** @odoo-module */

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

function showTRMQrCode(root = document, ctx = null) {
    let found = false;
    const paymentScreen = root.querySelector('.payment-buttons');
    if (!paymentScreen) return false;

    // Obtener la orden actual desde el contexto (ctx) o desde window.pos
    let pos = ctx;
    if (!pos) {
        pos = window.pos;
    }
    if (!pos || !pos.get_order()) {
        // Si no hay POS u orden, ocultar el QR si existe
        const existingQr = paymentScreen.querySelector('.trm-qr-container');
        if (existingQr) {
            existingQr.remove();
        }
        return false;
    }

    const order = pos.get_order();
    const selectedPaymentLine = order.selected_paymentline;

    // Verificar si el método de pago seleccionado es "Banco" o "Transferencia"
    const isBankPayment = selectedPaymentLine &&
        (selectedPaymentLine.payment_method.type === 'bank' ||
         selectedPaymentLine.payment_method.name.toLowerCase().includes('banco') ||
         selectedPaymentLine.payment_method.name.toLowerCase().includes('Tranferencia') ||
         selectedPaymentLine.payment_method.name.toLowerCase().includes('Transferencia'));

    // Verificar si ya existe el QR
    const existingQr = paymentScreen.querySelector('.trm-qr-container');

    if (isBankPayment && pos.config.show_trm_qr_in_pos) {
        // Usar el importe de la línea de pago seleccionada (solo Transferencia)
        const transferAmount = selectedPaymentLine ? selectedPaymentLine.amount : order.get_total_with_tax();
              
        // Generar QR básico para POS con el importe correcto
        const qrData = {
            'id_transaccion': "ESTATICO",
            'importe': transferAmount,
            'moneda': pos.currency.display_name || 'CUP',
            'numero_proveedor': '0000000000', 
            'version': 1,
            'titulo': pos.config.display_name
        };
        const newQrString = JSON.stringify(qrData);
        const qrUrl = `/report/barcode/?barcode_type=QR&value=${encodeURIComponent(newQrString)}&width=150&height=150`;

        if (existingQr) {
            // Si ya existe, verificar si necesita actualizarse
            const img = existingQr.querySelector('img');
            if (img && img.src !== qrUrl) {
                img.src = qrUrl;
                order.trm_qr_code_str = newQrString; // Actualizar el string en la orden
            }
            found = true;
        } else {
            // Crear contenedor del QR
            const qrContainer = document.createElement('div');
            qrContainer.className = 'trm-qr-container mt-2';
            qrContainer.style.textAlign = 'center';
            qrContainer.innerHTML = `
                <h5>Escanear con Transfermóvil</h5>
                <img class="border border-dark rounded" src="${qrUrl}" alt="QR Transfermovil" />
            `;

            // Insertar justo debajo del botón "Factura"
            const invoiceButton = paymentScreen.querySelector('.js_invoice');
            if (invoiceButton) {
                const paymentControls = invoiceButton.closest('.payment-controls');
                if (paymentControls) {
                    paymentControls.insertAdjacentElement('afterend', qrContainer);
                    order.trm_qr_code_str = newQrString; // Guardar el string en la orden
                    found = true;
                }
            }
        }
    } else {
        // Si no es pago por banco o no está habilitado, ocultar el QR
        if (existingQr) {
            existingQr.remove();
            order.trm_qr_code_str = false; // Limpiar el string cuando no hay QR
        }
    }

    return found;
}

function startTRMQrObserver(ctx) {
    if (window.__POS_TRM_QR_OBS__) return;
    try {
        const enabled = !!(ctx && ctx.config && ctx.config.show_trm_qr_in_pos);
        if (!enabled) return;

        let timeoutId = null;
        const obs = new MutationObserver((mutations) => {
            // Verificar si hay cambios relevantes en elementos de pago
            let hasPaymentChanges = false;
            for (const mutation of mutations) {
                if (mutation.type === 'characterData' && mutation.target.parentElement) {
                    // Detectar cambios en el texto de .payment-amount
                    if (mutation.target.parentElement.classList.contains('payment-amount')) {
                        hasPaymentChanges = true;
                        break;
                    }
                }
                if (mutation.type === 'childList') {
                    // Detectar cambios en la estructura de paymentlines
                    if (mutation.target.classList && mutation.target.classList.contains('paymentlines')) {
                        hasPaymentChanges = true;
                        break;
                    }
                    // Detectar cuando se añade/quita una paymentline
                    if (mutation.target.classList && mutation.target.classList.contains('paymentline')) {
                        hasPaymentChanges = true;
                        break;
                    }
                }
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    // Detectar cuando una paymentline se vuelve selected
                    if (mutation.target.classList && mutation.target.classList.contains('paymentline')) {
                        hasPaymentChanges = true;
                        break;
                    }
                }
            }

            if (hasPaymentChanges) {
                // Evitar llamadas repetidas con debounce
                if (timeoutId) clearTimeout(timeoutId);
                timeoutId = setTimeout(() => {
                    showTRMQrCode(document, ctx);
                }, 50); // Delay muy corto para respuesta inmediata
            }
        });
        obs.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['class'],
            characterData: true
        });
        window.__POS_TRM_QR_OBS__ = obs;
    } catch (e) {
        console.error("[asi_pos_options] Error al iniciar observer de QR TRM:", e);
    }
}

async function runTRMQrInit(ctx) {
    try {
        const enabled = !!(ctx && ctx.config && ctx.config.show_trm_qr_in_pos);
        if (!enabled) return;

        await domReady();

        // Ejecutar inmediatamente y luego iniciar observer
        showTRMQrCode(document, ctx);
        startTRMQrObserver(ctx);
    } catch (e) {
        console.error("[asi_pos_options] Error en inicialización de QR TRM:", e);
    }
}

patch(PosGlobalState.prototype, "asi_pos_options.show_trm_qr_in_pos", {
    async loadServerData(...args) {
        const out = await this._super?.(...args);
        // Esperar un poco más para que el POS esté completamente inicializado
        setTimeout(() => runTRMQrInit(this), 1000);
        return out;
    },
    async _processData(...args) {
        const out = await this._super?.(...args);
        // Esperar un poco más para que el POS esté completamente inicializado
        setTimeout(() => runTRMQrInit(this), 1000);
        return out;
    },
});