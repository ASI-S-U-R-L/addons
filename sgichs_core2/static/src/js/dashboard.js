odoo.define('sgichs_core2.dashboard', function (require) {
    "use strict";

    /**
     * Esto define la lógica del dashboard. Este componente se encarga de:
     * 1. Definir la acción de cliente 'sgichs_core2.dashboard'.
     * 2. Heredar de AbstractAction para crear una nueva vista.
     * 3. Utilizar el servicio RPC para llamar al método 'get_dashboard_data' del backend.
     * 4. Almacenar los datos y, una vez que el DOM está listo, renderizar los gráficos
     * utilizando la librería Chart.js.
     * 5. Definir manejadores de eventos para la interactividad del dashboard (clics en tarjetas, etc.).
     */

    var AbstractAction = require('web.AbstractAction');
    var core = require('web.core');
    var rpc = require('web.rpc');

    var ITDashboard = AbstractAction.extend({
        template: 'sgichs_core2.Dashboard',

        events: {
            // Esto define aquí los selectores y los métodos que se ejecutarán.
            'click .kpi-card': '_onKpiCardClick',
            'click .list-group-item-action': '_onListItemClick',
            'click #refresh_dashboard': '_onRefreshDashboard',

            // Habilita/desambigua el scroll con la rueda del mouse dentro del dashboard.
            // En teoría el CSS es suficiente, pero este handler asegura el comportamiento
            // incluso si algún otro estilo o widget interfiere.
            'wheel .o-dashboard-scroll': '_onWheelScroll',
        },

        init: function (parent, context) {
            this._super.apply(this, arguments);
            // Se inicializan los datos del dashboard para evitar errores antes de la carga.
            this.dashboard_data = {
                kpis: {},
                charts: {},
                lists: {
                        recent_high_incidents: [], // <- evita .length de undefined
}
            };
            this.charts = {}; // Objeto para mantener las instancias de los gráficos.
        },

        /**
         * El método willStart se ejecuta antes de que se renderice el template.
         * Es el lugar ideal para cargar los datos asíncronos.
         */
        willStart: function () {
            var self = this;
            return this._super().then(function () {
                return self._loadDashboardData();
            });
        },

        /**
         * El método start se ejecuta después de que el template se ha renderizado en el DOM.
         * Es el lugar perfecto para inicializar librerías JS como Chart.js que necesitan
         * acceder a los elementos del DOM (ej. el <canvas>).
         */
        start: function() {
            var self = this;
            return this._super().then(function() {
                self._renderCharts();
            });
        },

        // --- Métodos de Carga y Renderizado ---

        _loadDashboardData: function () {
            var self = this;
            
            // Se realiza la llamada RPC al modelo 'it.dashboard' y al método 'get_dashboard_data'.
            return rpc.query({
                model: 'it.dashboard',
                method: 'get_dashboard_data',
            }).then(function (result) {
                if (result) {
                    self.dashboard_data = result;
                    self.dashboard_data.kpis = self.dashboard_data.kpis || {};
                    self.dashboard_data.charts = self.dashboard_data.charts || {};
                    self.dashboard_data.lists = self.dashboard_data.lists || {};
                    self.dashboard_data.lists.recent_high_incidents = self.dashboard_data.lists.recent_high_incidents || [];
                }
            }).catch(function(error) {
                console.error("Dashboard: Error al cargar datos:", error);
            });
        },

        _renderCharts: function() {
            var self = this;
            // Colores estándar de Odoo para mantener la consistencia visual.
            const odooColors = ['#dc3545', '#ffc107', '#17a2b8', '#6c757d'];

            // Gráfico de Incidentes por Severidad (el único gráfico del dashboard base).
            var incidentCtx = self.$('#incidentSeverityChart');
            if (incidentCtx.length && self.dashboard_data.charts.incident_severity) {
                try {
                    // Esto se asegura de destruir gráficos anteriores para evitar fugas de memoria.
                    if (self.charts.incidentSeverity) {
                        self.charts.incidentSeverity.destroy();
                    }
                    self.charts.incidentSeverity = new Chart(incidentCtx, {
                        type: 'bar',
                        data: {
                            labels: self.dashboard_data.charts.incident_severity.labels,
                            datasets: [{ 
                                label: 'Incidentes Abiertos', 
                                data: self.dashboard_data.charts.incident_severity.data, 
                                backgroundColor: odooColors,
                            }]
                        },
                        options: { 
                            responsive: true, 
                            maintainAspectRatio: false, 
                            legend: { display: false }, 
                            scales: { 
                                yAxes: [{ ticks: { beginAtZero: true, stepSize: 1 } }] 
                            } 
                        }
                    });
                } catch (e) {
                    console.error("Error creando gráfico de incidentes:", e);
                }
            }
        },

        // --- Manejadores de Eventos ---

        /**
         * Al hacer clic en una tarjeta KPI, se ejecuta una acción de Odoo para abrir
         * la vista de lista del modelo correspondiente, aplicando el dominio definido
         * en el atributo 'data-domain' de la tarjeta.
         */
        _onKpiCardClick: function(ev) {
            var $card = $(ev.currentTarget);
            // Si la tarjeta no tiene un modelo definido, no se hace nada.
            if (!$card.data('model')) return;

            this.do_action({
                name: $card.find('.kpi-title').text(),
                type: 'ir.actions.act_window',
                res_model: $card.data('model'),
                views: [[false, 'list'], [false, 'form']],
                domain: $card.data('domain') || [],
                target: 'current',
            });
        },

        /**
         * Al hacer clic en un elemento de una lista, se abre la vista de formulario
         * del registro correspondiente.
         */
        _onListItemClick: function(ev) {
            ev.preventDefault();
            var $item = $(ev.currentTarget);
            this.do_action({
                type: 'ir.actions.act_window',
                res_model: $item.data('model'),
                res_id: $item.data('res-id'),
                views: [[false, 'form']],
                target: 'current',
            });
        },

        _onRefreshDashboard: function() {
            var self = this;
            var $refreshBtn = this.$('#refresh_dashboard');
            $refreshBtn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"/> Actualizando...');

            this._loadDashboardData().then(function() {
                // RenderElement() redibuja todo el template con los nuevos datos.
                self.renderElement(); 
                // Después de redibujar el DOM, se deben volver a renderizar los gráficos.
                self._renderCharts();
            }).finally(function() {
                $refreshBtn.prop('disabled', false).html('<i class="fa fa-refresh mr-1"/> Actualizar');
            });
        },

        _onWheelScroll: function(ev) {
            var container = ev.currentTarget; // .o-dashboard-scroll
            if (!container) return;

            // deltaY > 0 => usuario desplaza hacia abajo; deltaY < 0 => hacia arriba.
            var dy = (ev.originalEvent && typeof ev.originalEvent.deltaY === 'number') ? ev.originalEvent.deltaY : 0;

            var atTop = container.scrollTop === 0;
            var atBottom = Math.ceil(container.scrollTop + container.clientHeight) >= container.scrollHeight;

            // Solo interceptar si no estamos pegados a los extremos (para evitar bloquear el scroll del padre).
            var canScrollDown = dy > 0 && !atBottom;
            var canScrollUp = dy < 0 && !atTop;

            if (canScrollDown || canScrollUp) {
                ev.preventDefault(); // Evita que el scroll “escape” al padre
                container.scrollTop += dy; // Aplica el desplazamiento
            }
        },
    });



    // Se registra la acción de cliente en el registro de acciones de Odoo.
    // El tag 'sgichs_core2.dashboard' debe coincidir con el de la acción XML.
    core.action_registry.add('sgichs_core2.dashboard', ITDashboard);
    return ITDashboard;
});