# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError
from .versat_api_mixin import VersatApiMixin

_logger = logging.getLogger(__name__)


class VersatSolicitud(models.Model, VersatApiMixin):
    _name = 'versat.solicitud'
    _description = 'Solicitud de Licencia Versat'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'fecha desc, id desc'

    name = fields.Char(string='Referencia', readonly=True, default='Nuevo', copy=False)
    tipo = fields.Selection(
        selection=[('actualizacion', 'Actualización')],
        string='Tipo', required=True, default='actualizacion', tracking=True,
    )
    fecha = fields.Date(string='Fecha', required=True, default=fields.Date.today, tracking=True)
    persona_id = fields.Many2one('versat.persona', string='Persona que Solicita', required=True, tracking=True)
    convenio_id = fields.Many2one('versat.convenio', string='Convenio / Cliente Final', required=True, tracking=True)

    usuario_final_id_ext = fields.Char(related='convenio_id.usuario_final_id_ext', string='ID Usuario Final', readonly=True, store=True)
    usuario_final_nombre = fields.Char(related='convenio_id.usuario_final_nombre', string='Usuario Final', readonly=True, store=True)
    # El 'cliente' del POST es el id que devuelve usuario_final, no el id del convenio
    cliente_final_id_ext = fields.Char(related='convenio_id.usuario_final_id_ext', string='ID Cliente (para API)', readonly=True, store=True)

    linea_ids = fields.One2many('versat.solicitud.linea', 'solicitud_id', string='Servicios')

    total_lineas = fields.Integer(string='Total', compute='_compute_totales')
    lineas_enviadas = fields.Integer(string='Enviados', compute='_compute_totales')
    lineas_error = fields.Integer(string='Con Error', compute='_compute_totales')

    no_solicitud = fields.Char(
        string='Nº Solicitud',
        required=True,
        tracking=True,
    )
    problema_reg_anterior = fields.Boolean(
        string='Problema registro anterior',
        default=False,
        tracking=True,
    )
    observaciones = fields.Text(string='Observaciones')
    state = fields.Selection(
        selection=[
            ('borrador', 'Borrador'),
            ('parcial', 'Parcial'),
            ('enviado', 'Enviado'),
            ('error', 'Error'),
        ],
        string='Estado', default='borrador', tracking=True, readonly=True,
    )

    @api.depends('linea_ids.state')
    def _compute_totales(self):
        for rec in self:
            rec.total_lineas = len(rec.linea_ids)
            rec.lineas_enviadas = len(rec.linea_ids.filtered(lambda l: l.state == 'enviado'))
            rec.lineas_error = len(rec.linea_ids.filtered(lambda l: l.state == 'error'))

    @api.model
    def create(self, vals):
        if vals.get('name', 'Nuevo') == 'Nuevo':
            vals['name'] = self.env['ir.sequence'].next_by_code('versat.solicitud') or 'Nuevo'
        return super().create(vals)

    @api.onchange('convenio_id')
    def _onchange_convenio_id(self):
        if not self.convenio_id:
            return

        # 1. Cargar usuario final si no está
        if not self.convenio_id.usuario_final_id_ext:
            try:
                self.convenio_id.action_cargar_usuario_final()
            except Exception as e:
                return {'warning': {'title': 'Advertencia', 'message': f'No se pudo cargar el usuario final: {e}'}}

        # 2. Cargar servicios del convenio
        try:
            data = self._api_get(
                '/api-acceso/solicitud_licencia/servicios_venta/',
                params={'convenio': self.convenio_id.convenio_id}
            )
            servicios_api = data if isinstance(data, list) else data.get('results', [])
        except Exception as e:
            return {'warning': {'title': 'Advertencia', 'message': f'No se pudieron cargar los servicios del convenio: {e}'}}

        # 3. Consultar solicitudes pendientes (otorgada=false) para este cliente
        solicitudes_pendientes = {}  # {servicio_id_ext: no_solicitud}
        try:
            sol_data = self._api_get(
                '/api-acceso/solicitud_licencia/',
                params={'cliente': self.convenio_id.convenio_id, 'page_size': 1000}
            )
            sol_results = sol_data.get('results', [])
            for sol in sol_results:
                if not sol.get('otorgada', True):
                    servicio_ext = sol.get('servicio', '')
                    if servicio_ext:
                        solicitudes_pendientes[servicio_ext] = sol.get('no_solicitud', '')
        except Exception as e:
            _logger.warning("No se pudieron verificar solicitudes pendientes: %s", e)

        # 4. Construir líneas
        lineas = []
        for item in servicios_api:
            servicio_ext_id = item.get('servicio_id')
            if not servicio_ext_id:
                continue
            servicio = self.env['versat.servicio'].search(
                [('servicio_id', '=', servicio_ext_id)], limit=1
            )
            if servicio:
                pendiente = servicio_ext_id in solicitudes_pendientes
                lineas.append((0, 0, {
                    'servicio_id': servicio.id,
                    'clave_registro': '',
                    'state': 'pendiente',
                    'solicitud_pendiente': pendiente,
                    'solicitud_pendiente_no': solicitudes_pendientes.get(servicio_ext_id, ''),
                }))

        if lineas:
            self.linea_ids = [(5, 0, 0)] + lineas
        else:
            return {
                'warning': {
                    'title': 'Sin servicios',
                    'message': 'No se encontraron servicios asociados a este convenio.',
                }
            }

        # 5. Avisar si hay servicios con solicitudes pendientes
        pendientes_count = sum(1 for l in lineas if l[2].get('solicitud_pendiente'))
        if pendientes_count:
            return {
                'warning': {
                    'title': 'Atención: Solicitudes pendientes',
                    'message': f'{pendientes_count} servicio(s) ya tienen una solicitud pendiente (no otorgada) en el sistema. Se muestran marcados en la tabla.',
                }
            }

    def action_enviar(self):
        self.ensure_one()
        if not self.linea_ids:
            raise UserError('Debe agregar al menos un servicio antes de enviar.')
        if not self.convenio_id:
            raise UserError('Debe seleccionar un convenio.')
        if not self.usuario_final_id_ext:
            raise UserError('No se pudo obtener el usuario final del convenio. Use el botón "Cargar Usuario Final" en el convenio.')

        endpoint = f'/api-acceso/solicitud_licencia/servicios_actualizacion/?cliente={self.convenio_id.convenio_id}'
        enviados = 0
        errores = 0

        for linea in self.linea_ids.filtered(lambda l: l.state != 'enviado'):
            payload = self._build_payload(linea)
            try:
                response = self._api_post(endpoint, payload)
                linea.write({'state': 'enviado', 'respuesta_api': str(response)})
                enviados += 1
            except Exception as e:
                linea.write({'state': 'error', 'respuesta_api': str(e)})
                errores += 1
                _logger.error("Error enviando servicio %s de solicitud %s: %s", linea.servicio_id.descripcion, self.name, e)

        if errores == 0:
            nuevo_state = 'enviado'
        elif enviados == 0:
            nuevo_state = 'error'
        else:
            nuevo_state = 'parcial'

        self.write({'state': nuevo_state})
        msg = f'✅ {enviados} servicio(s) enviados correctamente.'
        if errores:
            msg += f' ❌ {errores} servicio(s) con error.'
        self.message_post(body=msg)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Solicitud procesada',
                'message': msg,
                'sticky': errores > 0,
                'type': 'success' if errores == 0 else 'warning',
            },
        }

    def _build_payload(self, linea):
        return {
            'venta': False,
            'fecha': str(self.fecha),
            'negocio': '',
            'contrato': '',
            'no_solicitud': self.no_solicitud or '',
            'observaciones': self.observaciones or '',
            'problema_reg_anterior': self.problema_reg_anterior,
            'semilla': linea.clave_registro,
            'servicio': linea.servicio_id.servicio_id,
            'solicitado_por': self.persona_id.persona_id,
            'cliente': self.cliente_final_id_ext,
        }

    def action_restablecer_borrador(self):
        self.ensure_one()
        self.write({'state': 'borrador'})
        self.linea_ids.filtered(lambda l: l.state == 'error').write({'state': 'pendiente', 'respuesta_api': False})

    @api.model
    def action_sync_convenios(self):
        result = self.env['versat.convenio'].sync_from_api()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sincronización completada',
                'message': f"{result['created']} convenios creados, {result['updated']} actualizados.",
                'sticky': False,
                'type': 'success',
            },
        }
