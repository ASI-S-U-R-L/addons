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

    // Verificar el tipo de método de pago
    const paymentName = selectedPaymentLine ? selectedPaymentLine.payment_method.name.toLowerCase() : '';
    const isTransfermovilPagoEnLinea = paymentName.includes('transfermovil pago en linea');
    const isTransfermovil = (paymentName.includes('transfermovil') || paymentName.includes('transferencia')) && !isTransfermovilPagoEnLinea;

    // Verificar si ya existe el QR
    const existingQr = paymentScreen.querySelector('.trm-qr-container');

    if ((isTransfermovilPagoEnLinea || isTransfermovil) && pos.config.show_trm_qr_in_pos) {
        let qrData;
         const phone_extra_val = pos.user.phone_extra || '';
        if (isTransfermovilPagoEnLinea) {
            // QR anterior para Transfermovil Pago en Linea
            qrData = {
                'id_transaccion': "ESTATICO",
                'importe': order.get_total_with_tax(),
                'moneda': pos.currency.display_name || 'CUP',
                'numero_proveedor': phone_extra_val,
                'version': 1,
                'titulo': pos.config.display_name
            };
            qrData = JSON.stringify(qrData);
        } else if (isTransfermovil) {
            // QR del módulo transfermovil_trasnferencia para Transfermovil
            const cc_number = pos.user.credit_card_number || '';
           
            qrData = `TRANSFERMOVIL_ETECSA,TRANSFERENCIA,${cc_number},${phone_extra_val}`;
        }
        const qrUrl = `/report/barcode/?barcode_type=QR&value=${encodeURIComponent(qrData)}&width=150&height=150`;

        if (existingQr) {
            // Si ya existe, verificar si necesita actualizarse
            const img = existingQr.querySelector('img');
            if (img && img.src !== qrUrl) {
                img.src = qrUrl;
                order.trm_qr_code_str = qrData; // Actualizar el string en la orden
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
                    order.trm_qr_code_str = qrData; // Guardar el string en la orden
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
        const result = await this._super(...args);

        // Forzar la carga de campos personalizados del usuario logueado
     

        setTimeout(() => runTRMQrInit(this), 200);
        return result;
    },
    async _processData(...args) {
        const out = await this._super?.(...args);
           console.log("forzando carga");
        if (this.user) {
            const userFields = await this.env.services.rpc({
                model: 'res.users',
                method: 'read',
                args: [[this.user.id], ['credit_card_number', 'phone_extra']],
            });
            if (userFields && userFields.length > 0) {
                const userData = userFields[0];
                this.user.credit_card_number = userData.credit_card_number || '';
                this.user.phone_extra = userData.phone_extra || '';
            }
        }
        setTimeout(() => runTRMQrInit(this), 200);
        return out;
    },
});