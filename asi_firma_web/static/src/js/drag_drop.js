document.addEventListener('DOMContentLoaded', function () {
    console.log('Drag and drop script loaded');

    const dropZone = document.getElementById('pdf-drop-zone');
    const fileInput = document.getElementById('pdf-input');
    const filesList = document.getElementById('files-list');
    const form = dropZone ? dropZone.closest('form') : null;

    console.log('Elements found:', { dropZone, fileInput, filesList, form });

    if (!dropZone || !fileInput || !filesList || !form) {
        console.log('Missing elements, exiting');
        return;
    }

    let dragCounter = 0;
    let selectedFiles = [];

    // Función para validar campos requeridos y habilitar/deshabilitar botón
    function validateForm() {
        const submitButton = document.querySelector('button[type="submit"]');
        if (!submitButton) return;

        let isValid = true;

        // Validar PDF seleccionado
        if (selectedFiles.length === 0) {
            isValid = false;
        }

        // Validar etiqueta/rol de firma
        const signatureRole = document.querySelector('select[name="signature_role"]');
        if (!signatureRole || !signatureRole.value) {
            isValid = false;
        }

        // Verificar si los campos están en modo de modificación
        const isModifyingCert = document.querySelector('.certificate-input-group')?.style.display === 'block';
        const isModifyingPassword = document.querySelector('.password-input-group')?.style.display === 'block';
        const isModifyingImage = document.querySelector('.image-input-group')?.style.display === 'block';
        
        // Verificar si hay datos del perfil disponibles
        let hasProfileCert = false;
        let hasProfileImage = false;
        let hasProfilePassword = false;
        
        // Buscar mensajes que indican datos del perfil
        const profileAlert = document.querySelector('.alert.alert-info');
        if (profileAlert) {
            const alertText = profileAlert.textContent;
            hasProfileCert = alertText.includes('Se utilizará el certificado almacenado');
            hasProfileImage = alertText.includes('Se utilizará la imagen de firma almacenada');
            hasProfilePassword = alertText.includes('Se utilizará la contraseña almacenada');
        }
        
        // Verificar si los campos están visibles y necesitan datos
        const certificateInput = document.getElementById('certificate-input');
        const passwordInput = document.querySelector('input[name="signature_password"]');
        const signatureImageInput = document.getElementById('signature-image');
        
        // Validar certificado
        if (certificateInput && certificateInput.offsetParent !== null) {
            if (!certificateInput.files || certificateInput.files.length === 0) {
                // Si está en modo de modificación, es requerido
                if (isModifyingCert) {
                    isValid = false;
                }
                // Si no está modificando y no hay perfil, es requerido
                else if (!hasProfileCert) {
                    isValid = false;
                }
            }
        }

        // Validar contraseña
        if (passwordInput && passwordInput.offsetParent !== null) {
            if (!passwordInput.value || passwordInput.value.trim() === '') {
                // Si está en modo de modificación, es requerido
                if (isModifyingPassword) {
                    isValid = false;
                }
                // Si no está modificando y no hay perfil, es requerido
                else if (!hasProfilePassword) {
                    isValid = false;
                }
            }
        }

        // Validar imagen de firma
        if (signatureImageInput && signatureImageInput.offsetParent !== null) {
            if (!signatureImageInput.files || signatureImageInput.files.length === 0) {
                // Si está en modo de modificación, es requerido
                if (isModifyingImage) {
                    isValid = false;
                }
                // Si no está modificando y no hay perfil, es requerido
                else if (!hasProfileImage) {
                    isValid = false;
                }
            }
        }

        // Habilitar/deshabilitar botón y actualizar mensaje
        if (isValid) {
            submitButton.disabled = false;
            submitButton.innerHTML = '<i class="fa fa-pencil"></i> Firmar';
            submitButton.classList.remove('btn-secondary');
            submitButton.classList.add('btn-primary');
        } else {
            submitButton.disabled = true;
            submitButton.innerHTML = '<i class="fa fa-lock"></i> Completar campos requeridos';
            submitButton.classList.remove('btn-primary');
            submitButton.classList.add('btn-secondary');
        }

        return isValid;
    }

    // Funciones de utilidad
    function formatFileSize(bytes) {
      if (bytes === 0) return '0 Bytes';
      const k = 1024;
      const sizes = ['Bytes', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function updateFilesList() {
      filesList.innerHTML = '';
      selectedFiles.forEach((file, index) => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.innerHTML = `
          <div class="file-name">${file.name}</div>
          <div class="file-size">${formatFileSize(file.size)}</div>
          <div class="remove-file" data-index="${index}">×</div>
        `;
        filesList.appendChild(fileItem);
      });

      // Actualizar el input file
      const dt = new DataTransfer();
      selectedFiles.forEach(file => dt.items.add(file));
      try {
        fileInput.files = dt.files;
        console.log('Files set successfully');
      } catch (error) {
        console.error('Error setting files:', error);
      }
      
      // Validar formulario después de actualizar archivos
      validateForm();
    }

    function addFiles(files) {
      const pdfFiles = Array.from(files).filter(file =>
        file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
      );

      if (pdfFiles.length === 0) {
        alert('Solo se permiten archivos PDF.');
        return;
      }

      // Evitar duplicados
      const newFiles = pdfFiles.filter(newFile =>
        !selectedFiles.some(existingFile => existingFile.name === newFile.name && existingFile.size === newFile.size)
      );

      selectedFiles = selectedFiles.concat(newFiles);
      updateFilesList();
    }

    function removeFile(index) {
      selectedFiles.splice(index, 1);
      updateFilesList();
    }
    
    // Función para actualizar los mensajes del perfil desde el servidor
    async function updateProfileMessages() {
        try {
            const response = await fetch('/firmar-documentos', {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (response.ok) {
                const html = await response.text();
                // Crear un elemento temporal para parsear el HTML
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = html;
                
                // Actualizar mensajes existentes sin moverlos de posición
                const existingAlerts = document.querySelectorAll('.alert.alert-info');
                const newAlerts = tempDiv.querySelectorAll('.alert.alert-info');
                
                existingAlerts.forEach((existingAlert, index) => {
                    if (newAlerts[index]) {
                        // Actualizar el contenido del mensaje existente
                        existingAlert.innerHTML = newAlerts[index].innerHTML;
                    }
                });
                
                // Si hay más mensajes nuevos que existentes, agregarlos en su posición correcta
                if (newAlerts.length > existingAlerts.length) {
                    for (let i = existingAlerts.length; i < newAlerts.length; i++) {
                        const newAlert = newAlerts[i].cloneNode(true);
                        // Buscar el contenedor del campo correspondiente
                        if (newAlert.textContent.includes('certificado almacenado')) {
                            const certificateGroup = document.querySelector('.col-12:has(#certificate-input), .col-12:has(.certificate-input-group)');
                            if (certificateGroup) {
                                certificateGroup.appendChild(newAlert);
                            }
                        } else if (newAlert.textContent.includes('imagen de firma almacenada')) {
                            const imageGroup = document.querySelector('.col-md-3:last-child');
                            if (imageGroup) {
                                imageGroup.appendChild(newAlert);
                            }
                        } else if (newAlert.textContent.includes('contraseña almacenada')) {
                            const passwordGroup = document.querySelector('.col-12:has(input[name="signature_password"])');
                            if (passwordGroup) {
                                passwordGroup.appendChild(newAlert);
                            }
                        }
                    }
                }
                
                // Buscar campos ocultos en la respuesta
                const hiddenInputs = tempDiv.querySelectorAll('input[type="hidden"]');
                const container = document.querySelector('.card-body') || document.body;
                
                hiddenInputs.forEach(hiddenInput => {
                    // Verificar si ya existe un input con el mismo nombre
                    const existing = document.querySelector(`input[name="${hiddenInput.name}"]`);
                    if (existing) {
                        existing.value = hiddenInput.value;
                    } else {
                        container.appendChild(hiddenInput.cloneNode(true));
                    }
                });
                
                // Actualizar la visibilidad de campos basado en datos del perfil
                const bodyHtml = tempDiv.innerHTML;
                const hasCert = bodyHtml.includes('Se utilizará el certificado almacenado');
                const hasImage = bodyHtml.includes('Se utilizará la imagen de firma almacenada');
                const hasPassword = bodyHtml.includes('Se utilizará la contraseña almacenada');
                
                // Mostrar/ocultar campos basados en datos del perfil
                const certificateInput = document.getElementById('certificate-input');
                const signatureImageInput = document.getElementById('signature-image');
                const passwordInput = document.querySelector('input[name="signature_password"]');
                
                // Solo ocultar campos si NO están en modo de modificación
                const isModifyingCert = document.querySelector('.certificate-input-group')?.style.display === 'block';
                const isModifyingPassword = document.querySelector('.password-input-group')?.style.display === 'block';
                const isModifyingImage = document.querySelector('.image-input-group')?.style.display === 'block';
                
                if (certificateInput) {
                    const certificateGroup = certificateInput.closest('.form-group');
                    if (certificateGroup) {
                        if (hasCert && !isModifyingCert) {
                            certificateGroup.style.display = 'none';
                        } else {
                            certificateGroup.style.display = 'block';
                        }
                    }
                }
                
                if (signatureImageInput) {
                    const signatureGroup = signatureImageInput.closest('.form-group');
                    if (signatureGroup) {
                        if (hasImage && !isModifyingImage) {
                            signatureGroup.style.display = 'none';
                        } else {
                            signatureGroup.style.display = 'block';
                        }
                    }
                }
                
                if (passwordInput) {
                    const passwordGroup = passwordInput.closest('.form-group');
                    if (passwordGroup) {
                        if (hasPassword && !isModifyingPassword) {
                            passwordGroup.style.display = 'none';
                        } else {
                            passwordGroup.style.display = 'block';
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Error al actualizar mensajes del perfil:', error);
        }
    }
    
    // Función para resetear el formulario
    async function resetForm() {
      // Limpiar archivos seleccionados
      selectedFiles = [];
      updateFilesList();
      
      // Resetear campos de archivo
      const pdfInput = document.getElementById('pdf-input');
      const certificateInput = document.getElementById('certificate-input');
      const signatureImageInput = document.getElementById('signature-image');
      
      if (pdfInput) pdfInput.value = '';
      if (certificateInput) {
        certificateInput.value = '';
        const certificateName = document.getElementById('certificate-name');
        if (certificateName) certificateName.textContent = '';
      }
      if (signatureImageInput) {
        signatureImageInput.value = '';
        const signatureName = document.getElementById('signature-name');
        const signaturePreview = document.getElementById('signature-preview');
        if (signatureName) signatureName.textContent = '';
        if (signaturePreview) {
          signaturePreview.style.display = 'none';
          signaturePreview.src = '';
        }
      }
      
      // Resetear select de rol de firma
      const signatureRole = document.querySelector('select[name="signature_role"]');
      if (signatureRole) signatureRole.value = '';
      
      // Resetear contraseña
      const passwordInput = document.querySelector('input[name="signature_password"]');
      if (passwordInput) passwordInput.value = '';
      
      // Resetear checkboxes
      const checkboxes = form.querySelectorAll('input[type="checkbox"]');
      checkboxes.forEach(checkbox => checkbox.checked = false);
      
      // Resetear select de posición
      const positionSelect = document.querySelector('select[name="signature_position"]');
      if (positionSelect) positionSelect.value = 'derecha';
      
      // Limpiar campos de modificación y restaurar alertas del perfil
      const modifyButtons = document.querySelectorAll('.modify-certificate-btn, .modify-password-btn, .modify-image-btn');
      modifyButtons.forEach(button => {
          const buttonType = button.classList.contains('modify-certificate-btn') ? 'certificate' :
                           button.classList.contains('modify-password-btn') ? 'password' : 'image';
          
          const alertDiv = button.previousElementSibling;
          const inputGroup = button.nextElementSibling;
          
          // Ocultar campos de entrada y mostrar alertas
          inputGroup.style.display = 'none';
          alertDiv.style.display = 'block';
          button.innerHTML = `<i class="fa fa-edit"></i> Modificar ${buttonType}`;
          button.classList.remove('btn-outline-secondary');
          button.classList.add('btn-outline-primary');
          
          // Limpiar valores de campos
          if (buttonType === 'certificate') {
              const certInput = inputGroup.querySelector('#certificate-input');
              const certName = document.getElementById('certificate-name');
              if (certInput) certInput.value = '';
              if (certName) certName.textContent = '';
          } else if (buttonType === 'password') {
              const passwordInput = inputGroup.querySelector('input[name="signature_password"]');
              if (passwordInput) passwordInput.value = '';
          } else if (buttonType === 'image') {
              const imageInput = inputGroup.querySelector('#signature-image');
              const imageName = document.getElementById('signature-name');
              const imagePreview = document.getElementById('signature-preview');
              if (imageInput) imageInput.value = '';
              if (imageName) imageName.textContent = '';
              if (imagePreview) {
                  imagePreview.style.display = 'none';
                  imagePreview.src = '';
              }
          }
          
          // Remover campos ocultos
          removeHiddenField(buttonType);
      });
      
      // NO hacer petición al servidor, solo validar con los mensajes existentes
      // Esperar un momento para que se actualicen los mensajes
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // Revalidar formulario con los datos del perfil actualizados
      validateForm();
    }
    
    // Función para mostrar mensaje de éxito
    function showSuccessMessage(message) {
      showAlert(message, 'success');
    }
    
    // Función para mostrar mensaje de error
    function showErrorMessage(message) {
      showAlert(message, 'danger');
    }
    
    // Función genérica para mostrar alertas
    function showAlert(message, type = 'info') {
      const notificationContainer = document.getElementById('notification-container');
      
      if (notificationContainer) {
        // Remover mensajes previos del mismo tipo (máximo 3)
        const existingAlerts = notificationContainer.querySelectorAll(`.alert-${type}`);
        if (existingAlerts.length >= 3) {
          existingAlerts[0].remove(); // Remover el más antiguo
        }
        
        // Crear nuevo mensaje
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show mb-2 shadow`;
        alertDiv.style.cssText = 'min-width: 280px; max-width: 350px; word-wrap: break-word;';
        
        const iconClass = type === 'success' ? 'fa-check-circle' :
                         type === 'danger' ? 'fa-exclamation-triangle' :
                         type === 'warning' ? 'fa-exclamation-circle' : 'fa-info-circle';
        
        alertDiv.innerHTML = `
          <i class="fa ${iconClass}"></i>
          <span class="ms-2">${message}</span>
          <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        // Insertar en el contenedor de notificaciones (apilar verticalmente)
        notificationContainer.appendChild(alertDiv);
        
        // Auto-ocultar después de 10 segundos para errores, 8 para éxito
        const timeout = type === 'danger' ? 10000 : 8000;
        setTimeout(() => {
          if (alertDiv && alertDiv.parentNode) {
            alertDiv.remove();
          }
        }, timeout);
      } else {
        // Fallback si no existe el contenedor
        const container = document.querySelector('.container');
        if (container) {
          const header = container.querySelector('h2');
          if (header) {
            header.insertAdjacentElement('afterend', alertDiv);
          }
        }
      }
    }

    // Event listeners
    dropZone.addEventListener('click', () => {
      fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
      addFiles(e.target.files);
    });

    // Drag and drop events
    dropZone.addEventListener('dragenter', (e) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounter++;
      dropZone.classList.add('is-dragover');
    });

    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.stopPropagation();
    });

    dropZone.addEventListener('dragleave', (e) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounter--;
      if (dragCounter === 0) {
        dropZone.classList.remove('is-dragover');
      }
    });

    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('is-dragover');
      dragCounter = 0;

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        addFiles(files);
      }
    });

    // Remover archivos
    filesList.addEventListener('click', (e) => {
      e.stopPropagation();
      if (e.target.classList.contains('remove-file')) {
        const index = parseInt(e.target.dataset.index);
        removeFile(index);
      }
    });

    // Función para verificar qué datos nuevos se proporcionan en el formulario
    function getNewFormData() {
        const newFormData = [];
        
        // Verificar si hay datos del perfil disponibles
        let hasProfileCert = false;
        let hasProfileImage = false;
        let hasProfilePassword = false;
        
        const profileAlert = document.querySelector('.alert.alert-info');
        if (profileAlert) {
            const alertText = profileAlert.textContent;
            hasProfileCert = alertText.includes('Se utilizará el certificado almacenado');
            hasProfileImage = alertText.includes('Se utilizará la imagen de firma almacenada');
            hasProfilePassword = alertText.includes('Se utilizará la contraseña almacenada');
        }
        
        // Verificar si los campos están en modo de modificación
        const isModifyingCert = document.querySelector('.certificate-input-group')?.style.display === 'block';
        const isModifyingPassword = document.querySelector('.password-input-group')?.style.display === 'block';
        const isModifyingImage = document.querySelector('.image-input-group')?.style.display === 'block';
        
        // Verificar certificado
        const certificateInput = document.getElementById('certificate-input');
        if (certificateInput && certificateInput.offsetParent !== null) {
            if (certificateInput.files && certificateInput.files.length > 0) {
                newFormData.push(`Certificado (.p12): ${certificateInput.files[0].name}`);
            } else if (isModifyingCert && !hasProfileCert) {
                newFormData.push('Se requiere un certificado de firma');
            }
        }
        
        // Verificar imagen
        const signatureImageInput = document.getElementById('signature-image');
        if (signatureImageInput && signatureImageInput.offsetParent !== null) {
            if (signatureImageInput.files && signatureImageInput.files.length > 0) {
                newFormData.push(`Imagen de firma: ${signatureImageInput.files[0].name}`);
            } else if (isModifyingImage && !hasProfileImage) {
                newFormData.push('Se requiere una imagen de firma');
            }
        }
        
        // Verificar contraseña
        const passwordInput = document.querySelector('input[name="signature_password"]');
        if (passwordInput && passwordInput.offsetParent !== null) {
            if (passwordInput.value && passwordInput.value.trim() !== '') {
                newFormData.push('Contraseña del certificado');
            } else if (isModifyingPassword && !hasProfilePassword) {
                newFormData.push('Se requiere la contraseña del certificado');
            }
        }
        
        return newFormData;
    }
    
    // Función para guardar datos en perfil
    async function saveToProfile() {
        try {
            const formData = new FormData();
            
            // Agregar archivos si existen
            const certificateInput = document.getElementById('certificate-input');
            if (certificateInput && certificateInput.files.length > 0) {
                formData.append('certificate_wizard', certificateInput.files[0]);
            }
            
            const signatureImageInput = document.getElementById('signature-image');
            if (signatureImageInput && signatureImageInput.files.length > 0) {
                formData.append('wizard_signature_image', signatureImageInput.files[0]);
            }
            
            const passwordInput = document.querySelector('input[name="signature_password"]');
            if (passwordInput && passwordInput.value.trim() !== '') {
                formData.append('signature_password', passwordInput.value);
            }
            
            const response = await fetch('/firmar-documentos/guardar-perfil', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            const result = await response.json();
            return result.success;
        } catch (error) {
            console.error('Error al guardar en perfil:', error);
            return false;
        }
    }
    
    // Función para realizar la firma
    async function submitFormData(saveToProfile = false) {
        const submitButton = document.querySelector('button[type="submit"]');
        
        // Mostrar indicador de carga
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Firmando documentos...';
            submitButton.classList.remove('btn-primary');
            submitButton.classList.add('btn-secondary');
        }
        
        try {
            // Crear FormData
            const formData = new FormData(form);
            formData.append('save_to_profile', saveToProfile);
            
            console.log('Enviando formulario a:', form.action);
            
            // Realizar petición AJAX
            const response = await fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            console.log('Respuesta recibida:', response.status, response.headers.get('content-type'));
            
            // Manejar respuestas de redirección (303, 302, etc.) - ERROR
            if (response.status >= 300 && response.status < 400) {
                const location = response.headers.get('Location');
                if (location && location.includes('/firmar-documentos?msg=')) {
                    // Extraer mensaje del URL
                    const urlParams = new URLSearchParams(location.split('?')[1]);
                    const msg = urlParams.get('msg');
                    if (msg) {
                        const decodedMsg = decodeURIComponent(msg);
                        showErrorMessage(decodedMsg);
                        return; // NO RESETEAR
                    }
                }
                // Si no podemos extraer el mensaje, mostrar error genérico
                showErrorMessage('Error al procesar la solicitud. Por favor, intente nuevamente.');
                return; // NO RESETEAR
            }
            
            // Verificar códigos de estado HTTP de error
            if (response.status === 500) {
                // Error interno del servidor - NO RESETEAR
                try {
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        const jsonData = await response.json();
                        showErrorMessage(jsonData.error || 'Error interno del servidor. Por favor, intente más tarde.');
                    } else {
                        const html = await response.text();
                        let errorMessage = 'Error interno del servidor. Por favor, intente más tarde.';
                        
                        // Intentar extraer mensaje de error del HTML
                        const tempDiv = document.createElement('div');
                        tempDiv.innerHTML = html;
                        const errorAlert = tempDiv.querySelector('.alert-danger, .alert-error');
                        if (errorAlert) {
                            errorMessage = errorAlert.textContent.trim();
                        }
                        
                        showErrorMessage(errorMessage);
                    }
                } catch (e) {
                    showErrorMessage('Error interno del servidor. Por favor, intente más tarde.');
                }
                return; // NO RESETEAR
            }
            
            if (response.status === 400) {
                // Error de datos incorrectos - NO RESETEAR
                try {
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        const jsonData = await response.json();
                        showErrorMessage(jsonData.error || 'Los datos enviados no son válidos. Verifique que todos los campos estén correctos.');
                    } else {
                        const html = await response.text();
                        let errorMessage = 'Los datos enviados no son válidos. Verifique que todos los campos estén correctos.';
                        
                        const tempDiv = document.createElement('div');
                        tempDiv.innerHTML = html;
                        const errorAlert = tempDiv.querySelector('.alert-danger, .alert-error');
                        if (errorAlert) {
                            errorMessage = errorAlert.textContent.trim();
                        }
                        
                        showErrorMessage(errorMessage);
                    }
                } catch (e) {
                    showErrorMessage('Los datos enviados no son válidos. Verifique que todos los campos estén correctos.');
                }
                return; // NO RESETEAR
            }
            
            if (response.status === 413) {
                showErrorMessage('El archivo es demasiado grande. Por favor, use archivos más pequeños.');
                return; // NO RESETEAR
            }
            
            if (response.status === 415) {
                showErrorMessage('Tipo de archivo no soportado. Solo se permiten archivos PDF.');
                return; // NO RESETEAR
            }
            
            // Verificar si la respuesta indica éxito por header
            if (response.headers.get('X-Form-Reset') === 'success') {
                // Éxito confirmado - resetear formulario y mostrar mensaje
                setTimeout(() => {
                    resetForm();
                    showSuccessMessage('¡Documentos firmados exitosamente!');
                }, 1500);
                
                // Obtener el archivo y forzar descarga
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                
                // Determinar nombre del archivo
                let filename = 'documentos_firmados.zip';
                const contentDisposition = response.headers.get('Content-Disposition');
                if (contentDisposition) {
                    const match = contentDisposition.match(/filename="(.+)"/);
                    if (match) filename = match[1];
                }
                
                console.log('Descargando archivo:', filename);
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
            } else {
                // La respuesta no tiene header de éxito, verificar contenido
                
                // 1. Verificar si es HTML con mensajes
                const contentType = response.headers.get('content-type');
                if (contentType && contentType.includes('text/html')) {
                    const html = await response.text();
                    console.log('Respuesta HTML recibida:', html.substring(0, 200));
                    
                    // Buscar mensajes de error en el HTML
                    const tempDiv = document.createElement('div');
                    tempDiv.innerHTML = html;
                    
                    const errorAlert = tempDiv.querySelector('.alert-danger, .alert-error');
                    if (errorAlert) {
                        showErrorMessage(errorAlert.textContent.trim());
                        return; // NO RESETEAR
                    }
                    
                    const successAlert = tempDiv.querySelector('.alert.alert-info, .alert.alert-success');
                    if (successAlert) {
                        showSuccessMessage(successAlert.textContent.trim());
                        resetForm(); // Solo resetear en éxito confirmado
                    } else {
                        showSuccessMessage('Procesamiento completado');
                        resetForm(); // Solo resetear en éxito confirmado
                    }
                } else if (contentType && contentType.includes('application/json')) {
                    // 2. Verificar respuesta JSON para errores
                    try {
                        const jsonData = await response.json();
                        if (jsonData.error || jsonData.message) {
                            showErrorMessage(jsonData.error || jsonData.message);
                            return; // NO RESETEAR
                        }
                    } catch (e) {
                        showErrorMessage('Respuesta inválida del servidor');
                        return; // NO RESETEAR
                    }
                } else if (contentType && (contentType.includes('application/pdf') || contentType.includes('application/zip'))) {
                    // 3. Procesar archivos (asumiendo éxito)
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    
                    // Intentar obtener nombre del archivo
                    let filename = 'documentos_firmados.zip';
                    const contentDisposition = response.headers.get('Content-Disposition');
                    if (contentDisposition) {
                        const match = contentDisposition.match(/filename="(.+)"/);
                        if (match) filename = match[1];
                    }
                    
                    console.log('Descargando archivo (binario):', filename);
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                    
                    showSuccessMessage('¡Documentos firmados exitosamente!');
                    resetForm(); // Solo resetear después de descarga exitosa
                } else {
                    // 4. Tipo de respuesta desconocido
                    const html = await response.text();
                    if (html.includes('error') || html.includes('Error')) {
                        showErrorMessage('Error al procesar la solicitud. Revise los datos e intente nuevamente.');
                        return; // NO RESETEAR
                    } else {
                        showSuccessMessage('Procesamiento completado');
                        resetForm(); // Solo resetear si no hay errores evidentes
                    }
                }
            }
            
        } catch (error) {
            console.error('Error en la firma:', error);
            
            // Manejar diferentes tipos de errores
            if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
                showErrorMessage('Error de conexión. Verifique su conexión a internet e intente nuevamente.');
            } else if (error.name === 'TypeError' && error.message.includes('NetworkError')) {
                showErrorMessage('Error de red. Verifique su conexión e intente nuevamente.');
            } else if (error.name === 'AbortError') {
                showErrorMessage('La operación fue cancelada. Intente nuevamente.');
            } else if (error.message) {
                // Mostrar mensaje de error específico si está disponible
                showErrorMessage(`Error al procesar la firma: ${error.message}`);
            } else {
                showErrorMessage('Error desconocido al procesar la firma. Por favor, intente nuevamente.');
            }
        } finally {
            // Restaurar botón
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.innerHTML = '<i class="fa fa-pencil"></i> Firmar';
                submitButton.classList.remove('btn-secondary');
                submitButton.classList.add('btn-primary');
            }
        }
    }
    
    // Validación y envío del formulario con confirmación
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      if (!validateForm()) {
        return false;
      }
      
      // Verificar qué datos nuevos se proporcionan en el formulario
      const newFormData = getNewFormData();
      
      // Si se proporcionaron archivos o contraseña nuevos, mostrar confirmación
      if (newFormData.length > 0) {
          const dataText = newFormData.join('\n');
          const confirmMessage = `Has proporcionado los siguientes datos:\n${dataText}\n\n¿Deseas guardar estos datos en tu perfil para futuras firmas?\n\nBeneficios:\n• No necesitarás subir los archivos en cada firma\n• Proceso de firma más rápido\n• Tus datos estarán seguros en tu cuenta`;
          
          const shouldSaveToProfile = confirm(confirmMessage);
          
          if (shouldSaveToProfile) {
              // Guardar datos en perfil y proceder
              const saveSuccess = await saveToProfile();
              
              if (saveSuccess) {
                  await submitFormData(true);
                  showSuccessMessage('¡Datos guardados en tu perfil y documentos firmados exitosamente!');
              } else {
                  await submitFormData(false);
                  showSuccessMessage('Documentos firmados. Error al guardar en perfil.');
              }
          } else {
              // Proceder solo con la firma
              await submitFormData(false);
          }
      } else {
          // Solo se usan datos del perfil, proceder directamente
          await submitFormData(false);
      }
    });

    // Preview de imagen de firma
    const signatureInput = document.getElementById('signature-image');
    const signaturePreview = document.getElementById('signature-preview');
    const signatureName = document.getElementById('signature-name');
    if (signatureInput && signaturePreview) {
      signatureInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
          const reader = new FileReader();
          reader.onload = (e) => {
            signaturePreview.src = e.target.result;
            signaturePreview.style.display = 'block';
          };
          reader.readAsDataURL(file);
          if (signatureName) signatureName.textContent = file.name;
        } else {
          signaturePreview.style.display = 'none';
          if (signatureName) signatureName.textContent = '';
        }
        // Validar formulario después de cambiar imagen
        validateForm();
      });
    }

    // Nombre de archivo para certificado
    const certificateInputFile = document.getElementById('certificate-input');
    const certificateName = document.getElementById('certificate-name');
    if (certificateInputFile && certificateName) {
      certificateInputFile.addEventListener('change', (e) => {
        const file = e.target.files[0];
        certificateName.textContent = file ? file.name : '';
        // Validar formulario después de cambiar certificado
        validateForm();
      });
    }

    // Validar rol de firma
    const signatureRoleSelect = document.querySelector('select[name="signature_role"]');
    if (signatureRoleSelect) {
      signatureRoleSelect.addEventListener('change', validateForm);
    }

    // Validar contraseña
    const passwordInput = document.querySelector('input[name="signature_password"]');
    if (passwordInput) {
      passwordInput.addEventListener('input', validateForm);
    }

    // Funcionalidad de botones de modificar
    const modifyButtons = document.querySelectorAll('.modify-certificate-btn, .modify-password-btn, .modify-image-btn');
    
    modifyButtons.forEach(button => {
        button.addEventListener('click', function() {
            const buttonType = this.classList.contains('modify-certificate-btn') ? 'certificate' :
                             this.classList.contains('modify-password-btn') ? 'password' : 'image';
            
            const alertDiv = this.previousElementSibling;
            const inputGroup = this.nextElementSibling;
            
            if (inputGroup.style.display === 'none') {
                // Mostrar el campo de entrada y ocultar el mensaje del perfil
                inputGroup.style.display = 'block';
                alertDiv.style.display = 'none';
                this.innerHTML = '<i class="fa fa-times"></i> Cancelar modificación';
                this.classList.remove('btn-outline-primary');
                this.classList.add('btn-outline-secondary');
                
                // Agregar el campo oculto al formulario para evitar que se use el del perfil
                addHiddenField(buttonType);
            } else {
                // Ocultar el campo de entrada y mostrar el mensaje del perfil
                inputGroup.style.display = 'none';
                alertDiv.style.display = 'block';
                this.innerHTML = `<i class="fa fa-edit"></i> Modificar ${buttonType}`;
                this.classList.remove('btn-outline-secondary');
                this.classList.add('btn-outline-primary');
                
                // Remover el campo oculto del formulario
                removeHiddenField(buttonType);
            }
            
            // Revalidar formulario después del cambio
            setTimeout(() => {
                validateForm();
            }, 100);
        });
    });
    
    // Función para agregar campos ocultos al formulario
    function addHiddenField(type) {
        const hiddenFieldName = `override_${type}`;
        let hiddenField = document.querySelector(`input[name="${hiddenFieldName}"]`);
        
        if (!hiddenField) {
            hiddenField = document.createElement('input');
            hiddenField.type = 'hidden';
            hiddenField.name = hiddenFieldName;
            hiddenField.value = '1';
            form.appendChild(hiddenField);
        }
    }
    
    // Función para remover campos ocultos del formulario
    function removeHiddenField(type) {
        const hiddenFieldName = `override_${type}`;
        const hiddenField = document.querySelector(`input[name="${hiddenFieldName}"]`);
        if (hiddenField) {
            hiddenField.remove();
        }
    }

    // Validación inicial
    validateForm();

    console.log('Script initialization complete');
    
    // Verificar si hay mensajes en la URL (después de redirección)
    const urlParams = new URLSearchParams(window.location.search);
    const message = urlParams.get('msg');
    if (message) {
      const decodedMessage = decodeURIComponent(message);
      if (decodedMessage.includes('Error') || decodedMessage.includes('error')) {
        showErrorMessage(decodedMessage);
      } else {
        showSuccessMessage(decodedMessage);
      }
      // Limpiar la URL (quitar el parámetro msg)
      const newUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
      window.history.replaceState({}, document.title, newUrl);
    }
  });