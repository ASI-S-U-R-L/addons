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

function hideStockInfo(root = document) {
    let found = false;
    // Selecciona los indicadores de stock (Odoo 16 usa típicamente .product .stock-quantity o similares)
    const stockElements = root.querySelectorAll('.product .stock-quantity, .product [data-stock], .product .oe_pos_stock');
    if (stockElements.length) {
        stockElements.forEach(el => {
            el.style.display = "none";
            el.style.pointerEvents = "none";
            el.setAttribute("data-hidden-stock", "1");
            found = true;
        });
    }
    return found;
}

function showStockInfo(root = document) {
    let found = false;
    // Selecciona los indicadores de stock y restaura su visibilidad
    const stockElements = root.querySelectorAll('.product .stock-quantity, .product [data-stock], .product .oe_pos_stock');
    if (stockElements.length) {
        stockElements.forEach(el => {
            el.style.display = "";
            el.style.pointerEvents = "";
            el.removeAttribute("data-hidden-stock");
            found = true;
        });
    }
    return found;
}

function startStockObserver(ctx) {
    if (window.__POS_STOCK_OBS__) return;
    try {
        const enabled = !!(ctx && ctx.config && ctx.config.show_product_stock);
        const obs = new MutationObserver(() => {
            if (enabled) {
                showStockInfo(document);
            } else {
                hideStockInfo(document);
            }
        });
        obs.observe(document.body, { childList: true, subtree: true });
        window.__POS_STOCK_OBS__ = obs;
    } catch (_) {}
}

async function runStockInit(ctx) {
    try {
        const enabled = !!(ctx && ctx.config && ctx.config.show_product_stock);
        await domReady();
        
        let found = false;
        for (let i = 0; i < 60; i++) { 
            if (enabled) {
                found = showStockInfo(document) || found;
            } else {
                found = hideStockInfo(document) || found;
            }
            await new Promise(r => setTimeout(r, 100));
        }
        startStockObserver(ctx);
        if (!found) console.warn("[asi_pos_options] No se encontraron indicadores de stock; observer activo.");
    } catch (e) {
        console.warn("[asi_pos_options] post-init stock handling failed:", e);
    }
}

patch(PosGlobalState.prototype, "asi_pos_options.show_product_stock", {
    async loadServerData(...args) {
        const out = await this._super?.(...args);
        runStockInit(this);
        return out;
    },
    async _processData(...args) {
        const out = await this._super?.(...args);
        runStockInit(this);
        return out;
    },
});