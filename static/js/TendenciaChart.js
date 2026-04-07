// static/js/TendenciaChart.js
document.addEventListener("DOMContentLoaded", function() {
    const canvasElement = document.getElementById('tendenciaChart');
    if (!canvasElement) return;

    if (!window.tendenciaData) {
        console.error("Faltan los datos para la gráfica de tendencias.");
        return;
    }

    const ctx = canvasElement.getContext('2d');
    
    const labels = window.tendenciaData.labels;
    const dataVentas = window.tendenciaData.ventas;
    const dataCompras = window.tendenciaData.compras;

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Ventas (Ingresos)',
                    data: dataVentas,
                    borderColor: '#206bc4', 
                    backgroundColor: 'rgba(32, 107, 196, 0.1)',
                    borderWidth: 3,
                    tension: 0.4, 
                    fill: true,
                    pointBackgroundColor: '#206bc4',
                    yAxisID: 'y' // Lo atamos al eje izquierdo
                },
                {
                    label: 'Compras (Egresos)',
                    data: dataCompras,
                    borderColor: '#f76707', 
                    borderWidth: 2,
                    borderDash: [5, 5], 
                    tension: 0.4,
                    pointBackgroundColor: '#f76707',
                    yAxisID: 'y1' // Lo atamos al eje derecho (NUEVO)
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            color: '#a1a8c3', 
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    labels: { color: '#a1a8c3' }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) { label += ': '; }
                            if (context.parsed.y !== null) {
                                label += new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(context.parsed.y);
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#a1a8c3', maxTicksLimit: 15 } 
                },
                // Eje Y principal (Izquierdo) - Para Ventas
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: {
                        color: '#206bc4', // Color azul para relacionarlo con ventas
                        callback: function(value) { return '$' + value; }
                    }
                },
                // Eje Y Secundario (Derecho) - Para Compras (NUEVO)
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    beginAtZero: true,
                    grid: { drawOnChartArea: false }, // Evita que se crucen las cuadrículas
                    ticks: {
                        color: '#f76707', // Color naranja para relacionarlo con compras
                        callback: function(value) { return '$' + value; }
                    }
                }
            }
        }
    });
});