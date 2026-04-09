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
 * Render a textual analysis of the selected sectors and period.
 */
function renderAnalysis(selectedSectors) {
    const analysisText = document.getElementById('analysisText');
    if (!analysisText) return;

    const yearMin = parseInt(document.getElementById('yearMin').value) || minYear;
    const yearMax = parseInt(document.getElementById('yearMax').value) || maxYear;
    const selectedCount = selectedSectors.length;

    if (selectedCount === 0) {
        analysisText.textContent = 'Selecteer sectoren om een trendanalyse te ontvangen.';
        return;
    }

    const stats = selectedSectors.map(sector => getSectorStats(sector, yearMin, yearMax));
    const validStats = stats.filter(stat => stat.count > 0);

    if (validStats.length === 0) {
        analysisText.textContent = `Er is geen kwartaaldata voor ${yearMin}-${yearMax}. Kies een ander jaarbereik.`;
        return;
    }

    if (validStats.length === 1) {
        const stat = validStats[0];
        const trendLabel = getTrendLabel(stat.changePct);
        analysisText.textContent = `${stat.sector} toont een ${trendLabel} trend in ${yearMin}-${yearMax}. Het verzuim begon rond ${stat.start.toFixed(2)}% en eindigde op ${stat.end.toFixed(2)}%, een verandering van ${stat.changePct.toFixed(1)}% over ${stat.count} kwartalen.`;
        return;
    }

    if (validStats.length === 2) {
        const [a, b] = validStats;
        const comparison = a.end > b.end ? `${a.sector} eindigt hoger dan ${b.sector}` : `${b.sector} eindigt hoger dan ${a.sector}`;
        analysisText.textContent = `${a.sector} en ${b.sector} laten beide trends zien over ${yearMin}-${yearMax}. ${a.sector}: ${getTrendLabel(a.changePct)}. ${b.sector}: ${getTrendLabel(b.changePct)}. ${comparison}.`;
        return;
    }

    const overall = validStats.reduce((acc, stat) => ({
        changePct: acc.changePct + stat.changePct,
        sectors: acc.sectors + 1
    }), { changePct: 0, sectors: 0 });
    const avgChange = overall.changePct / overall.sectors;
    analysisText.textContent = `Je bekijkt ${validStats.length} sectoren in ${yearMin}-${yearMax}. De gemiddelde trend is ${getTrendLabel(avgChange)} over de geselecteerde periode.`;
}

function getSectorStats(sector, yearMin, yearMax) {
    const quarters = sectorData[sector].quarters;
    const values = sectorData[sector].values;
    const years = sectorData[sector].years;

    const filtered = [];
    for (let i = 0; i < years.length; i++) {
        if (years[i] >= yearMin && years[i] <= yearMax) {
            filtered.push(values[i]);
        }
    }

    if (filtered.length === 0) {
        return { sector, count: 0, start: 0, end: 0, changePct: 0 };
    }

    const start = filtered[0];
    const end = filtered[filtered.length - 1];
    const changePct = start === 0 ? 0 : ((end - start) / start) * 100;
    return { sector, count: filtered.length, start, end, changePct };
}

function getTrendLabel(changePct) {
    if (Math.abs(changePct) < 1) return 'stabiele';
    return changePct > 0 ? 'opwaartse' : 'neerwaartse';
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

    // Apply the default filter window immediately on load
    updateFilter();
});
