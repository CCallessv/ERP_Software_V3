

// Variable aislada solo para clientes
let modalClienteInstancia = null;

document.addEventListener('DOMContentLoaded', function() {
    
    // 1. ABRIR EL MODAL
    document.body.addEventListener('htmx:afterSwap', function(evt) {
        if (evt.target.id === "modal-container") {
            // CORRECCIÓN: Buscamos CUALQUIER modal que esté dentro del contenedor
            const modalEl = document.querySelector('#modal-container .modal'); 
            
            if (modalEl) {
                // EXTRACCIÓN DE BASURA PREVENTIVA
                if (modalClienteInstancia) {
                    modalClienteInstancia.dispose();
                }

                modalClienteInstancia = new bootstrap.Modal(modalEl);
                modalClienteInstancia.show();
            }
        }
    });

    // 2. CERRAR EL MODAL AL GUARDAR O ELIMINAR (Señal de Django)
    document.body.addEventListener('proveedorActualizado', function () {
        if (modalClienteInstancia) {
            modalClienteInstancia.hide(); // Esto dispara la animación de cierre
        }
    });

    // 3. LIMPIEZA ESTRICTA AL CERRAR
    document.body.addEventListener('hidden.bs.modal', function (evt) {
        if (evt.target.id === 'modal-cliente' || evt.target.id === 'modal-eliminar-cliente') {
            
            if (modalClienteInstancia) {
                modalClienteInstancia.dispose();
                modalClienteInstancia = null;
            }
            
            document.getElementById('modal-container').innerHTML = ''; 
            document.body.classList.remove('modal-open');
            document.body.style = '';
            document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        }
    });
});