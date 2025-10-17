/** @odoo-module **/

import { PosSession } from "@point_of_sale/js/models"
import { patch } from "@web/core/utils/patch"

// Extender el comportamiento del cierre de sesión
patch(PosSession.prototype, "asi_pos_reports.PosSession", {
  async close(...args) {
    // Llamar al método original
    const result = await this._super(...args)

    // Generar automáticamente el reporte de mercancías
    try {
      await this._generateMerchandiseReport()
    } catch (error) {
      console.warn("Error al generar reporte de mercancías:", error)
    }

    return result
  },

  async _generateMerchandiseReport() {
    // Llamar al método del servidor para generar el reporte
    const rpc = this.env.services.rpc

    await rpc({
      model: "pos.session",
      method: "_generate_merchandise_report_on_close",
      args: [this.id],
    })

    // Mostrar notificación
    this.env.services.notification.add("Reporte de mercancías generado automáticamente", { type: "success" })
  },
})
