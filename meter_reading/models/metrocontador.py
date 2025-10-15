from odoo import models, fields, api


class Metrocontador(models.Model):
    _name = 'meter.reading.metrocontador'
    _description = 'Metrocontador'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Código del Medidor',
        required=True,
        tracking=True,
        help='Identificador único del metrocontador'
    )
    
    tipo_medidor = fields.Selection([
        ('normal', 'Normal'),
        ('inteligente', 'Inteligente'),
        ('prepago', 'Prepago')
    ], string='Tipo de Medidor', required=True, default='normal', tracking=True,
       help='Tipo de medidor: Normal (3 lecturas), Inteligente (4 lecturas) o Prepago (sin lecturas)')
    
    ubicacion = fields.Char(
        string='Ubicación',
        required=True,
        tracking=True,
        help='Ubicación física dentro de la empresa'
    )
        
    responsable_id = fields.Many2one(
        'res.users',
        string='Responsable',
        required=True,
        tracking=True,
        help='Logístico asignado al metrocontador'
    )
    
    activo = fields.Boolean(
        string='Activo',
        default=True,
        tracking=True,
        help='Estado del medidor'
    )
    
    factor_conversion = fields.Float(
        string='Factor de Conversión',
        default=1.0,
        required=True,
        tracking=True,
        help='Factor para convertir lecturas del medidor a kWh. Ej: 1, 3, etc.'
    )
    
    # Relaciones
    lectura_ids = fields.One2many(
        'meter.reading.lectura.consumo',
        'metrocontador_id',
        string='Lecturas'
    )
    
    plan_energetico_ids = fields.Many2many(
        'meter.reading.plan.energetico',
        string='Planes Energéticos'
    )
    
    # Campos calculados
    ultima_lectura = fields.Float(
        string='Última Lectura (kWh)',
        compute='_compute_ultima_lectura',
        store=True,
        depends=['lectura_ids.lectura_kwh']
    )
    
    consumo_hoy = fields.Float(
        string='Consumo Hoy (kWh)',
        compute='_compute_consumo_hoy'
    )
    
    @api.depends('lectura_ids.lectura_kwh', 'lectura_ids.fecha')
    def _compute_ultima_lectura(self):
        for record in self:
            # Para medidores prepago, no mostrar última lectura
            if record.tipo_medidor == 'prepago':
                record.ultima_lectura = 0.0
            elif record.lectura_ids:
                ultima = record.lectura_ids.sorted(key=lambda r: (r.fecha, r.hora), reverse=True)
                record.ultima_lectura = ultima[0].lectura_kwh if ultima else 0.0
            else:
                record.ultima_lectura = 0.0
    
    def _compute_consumo_hoy(self):
        today = fields.Date.today()
        for record in self:
            # Para medidores prepago, no mostrar consumo hoy
            if record.tipo_medidor == 'prepago':
                record.consumo_hoy = 0.0
            else:
                lecturas_hoy = record.lectura_ids.filtered(
                    lambda l: l.fecha == today
                )
                # El consumo total del día es la suma de todos los consumos parciales del día.
             
                record.consumo_hoy = sum(lecturas_hoy.mapped('consumo_parcial'))
    
    def action_view_lecturas(self):
        """Acción para ver las lecturas del metrocontador"""
        self.ensure_one()
       
        if self.tipo_medidor == 'prepago':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Información',
                    'message': 'Los medidores de tipo Prepago no tienen lecturas asociadas.',
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        return {
            'name': f'Lecturas - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'meter.reading.lectura.consumo',
            'view_mode': 'tree,form,graph',
            'domain': [('metrocontador_id', '=', self.id)],
            'context': {
                'default_metrocontador_id': self.id,
                'default_tipo_medidor': self.tipo_medidor,
                'form_view_initial_mode': 'edit'
            }
        }