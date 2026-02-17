//Esta funcion lo que hace es que oculta y aparece la contraseña del lado del input de contraseña
        document.addEventListener("DOMContentLoaded", function () {
            // 1. Buscamos los elementos por su ID
            const toggleBtn = document.getElementById('togglePassword');
            const passwordInput = document.getElementById('id_password');
    
            // 2. Verificamos que existan para no causar errores
            if (toggleBtn && passwordInput) {
                toggleBtn.addEventListener('click', function (e) {
                    e.preventDefault(); // Evita que el enlace te lleve arriba de la página
                    
                    // 3. La lógica: Si es password lo paso a texto, y viceversa
                    if (passwordInput.type === "password") {
                        passwordInput.type = "text";
                    } else {
                        passwordInput.type = "password";
                    }
                });
            }
        });
    