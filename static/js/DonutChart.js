document.addEventListener("DOMContentLoaded", function () {
    const chartContainer = document.getElementById('chart-flujo-capital');
    
    if (!chartContainer) return;

    // Extraemos los valores. El || 0 nos asegura que si falla la conversión, será un cero numérico.
    const totalVentas = parseFloat(chartContainer.dataset.ventas) || 0;
    const totalCompras = parseFloat(chartContainer.dataset.compras) || 0;

    // --- LA REGLA DEFENSIVA (CASO LÍMITE: INICIO DE MES) ---
    if (totalVentas === 0 && totalCompras === 0) {
        // Destruimos el contenedor del gráfico e inyectamos un mensaje visualmente limpio
        chartContainer.innerHTML = `
            <div class="d-flex flex-column justify-content-center align-items-center" style="height: 288px;">
                <svg xmlns="http://www.w3.org/2000/svg" class="icon text-muted mb-3" width="48" height="48" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M3 3v18h18" /><path d="M20 18v3" /><path d="M16 16v5" /><path d="M12 13v8" /><path d="M8 16v5" /><path d="M3 11c6 0 5 -5 9 -5s3 5 9 5" /></svg>
                <span class="text-muted text-center">Sin flujo de capital registrado para el mes actual.</span>
            </div>
        `;
        return; // Cortamos la ejecución aquí. ApexCharts no se inicializa.
    }

    // --- RENDERIZADO NORMAL ---
    if (window.ApexCharts) {
        new ApexCharts(chartContainer, {
            chart: {
                type: "donut",
                fontFamily: 'inherit',
                height: 288,
                sparkline: {
                    enabled: false
                },
                animations: {
                    enabled: true
                },
            },
            fill: {
                opacity: 1,
            },
            series: [totalVentas, totalCompras],
            labels: ["Ingresos (Ventas)", "Egresos (Compras)"],
            tooltip: {
                theme: 'dark',
                y: {
                    formatter: function (val) {
                        return "$" + val.toFixed(2);
                    }
                }
            },
            colors: ["#2fb344", "#d63939"],
            legend: {
                position: 'bottom'
            }
        }).render();
    } else {
        console.error("ApexCharts no está cargado en el navegador.");
    }
});