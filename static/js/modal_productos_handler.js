// static/js/modal_productos_handler.js

// 1. Variable global para rastrear la instancia activa del modal y evitar duplicados
let modalProductoInstancia = null;

function selectTipo(tipo) {
    const inputTipo = document.getElementById('id_tipo');
    if (inputTipo) inputTipo.value = tipo;

    document.querySelectorAll('.card-tipo').forEach(card => {
        card.querySelector('.card').classList.remove('border-primary', 'bg-primary-lt');
    });

    const cards = document.querySelectorAll('.card-tipo');
    if (cards.length > 0) {
        if (tipo === 'materia_prima') cards[0].querySelector('.card').classList.add('border-primary', 'bg-primary-lt');
        if (tipo === 'subproducto')  cards[1].querySelector('.card').classList.add('border-primary', 'bg-primary-lt');
        if (tipo === 'producto')     cards[2].querySelector('.card').classList.add('border-primary', 'bg-primary-lt');
    }

    const divPadre = document.getElementById('campo-padre');
    const divPrecio = document.getElementById('div-precio-venta');
    const inputPrecio = document.querySelector('[name="precio_venta"]');
    const checkVende = document.querySelector('[name="es_vendible"]');

    if (!divPrecio) return; 

    // Lógica estricta de negocio
    if (tipo === 'materia_prima') {
        if(divPadre) divPadre.style.display = 'none';
        if(divPrecio) divPrecio.style.display = 'none';
        if(inputPrecio) inputPrecio.value = 0; 
        if(checkVende) checkVende.checked = false;
    } 
    else if (tipo === 'subproducto') {
        if(divPadre) divPadre.style.display = 'block';
        if(divPrecio) divPrecio.style.display = 'block';
        if(checkVende) checkVende.checked = true;
    } 
    else {
        if(divPadre) divPadre.style.display = 'none';
        if(divPrecio) divPrecio.style.display = 'block';
        if(checkVende) checkVende.checked = true;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    
    // Intercepción de carga de HTMX
    document.body.addEventListener('htmx:afterSwap', function(evt) {
        if (evt.target.id === "modal-container") {
            const modalEl = document.getElementById('modal-producto');
            
            if (modalEl) {
                // EXTRACCIÓN DE BASURA: Si ya existía un modal en memoria, lo destruimos correctamente
                if (modalProductoInstancia) {
                    modalProductoInstancia.dispose();
                }

                // Creamos la instancia nueva y limpia
                modalProductoInstancia = new bootstrap.Modal(modalEl);
                modalProductoInstancia.show();

                // Disparamos las reglas lógicas del formulario
                const inputTipo = document.getElementById('id_tipo');
                selectTipo(inputTipo && inputTipo.value ? inputTipo.value : 'materia_prima');
            }
        }
    });

    // Limpieza estricta cuando el modal se cierra visualmente
    document.body.addEventListener('hidden.bs.modal', function (evt) {
        if (evt.target.id === 'modal-producto') {
            // Destruimos la instancia de Bootstrap de la RAM
            if (modalProductoInstancia) {
                modalProductoInstancia.dispose();
                modalProductoInstancia = null;
            }
            
            // Purgamos el contenedor HTML
            document.getElementById('modal-container').innerHTML = ''; 
            
            // Aseguramos que el body vuelva a su estado normal (scroll activo)
            document.body.classList.remove('modal-open');
            document.body.style = '';
            document.querySelectorAll('.modal-backdrop').forEach(el => el.remove()); // Solo como fail-safe
        }
    });
});