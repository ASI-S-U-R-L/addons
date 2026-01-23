/* Split-view Bandeja: carga preview y navega a la firma web (sin abrir backend). */
document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    const workflowItems = document.querySelectorAll('.workflow-item');
    const workflowCheckboxes = document.querySelectorAll('.workflow-checkbox');
    const rightPanel = document.querySelector('.split-panel-right .split-panel-body');
    const csrfTokenEl = document.getElementById('asi_csrf_token');
    const csrfToken = csrfTokenEl ? csrfTokenEl.value : null;

    function setSelected(checkbox) {
        workflowCheckboxes.forEach(cb => {
            if (cb !== checkbox) cb.checked = false;
        });

        // Estilo visual
        workflowItems.forEach(item => {
            item.classList.remove('active');
            const lbl = item.querySelector('.workflow-select-checkbox');
            if (lbl) lbl.classList.remove('selected');
        });
        const workflowItem = checkbox.closest('.workflow-item');
        if (workflowItem) {
            workflowItem.classList.add('active');
            const lbl = workflowItem.querySelector('.workflow-select-checkbox');
            if (lbl) lbl.classList.add('selected');
        }
    }

    function showLoading() {
        if (!rightPanel) return;
        rightPanel.innerHTML = `
            <div class="text-center py-5 text-muted">
                <i class="fa fa-spinner fa-spin fa-3x"></i>
                <p class="mt-3">Cargando documento...</p>
            </div>
        `;
    }

    function showEmpty() {
        if (!rightPanel) return;
        rightPanel.innerHTML = `
            <div class="text-center py-5 text-muted">
                <div class="mb-4">
                    <i class="fa fa-hand-o-left fa-4x text-primary"></i>
                </div>
                <h4>Selecciona una solicitud</h4>
                <p class="lead">Marca una solicitud en la lista de la izquierda para ver el detalle.</p>
            </div>
        `;
    }

    function renderDetails(data) {
        if (!rightPanel) return;

        const documents = Array.isArray(data.documents) ? data.documents : [];
        const docsList = (data.document_names || []).map(n => `<li>${escapeHtml(n)}</li>`).join('');
        const reason = data.reason ? `<div class="alert alert-warning mb-3"><i class="fa fa-info-circle me-2"></i>${escapeHtml(data.reason)}</div>` : '';

        const missing = Array.isArray(data.missing_profile_fields)
            ? data.missing_profile_fields
            : [
                (!data.user_has_certificado ? 'certificado_firma' : null),
                (!data.user_has_imagen ? 'imagen_firma' : null),
                (!data.user_has_password ? 'contrasena_certificado' : null),
            ].filter(Boolean);
        const profileComplete = (data.profile_complete === true) || (missing.length === 0);

        const credFieldLabel = (field, okLabel) => {
            return profileComplete && !missing.includes(field)
                ? `<span class="badge bg-success ms-2"><i class="fa fa-check"></i> ${okLabel}</span>`
                : `<span class="badge bg-warning text-dark ms-2"><i class="fa fa-exclamation-triangle"></i> Requerido</span>`;
        };

        const credentialsCard = `
            <div class="card mb-3" id="cred-card">
                <div class="card-header bg-light d-flex justify-content-between align-items-center">
                    <strong><i class="fa fa-id-card-o me-2"></i>Datos de firma</strong>
                    ${profileComplete ? `<span class="text-success small"><i class="fa fa-check-circle"></i> Listo (perfil)</span>` : `<span class="text-warning small"><i class="fa fa-exclamation-triangle"></i> Completa para firmar</span>`}
                </div>
                <div class="card-body">
                    ${profileComplete ? `
                        <div class="alert alert-success py-2 mb-3">
                            <i class="fa fa-shield me-2"></i>
                            Usaremos tu <strong>certificado</strong>, <strong>imagen</strong> y <strong>contraseña</strong> guardados en tu perfil.
                            <a href="#" id="btn-show-cred" class="ms-2">Actualizar</a>
                        </div>
                    ` : `
                        <div class="alert alert-warning py-2 mb-3">
                            <i class="fa fa-info-circle me-2"></i>
                            Para firmar necesitas completar los datos faltantes.
                        </div>
                    `}

                    <div class="row g-3 ${profileComplete ? 'd-none' : ''}" id="cred-form">
                        ${missing.includes('certificado_firma') ? `
                        <div class="col-12">
                            <label class="form-label">Certificado (.p12) ${credFieldLabel('certificado_firma','En perfil')}</label>
                            <input type="file" class="form-control" id="cred-certificate" accept=".p12,.pfx,application/x-pkcs12" required/>
                        </div>
                        ` : ''}
                        ${missing.includes('imagen_firma') ? `
                        <div class="col-12">
                            <label class="form-label">Imagen de firma ${credFieldLabel('imagen_firma','En perfil')}</label>
                            <input type="file" class="form-control" id="cred-image" accept="image/*" required/>
                        </div>
                        ` : ''}
                        ${missing.includes('contrasena_certificado') ? `
                        <div class="col-12">
                            <label class="form-label">Contraseña del certificado ${credFieldLabel('contrasena_certificado','En perfil')}</label>
                            <input type="password" class="form-control" id="cred-password" placeholder="Contraseña" required/>
                        </div>
                        ` : ''}
                        <div class="col-12 d-flex justify-content-between align-items-center">
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="cred-save" ${!profileComplete ? 'checked' : ''}>
                                <label class="form-check-label" for="cred-save">Guardar en mi perfil</label>
                            </div>
                            <button type="button" class="btn btn-outline-secondary btn-sm" id="btn-save-profile">
                                <i class="fa fa-save me-1"></i>Guardar
                            </button>
                        </div>
                        <div class="col-12">
                            <div id="cred-msg"></div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        const selector = (documents && documents.length > 1) ? `
            <div class="card mb-3">
                <div class="card-header bg-light"><strong>Seleccionar documento</strong></div>
                <div class="card-body">
                    <select class="form-select" id="doc-select">
                        ${documents.map(d => {
                            const signed = d.is_signed ? ' (firmado)' : '';
                            const selected = (String(d.id) === String(data.document_id)) ? 'selected' : '';
                            return `<option value="${d.id}" ${selected}>${escapeHtml(d.name)}${signed}</option>`;
                        }).join('')}
                    </select>
                    <small class="text-muted d-block mt-2">Si hay varios archivos, elige cuál quieres previsualizar.</small>
                </div>
            </div>
        ` : '';

        const preview = `
            <div class="row mt-4">
                <div class="col-12">
                    <div class="card">
                        <div class="card-header bg-light d-flex justify-content-between align-items-center">
                            <h6 class="mb-0"><i class="fa fa-eye me-2"></i>Vista Previa</h6>
                            <small class="text-muted" id="preview-status"></small>
                        </div>
                        <div class="card-body p-0" style="min-height: 140px;">
                            ${data.document_data ? `
                                <iframe id="pdf-preview-iframe" src="data:application/pdf;base64,${data.document_data}" style="width:100%; height:500px; border:none;"></iframe>
                            ` : `
                                <div class="p-3">
                                    <div class="alert alert-info mb-0">
                                        <i class="fa fa-info-circle me-2"></i>
                                        No se pudo cargar una vista previa.
                                    </div>
                                </div>
                                <iframe id="pdf-preview-iframe" style="display:none"></iframe>
                            `}
                        </div>
                    </div>
                </div>
            </div>
        `;

        rightPanel.innerHTML = `
            
            ${reason}

            <div class="row g-3">
                <div class="col-md-6">
                    ${selector}
                    
                    ${(!selector && data.document_names && data.document_names.length > 1) ? `
                        <div class="card mb-3">
                            <div class="card-header bg-light"><strong>Documentos en la solicitud</strong></div>
                            <div class="card-body"><ul class="mb-0">${docsList}</ul></div>
                        </div>
                    ` : ''}
                </div>
                
                <div class="col-md-6">
                    ${credentialsCard}
                </div>
            </div>

            <div class="row mt-4">
                <div class="col-6">
                    <button type="button" class="btn btn-success btn-lg w-100" id="btn-firmar">
                        <i class="fa fa-pencil me-2"></i>Firmar
                    </button>
                    <div class="text-muted small mt-1 text-center" id="btn-hint"></div>
                </div>
                <div class="col-6">
                    <a href="/bandeja-entrada/rechazar/${data.workflow_id}" class="btn btn-danger btn-lg w-100">
                        <i class="fa fa-times me-2"></i>Rechazar
                    </a>
                </div>
            </div>

            ${preview}
        `;

        const btn = document.getElementById('btn-firmar');
        const hint = document.getElementById('btn-hint');

        // Cambio de documento para preview
        const docSelect = document.getElementById('doc-select');
        if (docSelect) {
            docSelect.addEventListener('change', function () {
                const docId = this.value;
                const status = document.getElementById('preview-status');
                if (status) status.textContent = 'Cargando...';

                fetch(`/api/workflow-document-preview/${data.workflow_id}/${docId}`)
                    .then(r => r.json())
                    .then(resp => {
                        if (!resp || !resp.success) {
                            const err = (resp && resp.error) ? resp.error : 'Error al cargar preview.';
                            if (status) status.textContent = err;
                            return;
                        }
                        const iframe = document.getElementById('pdf-preview-iframe');
                        const nameEl = document.getElementById('selected-doc-name');
                        if (iframe) {
                            iframe.style.display = 'block';
                            iframe.src = `data:application/pdf;base64,${resp.document_data}`;
                        }
                        if (nameEl) {
                            nameEl.textContent = resp.document_name || '';
                        }
                        if (status) status.textContent = '';
                    })
                    .catch(() => {
                        if (status) status.textContent = 'Error al cargar preview.';
                    });
            });
        }

        // Credenciales UI helpers
        const credForm = document.getElementById('cred-form');
        const showCred = document.getElementById('btn-show-cred');
        const credMsg = document.getElementById('cred-msg');
        const certInput = document.getElementById('cred-certificate');
        const imgInput = document.getElementById('cred-image');
        const pwdInput = document.getElementById('cred-password');
        const saveCheckbox = document.getElementById('cred-save');
        const btnSaveProfile = document.getElementById('btn-save-profile');

        function setCredMessage(html) {
            if (credMsg) credMsg.innerHTML = html || '';
        }

        function clearInvalid() {
            [certInput, imgInput, pwdInput].forEach(el => {
                if (el) el.classList.remove('is-invalid');
            });
        }

        function markInvalid(field) {
            const map = {
                'certificado_firma': certInput,
                'imagen_firma': imgInput,
                'contrasena_certificado': pwdInput,
            };
            const el = map[field];
            if (el) el.classList.add('is-invalid');
        }

        function requiredReady() {
            // Solo bloquear si originalmente faltaba en el perfil
            if (missing.includes('certificado_firma')) {
                if (!(certInput && certInput.files && certInput.files.length)) return false;
            }
            if (missing.includes('imagen_firma')) {
                if (!(imgInput && imgInput.files && imgInput.files.length)) return false;
            }
            if (missing.includes('contrasena_certificado')) {
                if (!(pwdInput && (pwdInput.value || '').trim())) return false;
            }
            return true;
        }

        function updateButtonState() {
            if (!btn) return;
            if (!data.can_sign) {
                btn.disabled = true;
                btn.classList.remove('btn-success');
                btn.classList.add('btn-secondary');
                if (hint) hint.textContent = data.reason || 'No disponible.';
                return;
            }

            if (!profileComplete && !requiredReady()) {
                btn.disabled = true;
                if (hint) {
                    hint.textContent = 'Completa los datos de firma para habilitar la firma.';
                    hint.className = 'text-muted small mt-1 text-center';
                }
            } else {
                btn.disabled = false;
                if (hint) {
                    hint.textContent = profileComplete ? 'Listo: usaremos tu perfil' : 'Listo para firmar';
                    hint.className = 'text-success small mt-1 text-center';
                }
            }
        }

        // Toggle "Actualizar"
        if (showCred && credForm) {
            showCred.addEventListener('click', function (e) {
                e.preventDefault();
                credForm.classList.toggle('d-none');
                setCredMessage('');
            });
        }

        // Guardar perfil (sin firmar)
        if (btnSaveProfile) {
            btnSaveProfile.addEventListener('click', function () {
                clearInvalid();
                setCredMessage('');

                if (!csrfToken) {
                    setCredMessage('<div class="alert alert-danger mb-0">No se encontró el token CSRF. Recarga la página.</div>');
                    return;
                }

                const fd = new FormData();
                fd.append('csrf_token', csrfToken);
                if (certInput && certInput.files && certInput.files[0]) fd.append('certificate_wizard', certInput.files[0]);
                if (imgInput && imgInput.files && imgInput.files[0]) fd.append('wizard_signature_image', imgInput.files[0]);
                if (pwdInput && (pwdInput.value || '').trim()) fd.append('signature_password', (pwdInput.value || '').trim());

                fetch('/firmar-documentos/guardar-perfil', {
                    method: 'POST',
                    body: fd,
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                })
                    .then(r => r.json())
                    .then(resp => {
                        if (resp && resp.success) {
                            setCredMessage('<div class="alert alert-success mb-0">Datos guardados en tu perfil.</div>');
                        } else {
                            setCredMessage(`<div class="alert alert-danger mb-0">${escapeHtml((resp && resp.message) || 'No se pudo guardar.')}</div>`);
                        }
                    })
                    .catch(() => {
                        setCredMessage('<div class="alert alert-danger mb-0">Error al guardar en perfil.</div>');
                    });
            });
        }

        // Validar inputs requeridos
        [certInput, imgInput, pwdInput].forEach(el => {
            if (!el) return;
            el.addEventListener('change', updateButtonState);
            el.addEventListener('input', updateButtonState);
        });

        // Firma AJAX
        if (btn) {
            updateButtonState();

            btn.addEventListener('click', function () {
                clearInvalid();
                setCredMessage('');

                if (btn.disabled) return;
                if (!csrfToken) {
                    setCredMessage('<div class="alert alert-danger mb-0">No se encontró el token CSRF. Recarga la página.</div>');
                    return;
                }

                const fd = new FormData();
                fd.append('csrf_token', csrfToken);
                fd.append('save_to_profile', (saveCheckbox && saveCheckbox.checked) ? 'true' : 'false');
                if (certInput && certInput.files && certInput.files[0]) fd.append('certificate_wizard', certInput.files[0]);
                if (imgInput && imgInput.files && imgInput.files[0]) fd.append('wizard_signature_image', imgInput.files[0]);
                if (pwdInput && (pwdInput.value || '').trim()) fd.append('signature_password', (pwdInput.value || '').trim());

                btn.disabled = true;
                const oldHtml = btn.innerHTML;
                btn.innerHTML = '<i class="fa fa-spinner fa-spin me-2"></i>Firmando...';

                fetch(`/api/workflow-sign/${data.workflow_id}`, {
                    method: 'POST',
                    body: fd,
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                })
                    .then(r => r.json())
                    .then(resp => {
                        if (resp && resp.success) {
                            setCredMessage('<div class="alert alert-success mb-0">Firma completada. La solicitud avanzó en el flujo.</div>');

                            // Quitar de la lista izquierda
                            const item = document.querySelector(`.workflow-item[data-id="${data.workflow_id}"]`);
                            if (item && item.parentNode) item.parentNode.removeChild(item);

                            // Limpiar selección y mostrar vacío
                            workflowCheckboxes.forEach(cb => { cb.checked = false; });
                            showEmpty();
                            return;
                        }

                        // Error
                        const err = (resp && (resp.error || resp.message)) || 'No se pudo firmar.';
                        setCredMessage(`<div class="alert alert-danger mb-0">${escapeHtml(err)}</div>`);
                        if (resp && Array.isArray(resp.missing_fields)) {
                            resp.missing_fields.forEach(markInvalid);
                        }
                    })
                    .catch(() => {
                        setCredMessage('<div class="alert alert-danger mb-0">Error al firmar (red). Intenta de nuevo.</div>');
                    })
                    .finally(() => {
                        btn.innerHTML = oldHtml;
                        updateButtonState();
                    });
            });
        }
    }

    function escapeHtml(str) {
        return (str || '').toString()
            .replace(/&/g, '&')
            .replace(/</g, '<')
            .replace(/>/g, '>')
            .replace(/"/g, '"')
            .replace(/'/g, '&#039;');
    }

    function loadWorkflow(workflowId) {
        showLoading();
        fetch(`/api/workflow-data/${workflowId}`)
            .then(r => r.json())
            .then(data => {
                if (data && data.success) {
                    renderDetails(data);
                } else {
                    rightPanel.innerHTML = `<div class="alert alert-danger">${escapeHtml((data && data.error) || 'Error al cargar datos.')}</div>`;
                }
            })
            .catch(() => {
                rightPanel.innerHTML = `<div class="alert alert-danger">Error al cargar datos del workflow.</div>`;
            });
    }

    if (workflowCheckboxes && workflowCheckboxes.length) {
        workflowCheckboxes.forEach(cb => {
            cb.addEventListener('change', function () {
                if (this.checked) {
                    setSelected(this);
                    loadWorkflow(this.value);
                } else {
                    showEmpty();
                }
            });
        });
    }

    // Si el usuario hace click sobre el item, toggle del checkbox
    if (workflowItems && workflowItems.length) {
        workflowItems.forEach(item => {
            item.addEventListener('click', function (e) {
                if (e.target && (e.target.classList.contains('workflow-checkbox') || e.target.closest('.workflow-checkbox'))) {
                    return; // ya lo manejó el checkbox
                }
                const cb = this.querySelector('.workflow-checkbox');
                if (cb) {
                    cb.checked = true;
                    setSelected(cb);
                    loadWorkflow(cb.value);
                }
            });
        });
    }

    showEmpty();
});
