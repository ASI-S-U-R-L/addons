/**
 * addons/sgichs_hardware/static/src/js/dashboard_hardware.js
 *
 * Este módulo extiende el dashboard base (sgichs_core2.dashboard) para
 * renderizar gráficos específicos del módulo de hardware. La estrategia es:
 * 1) Llamar primero al _renderCharts del core para no romper su lógica.
 * 2) Renderizar los gráficos propios usando los datos inyectados desde el backend
 *    en dashboard_data.charts.asset_type y dashboard_data.charts.component_subtype.
 *
 * Notas importantes:
 * - Usamos el nodo DOM del canvas (self.$('#id')[0]) en lugar del objeto jQuery,
 *   ya que Chart.js requiere el canvas o su contexto.
 * - Destruimos instancias previas de gráficos para evitar fugas de memoria o dobles gráficos
 *   cuando el dashboard se re-renderiza (por ejemplo, al pulsar "Actualizar").
 * - Blindamos el código contra la falta de Chart.js o datos incompletos para evitar que
 *   un error en hardware rompa el dashboard completo.
 */

odoo.define('sgichs_hardware.dashboard_hardware', function (require) {
    "use strict";

    // Importamos la clase de acción del dashboard base para poder extenderla.
    var ITDashboard = require('sgichs_core2.dashboard');

    ITDashboard.include({
        /**
         * Sobrescribimos el método de renderizado de gráficos del dashboard base.
         * - Primero llamamos al super para que se dibujen los gráficos del core.
         * - Luego añadimos los gráficos específicos de hardware.
         */
        _renderCharts: function () {
            // 1) Renderiza primero los gráficos del core (incidentes, etc.)
            this._super.apply(this, arguments);

            var self = this;

            // Aseguramos que las estructuras existen (defensa ante inicializaciones parciales)
            self.charts = self.charts || {};
            self.dashboard_data = self.dashboard_data || {};
            self.dashboard_data.charts = self.dashboard_data.charts || {};

            // Si Chart.js no está disponible por alguna razón, no rompemos el flujo.
            if (typeof Chart === 'undefined') {
                console.warn('sgichs_hardware: Chart.js no está disponible; se omite el renderizado de gráficos de hardware.');
                return;
            }

            // Paleta de colores (consistente y suficiente para 5 segmentos).
            var odooColors = ['#667eea', '#764ba2', '#56ab2f', '#ff4b2b', '#f5576c'];

            /**
             * Utilidad: destruye una instancia previa de Chart de forma segura.
             * Evita memoria residual y gráficos duplicados después de re-renderizar el DOM.
             */
            var destroyChart = function (chartInstance) {
                try {
                    if (chartInstance && typeof chartInstance.destroy === 'function') {
                        chartInstance.destroy();
                    }
                } catch (e) {
                    console.warn('sgichs_hardware: error al destruir instancia de Chart', e);
                }
            };

            // ==============================
            // Gráfico: Activos de Hardware por Tipo (doughnut)
            // ==============================
            try {
                var assetCanvasEl = self.$('#assetTypeChart')[0];
                var assetCtx = assetCanvasEl ? assetCanvasEl.getContext('2d') : null;
                var assetData = self.dashboard_data.charts.asset_type;

                if (assetCtx && assetData && Array.isArray(assetData.labels) && Array.isArray(assetData.data)) {
                    // Forzar valores numéricos por si vienen como string
                    var values = assetData.data.map(function (v) {
                        var n = typeof v === 'string' ? parseFloat(v) : v;
                        return isNaN(n) ? 0 : n;
                    });

                    // Destruir gráfico previo si existía
                    destroyChart(self.charts.assetType);

                    self.charts.assetType = new Chart(assetCtx, {
                        type: 'doughnut',
                        data: {
                            labels: assetData.labels,
                            datasets: [{
                                data: values,
                                backgroundColor: odooColors
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            // Compatibilidad v2 y v3
                            legend: { position: 'right' },
                            plugins: { legend: { position: 'right' } },
                            animation: { animateRotate: true, animateScale: true },
                            tooltips: {
                                callbacks: {
                                    label: function (tooltipItem, data) {
                                        var idx = tooltipItem.index;
                                        var label = data.labels[idx] || '';
                                        var value = data.datasets[0].data[idx] || 0;
                                        return label + ': ' + value;
                                    }
                                }
                            }
                        }
                    });

                    // Log de depuración
                    console.debug('HW Chart - asset_type labels:', assetData.labels, 'data:', values);
                }
            } catch (e) {
                console.error('sgichs_hardware: Error creando gráfico de activos por tipo:', e);
            }

            // ==============================
            // Gráfico: Componentes por Subtipo (pie)
            // ==============================
            try {
                var componentCanvasEl = self.$('#componentSubtypeChart')[0];
                var componentCtx = componentCanvasEl ? componentCanvasEl.getContext('2d') : null;
                var compData = self.dashboard_data.charts.component_subtype;

                if (componentCtx && compData && Array.isArray(compData.labels) && Array.isArray(compData.data)) {
                    var values2 = compData.data.map(function (v) {
                        var n = typeof v === 'string' ? parseFloat(v) : v;
                        return isNaN(n) ? 0 : n;
                    });

                    destroyChart(self.charts.componentSubtype);

                    self.charts.componentSubtype = new Chart(componentCtx, {
                        type: 'pie',
                        data: {
                            labels: compData.labels,
                            datasets: [{
                                data: values2,
                                backgroundColor: odooColors.slice().reverse()
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            legend: { position: 'right' },
                            plugins: { legend: { position: 'right' } },
                            tooltips: {
                                callbacks: {
                                    label: function (tooltipItem, data) {
                                        var idx = tooltipItem.index;
                                        var label = data.labels[idx] || '';
                                        var value = data.datasets[0].data[idx] || 0;
                                        return label + ': ' + value;
                                    }
                                }
                            }
                        }
                    });

                    console.debug('HW Chart - component_subtype labels:', compData.labels, 'data:', values2);
                }
            } catch (e) {
                console.error('sgichs_hardware: Error creando gráfico de componentes por subtipo:', e);
            }                                                                                                                                                                                                                           

            // Nota: Si no se ven datos en los gráficos (quedan en 0),
            // revisa la llamada RPC y el log del servidor:
            // - Network → /web/dataset/call_kw/it.dashboard/get_dashboard_data
            // - Log de Odoo → traceback de Python en el método heredado de hardware
        },
    });
});