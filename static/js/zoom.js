(function () {
  const zoomShortcutSuffix = ' (atalho: Shift+Z)';
  const editableInputTypes = new Set([
    'color',
    'date',
    'datetime-local',
    'email',
    'month',
    'number',
    'password',
    'search',
    'tel',
    'text',
    'time',
    'url',
    'week'
  ]);

  const isEditableElement = (element) => {
    if (!(element instanceof HTMLElement)) {
      return false;
    }

    if (element.isContentEditable) {
      return true;
    }

    if (element instanceof HTMLInputElement) {
      if (element.readOnly || element.disabled) {
        return false;
      }

      const type = (element.type || 'text').toLowerCase();
      return editableInputTypes.has(type);
    }

    if (element instanceof HTMLTextAreaElement) {
      return !(element.readOnly || element.disabled);
    }

    return false;
  };

  const zoomLens = document.querySelector('.zoom-lens');
  const root = document.documentElement;
  let pointerMoveHandler = null;

  const toggleModalTargets = (isActive) => {
    const modals = document.querySelectorAll('.modal');
    modals.forEach((modal) => {
      modal.classList.toggle('zoom-mode-target', isActive);
    });
  };

  const getActiveModal = () => {
    const opened = Array.from(document.querySelectorAll('.modal.show.zoom-mode-target'));
    return opened[opened.length - 1] || null;
  };

  const resolveZoomElement = (eventTarget) => {
    if (!(eventTarget instanceof Element)) {
      return null;
    }

    const modalFromTarget = eventTarget.closest('.modal.show.zoom-mode-target');
    if (modalFromTarget) {
      return modalFromTarget.querySelector('.modal-dialog') || modalFromTarget;
    }

    if (eventTarget.closest('.modal-backdrop')) {
      const fallbackModal = getActiveModal();
      if (fallbackModal) {
        return fallbackModal.querySelector('.modal-dialog') || fallbackModal;
      }
    }

    const zoomAncestor = eventTarget.closest('.zoom-target');
    if (zoomAncestor) {
      return zoomAncestor;
    }

    const allTargets = document.querySelectorAll('.zoom-target');
    return allTargets.length ? allTargets[0] : null;
  };

  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

  const updateLensPosition = (clientX, clientY) => {
    if (!zoomLens) {
      return;
    }
    root.style.setProperty('--zoom-pointer-x', `${clientX}px`);
    root.style.setProperty('--zoom-pointer-y', `${clientY}px`);
  };

  const updateTransformOrigin = (element, clientX, clientY) => {
    if (!element) {
      return;
    }

    const rect = element.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) {
      return;
    }

    const relativeX = clamp((clientX - rect.left) / rect.width, 0, 1);
    const relativeY = clamp((clientY - rect.top) / rect.height, 0, 1);
    root.style.setProperty('--zoom-origin-x', `${(relativeX * 100).toFixed(2)}%`);
    root.style.setProperty('--zoom-origin-y', `${(relativeY * 100).toFixed(2)}%`);
  };

  const resetLensState = () => {
    root.style.setProperty('--zoom-pointer-x', '-9999px');
    root.style.setProperty('--zoom-pointer-y', '-9999px');
    root.style.setProperty('--zoom-origin-x', '50%');
    root.style.setProperty('--zoom-origin-y', '50%');
  };

  const handlePointerMove = (event) => {
    if (!document.body.classList.contains('zoom-mode-active')) {
      return;
    }

    const { clientX, clientY } = event;
    updateLensPosition(clientX, clientY);
    const zoomElement = resolveZoomElement(event.target);
    if (zoomElement) {
      updateTransformOrigin(zoomElement, clientX, clientY);
    }
  };

  const registerPointerTracking = () => {
    if (pointerMoveHandler) {
      return;
    }
    if (!zoomLens) {
      return;
    }

    pointerMoveHandler = handlePointerMove;
    document.addEventListener('pointermove', pointerMoveHandler);
  };

  const unregisterPointerTracking = () => {
    if (pointerMoveHandler) {
      document.removeEventListener('pointermove', pointerMoveHandler);
      pointerMoveHandler = null;
    }
    resetLensState();
  };

  const applyZoomState = (button, isActive) => {
    document.body.classList.toggle('zoom-mode-active', isActive);
    toggleModalTargets(isActive);
    if (isActive) {
      registerPointerTracking();
    } else {
      unregisterPointerTracking();
    }
    if (!button) {
      return;
    }
    button.setAttribute('aria-pressed', String(isActive));
    const labelBase = isActive ? 'Desativar modo de zoom' : 'Ativar modo de zoom';
    const label = `${labelBase}${zoomShortcutSuffix}`;
    button.setAttribute('aria-label', label);
    button.setAttribute('title', label);
    button.classList.toggle('zoom-toggle-active', isActive);
  };

  const init = () => {
    const zoomToggleButton = document.getElementById('zoomToggleButton');
    if (!zoomToggleButton) {
      return;
    }

    const isInitiallyActive = document.body.classList.contains('zoom-mode-active');
    toggleModalTargets(isInitiallyActive);
    if (isInitiallyActive) {
      registerPointerTracking();
    }

    zoomToggleButton.addEventListener('click', () => {
      const isActive = !document.body.classList.contains('zoom-mode-active');
      applyZoomState(zoomToggleButton, isActive);
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && document.body.classList.contains('zoom-mode-active')) {
        applyZoomState(zoomToggleButton, false);
        return;
      }

      if (event.defaultPrevented) {
        return;
      }

      if (event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey) {
        const isZoomShortcut = event.code === 'KeyZ' || event.key.toLowerCase() === 'z';
        if (isZoomShortcut && !isEditableElement(event.target)) {
          event.preventDefault();
          const isActive = !document.body.classList.contains('zoom-mode-active');
          applyZoomState(zoomToggleButton, isActive);
        }
      }
    });

    document.addEventListener('show.bs.modal', (event) => {
      if (document.body.classList.contains('zoom-mode-active')) {
        event.target.classList.add('zoom-mode-target');
      }
    });

    document.addEventListener('hidden.bs.modal', (event) => {
      event.target.classList.remove('zoom-mode-target');
    });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
