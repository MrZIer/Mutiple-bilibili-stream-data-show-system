// File: /bilibili-live-monitor-django/bilibili-live-monitor-django/static/js/charts.js

const ctx = document.getElementById('myChart').getContext('2d');
const myChart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: [], // This will be populated with live data labels
        datasets: [{
            label: 'Live Streaming Data',
            data: [], // This will be populated with live data values
            borderColor: 'rgba(75, 192, 192, 1)',
            borderWidth: 1,
            fill: false
        }]
    },
    options: {
        responsive: true,
        scales: {
            y: {
                beginAtZero: true
            }
        }
    }
});

// Function to update the chart with new data
function updateChart(newLabels, newData) {
    myChart.data.labels = newLabels;
    myChart.data.datasets[0].data = newData;
    myChart.update();
}

// Example of how to fetch data and update the chart periodically
setInterval(() => {
    fetch('/api/live-data') // Adjust the endpoint as necessary
        .then(response => response.json())
        .then(data => {
            const labels = data.map(item => item.timestamp); // Adjust based on your data structure
            const values = data.map(item => item.value); // Adjust based on your data structure
            updateChart(labels, values);
        })
        .catch(error => console.error('Error fetching live data:', error));
}, 5000); // Update every 5 seconds