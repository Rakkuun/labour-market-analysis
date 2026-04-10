/**
 * Dashboard interactivity functions
 */

const COLORS = [
    '#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A',
    '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52',
    '#1F77B4', '#FF7F0E', '#2CA02C', '#D62728', '#9467BD',
    '#8C564B', '#E377C2', '#7F7F7F', '#BCBD22', '#17BECF',
    '#AEC7E8', '#FFBB78', '#98DF8A', '#FF9896', '#C5B0D5',
    '#C49C94', '#F7B6D2', '#C7C7C7', '#DBDB8D', '#9EDAE5',
    '#393B79', '#637939', '#8C6D31', '#843C39', '#7B4173',
    '#5254A3', '#B5CF6B', '#E7CB94', '#AD494A', '#A55194'
];

let allSectors = [];

/**
 * Rebuild the plot with selected sectors and year range
 * @param {string[]} selectedSectors - Array of selected sector names
 */
function rebuildPlot(selectedSectors) {
    const plot = document.getElementById('plotly-chart');
    if (!plot) {
        console.error('Plot element not found');
        return;
    }
    
    // Get year range filter
    const yearMin = parseInt(document.getElementById('yearMin').value) || minYear;
    const yearMax = parseInt(document.getElementById('yearMax').value) || maxYear;
    
    // Build traces for selected sectors, filtered by year
    const traces = selectedSectors.map((sector, idx) => {
        const sectorIdx = allSectors.indexOf(sector);
        const color = COLORS[(sectorIdx >= 0 ? sectorIdx : idx) % COLORS.length];
        const quarters = sectorData[sector].quarters;
        const values = sectorData[sector].values;
        const years = sectorData[sector].years;
        
        // Filter data points based on year range
        const x = [];
        const y = [];
        for (let i = 0; i < years.length; i++) {
            if (years[i] >= yearMin && years[i] <= yearMax) {
                x.push(quarters[i]);
                y.push(values[i]);
            }
        }
        
        return {
            x: x,
            y: y,
            mode: 'lines+markers',
            name: sector,
            legendgroup: sector,
            type: 'scatter',
            line: { color: color },
            marker: { color: color },
            hovertemplate: '<b>' + sector + '</b><br>Kwartaal: %{x}<br>Verzuim: %{y:.2f}%<extra></extra>'
        };
    });

    // Add dashed forecast traces for each selected sector
    selectedSectors.forEach((sector, idx) => {
        if (predictionData && predictionData[sector] && sectorData[sector]) {
            const sectorIdx = allSectors.indexOf(sector);
            const color = COLORS[(sectorIdx >= 0 ? sectorIdx : idx) % COLORS.length];
            const quarters = sectorData[sector].quarters;
            const values = sectorData[sector].values;
            const years = sectorData[sector].years;
            if (!quarters.length) return;

            // Filter to get last point within year range
            let lastX = null, lastY = null;
            for (let i = quarters.length - 1; i >= 0; i--) {
                if (years[i] >= yearMin && years[i] <= yearMax) {
                    lastX = quarters[i];
                    lastY = values[i];
                    break;
                }
            }
            if (lastX === null) return;

            const predQ = predictionData[sector].quarters;
            const predV = predictionData[sector].values;
            traces.push({
                x: [lastX, ...predQ],
                y: [lastY, ...predV],
                mode: 'lines+markers',
                name: sector + ' (prognose)',
                legendgroup: sector,
                showlegend: false,
                type: 'scatter',
                line: { dash: 'dot', color: color },
                marker: { color: color },
                hovertemplate: '<b>' + sector + '</b><br>%{x}<br>Prognose: %{y:.2f}%<extra></extra>'
            });
        }
    });

    const layout = {
        title: 'Ziekteverzuimpercentage per sector over tijd',
        xaxis: { title: 'Kwartaal' },
        yaxis: { title: 'Ziekteverzuim %' },
        legend: { title: { text: 'Sector' } },
        hovermode: 'closest',
        margin: { l: 40, r: 40, t: 70, b: 40 },
        plot_bgcolor: 'rgba(0,0,0,0)',
        paper_bgcolor: 'rgba(0,0,0,0)'
    };
    
    try {
        window.Plotly.newPlot(plot, traces, layout, { responsive: true });
    } catch (e) {
        console.error('Plotly error:', e);
    }
}

/**
 * Update plot based on current filter selections
 */
function updateFilter() {
    const select = document.getElementById('sectorFilter');
    if (!select) return;
    
    const selected = Array.from(select.selectedOptions).map(opt => opt.value);
    
    if (selected.length === 0) {
        // If nothing selected, show all
        rebuildPlot(allSectors);
        renderAnalysis(allSectors);
    } else {
        rebuildPlot(selected);
        renderAnalysis(selected);
    }
}

/**
 * Render a textual analysis of the selected sectors and period using AI.
 */
function renderAnalysis(selectedSectors) {
    const yearMin = parseInt(document.getElementById('yearMin').value) || minYear;
    const yearMax = parseInt(document.getElementById('yearMax').value) || maxYear;

    if (selectedSectors.length === 0) {
        const placeholder = document.getElementById('analysisPlaceholder');
        const historyPanel = document.getElementById('historyPanel');
        const forecastPanel = document.getElementById('forecastPanel');
        if (placeholder) placeholder.style.display = 'block';
        if (historyPanel) historyPanel.style.display = 'none';
        if (forecastPanel) forecastPanel.style.display = 'none';
        return;
    }

    // Show loading state
    const analysisText = document.getElementById('analysisText');
    const historyPanel = document.getElementById('historyPanel');
    const placeholder = document.getElementById('analysisPlaceholder');
    const forecastPanel = document.getElementById('forecastPanel');
    const forecastText = document.getElementById('forecastText');

    if (placeholder) { placeholder.style.display = 'block'; placeholder.innerHTML = '<em class="text-muted">AI-analyse wordt gegenereerd...</em>'; }
    if (historyPanel) historyPanel.style.display = 'none';
    if (forecastPanel) forecastPanel.style.display = 'none';

    // Build pred_dict subset for selected sectors
    const predSubset = {};
    selectedSectors.forEach(s => {
        if (predictionData && predictionData[s]) predSubset[s] = predictionData[s];
    });

    // Call the API endpoint
    fetch('/api/analyze', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            sectors: selectedSectors,
            year_min: yearMin,
            year_max: yearMax,
            pred_dict: predSubset
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            analysisText.textContent = `Fout: ${data.error}`;
            if (placeholder) placeholder.style.display = 'none';
            if (historyPanel) historyPanel.style.display = 'block';
        } else {
            analysisText.textContent = data.analysis;
            if (placeholder) placeholder.style.display = 'none';
            if (historyPanel) historyPanel.style.display = 'block';
            if (forecastPanel && forecastText && data.forecast) {
                forecastText.textContent = data.forecast;
                forecastPanel.style.display = 'block';
            }
        }
    })
    .catch(error => {
        if (placeholder) placeholder.style.display = 'none';
        if (historyPanel) historyPanel.style.display = 'block';
        analysisText.textContent = `Fout bij analysevraag: ${error}`;
    });
}

/**
 * Select all sectors in the filter
 */
function selectAll() {
    const select = document.getElementById('sectorFilter');
    Array.from(select.options).forEach(opt => opt.selected = true);
    updateFilter();
}

/**
 * Deselect all sectors in the filter
 */
function deselectAll() {
    const select = document.getElementById('sectorFilter');
    Array.from(select.options).forEach(opt => opt.selected = false);
    updateFilter();
}

/**
 * Reset year range to the default latest five-year window
 */
function resetYears() {
    document.getElementById('yearMin').value = defaultMinYear;
    document.getElementById('yearMax').value = defaultMaxYear;
    updateFilter();
}

/**
 * Initialize event listeners on page load
 */
document.addEventListener('DOMContentLoaded', function() {
    allSectors = Object.keys(sectorData);

    const select = document.getElementById('sectorFilter');
    if (select) {
        select.addEventListener('change', updateFilter);
    }
    
    // Add listeners for year range inputs
    const yearMin = document.getElementById('yearMin');
    const yearMax = document.getElementById('yearMax');
    if (yearMin) yearMin.addEventListener('change', updateFilter);
    if (yearMax) yearMax.addEventListener('change', updateFilter);

    // On initial load: only build the plot, no AI call
    rebuildPlot(allSectors);
});
