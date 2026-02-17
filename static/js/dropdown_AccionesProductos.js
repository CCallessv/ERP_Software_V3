/* static/js/dropdown_AccionesProductos.js */

function toggleAccionesProducto(event, btn) {
    event.preventDefault();
    event.stopPropagation();

    const menu = btn.nextElementSibling;
    const isShown = menu.classList.contains('show');

    // 1. LIMPIEZA: Cerrar todos los menus abiertos y limpiar estilos viejos
    document.querySelectorAll('.dropdown-menu.show').forEach(m => {
        m.classList.remove('show');
        // Importante: Limpiamos los estilos "fijos" para que no estorben despues
        m.style.position = '';
        m.style.top = '';
        m.style.left = '';
        m.style.transform = '';
        m.style.zIndex = '';
    });

    if (isShown) {
        return; // Si ya estaba abierto solo lo cerramos (lo hizo el bloque de arriba)
    }

    // 2. PREPARACION: Mostramos el menú invisiblemente para poder medirlo
    menu.style.display = 'block'; 
    menu.style.visibility = 'hidden';
    
    const btnRect = btn.getBoundingClientRect();   // Dónde está el botón
    const menuRect = menu.getBoundingClientRect(); // Cuánto mide el menú
    const viewportHeight = window.innerHeight;     // Alto de la pantalla

    // 3. CÁLCULO VERTICAL: ¿Cabe abajo?
    const espacioAbajo = viewportHeight - btnRect.bottom;
    let topPos;
    
    // Si hay poco espacio abajo (menos de la altura del menú), lo mandamos arriba
    if (espacioAbajo < menuRect.height) {
        // Posición: Borde superior del botón - Altura del menú
        topPos = btnRect.top - menuRect.height;
    } else {
        // Posición: Borde inferior del botón
        topPos = btnRect.bottom;
    }

    // 4. CÁLCULO HORIZONTAL: Alinear a la derecha del botón
    // (Borde derecho del botón - Ancho del menú)
    const leftPos = btnRect.right - menuRect.width;

    // 5. APLICAR ESTILOS "FIXED" (Aqui ocurre la magia)
    menu.style.visibility = 'visible'; // Lo hacemos visible
    menu.style.display = '';          // Quitamos el display forzado (Bootstrap lo maneja)
    
    menu.style.position = 'fixed';   
    menu.style.top = `${topPos}px`;
    menu.style.left = `${leftPos}px`;
    menu.style.zIndex = '9999';       // Siempre encima de todo
    menu.style.margin = '0';          // Evitar márgenes raros

    // Finalmente, activamos la clase de Bootstrap
    menu.classList.add('show');
}

/* * Listener Global: Cerrar al hacer scroll o resize 
 * (Porque al ser 'fixed', si mueves la página, el menu se quedaria flotando raro)
 */
window.addEventListener('scroll', cerrarMenus, true);
window.addEventListener('resize', cerrarMenus);
window.addEventListener('click', function(e) {
    if (!e.target.closest('.dropdown-toggle') && !e.target.closest('.dropdown-menu')) {
        cerrarMenus();
    }
});

function cerrarMenus() {
    document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
        menu.classList.remove('show');
        menu.style.position = ''; // Limpiar al cerrar
    });
}