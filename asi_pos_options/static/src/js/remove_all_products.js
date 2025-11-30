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

function toggleButton(button) {
    const order = document.querySelector('.order');
    const hasProducts = order && order.querySelector('.orderlines') !== null;
    console.log('[asi_pos_options] toggleButton: hasProducts =', hasProducts);
    if (hasProducts) {
        button.style.opacity = '1';
        button.style.pointerEvents = '';
        button.style.minHeight = '40px';
    } else {
        button.style.opacity = '0.5';
        button.style.pointerEvents = 'none';
        button.style.minHeight = '40px';
    }
}

function addRemoveAllButton(root = document, ctx = null) {
    console.log('[asi_pos_options] addRemoveAllButton called');
    const controlButtons = root.querySelector('.control-buttons');
    if (!controlButtons) return false;

    // Verificar si ya existe el botón
    if (controlButtons.querySelector('.remove-all-control')) return true;

    // Crear el botón como control-button
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'control-button remove-all-control';
    buttonContainer.innerHTML = `
        <i class="fa fa-trash"></i> <span>Limpiar productos</span>
    `;

    // Insertar en control-buttons
    controlButtons.appendChild(buttonContainer);

    // Agregar evento
    buttonContainer.ctx = ctx;  // Guardar ctx en el contenedor
    buttonContainer.addEventListener('click', () => {
        console.log('[asi_pos_options] Remove all button clicked');
        const pos = buttonContainer.ctx;
        if (!pos) {
            console.warn('[asi_pos_options] No pos found');
            return;
        }
        const order = pos.get_order();
        if (!order) {
            console.warn('[asi_pos_options] No order found');
            return;
        }
        console.log('[asi_pos_options] Removing', order.orderlines.length, 'lines');
        while (order.orderlines.length > 0) {
            order.remove_orderline(order.orderlines[0]);
        }
        console.log('[asi_pos_options] All lines removed');
        // Toggle visibility after removal
        toggleButton(buttonContainer);
    });

    // Toggle initial visibility
    toggleButton(buttonContainer);

    return true;
}

function startRemoveAllObserver(ctx) {
    console.log('[asi_pos_options] startRemoveAllObserver called');
    if (window.__POS_REMOVE_ALL_OBS__) return;
    try {
        const obs = new MutationObserver(() => {
            console.log('[asi_pos_options] Observer callback triggered');
            addRemoveAllButton(document, ctx);
            // Toggle button visibility on any DOM change
            const button = document.querySelector('.remove-all-control');
            if (button) {
                toggleButton(button);
            }
            // Setup orderlines observer if not already
            if (!window.__POS_REMOVE_ALL_ORDERLINES_OBS__) {
                const orderlines = document.querySelector('.orderlines');
                if (orderlines) {
                    const orderlinesObs = new MutationObserver(() => {
                        console.log('[asi_pos_options] Orderlines observer callback triggered');
                        const button2 = document.querySelector('.remove-all-control');
                        if (button2) {
                            toggleButton(button2);
                        }
                    });
                    orderlinesObs.observe(orderlines, { childList: true });
                    window.__POS_REMOVE_ALL_ORDERLINES_OBS__ = orderlinesObs;
                }
            }
        });
        obs.observe(document.body, { childList: true, subtree: true });
        window.__POS_REMOVE_ALL_OBS__ = obs;
    } catch (_) {}
}

async function runRemoveAllInit(ctx) {
    console.log('[asi_pos_options] runRemoveAllInit called');
    try {
        await domReady();

        addRemoveAllButton(document, ctx);
        startRemoveAllObserver(ctx);
    } catch (e) {
        console.warn("[asi_pos_options] init remove all failed:", e);
    }
}

patch(PosGlobalState.prototype, "asi_pos_options.remove_all_products", {
    async loadServerData(...args) {
        const out = await this._super?.(...args);
        setTimeout(() => runRemoveAllInit(this), 200);
        return out;
    },
    async _processData(...args) {
        const out = await this._super?.(...args);
        setTimeout(() => runRemoveAllInit(this), 200);
        return out;
    },
});