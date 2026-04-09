from flask import Flask, render_template_string
import pandas as pd
import sqlite3
import plotly.graph_objects as go
import json

app = Flask(__name__)

@app.route('/')
def index():
    # Load data from cleaned absenteeism table
    conn = sqlite3.connect('data.db')
    df = pd.read_sql('SELECT * FROM cleaned_absenteeism', conn)
    pred_df = pd.read_sql('SELECT * FROM predictions', conn)
    conn.close()

    if df.empty:
        plot_html = '<p>No data available for plotting.</p>'
        sectors = []
        sector_data_json = '{}'
    else:
        sectors = sorted(df['Sector'].unique().tolist())
        
        # Build data structure for JavaScript: {sector: {years: [...], values: [...]}}
        sector_data = {}
        for sector in sectors:
            data = df[df['Sector'] == sector].sort_values('Year')
            sector_data[sector] = {
                'years': data['Year'].tolist(),
                'values': data['AbsenteeismPercentage'].tolist()
            }
        
        sector_data_json = json.dumps(sector_data)
        
        # Create initial plot with all sectors visible
        fig = go.Figure()
        for sector in sectors:
            years = sector_data[sector]['years']
            values = sector_data[sector]['values']
            fig.add_trace(go.Scatter(
                x=years,
                y=values,
                mode='lines+markers',
                name=sector,
                visible=True,
                hovertemplate='<b>%{text}</b><br>Jaar: %{x}<br>Verzuim: %{y:.2f}%<extra></extra>',
                text=[sector] * len(values)
            ))

        fig.update_layout(
            title='Ziekteverzuimpercentage per sector over tijd',
            xaxis_title='Jaar',
            yaxis_title='Ziekteverzuim %',
            legend_title='Sector',
            hovermode='closest',
            margin=dict(l=40, r=40, t=70, b=40)
        )

        plot_html = fig.to_html(full_html=False, include_plotlyjs='cdn', div_id='plotly-chart')


    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset='utf-8'>
        <meta name='viewport' content='width=device-width, initial-scale=1'>
        <title>Labour Market Analysis</title>
        <link href='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css' rel='stylesheet'>
        <style>
            :root {
                --bs-primary: #0d6efd;
                --bs-secondary: #6c757d;
                --bs-success: #198754;
                --bs-info: #0dcaf0;
            }
            body {
                background-color: #f8f9fa;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            .navbar-custom {
                background: linear-gradient(135deg, #0d6efd 0%, #0a58ca 100%);
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .card-header-custom {
                background: linear-gradient(135deg, #0d6efd 0%, #0056b3 100%);
                color: white;
            }
            .filter-panel {
                background: white;
                border-radius: 8px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                border-left: 4px solid #0d6efd;
            }
            #sectorFilter {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                min-height: 260px;
                font-size: 0.95rem;
            }
            #sectorFilter option:checked {
                background: linear-gradient(#0d6efd, #0d6efd);
                background-color: #0d6efd !important;
            }
            .btn-filter {
                border-radius: 4px;
                font-weight: 500;
            }
            .plot-container {
                background: white;
                border-radius: 8px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                padding: 20px;
                margin: 20px 0;
            }
            .data-table {
                background: white;
                border-radius: 8px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                overflow: hidden;
            }
            .data-table table {
                margin-bottom: 0;
            }
            .data-table thead {
                background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            }
            .data-table tbody tr:hover {
                background-color: #f8f9fa;
            }
            h1 {
                color: #0d6efd;
                font-weight: 700;
                margin-bottom: 30px;
            }
            h2 {
                color: #0056b3;
                font-weight: 600;
                margin-top: 25px;
                margin-bottom: 15px;
                position: relative;
                padding-bottom: 10px;
            }
            h2::after {
                content: '';
                position: absolute;
                bottom: 0;
                left: 0;
                width: 50px;
                height: 3px;
                background: linear-gradient(90deg, #0d6efd, transparent);
                border-radius: 2px;
            }
        </style>
    </head>
    <body>
        <nav class='navbar navbar-dark navbar-custom mb-5'>
            <div class='container-lg'>
                <span class='navbar-brand mb-0 h1'>
                    <i class='bi bi-graph-up'></i> Labour Market Analysis
                </span>
            </div>
        </nav>

        <div class='container-lg'>
            <div class='row mb-5'>
                <div class='col-lg-3'>
                    <div class='filter-panel p-4'>
                        <h5 class='mb-3'>
                            <i class='bi bi-funnel'></i> Sector filter
                        </h5>
                        <p class='text-muted small mb-3'>Selecteer sectoren om in de grafiek te tonen.</p>
                        <div class='d-grid gap-2 mb-3'>
                            <button type='button' class='btn btn-primary btn-sm btn-filter' onclick='selectAll()'>
                                <i class='bi bi-check-all'></i> Select all
                            </button>
                            <button type='button' class='btn btn-outline-secondary btn-sm btn-filter' onclick='deselectAll()'>
                                <i class='bi bi-x-circle'></i> Deselect all
                            </button>
                        </div>
                        <select id='sectorFilter' class='form-select' multiple>
                            {% for sector in sectors %}
                            <option value='{{ sector }}' selected>{{ sector }}</option>
                            {% endfor %}
                        </select>
                    </div>
                </div>
                <div class='col-lg-9'>
                    <div class='plot-container'>
                        {{ plot_html|safe }}
                    </div>
                </div>
            </div>

            <div class='row'>
                <div class='col-12'>
                    <h2>Voorbeelddata</h2>
                    <div class='data-table table-responsive'>
                        {{ table|safe }}
                    </div>
                </div>
            </div>

            <div class='row mt-5'>
                <div class='col-12'>
                    <h2>Prognoses</h2>
                    <div class='data-table table-responsive'>
                        {{ pred_table|safe }}
                    </div>
                </div>
            </div>

            <footer class='mt-5 pt-5 text-center text-muted pb-5'>
                <small>Dutch Labour Market Analysis Dashboard</small>
            </footer>
        </div>

        <script src='https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'></script>
        <script src='https://cdn.plot.ly/plotly-latest.min.js'></script>
        <script>
            // Store sector data from Python backend
            const sectorData = {{ sector_data_json|safe }};
            const allSectors = Object.keys(sectorData);
            
            function rebuildPlot(selectedSectors) {
                const plot = document.getElementById('plotly-chart');
                if (!plot) {
                    console.error('Plot element not found');
                    return;
                }
                
                // Build traces for selected sectors
                const traces = selectedSectors.map(sector => ({
                    x: sectorData[sector].years,
                    y: sectorData[sector].values,
                    mode: 'lines+markers',
                    name: sector,
                    type: 'scatter',
                    hovertemplate: '<b>' + sector + '</b><br>Jaar: %{x}<br>Verzuim: %{y:.2f}%<extra></extra>'
                }));
                
                const layout = {
                    title: 'Ziekteverzuimpercentage per sector over tijd',
                    xaxis: { title: 'Jaar' },
                    yaxis: { title: 'Ziekteverzuim %' },
                    legend: { title: { text: 'Sector' } },
                    hovermode: 'closest',
                    margin: { l: 40, r: 40, t: 70, b: 40 }
                };
                
                try {
                    window.Plotly.newPlot(plot, traces, layout, {responsive: true});
                } catch (e) {
                    console.error('Plotly error:', e);
                }
            }
            
            function updateFilter() {
                const select = document.getElementById('sectorFilter');
                if (!select) return;
                
                const selected = Array.from(select.selectedOptions).map(opt => opt.value);
                
                if (selected.length === 0) {
                    // If nothing selected, show all
                    rebuildPlot(allSectors);
                } else {
                    rebuildPlot(selected);
                }
            }

            function selectAll() {
                const select = document.getElementById('sectorFilter');
                Array.from(select.options).forEach(opt => opt.selected = true);
                updateFilter();
            }

            function deselectAll() {
                const select = document.getElementById('sectorFilter');
                Array.from(select.options).forEach(opt => opt.selected = false);
                updateFilter();
            }

            // Initialize on page load
            document.addEventListener('DOMContentLoaded', function() {
                const select = document.getElementById('sectorFilter');
                if (select) {
                    select.addEventListener('change', updateFilter);
                }
            });
        </script>
    </body>
    </html>
    """

    table = df.head(20).to_html(index=False) if not df.empty else '<p>No data available.</p>'
    pred_table = pred_df.to_html(index=False) if not pred_df.empty else '<p>No predictions available.</p>'
    return render_template_string(html, table=table, pred_table=pred_table, plot_html=plot_html, sectors=sectors, sector_data_json=sector_data_json)

if __name__ == "__main__":
    app.run(debug=True)
