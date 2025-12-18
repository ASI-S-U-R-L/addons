/**
 * JavaScript para el módulo asi_signature_validator
 * Maneja la funcionalidad de:
 * - Drag and drop para certificados y PDFs
 * - Validación de certificados P12
 * - Verificación de firmas en PDFs
 * - Visualización de resultados con detalles de errores
 */

document.addEventListener("DOMContentLoaded", () => {
  console.log("Validador de firmas cargado")

  if (document.getElementById("certificate-validation-form")) {
    initCertificateValidation()
  }

  if (document.getElementById("pdf-verification-form")) {
    initPdfVerification()
  }
})

/* =====================================================
   FUNCIONES DE UTILIDAD
   ===================================================== */

function formatFileSize(bytes) {
  if (bytes === 0) return "0 Bytes"
  const k = 1024
  const sizes = ["Bytes", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Number.parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
}

function showNotification(message, type = "info") {
  const container = document.getElementById("notification-container")
  if (!container) {
    alert(message)
    return
  }

  const existing = container.querySelectorAll(`.alert-${type}`)
  if (existing.length >= 3) {
    existing[0].remove()
  }

  const iconClass =
    {
      success: "fa-check-circle",
      danger: "fa-exclamation-triangle",
      warning: "fa-exclamation-circle",
      info: "fa-info-circle",
    }[type] || "fa-info-circle"

  const alertDiv = document.createElement("div")
  alertDiv.className = `alert alert-${type} alert-dismissible fade show mb-2 shadow`
  alertDiv.style.cssText = "min-width: 280px; max-width: 400px; word-wrap: break-word;"
  alertDiv.innerHTML = `
        <i class="fa ${iconClass}"></i>
        <span class="ms-2">${message}</span>
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Cerrar"></button>
    `

  container.appendChild(alertDiv)

  const timeout = type === "danger" ? 10000 : 6000
  setTimeout(() => {
    if (alertDiv && alertDiv.parentNode) {
      alertDiv.classList.remove("show")
      setTimeout(() => alertDiv.remove(), 150)
    }
  }, timeout)
}

function escapeHtml(text) {
  if (!text) return ""
  const div = document.createElement("div")
  div.textContent = text
  return div.innerHTML
}

/* =====================================================
   VALIDACIÓN DE CERTIFICADOS P12
   ===================================================== */

function initCertificateValidation() {
  console.log("Inicializando validación de certificados")

  const form = document.getElementById("certificate-validation-form")
  const dropZone = document.getElementById("cert-drop-zone")
  const fileInput = document.getElementById("cert-input")
  const fileInfo = document.getElementById("cert-file-info")
  const validateBtn = document.getElementById("validate-btn")
  const resultsContainer = document.getElementById("validation-results")

  const useProfileCert = document.getElementById("use-profile-cert")
  const useProfilePassword = document.getElementById("use-profile-password")
  const passwordInput = document.getElementById("cert-password")
  const passwordGroup = document.getElementById("password-input-group")
  const certRequiredMark = document.getElementById("cert-required-mark")
  const passRequiredMark = document.getElementById("pass-required-mark")

  const autoValidate = document.getElementById("auto-validate-trigger")
  if (autoValidate && autoValidate.value === "true") {
    console.log("Auto-validando certificado del perfil...")
    setTimeout(() => {
      autoValidateProfile()
    }, 500)
  }

  let selectedFile = null
  let dragCounter = 0

  async function autoValidateProfile() {
    try {
      resultsContainer.style.display = "block"
      resultsContainer.innerHTML = `
        <div class="spinner-container">
          <i class="fa fa-spinner fa-spin"></i>
          <p class="mt-3">Validando tu certificado configurado...</p>
        </div>
      `

      const formData = new FormData()
      formData.append("use_profile", "true")

      const response = await fetch("/validar-certificado/verificar", {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
      })

      const result = await response.json()
      displayCertificateResult(result)

      // Mostrar mensaje informativo después de la auto-validación
      showNotification(
        "Se ha validado automáticamente tu certificado configurado. Puedes validar otro certificado si lo deseas.",
        "info",
      )
    } catch (error) {
      console.error("Error en auto-validación:", error)
      resultsContainer.style.display = "none"
      showNotification("No se pudo validar automáticamente tu certificado. Puedes validarlo manualmente.", "warning")
    }
  }

  if (useProfileCert) {
    useProfileCert.addEventListener("change", function () {
      if (this.checked) {
        dropZone.classList.add("disabled")
        fileInput.disabled = true
        certRequiredMark.style.display = "none"
        selectedFile = null
        fileInfo.innerHTML = ""
      } else {
        dropZone.classList.remove("disabled")
        fileInput.disabled = false
        certRequiredMark.style.display = "inline"
      }
      validateForm()
    })
  }

  if (useProfilePassword) {
    useProfilePassword.addEventListener("change", function () {
      if (this.checked) {
        passwordGroup.style.opacity = "0.5"
        passwordInput.disabled = true
        passwordInput.value = ""
        passRequiredMark.style.display = "none"
      } else {
        passwordGroup.style.opacity = "1"
        passwordInput.disabled = false
        passRequiredMark.style.display = "inline"
      }
      validateForm()
    })
  }

  function validateForm() {
    let isValid = true

    const usingProfileCert = useProfileCert && useProfileCert.checked
    if (!usingProfileCert && !selectedFile) {
      isValid = false
    }

    const usingProfilePass = useProfilePassword && useProfilePassword.checked
    if (!usingProfilePass && (!passwordInput.value || passwordInput.value.trim() === "")) {
      isValid = false
    }

    validateBtn.disabled = !isValid
    return isValid
  }

  dropZone.addEventListener("click", () => {
    if (!fileInput.disabled) {
      fileInput.click()
    }
  })

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleCertificateFile(e.target.files[0])
    }
  })

  dropZone.addEventListener("dragenter", (e) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounter++
    if (!dropZone.classList.contains("disabled")) {
      dropZone.classList.add("is-dragover")
    }
  })

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault()
    e.stopPropagation()
  })

  dropZone.addEventListener("dragleave", (e) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounter--
    if (dragCounter === 0) {
      dropZone.classList.remove("is-dragover")
    }
  })

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault()
    e.stopPropagation()
    dropZone.classList.remove("is-dragover")
    dragCounter = 0

    if (dropZone.classList.contains("disabled")) return

    const files = e.dataTransfer.files
    if (files.length > 0) {
      handleCertificateFile(files[0])
    }
  })

  function handleCertificateFile(file) {
    const validExtensions = [".p12", ".pfx"]
    const fileName = file.name.toLowerCase()
    const isValid = validExtensions.some((ext) => fileName.endsWith(ext))

    if (!isValid) {
      showNotification("Solo se permiten archivos .p12 o .pfx", "danger")
      return
    }

    selectedFile = file

    fileInfo.innerHTML = `
            <div class="file-item">
                <i class="fa fa-key file-icon text-success"></i>
                <span class="file-name">${escapeHtml(file.name)}</span>
                <span class="file-size">${formatFileSize(file.size)}</span>
                <span class="remove-file" onclick="removeCertFile(event)">&times;</span>
            </div>
        `

    const dt = new DataTransfer()
    dt.items.add(file)
    fileInput.files = dt.files

    validateForm()
  }

  window.removeCertFile = (e) => {
    e.stopPropagation()
    selectedFile = null
    fileInfo.innerHTML = ""
    fileInput.value = ""
    validateForm()
  }

  const togglePassword = document.getElementById("toggle-password")
  if (togglePassword) {
    togglePassword.addEventListener("click", () => {
      const type = passwordInput.type === "password" ? "text" : "password"
      passwordInput.type = type
      togglePassword.querySelector("i").className = type === "password" ? "fa fa-eye" : "fa fa-eye-slash"
    })
  }

  passwordInput.addEventListener("input", validateForm)

  form.addEventListener("submit", async (e) => {
    e.preventDefault()

    if (!validateForm()) {
      showNotification("Por favor complete todos los campos requeridos", "warning")
      return
    }

    validateBtn.disabled = true
    validateBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Validando...'
    resultsContainer.style.display = "none"

    try {
      const formData = new FormData()

      const usingProfileCert = useProfileCert && useProfileCert.checked
      const usingProfilePass = useProfilePassword && useProfilePassword.checked

      if (usingProfileCert) {
        formData.append("use_profile", "true")
      } else if (selectedFile) {
        formData.append("certificate", selectedFile)
      }

      if (!usingProfilePass && passwordInput.value) {
        formData.append("password", passwordInput.value)
      }

      const response = await fetch("/validar-certificado/verificar", {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
      })

      const result = await response.json()
      displayCertificateResult(result)
    } catch (error) {
      console.error("Error:", error)
      showNotification("Error al comunicarse con el servidor", "danger")
    } finally {
      validateBtn.disabled = false
      validateBtn.innerHTML = '<i class="fa fa-check-circle"></i> Validar Certificado'
      validateForm()
    }
  })

  function displayCertificateResult(result) {
    resultsContainer.style.display = "block"

    if (!result.success) {
      const statusClass = "invalid"
      let icon = "fa-times-circle"
      let title = "Error de Validación"

      if (result.password_correct === false) {
        title = "Contraseña Incorrecta"
        icon = "fa-lock"
      }

      // Mostrar errores detallados
      let errorsHtml = ""
      if (result.validation_errors && result.validation_errors.length > 0) {
        errorsHtml = `
          <div class="validation-errors-section mt-3">
            <h5><i class="fa fa-exclamation-triangle text-danger"></i> Detalles del Error</h5>
            <ul class="validation-errors-list">
              ${result.validation_errors.map((err) => `<li>${escapeHtml(err)}</li>`).join("")}
            </ul>
          </div>
        `
      }

      resultsContainer.innerHTML = `
                <div class="validation-result ${statusClass}">
                    <div class="text-center">
                        <div class="result-icon"><i class="fa ${icon}"></i></div>
                        <h4>${title}</h4>
                        <p>${escapeHtml(result.error)}</p>
                    </div>
                    ${errorsHtml}
                </div>
            `
      return
    }

    const info = result.certificate_info
    const chainValidation = result.chain_validation || {}

    // Determinar estado general
    let statusClass, icon, title, statusMessage

    if (result.valid) {
      statusClass = "valid"
      icon = "fa-check-circle"
      title = "Certificado Válido"
      if (chainValidation.valid && chainValidation.trusted_ca) {
        statusMessage = `El certificado es válido y está verificado contra la CA "${chainValidation.trusted_ca.name}". Expira en ${info.days_until_expiry} días.`
      } else {
        statusMessage = `El certificado es válido. Expira en ${info.days_until_expiry} días.`
      }
    } else if (result.expired) {
      statusClass = "invalid"
      icon = "fa-times-circle"
      title = "Certificado Expirado"
      statusMessage = "El certificado ha expirado y ya no es válido para firmar."
    } else if (result.not_yet_valid) {
      statusClass = "warning"
      icon = "fa-clock-o"
      title = "Certificado No Válido Aún"
      statusMessage = "El certificado aún no ha entrado en su período de validez."
    } else {
      statusClass = "invalid"
      icon = "fa-times-circle"
      title = "Certificado No Válido"
      statusMessage = "El certificado no pasó todas las verificaciones requeridas."
    }

    // Construir HTML de errores y advertencias
    let validationMessagesHtml = ""

    if (result.validation_errors && result.validation_errors.length > 0) {
      validationMessagesHtml += `
        <div class="validation-errors-section">
          <h5><i class="fa fa-times-circle text-danger"></i> Problemas Detectados</h5>
          <ul class="validation-errors-list">
            ${result.validation_errors.map((err) => `<li class="text-danger">${escapeHtml(err)}</li>`).join("")}
          </ul>
        </div>
      `
    }

    if (result.validation_warnings && result.validation_warnings.length > 0) {
      validationMessagesHtml += `
        <div class="validation-warnings-section">
          <h5><i class="fa fa-exclamation-triangle text-warning"></i> Advertencias</h5>
          <ul class="validation-warnings-list">
            ${result.validation_warnings.map((warn) => `<li class="text-warning">${escapeHtml(warn)}</li>`).join("")}
          </ul>
        </div>
      `
    }

    // Construir sección de verificación de cadena
    let chainHtml = ""
    if (chainValidation.verified !== undefined) {
      const chainStatus = chainValidation.valid ? "valid" : "invalid"
      const chainIcon = chainValidation.valid ? "fa-check" : "fa-times"
      const chainText = chainValidation.valid
        ? `Verificado contra: ${chainValidation.trusted_ca?.name || "CA de confianza"}`
        : "No se pudo verificar la cadena de confianza"

      chainHtml = `
        <div class="cert-info-section">
          <h5><i class="fa fa-link"></i> Verificación de Cadena de Confianza</h5>
          <div class="chain-status ${chainStatus}">
            <i class="fa ${chainIcon}"></i>
            <span>${escapeHtml(chainText)}</span>
          </div>
          ${chainValidation.trusted_ca
          ? `
            <div class="cert-info-row mt-2">
              <span class="cert-info-label">CA de Confianza:</span>
              <span class="cert-info-value">${escapeHtml(chainValidation.trusted_ca.name)}</span>
            </div>
            ${chainValidation.trusted_ca.organization
            ? `
            <div class="cert-info-row">
              <span class="cert-info-label">Organización:</span>
              <span class="cert-info-value">${escapeHtml(chainValidation.trusted_ca.organization)}</span>
            </div>
            `
            : ""
          }
          `
          : ""
        }
        </div>
      `
    }

    resultsContainer.innerHTML = `
            <div class="validation-result ${statusClass}">
                <div class="text-center mb-4">
                    <div class="result-icon"><i class="fa ${icon}"></i></div>
                    <h4>${title}</h4>
                    <p>${statusMessage}</p>
                </div>
                
                ${validationMessagesHtml}
                
                <div class="cert-info-section">
                    <h5><i class="fa fa-user"></i> Titular del Certificado</h5>
                    ${formatCertNameInfo(info.subject)}
                </div>
                
                <div class="cert-info-section">
                    <h5><i class="fa fa-building"></i> Emisor del Certificado</h5>
                    ${formatCertNameInfo(info.issuer)}
                </div>
                
                ${chainHtml}
                
                <div class="cert-info-section">
                    <h5><i class="fa fa-calendar"></i> Período de Validez</h5>
                    <div class="cert-info-row">
                        <span class="cert-info-label">Válido desde:</span>
                        <span class="cert-info-value">${escapeHtml(info.not_before)}</span>
                    </div>
                    <div class="cert-info-row">
                        <span class="cert-info-label">Válido hasta:</span>
                        <span class="cert-info-value">${escapeHtml(info.not_after)}</span>
                    </div>
                    <div class="cert-info-row">
                        <span class="cert-info-label">Número de serie:</span>
                        <span class="cert-info-value" style="font-family: monospace;">${escapeHtml(info.serial_number)}</span>
                    </div>
                </div>
            </div>
        `
  }

  function formatCertNameInfo(info) {
    const labels = {
      nombre: "Nombre",
      common_name: "Nombre",
      organizacion: "Organización",
      organization: "Organización",
      unidad_organizativa: "Unidad organizativa",
      organizational_unit: "Unidad organizativa",
      pais: "País",
      country: "País",
      provincia: "Provincia/Estado",
      state: "Provincia/Estado",
      localidad: "Localidad",
      locality: "Localidad",
      email: "Correo electrónico",
      numero_serie: "Número de serie",
      serial_number: "Número de serie",
    }

    let html = ""
    for (const [key, value] of Object.entries(info)) {
      if (!value) continue
      const label = labels[key] || key
      html += `
                <div class="cert-info-row">
                    <span class="cert-info-label">${escapeHtml(label)}:</span>
                    <span class="cert-info-value">${escapeHtml(value)}</span>
                </div>
            `
    }
    return html || '<p class="text-muted">No hay información disponible</p>'
  }

  validateForm()
}

/* =====================================================
   VERIFICACIÓN DE FIRMAS EN PDFs
   ===================================================== */

function initPdfVerification() {
  console.log("Inicializando verificación de PDFs")

  const form = document.getElementById("pdf-verification-form")
  const dropZone = document.getElementById("pdf-drop-zone")
  const fileInput = document.getElementById("pdf-input")
  const filesList = document.getElementById("pdf-files-list")
  const verifyBtn = document.getElementById("verify-btn")
  const resultsContainer = document.getElementById("pdf-results")

  let selectedFiles = []
  let dragCounter = 0

  function updateFilesList() {
    if (selectedFiles.length === 0) {
      filesList.innerHTML = ""
      verifyBtn.disabled = true
      return
    }

    let html = ""
    selectedFiles.forEach((file, index) => {
      html += `
                <div class="file-item">
                    <i class="fa fa-file-pdf-o file-icon"></i>
                    <span class="file-name">${escapeHtml(file.name)}</span>
                    <span class="file-size">${formatFileSize(file.size)}</span>
                    <span class="remove-file" data-index="${index}">&times;</span>
                </div>
            `
    })
    filesList.innerHTML = html

    const dt = new DataTransfer()
    selectedFiles.forEach((file) => dt.items.add(file))
    fileInput.files = dt.files

    verifyBtn.disabled = selectedFiles.length === 0
  }

  function addFiles(files) {
    const pdfFiles = Array.from(files).filter(
      (file) => file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf"),
    )

    if (pdfFiles.length === 0) {
      showNotification("Solo se permiten archivos PDF", "warning")
      return
    }

    const newFiles = pdfFiles.filter(
      (newFile) => !selectedFiles.some((existing) => existing.name === newFile.name && existing.size === newFile.size),
    )

    if (newFiles.length < pdfFiles.length) {
      showNotification("Algunos archivos ya estaban seleccionados", "info")
    }

    selectedFiles = selectedFiles.concat(newFiles)
    updateFilesList()
  }

  dropZone.addEventListener("click", () => fileInput.click())

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      addFiles(e.target.files)
    }
  })

  dropZone.addEventListener("dragenter", (e) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounter++
    dropZone.classList.add("is-dragover")
  })

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault()
    e.stopPropagation()
  })

  dropZone.addEventListener("dragleave", (e) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounter--
    if (dragCounter === 0) {
      dropZone.classList.remove("is-dragover")
    }
  })

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault()
    e.stopPropagation()
    dropZone.classList.remove("is-dragover")
    dragCounter = 0

    if (e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files)
    }
  })

  filesList.addEventListener("click", (e) => {
    if (e.target.classList.contains("remove-file")) {
      e.stopPropagation()
      const index = Number.parseInt(e.target.dataset.index)
      selectedFiles.splice(index, 1)
      updateFilesList()
    }
  })

  form.addEventListener("submit", async (e) => {
    e.preventDefault()

    if (selectedFiles.length === 0) {
      showNotification("Por favor seleccione al menos un archivo PDF", "warning")
      return
    }

    verifyBtn.disabled = true
    verifyBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Analizando...'
    resultsContainer.style.display = "block"
    resultsContainer.innerHTML = `
            <div class="spinner-container">
                <i class="fa fa-spinner fa-spin"></i>
                <p class="mt-3">Analizando ${selectedFiles.length} archivo(s)...</p>
            </div>
        `

    try {
      const formData = new FormData()
      selectedFiles.forEach((file) => {
        formData.append("pdfs", file)
      })

      const response = await fetch("/verificar-firmas-pdf/analizar", {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
      })

      const result = await response.json()
      displayPdfResults(result)
    } catch (error) {
      console.error("Error:", error)
      showNotification("Error al comunicarse con el servidor", "danger")
      resultsContainer.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fa fa-exclamation-triangle"></i>
                    Error al analizar los archivos. Por favor intente nuevamente.
                </div>
            `
    } finally {
      verifyBtn.disabled = false
      verifyBtn.innerHTML = '<i class="fa fa-search"></i> Verificar Firmas'
    }
  })

  function displayPdfResults(result) {
    if (!result.success) {
      resultsContainer.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fa fa-exclamation-triangle"></i>
                    ${escapeHtml(result.error)}
                </div>
            `
      return
    }

    let html = `
            <div class="mb-3">
                <h5><i class="fa fa-list"></i> Resultados del Análisis</h5>
                <p class="text-muted">Se analizaron ${result.total_files} archivo(s)</p>
            </div>
        `

    result.results.forEach((pdfResult) => {
      html += generatePdfResultCard(pdfResult)
    })

    resultsContainer.innerHTML = html
  }

  function generatePdfResultCard(pdfResult) {
    const hasSignatures = pdfResult.has_signatures && pdfResult.signatures.length > 0
    const badgeClass = hasSignatures ? "has-signatures" : "no-signatures"
    const badgeIcon = hasSignatures ? "fa-check" : "fa-times"
    const badgeText = hasSignatures ? `${pdfResult.total_signatures} firma(s) encontrada(s)` : "Sin firmas digitales"

    let signaturesHtml = ""

    if (pdfResult.error) {
      signaturesHtml = `
                <div class="alert alert-danger mt-3">
                    <i class="fa fa-exclamation-triangle"></i>
                    Error al analizar: ${escapeHtml(pdfResult.error)}
                </div>
            `
    } else if (hasSignatures) {
      signaturesHtml = generateSignaturesTable(pdfResult.signatures)
    } else {
      signaturesHtml = `
                <div class="no-signatures-message">
                    <div class="icon"><i class="fa fa-file-o"></i></div>
                    <p>Este documento no contiene firmas digitales</p>
                </div>
            `
    }

    return `
            <div class="pdf-result-card">
                <div class="pdf-result-header">
                    <h5>
                        <i class="fa fa-file-pdf-o file-icon"></i>
                        ${escapeHtml(pdfResult.filename)}
                    </h5>
                    <span class="signature-badge ${badgeClass}">
                        <i class="fa ${badgeIcon}"></i>
                        ${badgeText}
                    </span>
                </div>
                <div class="pdf-result-body">
                    ${signaturesHtml}
                </div>
            </div>
        `
  }

  function generateSignaturesTable(signatures) {
    let rows = ""

    signatures.forEach((sig, index) => {
      // Determinar el badge de validez
      let validityBadge = ""
      let validityClass = ""

      if (sig.valid === true) {
        validityBadge = '<span class="validity-badge valid"><i class="fa fa-check"></i> Válida</span>'
        validityClass = "signature-valid"
      } else if (sig.expired === true) {
        validityBadge = '<span class="validity-badge expired"><i class="fa fa-clock-o"></i> Expirada</span>'
        validityClass = "signature-expired"
      } else if (sig.valid === false) {
        validityBadge = '<span class="validity-badge invalid"><i class="fa fa-times"></i> No válida</span>'
        validityClass = "signature-invalid"
      } else {
        validityBadge = '<span class="validity-badge unknown"><i class="fa fa-question"></i> Desconocido</span>'
        validityClass = "signature-unknown"
      }

      let countBadge = ""
      if (sig.count && sig.count > 1) {
        countBadge = `<span class="count-badge"><i class="fa fa-clone"></i> x${sig.count}</span>`
      }

      // Construir información de cadena de confianza
      let chainInfo = ""
      if (sig.chain_validation) {
        if (sig.chain_validation.valid && sig.chain_validation.trusted_ca) {
          chainInfo = `
            <div class="chain-info valid mt-2">
              <i class="fa fa-shield text-success"></i>
              <small>Verificado contra: ${escapeHtml(sig.chain_validation.trusted_ca.name)}</small>
            </div>
          `
        } else if (sig.chain_validation.verified && !sig.chain_validation.valid) {
          chainInfo = `
            <div class="chain-info invalid mt-2">
              <i class="fa fa-shield text-danger"></i>
              <small>No verificado contra CA de confianza</small>
            </div>
          `
        }
      }

      // Construir lista de errores/advertencias
      let errorsHtml = ""
      if (sig.validation_errors && sig.validation_errors.length > 0) {
        errorsHtml += `
          <div class="signature-errors mt-2">
            <strong class="text-danger"><i class="fa fa-exclamation-circle"></i> Problemas:</strong>
            <ul class="error-list mb-0">
              ${sig.validation_errors.map((err) => `<li>${escapeHtml(err)}</li>`).join("")}
            </ul>
          </div>
        `
      }

      if (sig.validation_warnings && sig.validation_warnings.length > 0) {
        errorsHtml += `
          <div class="signature-warnings mt-2">
            <strong class="text-warning"><i class="fa fa-exclamation-triangle"></i> Advertencias:</strong>
            <ul class="warning-list mb-0">
              ${sig.validation_warnings.map((warn) => `<li>${escapeHtml(warn)}</li>`).join("")}
            </ul>
          </div>
        `
      }

      rows += `
                <tr class="${validityClass}">
                    <td>${index + 1}</td>
                    <td>
                        <strong>${escapeHtml(sig.signer || "Desconocido")}</strong>
                        ${countBadge}
                        ${sig.signer_details?.organization ? `<br><small class="text-muted">${escapeHtml(sig.signer_details.organization)}</small>` : ""}
                        ${chainInfo}
                    </td>
                    <td>${escapeHtml(sig.issuer || "Desconocido")}</td>
                    <td>
                      ${validityBadge}
                      ${errorsHtml}
                    </td>
                    <td>
                      ${escapeHtml(sig.expiry_date || "No disponible")}
                      ${sig.sign_date && sig.sign_date !== "No disponible" ? `<br><small class="text-muted">Firmado: ${escapeHtml(sig.sign_date)}</small>` : ""}
                    </td>
                </tr>
            `
    })

    return `
            <table class="signatures-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Firmante</th>
                        <th>Emisor del certificado</th>
                        <th>Estado de Validación</th>
                        <th>Fechas</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        `
  }
}
