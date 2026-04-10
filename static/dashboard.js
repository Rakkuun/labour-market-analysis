/**
 * Dashboard interactivity functions
 */

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
    const traces = selectedSectors.map(sector => {
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
            type: 'scatter',
            hovertemplate: '<b>' + sector + '</b><br>Kwartaal: %{x}<br>Verzuim: %{y:.2f}%<extra></extra>'
        };
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
    const analysisText = document.getElementById('analysisText');
    if (!analysisText) return;

    const yearMin = parseInt(document.getElementById('yearMin').value) || minYear;
    const yearMax = parseInt(document.getElementById('yearMax').value) || maxYear;
    
    if (selectedSectors.length === 0) {
        analysisText.textContent = 'Selecteer sectoren om een trendanalyse te ontvangen.';
        return;
    }

    // Show loading state
    analysisText.innerHTML = '<em class="text-muted">AI-analyse wordt gegenereerd...</em>';

    // Call the API endpoint
    fetch('/api/analyze', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            sectors: selectedSectors,
            year_min: yearMin,
            year_max: yearMax
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            analysisText.textContent = `Fout: ${data.error}`;
        } else {
            analysisText.textContent = data.analysis;
        }
    })
    .catch(error => {
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
