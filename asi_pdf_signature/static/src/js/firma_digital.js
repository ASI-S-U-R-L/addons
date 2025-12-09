odoo.define("firma_digital.firma_digital", ["web.core", "web.AbstractAction"], (require) => {
  var core = require("web.core")
  var AbstractAction = require("web.AbstractAction")
  var _t = core._t

  // Acción personalizada para descargar múltiples PDFs
  var DownloadMultiplePdfsAction = AbstractAction.extend({
    init: function (parent, action) {
      this._super.apply(this, arguments)
      this.document_ids = action.params.document_ids || []
      this.message = action.params.message || "Descargando archivos..."
    },

    start: function () {
      var self = this

      // Mostrar notificación
      this.do_notify(_t("Descarga iniciada"), this.message, false)

      // Función para descargar un archivo individual
      function downloadDocument(documentId, index) {
        setTimeout(() => {
          // Crear elemento temporal para la descarga
          var link = document.createElement("a")
          link.href = "/firma_digital/descargar_individual?documento_id=" + documentId
          link.download = "" // Forzar descarga
          link.style.display = "none"
          document.body.appendChild(link)
          link.click()
          document.body.removeChild(link)

          // Si es la última descarga, mostrar notificación de completado
          if (index === self.document_ids.length - 1) {
            setTimeout(() => {
              self.do_notify(_t("Descarga completada"), _t("Todos los documentos han sido descargados."), false)
            }, 1000)
          }
        }, index * 500) // 500ms de delay entre cada descarga
      }

      // Iniciar descargas
      this.document_ids.forEach((documentId, index) => {
        downloadDocument(documentId, index)
      })

      // Cerrar la acción después de iniciar todas las descargas
      setTimeout(
        () => {
          self.do_action({ type: "ir.actions.act_window_close" })
        },
        this.document_ids.length * 500 + 1000,
      )

      return this._super.apply(this, arguments)
    },
  })

  // Registrar la acción personalizada
  core.action_registry.add("download_multiple_pdfs", DownloadMultiplePdfsAction)
})
