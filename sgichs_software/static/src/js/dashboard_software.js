/**
 * addons/sgichs_software/static/src/js/dashboard_software.js
 *
 * Extiende el dashboard base para renderizar gráficas de software.
 * - Reutiliza _renderCharts del core, luego añade sus propias gráficas.
 * - Robusto ante ausencia de Chart.js o de datos incompletos.
 */

odoo.define('sgichs_software.dashboard_software', function (require) {
    "use strict";

    var ITDashboard = require('sgichs_core2.dashboard');

    ITDashboard.include({
        _renderCharts: function () {
            this._super.apply(this, arguments);

            var self = this;
            self.charts = self.charts || {};
            self.dashboard_data = self.dashboard_data || {};
            self.dashboard_data.charts = self.dashboard_data.charts || {};

            if (typeof Chart === 'undefined') {
                console.warn('sgichs_software: Chart.js no disponible');
                return;
            }

            var colorsMain = ['#20c997', '#0dcaf0', '#6f42c1', '#fd7e14', '#e83e8c', '#17a2b8'];
            var colorsAlt = ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b', '#858796'];

            var destroyChart = function (chartInstance) {
                try { chartInstance && chartInstance.destroy && chartInstance.destroy(); } catch (e) {}
            };

            // Software por Subtipo (doughnut)
            try {
                var subCanvasEl = self.$('#softwareSubtypeChart')[0];
                var subCtx = subCanvasEl ? subCanvasEl.getContext('2d') : null;
                var subData = self.dashboard_data.charts.software_subtype;

                if (subCtx && subData && Array.isArray(subData.labels) && Array.isArray(subData.data)) {
                    var values = subData.data.map(function (v) {
                        var n = typeof v === 'string' ? parseFloat(v) : v;
                        return isNaN(n) ? 0 : n;
                    });
                    destroyChart(self.charts.softwareSubtype);
                    self.charts.softwareSubtype = new Chart(subCtx, {
                        type: 'doughnut',
                        data: { labels: subData.labels, datasets: [{ data: values, backgroundColor: colorsMain }] },
                        options: { responsive: true, maintainAspectRatio: false, legend: { position: 'right' }, plugins: { legend: { position: 'right' } } }
                    });
                }
            } catch (e) { console.error('sgichs_software: error gráfico subtipo', e); }

            // Software por SO (bar)
            try {
                var osCanvasEl = self.$('#softwareOsChart')[0];
                var osCtx = osCanvasEl ? osCanvasEl.getContext('2d') : null;
                var osData = self.dashboard_data.charts.software_os;

                if (osCtx && osData && Array.isArray(osData.labels) && Array.isArray(osData.data)) {
                    var values2 = osData.data.map(function (v) {
                        var n = typeof v === 'string' ? parseFloat(v) : v;
                        return isNaN(n) ? 0 : n;
                    });
                    destroyChart(self.charts.softwareOS);
                    self.charts.softwareOS = new Chart(osCtx, {
                        type: 'bar',
                        data: { labels: osData.labels, datasets: [{ label: 'Software', data: values2, backgroundColor: colorsAlt }] },
                        options: { responsive: true, maintainAspectRatio: false, legend: { display: false }, plugins: { legend: { display: false } },
                            scales: { yAxes: [{ ticks: { beginAtZero: true, stepSize: 1 } }] } }
                    });
                }
            } catch (e) { console.error('sgichs_software: error gráfico SO', e); }

            console.debug('sgichs_software: charts renderizados (si hay datos).');
        },
    });
});