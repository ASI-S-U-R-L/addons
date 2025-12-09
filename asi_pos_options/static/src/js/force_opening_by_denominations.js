/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosGlobalState } from "point_of_sale.models";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

let observerStarted = false;
let posContextOpening = null; // Guardar referencia al contexto POS

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

    console.debug("[asi_pos_options] Iniciando captura de datos de denominaciones (apertura)");

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

        console.debug(`[asi_pos_options] Captura completada (apertura). Total denominaciones: ${denominationData.denominations.length}, Total: ${denominationData.total}`);

    } catch (error) {
        console.error("[asi_pos_options] Error capturando datos de denominaciones (apertura):", error);
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
async function saveDenominationControlToServer(posContextOpening, controlType, totalAmount, denominationData) {
    try {
         console.warn("[posContextOpening] ",posContextOpening);
        // Verificar que tenemos acceso al contexto POS
        if (!posContextOpening || !posContextOpening.pos_session) {
            console.warn("[asi_pos_options] No hay contexto POS disponible");
            return;
        }

        const sessionId = posContextOpening.pos_session.id;

        // Realizar RPC al servidor
        // Usar el servicio RPC del entorno
        const result = await posContextOpening.env.services.rpc({
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
        // NO actualizar input para no interferir en contabilidad
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
             wireCalculatorToOpeningPopupWithPersistence();
        }
        // Usar la función mejorada con persistencia de datos
       
    });
    obs.observe(document.body, { childList: true, subtree: true });
}

patch(PosGlobalState.prototype, "asi_pos_options.force_opening_by_denominations", {
    async loadServerData(...args) {
        const out = await this._super?.(...args);
        // Guardar referencia al contexto POS
        posContextOpening = this;
        console.log("[asi_pos_options] Contexto POS guardado en loadServerData (apertura)");
        bootObserverIfNeeded(this);
        return out;
    },
    async _processData(...args) {
        const out = await this._super?.(...args);
        // Guardar referencia al contexto POS
        posContextOpening = this;
        console.log("[asi_pos_options] Contexto POS guardado en _processData (apertura)");
        bootObserverIfNeeded(this);
        return out;
    },
});
/**
 * Versión mejorada de wireCalculatorToOpeningPopup que incluye persistencia de datos
 * Reemplaza la funcionalidad original agregando captura y envío de datos de denominaciones
 */
function wireCalculatorToOpeningPopupWithPersistence() {
    const openingPopup = findPopupRootByTitle(i18nIncludes);
    const calcPopup = openingPopup.querySelector('.popup.money-details');;
    console.log("[openingPopup] ", openingPopup);
    console.log("[calcPopup] ", calcPopup);
    if (!openingPopup || !calcPopup) {
        console.log("[asi_pos_options] No se encontraron popups de apertura o calculadora");
        return;
    }

    if (calcPopup.dataset._wiredPersistent === "1") {
        console.log("[asi_pos_options] Popup de calculadora ya está cableado");
        return;
    }
    calcPopup.dataset._wiredPersistent = "1";

    console.log("[asi_pos_options] Cableando popup de calculadora de apertura");

    // Buscar el botón de confirmar en el popup de calculadora
    const calcConfirm = Array.from(calcPopup.querySelectorAll('button, .button, [role="button"]'))
        .find((b) => /confirmar|aceptar|ok|confirm/i.test((b.textContent || "")));

    if (!calcConfirm) {
        console.log("[asi_pos_options] No se encontró botón de confirmar en popup de calculadora");
        return;
    }

    console.log("[asi_pos_options] Agregando listener al botón de confirmar");

    calcConfirm.addEventListener('click', async () => {
        console.log("[asi_pos_options] ¡Botón de confirmar clickeado en apertura!");

        // Capturar datos de denominaciones del popup
        const denominationData = captureDenominationData(calcPopup);
        console.log("[asi_pos_options] Datos de denominaciones capturados:", denominationData);
        const totalLabel = Array.from(calcPopup.querySelectorAll('div, span, p, b, strong'))
            .find((n) => /total/i.test((n.textContent || "")));
        let total = 0;
        if (totalLabel) {
            const text = (totalLabel.textContent || "") + " " + (totalLabel.parentElement?.textContent || "");
            const m = text.replace(/\s/g,'').match(/-?\\d+(?:[.,]\\d{1,2})?/g);
            if (m && m.length) {
                const last = m[m.length - 1].replace(',', '.');
                total = parseFloat(last) || 0;
            }
        }
        
        // Usar el total calculado de los datos de denominaciones si está disponible
        if (denominationData && denominationData.total > 0) {
            total = denominationData.total;
        }
        
        // NO actualizar input para no interferir en contabilidad

        const confirmBtn = Array.from(openingPopup.querySelectorAll('button, .button, [role="button"]'))
            .find((b) => /confirmar|confirm|aceptar/i.test((b.textContent || "")));
        if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.classList.remove('o_disabled');
            delete confirmBtn.dataset._needsDenom;
        }
        
        // Enviar datos al servidor si tenemos contexto POS y total válido
        if (posContextOpening && total > 0) {
            try {
                await saveDenominationControlToServer(posContextOpening, 'opening', total, denominationData);
                console.log("[asi_pos_options] Control de apertura guardado correctamente");
            } catch (error) {
                console.error("[asi_pos_options] Error guardando control de apertura:", error);
                // Mostrar notificación de error al usuario si es posible
                if (posContextOpening?.showNotification) {
                    posContextOpening.showNotification(
                        _t("Error guardando control de apertura de caja"),
                        { type: 'danger' }
                    );
                }
            }
        } else {
            console.warn("[asi_pos_options] No se puede enviar datos de apertura: pos =", !!posContextOpening, "total =", total);
        }
    }, { once: true });
}
