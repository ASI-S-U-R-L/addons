/**
 * Extiende el dashboard base para renderizar gráficas de Red.
 * - Usa getContext('2d'), destruye instancias previas y convierte datos a numéricos.
 * - Gráficas:
 *   1) network_connection_status → doughnut
 *   2) network_service_protocol → bar
 */
odoo.define('sgichs_red.dashboard_network', function (require) {
    "use strict";

    var ITDashboard = require('sgichs_core2.dashboard');

    ITDashboard.include({
        _renderCharts: function () {
            // Primero gráficos del core
            this._super.apply(this, arguments);

            var self = this;
            self.charts = self.charts || {};
            self.dashboard_data = self.dashboard_data || {};
            self.dashboard_data.charts = self.dashboard_data.charts || {};

            if (typeof Chart === 'undefined') {
                console.warn('sgichs_red: Chart.js no disponible; se omiten gráficos de red.');
                return;
            }

            var colorsMain = ['#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b', '#858796'];
            var colorsAlt  = ['#667eea', '#28a745', '#17a2b8', '#ffc107', '#dc3545', '#6c757d'];

            var destroyChart = function (inst) {
                try { inst && inst.destroy && inst.destroy(); } catch (e) {}
            };
            var toNumbers = function (arr) {
                return (Array.isArray(arr) ? arr : []).map(function (v) {
                    var n = typeof v === 'string' ? parseFloat(v) : v;
                    return isNaN(n) ? 0 : n;
                });
            };

            // ==============================
            // 1) Hardware por Estado de Conexión (doughnut)
            // ==============================
            try {
                var stEl = self.$('#networkConnectionChart')[0];
                var stCtx = stEl ? stEl.getContext('2d') : null;
                var stData = self.dashboard_data.charts.network_connection_status;

                if (stCtx && stData && Array.isArray(stData.labels) && Array.isArray(stData.data)) {
                    destroyChart(self.charts.networkConnection);
                    self.charts.networkConnection = new Chart(stCtx, {
                        type: 'doughnut',
                        data: {
                            labels: stData.labels,
                            datasets: [{
                                data: toNumbers(stData.data),
                                backgroundColor: colorsAlt
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            legend: { position: 'right' },
                            plugins: { legend: { position: 'right' } },
                            animation: { animateRotate: true, animateScale: true }
                        }
                    });
                }
            } catch (e) {
                console.error('sgichs_red: Error gráfico estado de conexión', e);
            }

            // ==============================
            // 2) Servicios por Protocolo (bar)
            // ==============================
            try {
                var protoEl = self.$('#networkServiceProtocolChart')[0];
                var protoCtx = protoEl ? protoEl.getContext('2d') : null;
                var protoData = self.dashboard_data.charts.network_service_protocol;

                if (protoCtx && protoData && Array.isArray(protoData.labels) && Array.isArray(protoData.data)) {
                    destroyChart(self.charts.networkProtocol);
                    self.charts.networkProtocol = new Chart(protoCtx, {
                        type: 'bar',
                        data: {
                            labels: protoData.labels,
                            datasets: [{
                                label: 'Servicios',
                                data: toNumbers(protoData.data),
                                backgroundColor: colorsMain
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            legend: { display: false },
                            plugins: { legend: { display: false } },
                            scales: { yAxes: [{ ticks: { beginAtZero: true, stepSize: 1 } }] }
                        }
                    });
                }
            } catch (e) {
                console.error('sgichs_red: Error gráfico servicios por protocolo', e);
            }
        },
    });
});