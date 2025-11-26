/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosGlobalState } from "point_of_sale.models";
import { _t } from "@web/core/l10n/translation";
// Funciones auxiliares para persistencia de datos de denominaciones
/**
 * Captura los datos de denominaciones desde el popup de la calculadora
 * @param {Element} calcPopup - Popup de la calculadora de denominaciones
 * @returns {Object} Datos de denominaciones en formato estructurado
 */
function captureDenominationData(calcPopup) {
    const denominationData = {
        denominations: [],
        total: 0,
        timestamp: new Date().toISOString(),
        currency: 'CUP'  // Por defecto CUP, se puede hacer dinámico
    };

    console.debug("[asi_pos_options] Iniciando captura de datos de denominaciones (cierre)");

    try {
        // Buscar todos los inputs de denominaciones (estructura específica del HTML proporcionado)
        const denominationInputs = calcPopup.querySelectorAll('.money-details-value input[type="number"]');

        console.debug(`[asi_pos_options] Encontrados ${denominationInputs.length} inputs de denominaciones`);

        denominationInputs.forEach((input, index) => {
            // El valor de la denominación está en el ID del input
            const value = parseFloat(input.id);
            // La cantidad está en el valor del input
            const count = parseInt(input.value || '0');

            console.debug(`[asi_pos_options] Procesando input ${index}: id=${input.id}, value=${value}, count=${count}`);

            if (!isNaN(value) && !isNaN(count) && value > 0 && count > 0) {
                const subtotal = value * count;
                denominationData.denominations.push({
                    value: value,
                    count: count,
                    subtotal: subtotal
                });
                denominationData.total += subtotal;
                console.debug(`[asi_pos_options] Denominación agregada:`, {value, count, subtotal});
            }
        });

        // Si no encontramos denominaciones específicas, intentar extraer del total mostrado
        if (denominationData.denominations.length === 0) {
            console.debug("[asi_pos_options] No se encontraron denominaciones específicas, buscando total alternativo");

            // Buscar el total en la sección de total
            const totalLabel = calcPopup.querySelector('.total-section label');
            if (totalLabel) {
                const totalText = totalLabel.textContent || '';
                const totalMatch = totalText.match(/(\d+(?:[.,]\d{1,2})?)/);
                if (totalMatch) {
                    const extractedTotal = parseFloat(totalMatch[1].replace(',', '.'));
                    if (!isNaN(extractedTotal) && extractedTotal > 0) {
                        denominationData.total = extractedTotal;
                        // Crear una denominación genérica si no tenemos detalles
                        denominationData.denominations.push({
                            value: extractedTotal,
                            count: 1,
                            subtotal: extractedTotal
                        });
                        console.debug(`[asi_pos_options] Total extraído del label: ${extractedTotal}`);
                    }
                }
            }
        }

        console.debug(`[asi_pos_options] Captura completada (cierre). Total denominaciones: ${denominationData.denominations.length}, Total: ${denominationData.total}`);

    } catch (error) {
        console.error("[asi_pos_options] Error capturando datos de denominaciones (cierre):", error);
    }

    return denominationData;
}

/**
 * Envía los datos de control de denominaciones al servidor via RPC
 * @param {Object} pos - Instancia del POS
 * @param {string} controlType - Tipo de control ('opening' o 'closing')
 * @param {number} totalAmount - Total contado
 * @param {Object} denominationData - Datos detallados de denominaciones
 * @returns {Promise} Resultado del RPC
 */
async function saveDenominationControlToServer(posContext, controlType, totalAmount, denominationData) {
    try {
        // Verificar que tenemos acceso al contexto POS
        if (!posContext || !posContext.pos_session) {
            console.warn("[asi_pos_options] No hay contexto POS disponible");
            return;
        }

        const sessionId = posContext.pos_session.id;

        // Realizar RPC al servidor
        const result = await posContext.env.services.rpc({
            model: 'pos.session',
            method: 'save_denomination_control_from_ui',
            args: [sessionId, controlType, totalAmount, denominationData],
        });

        if (result && result.success) {
            console.log(`[asi_pos_options] Control de ${controlType} guardado exitosamente:`, result);
        } else {
            console.warn(`[asi_pos_options] Error en respuesta del servidor para control de ${controlType}:`, result);
        }

        return result;

    } catch (error) {
        console.error(`[asi_pos_options] Error enviando control de ${controlType} al servidor:`, error);
        throw error;
    }
}

let observerStartedClosing = false;
let closingFlowArmed = false; // se arma SOLO cuando se hace click en Cerrar
let posContext = null; // Guardar referencia al contexto POS

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

    // Verificar si es un elemento HTML
    if (!(node instanceof Element)) return false;

    const txt = (node.textContent || "").toLowerCase();
    const className = (node.className || "").toLowerCase();

    // Patrones más específicos para detectar popup de denominaciones
    const denominationPatterns = [
        /monedas|billetes|denominaciones|coins|bills|denominations|detalles monetarios/,
        /cash.*details|money.*details|denomination.*calculator/,
        /contar.*efectivo|count.*cash|cash.*counting/
    ];

    const hasDenominationText = denominationPatterns.some(pattern => pattern.test(txt));
    const hasRelevantClass = /popup|modal|dialog/.test(className) && !/close-pos-popup/.test(className);

    console.debug("[asi_pos_options] Verificando popup:", {
        text: txt.substring(0, 100) + "...",
        className: className,
        hasDenominationText: hasDenominationText,
        hasRelevantClass: hasRelevantClass
    });

    return hasDenominationText && hasRelevantClass;
}

/**
 * Versión mejorada de wireCalculatorToClosingPopup que incluye persistencia de datos
 * Reemplaza la funcionalidad original agregando captura y envío de datos de denominaciones
 */
function wireCalculatorToClosingPopupWithPersistence() {
    const closingPopup = getClosingPopup();
    if (!closingPopup) {
        console.debug("[asi_pos_options] No se encontró popup de cierre");
        return;
    }

    // Buscar un posible popup de Money Details activo
    const dialogs = Array.from(document.querySelectorAll('.modal-dialog .popup'));
    console.debug(`[asi_pos_options] Encontrados ${dialogs.length} popups`);

    const calcPopup = dialogs.find((p) => p !== closingPopup && isMoneyDetailsPopup(p));
    if (!calcPopup) {
        console.debug("[asi_pos_options] No se encontró popup de calculadora de denominaciones");
        return;
    }

    if (calcPopup.dataset._wiredClosingPersistent === "1") {
        console.debug("[asi_pos_options] Popup ya está cableado");
        return;
    }

    calcPopup.dataset._wiredClosingPersistent = "1";
    console.debug("[asi_pos_options] Cableando popup de calculadora de denominaciones");

    // Confirmación del conteo: probamos con botones que tengan texto confirm-ish
    const allButtons = Array.from(calcPopup.querySelectorAll('button, .button, [role="button"], .footer .button'));
    console.debug(`[asi_pos_options] Encontrados ${allButtons.length} botones en popup de calculadora`);

    const calcConfirm = allButtons.find((b) => {
        const text = (b.textContent || "").toLowerCase().trim();
        const matches = /confirmar|aceptar|ok|confirm/i.test(text);
        console.debug(`[asi_pos_options] Verificando botón: "${text}" - matches: ${matches}`);
        return matches;
    });

    if (!calcConfirm) {
        console.debug("[asi_pos_options] No se encontró botón de confirmación");
        return;
    }

    console.debug("[asi_pos_options] Agregando listener al botón de confirmación");

    calcConfirm.addEventListener('click', async () => {
        console.debug("[asi_pos_options] ¡Botón de confirmación clickeado!");

        // Capturar datos de denominaciones del popup
        const denominationData = captureDenominationData(calcPopup);
        console.debug("[asi_pos_options] Datos de denominaciones capturados:", denominationData);

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

        // Usar el total calculado de los datos de denominaciones si está disponible
        if (denominationData && denominationData.total > 0) {
            total = denominationData.total;
            console.debug(`[asi_pos_options] Usando total de denominaciones: ${total}`);
        } else {
            console.debug(`[asi_pos_options] Usando total extraído del DOM: ${total}`);
        }

        // 2) NO setear input para no interferir en contabilidad - solo registrar denominaciones

        // 3) habilitar cierre
        const confirmBtn = getConfirmCloseButton(closingPopup);
        if (confirmBtn) {
            confirmBtn.classList.remove('o_disabled');
            confirmBtn.removeAttribute('aria-disabled');
            delete confirmBtn.dataset._needsDenomClosing;
            console.debug("[asi_pos_options] Botón de cierre habilitado");
        }

        // Enviar datos al servidor si tenemos contexto POS y total válido
        if (posContext && total > 0) {
            console.debug("[asi_pos_options] Enviando datos al servidor...");
            try {
                const result = await saveDenominationControlToServer(posContext, 'closing', total, denominationData);
                console.debug("[asi_pos_options] Control de cierre guardado correctamente:", result);
            } catch (error) {
                console.error("[asi_pos_options] Error guardando control de cierre:", error);
                // Mostrar notificación de error al usuario si es posible
                if (posContext?.showNotification) {
                    posContext.showNotification(
                        _t("Error guardando control de cierre de caja"),
                        { type: 'danger' }
                    );
                }
            }
        } else {
            console.warn("[asi_pos_options] No se puede enviar datos: pos =", !!posContext, "total =", total);
        }
    }, { once: true });
}


// Arranca el observer SOLO cuando el usuario pulsa el botón de cerrar sesión en la vista principal.
function startClosingObserver() {
    if (observerStartedClosing) return;
    observerStartedClosing = true;

    console.debug("[asi_pos_options] Iniciando observer de cierre de caja");

    const obs = new MutationObserver(() => {
        // Ejecutar en cada cambio del DOM para asegurar que se detecten los popups
        const closingPopup = getClosingPopup();
        if (closingPopup) {
            console.debug("[asi_pos_options] Encontrado popup de cierre, aplicando lógica");
            disableManualInputAndAutoOpenCalculator_Closing(closingPopup);
        }
        // Usar la función mejorada con persistencia de datos
        wireCalculatorToClosingPopupWithPersistence();
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

patch(PosGlobalState.prototype, "asi_pos_options.force_closing_by_denominations_dom_specific", {
    async loadServerData(...args) {
        const out = await this._super?.(...args);
        // Guardar referencia al contexto POS
        posContext = this;
        console.debug("[asi_pos_options] Contexto POS guardado en loadServerData");
        // NO iniciamos el observer en boot; solo armamos el listener de "Cerrar"
        armOnCloseButtonClick();
        return out;
    },
    async _processData(...args) {
        const out = await this._super?.(...args);
        // Guardar referencia al contexto POS
        posContext = this;
        console.debug("[asi_pos_options] Contexto POS guardado en _processData");
        armOnCloseButtonClick();
        return out;
    },
});
