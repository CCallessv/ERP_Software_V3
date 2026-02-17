// core/static/js/inventario.js

/**
 * Función encargada de la lógica visual del formulario de productos.
 * 1. Marca la tarjeta seleccionada con borde azul.
 * 2. Muestra/Oculta el campo "Padre" según si es subproducto.
 * 3. Actualiza el input oculto que se envía al servidor.
 */
function selectTipo(tipo) {

    // PASO 1: Actualizar el valor que se enviará a la base de datos
    var inputOculto = document.getElementById('id_tipo');
    if (inputOculto) {
        inputOculto.value = tipo;
    }
    
    // PASO 2: Manejo de Bordes (Quitar azul a todos, poner al seleccionado)
    
    // A. Buscamos todas las tarjetas y les quitamos el borde azul
    var todasLasCards = document.querySelectorAll('.card-tipo .card');
    todasLasCards.forEach(function(card) {
        card.classList.remove('border-primary');
    });

    // B. Buscamos ESPECÍFICAMENTE la tarjeta clickeada usando su atributo onclick
    // El selector busca: un elemento con clase .card-tipo que tenga el texto "tipo" en su onclick
    var selector = '.card-tipo[onclick*="' + tipo + '"] .card';
    var tarjetaSeleccionada = document.querySelector(selector);
    
    if (tarjetaSeleccionada) {
        tarjetaSeleccionada.classList.add('border-primary');
    }

    // PASO 3: Lógica de Negocio (Mostrar/Ocultar Padre)
    var campoPadre = document.getElementById('campo-padre');
    
    if (campoPadre) {
        if (tipo === 'subproducto') {
            // Si es subproducto, necesita un padre (ej: Carne viene de la Vaca)
            campoPadre.style.display = 'block';
        } else {
            // Si es otro tipo, ocultamos el selector de padre
            campoPadre.style.display = 'none';
            
            // Y limpiamos el valor para no enviar basura al servidor
            var selectPadre = document.getElementById('id_padre');
            if(selectPadre) {
                selectPadre.value = ""; 
            }
        }
    }
}