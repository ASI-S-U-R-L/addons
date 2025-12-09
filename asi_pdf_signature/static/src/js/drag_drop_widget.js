odoo.define('asi_pdf_signature.drag_drop_widget', function (require) {
  'use strict';
  const domReady = require('web.dom_ready');

  // ---------- UI helpers ----------
  function showProgress(area, filesCount) {
    const box = area.querySelector('.asi-dnd__progress');
    const label = area.querySelector('.asi-progress__text');
    if (box) box.style.display = '';
    if (label) label.textContent = `Subiendo ${filesCount} archivo(s)…`;
    area.classList.add('is-loading');
    setPercent(area, 10);
  }
  function setPercent(area, pct, text) {
    const bar = area.querySelector('.asi-progress__bar');
    const label = area.querySelector('.asi-progress__text');
    if (bar) {
      bar.style.opacity = '1';
      bar.style.transition = 'width .15s ease';
      bar.style.width = Math.max(0, Math.min(100, pct)) + '%';
    }
    if (text != null && label) label.textContent = text;
  }
  function finishAndReset(area, filesCount) {
    setPercent(area, 100, `¡Listo! ${filesCount} archivo(s) añadido(s)`);
    setTimeout(() => {
      const box = area.querySelector('.asi-dnd__progress');
      const bar = area.querySelector('.asi-progress__bar');
      const label = area.querySelector('.asi-progress__text');
      if (bar) { bar.style.width = '0%'; bar.style.opacity = '0'; }
      if (label) label.textContent = 'Subiendo…';
      if (box) box.style.display = 'none';
      area.classList.remove('is-loading');
      area.dataset.uploading = '0';
    }, 600);
  }

  // Nueva función: progreso basado en tiempo estimado
  function startTimeBasedProgress(area, filesCount, input) {
    const ESTIMATED_TIME_PER_FILE = 800; // ms por archivo
    const totalEstimatedTime = filesCount * ESTIMATED_TIME_PER_FILE;
    const startTime = Date.now();

    const progressInterval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(95, (elapsed / totalEstimatedTime) * 100); // Máximo 95% hasta que termine realmente

      setPercent(area, progress);

      if (elapsed >= totalEstimatedTime) {
        clearInterval(progressInterval);
        // Verificar si realmente terminó o continuar esperando
        checkIfReallyFinished(area, filesCount, input);
      }
    }, 100);

    function checkIfReallyFinished(area, filesCount, input) {
      // Hacer una verificación final después del tiempo estimado
      const finalCheckInterval = setInterval(() => {
        const container = getO2mContainer(area);
        const tbody = getTBodyFrom(container);
        const currentRows = countDataRows(tbody);

        if (currentRows >= filesCount) {
          clearInterval(finalCheckInterval);
          finishAndReset(area, filesCount);
        }
      }, 200);

      // Timeout de seguridad
      setTimeout(() => {
        clearInterval(finalCheckInterval);
        finishAndReset(area, filesCount);
      }, 10000); // 10 segundos máximo después del tiempo estimado
    }
  }

  // ---------- Utils (adaptados a tu DOM) ----------
  function getO2mContainer(area) {
    const form = area.closest('.o_form_view') || document;
    // Preferimos exactamente tu estructura:
    return form.querySelector('div.o_field_widget.o_field_one2many[name="document_ids"]')
        || form.querySelector('.o_field_x2many[name="document_ids"]')
        || form.querySelector('.o_field_x2many_list');
  }
  function getTBodyFrom(container) {
    // Dentro de .o_list_renderer hay <table class="o_list_table"> … <tbody class="ui-sortable">
    return container ? container.querySelector('.o_list_renderer table.o_list_table tbody') : null;
  }
  function countDataRows(tbody) {
    if (!tbody) return 0;
    // En tu captura, las filas de datos llevan .o_data_row (la fila "Añadir una línea" no)
    const rows = tbody.querySelectorAll('tr.o_data_row').length;
    if (rows) return rows;
    // Fallback si alguna vista no pone la clase:
    return tbody.querySelectorAll('tr:not(.o_add_record_row)').length;
  }
  function assignFilesToInput(input, files) {
    try {
      const dt = new DataTransfer();
      for (const f of files) dt.items.add(f);
      input.files = dt.files;
    } catch (_) {}
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  domReady(function () {
    let dragCounter = 0;

    // ---------- Highlight ----------
    document.addEventListener('dragenter', function (ev) {
      const area = ev.target.closest('.asi-dnd');
      if (!area) return;
      const hasFiles = ev.dataTransfer && Array.from(ev.dataTransfer.types || []).includes('Files');
      if (!hasFiles) return;
      dragCounter++;
      area.classList.add('is-dragover');
    }, true);

    document.addEventListener('dragover', function (ev) {
      const area = ev.target.closest('.asi-dnd');
      if (!area) return;
      ev.preventDefault();
    }, true);

    document.addEventListener('dragleave', function (ev) {
      const area = ev.target.closest('.asi-dnd');
      if (!area) return;
      dragCounter = Math.max(0, dragCounter - 1);
      if (dragCounter === 0) area.classList.remove('is-dragover');
    }, true);

    // ---------- Core ----------
    function startWatching(area, filesCount, input, isTableEmpty = false) {
      const container = getO2mContainer(area);
      let tbody = getTBodyFrom(container);
      const initial = countDataRows(tbody);
      const targetAdd = filesCount;

      // Seguimiento de actividad real
      let lastAdded = 0;
      let lastChangeTs = Date.now();
      let consecutiveSameCount = 0; // Contador para detectar estabilidad

      // Configuración diferente cuando la tabla está vacía vs con archivos
      const POLL_MS = isTableEmpty ? 20 : 50; // Mucho más agresivo cuando tabla vacía
      const INACTIVE_MS = isTableEmpty ? 4000 : 2000; // Más tiempo cuando tabla vacía
      const MAX_WAIT = 30000;
      const STABLE_COUNT_THRESHOLD = isTableEmpty ? 40 : 20; // Mucha más estabilidad cuando tabla vacía
      const t0 = Date.now();

      const poll = setInterval(() => {
        const now = Date.now();
        const freshContainer = getO2mContainer(area) || container;
        tbody = getTBodyFrom(freshContainer);
        const added = Math.max(0, countDataRows(tbody) - initial);

        // Actualizar progreso si hay cambios
        if (added !== lastAdded) {
          lastAdded = added;
          lastChangeTs = Date.now();
          consecutiveSameCount = 0; // Reset contador de estabilidad
          const progress = 10 + Math.min(added, targetAdd) / targetAdd * 85; // 10→95
          setPercent(area, progress);
        } else {
          consecutiveSameCount++; // Incrementar contador si no hay cambios
        }

        // Verificar si terminó - condición más flexible
        const inputCleared = !input.files || input.files.length === 0;
        const hasReachedTarget = added >= targetAdd;
        const isStable = consecutiveSameCount >= STABLE_COUNT_THRESHOLD;
        const isInactive = inputCleared && (now - lastChangeTs) > INACTIVE_MS;
        const timeout = (now - t0) > MAX_WAIT;

        if (hasReachedTarget || (isStable && inputCleared) || isInactive || timeout) {
          cleanup(true);
        }
      }, POLL_MS);

      function cleanup(finish) {
        clearInterval(poll);
        if (finish) finishAndReset(area, Math.max(1, lastAdded || targetAdd));
      }
      return () => cleanup(false);
    }

    function handleFiles(area, files, { useNativeDrop }) {
      if (area.dataset.uploading === '1') return;
      const input = area.querySelector('input[type="file"]');
      if (!files || !files.length || !input) return;

      area.dataset.uploading = '1';
      area.classList.remove('is-dragover');
      showProgress(area, files.length);

      // Usar progreso basado en tiempo estimado - más confiable
      startTimeBasedProgress(area, files.length, input);

      if (useNativeDrop) {
        // Deja que el widget maneje el drop/click nativo (evitamos duplicados)
        return;
      }
      // Fallback manual si soltó fuera de la dropzone nativa
      assignFilesToInput(input, files);
    }

    // DROP: decide nativo vs fallback
    document.addEventListener('drop', function (ev) {
      const area = ev.target.closest('.asi-dnd');
      if (!area) return;

      const insideNativeDropZone = !!ev.target.closest('.o_drop_zone, .o_m2m_binary_actions, .o_attach');
      const files = (ev.dataTransfer && ev.dataTransfer.files) ? ev.dataTransfer.files : null;

      if (!insideNativeDropZone) {
        ev.preventDefault();
        ev.stopPropagation();
        handleFiles(area, files, { useNativeDrop: false });
      } else {
        handleFiles(area, files, { useNativeDrop: true });
      }

      dragCounter = 0;
      area.classList.remove('is-dragover');
    }, true);

    // CHANGE (diálogo de archivos): solo eventos de usuario
    document.addEventListener('change', function (ev) {
      if (!ev.isTrusted) return;
      const input = ev.target.closest('.asi-dnd input[type="file"]');
      if (!input) return;
      const area = input.closest('.asi-dnd');
      handleFiles(area, input.files, { useNativeDrop: true });
    }, true);
  });
});
