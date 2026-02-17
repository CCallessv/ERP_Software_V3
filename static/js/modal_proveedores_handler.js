// Variable exclusiva para proveedores
let modalProveedorInstancia = null;

document.addEventListener('DOMContentLoaded', function() {
    
   // 1. ABRIR EL MODAL
   document.body.addEventListener('htmx:afterSwap', function(evt) {
    if (evt.target.id === "modal-container") {
        // CORRECCIÓN: Buscamos cualquier modal dentro del contenedor, igual que en Clientes
        const modalEl = document.querySelector('#modal-container .modal'); 
        
        if (modalEl) {
            if (modalProveedorInstancia) {
                modalProveedorInstancia.dispose();
            }
            modalProveedorInstancia = new bootstrap.Modal(modalEl);
            modalProveedorInstancia.show();
        }
    }
});

    // 2. CERRAR EL MODAL AL GUARDAR O ELIMINAR (Señal de Django)
    document.body.addEventListener('proveedorActualizado', function () {
        if (modalProveedorInstancia) {
            modalProveedorInstancia.hide();
        }
    });

    // 3. LIMPIEZA ESTRICTA AL CERRAR
    document.body.addEventListener('hidden.bs.modal', function (evt) {
        // Asegúrate de que los IDs coincidan con los de tus archivos HTML
        if (evt.target.id === 'modal-proveedor' || evt.target.id === 'modal-eliminar-proveedor') {
            
            if (modalProveedorInstancia) {
                modalProveedorInstancia.dispose();
                modalProveedorInstancia = null;
            }
            
            document.getElementById('modal-container').innerHTML = ''; 
            document.body.classList.remove('modal-open');
            document.body.style = '';
            document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        }
    });
});