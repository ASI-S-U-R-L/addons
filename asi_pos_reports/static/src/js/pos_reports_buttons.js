odoo.define('asi_pos_reports.pos_reports_buttons', function (require) {
    'use strict';

    const Registries    = require('point_of_sale.Registries');
    const ProductScreen = require('point_of_sale.ProductScreen');
    const rpc           = require('web.rpc');
    const core          = require('web.core');
    const _t            = core._t;

    const { Component } = owl;

    // Función auxiliar para abrir URLs en nueva pestaña con mejor UX
    function openInNewTab(url, name = '_blank') {
        const newWindow = window.open(url, name);
        if (newWindow) {
            newWindow.focus();
        }
        return !!newWindow;
    }

    // ==== Helpers ====

    async function callPosModel(self, { model, method, args = [], kwargs = {} }) {
        const pos = self?.env?.pos;
        if (pos?.rpc) {
            return pos.rpc({
                model, method, args, kwargs,
                context: pos.session?.user_context || {},
            });
        }
        return rpc.query({
            model, method, args,
            kwargs: { context: pos?.session?.user_context || {}, ...kwargs },
        });
    }


    // Abre acciones en nueva pestaña con mejor UX
    async function openActionAnywhere(self, action) {
    try {
        if (self?.env?.services?.action?.doAction) {
            await self.env.services.action.doAction(action);
            return true;
        }
    } catch (err) {
        console.warn('asi_pos_reports: doAction falló, fallback URL.', err);
    }
    const actId = action?.id || action?.action || action?.action_id;
    const resId = action?.res_id || (Array.isArray(action?.res_ids) ? action.res_ids[0] : undefined);
    const model = action?.res_model || action?.model;
    const viewT = action?.view_type || 'form';

    if (actId) {
        let url = `/web#action=${actId}`;
        if (model) url += `&model=${encodeURIComponent(model)}`;
        if (resId) url += `&id=${resId}`;
        if (viewT) url += `&view_type=${encodeURIComponent(viewT)}`;
        return openInNewTab(url, `wizard_${actId}`);
    }
    if (resId && model) {
        const url = `/web#id=${resId}&model=${encodeURIComponent(model)}&view_type=${encodeURIComponent(viewT)}`;
        return openInNewTab(url, `wizard_${model}_${resId}`);
    }
    return false;
}

    async function runWizardAction(self, methodName, failText) {
        try {
            const sessionId = self?.env?.pos?.pos_session?.id;
            if (!sessionId) throw new Error('No POS session id');

            const action = await callPosModel(self, {
                model: 'pos.session',
                method: methodName,
                args: [sessionId],
            });

            // Log para ver qué devuelve tu método
            console.log('asi_pos_reports: acción recibida ->', action);

            // Validación mínima: debe venir un dict de acción o algo con res_id+res_model
            if (!action || typeof action !== 'object') {
                throw new Error('El método no devolvió una acción válida.');
            }

            // Abrir en nueva pestaña (comportamiento original mejorado)
            const opened = await openActionAnywhere(self, action);
            if (!opened) throw new Error('No se pudo abrir el wizard.');

        } catch (e) {
            console.error(e);
            self?.env?.pos?.showAlert?.({ title: _t('Error'), body: failText });
        }
    }


    // ==== Botones ====
    class MerchandiseReportButton extends Component {
        async onClick() {
            await runWizardAction(
                this,
                'action_merchandise_sales_report',
                _t('No se pudo abrir el wizard de Ventas por Mercancías.')
            );
        }
    }
    MerchandiseReportButton.template = 'asi_pos_reports.MerchandiseReportButton';
    Registries.Component.add(MerchandiseReportButton);

    class ShiftBalanceReportButton extends Component {
        async onClick() {
            await runWizardAction(
                this,
                'action_shift_balance_report',
                _t('No se pudo abrir el wizard de Balance de Turno.')
            );
        }
    }
    ShiftBalanceReportButton.template = 'asi_pos_reports.ShiftBalanceReportButton';
    Registries.Component.add(ShiftBalanceReportButton);

    class InventorySummaryReportButton extends Component {
        async onClick() {
            await runWizardAction(
                this,
                'action_inventory_summary_report',
                _t('No se pudo abrir el wizard de Resumen de Inventario.')
            );
        }
    }
    InventorySummaryReportButton.template = 'asi_pos_reports.InventorySummaryReportButton';
    Registries.Component.add(InventorySummaryReportButton);

    if (ProductScreen?.addControlButton) {
        ProductScreen.addControlButton({ component: MerchandiseReportButton, condition: () => true });
        ProductScreen.addControlButton({ component: ShiftBalanceReportButton, condition: () => true });
        ProductScreen.addControlButton({ component: InventorySummaryReportButton, condition: () => true });
    }

    return { MerchandiseReportButton, ShiftBalanceReportButton, InventorySummaryReportButton };
});
