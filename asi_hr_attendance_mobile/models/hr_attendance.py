from odoo import models, api, _
from odoo.exceptions import AccessError

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    @api.model
    def create(self, vals):
        # Permitir la creación a través de la API para usuarios del modo quiosco
        if self.env.context.get('kiosk_mode') and self.env.user.has_group('hr_attendance.group_hr_attendance_kiosk'):
            employee = self.env['hr.employee'].browse(vals.get('employee_id'))
            if employee.user_id != self.env.user:
                raise AccessError(_("No puedes crear registros de asistencia para otros empleados."))
        return super(HrAttendance, self).create(vals)

    def write(self, vals):
        # Permitir la escritura a través de la API para usuarios del modo quiosco
        if self.env.context.get('kiosk_mode') and self.env.user.has_group('hr_attendance.group_hr_attendance_kiosk'):
            if any(attendance.employee_id.user_id != self.env.user for attendance in self):
                raise AccessError(_("No puedes modificar registros de asistencia de otros empleados."))
        return super(HrAttendance, self).write(vals)
