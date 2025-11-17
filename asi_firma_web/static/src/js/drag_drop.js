document.addEventListener('DOMContentLoaded', function () {
    console.log('Drag and drop script loaded');

    const dropZone = document.getElementById('pdf-drop-zone');
    const fileInput = document.getElementById('pdf-input');
    const filesList = document.getElementById('files-list');

    console.log('Elements found:', { dropZone, fileInput, filesList });

    if (!dropZone || !fileInput || !filesList) {
        console.log('Missing elements, exiting');
        return;
    }

    let dragCounter = 0;
    let selectedFiles = [];

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

    // Validación antes del envío
    const form = dropZone.closest('form');
    if (form) {
      form.addEventListener('submit', (e) => {
        if (selectedFiles.length === 0) {
          e.preventDefault();
          alert('Debes seleccionar al menos un archivo PDF.');
          return false;
        }
      });
    }

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
      });
    }

    // Nombre de archivo para certificado
    const certificateInput = document.getElementById('certificate-input');
    const certificateName = document.getElementById('certificate-name');
    if (certificateInput && certificateName) {
      certificateInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        certificateName.textContent = file ? file.name : '';
      });
    }

    console.log('Script initialization complete');
  });