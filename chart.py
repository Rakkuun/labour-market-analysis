"""Plotly chart creation for the absenteeism dashboard."""
import plotly.graph_objects as go

COLORS = [
    '#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A',
    '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52',
    '#1F77B4', '#FF7F0E', '#2CA02C', '#D62728', '#9467BD',
    '#8C564B', '#E377C2', '#7F7F7F', '#BCBD22', '#17BECF',
    '#AEC7E8', '#FFBB78', '#98DF8A', '#FF9896', '#C5B0D5',
    '#C49C94', '#F7B6D2', '#C7C7C7', '#DBDB8D', '#9EDAE5',
    '#393B79', '#637939', '#8C6D31', '#843C39', '#7B4173',
    '#5254A3', '#B5CF6B', '#E7CB94', '#AD494A', '#A55194',
]

_QUARTER_COLORS = ['#4C6EF5', '#37B24D', '#F59F00', '#E03131']


def hover_text_color(hex_color):
    """Return '#000000' or '#ffffff' for readable hover labels (WCAG luminance)."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255

    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    return '#000000' if lum > 0.179 else '#ffffff'


def _add_actual_trace(fig, sector, quarters, values, color):
    fig.add_trace(go.Scatter(
        x=quarters,
        y=values,
        mode='lines+markers',
        name=sector,
        legendgroup=sector,
        visible=True,
        line=dict(color=color),
        marker=dict(color=color),
        hoverlabel=dict(font=dict(color=hover_text_color(color))),
        hovertemplate='<b>%{text}</b><br>Kwartaal: %{x}<br>Verzuim: %{y:.2f}%<extra></extra>',
        text=[sector] * len(values),
    ))


def _add_forecast_trace(fig, sector, last_x, last_y, pred_quarters, pred_values, color):
    fig.add_trace(go.Scatter(
        x=[last_x] + pred_quarters,
        y=[last_y] + pred_values,
        mode='lines+markers',
        name=f"{sector} (prognose)",
        legendgroup=sector,
        showlegend=False,
        line=dict(dash='dot', color=color),
        marker=dict(color=color),
        hoverlabel=dict(font=dict(color=hover_text_color(color))),
        hovertemplate='<b>%{text}</b><br>%{x}<br>Prognose: %{y:.2f}%<extra></extra>',
        text=[sector] * (1 + len(pred_quarters)),
    ))


def create_plotly_figure(sector_data, sectors, pred_dict=None):
    """Build and return the Plotly figure HTML for the dashboard.

    Args:
        sector_data: {sector: {quarters, values, years}}
        sectors: ordered list of sector names
        pred_dict: optional {sector: {quarters, values}} for forecast traces

    Returns:
        str: self-contained HTML fragment (no full HTML wrapper)
    """
    fig = go.Figure()

    for i, sector in enumerate(sectors):
        color = COLORS[i % len(COLORS)]
        quarters = sector_data[sector]['quarters']
        values = sector_data[sector]['values']

        _add_actual_trace(fig, sector, quarters, values, color)

        if pred_dict and sector in pred_dict and quarters:
            pred = pred_dict[sector]
            _add_forecast_trace(
                fig, sector,
                quarters[-1], values[-1],
                pred['quarters'], pred['values'],
                color,
            )

    fig.update_layout(
        title='Ziekteverzuimpercentage per sector over tijd',
        xaxis=dict(title=dict(text='Kwartaal', standoff=20), tickangle=-45),
        yaxis=dict(title=dict(text='Ziekteverzuim %', standoff=10)),
        legend_title='Sector',
        hovermode='closest',
        height=500,
        margin=dict(l=70, r=40, t=70, b=80),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )

    return fig.to_html(full_html=False, include_plotlyjs='cdn', div_id='plotly-chart')


def create_seasonal_figure(df, last_n_years=5):
    """Bar chart of average absenteeism per quarter (Q1-Q4) over the last N years.

    Each quarter gets its own colour to visually separate the seasons.
    A horizontal dashed line shows the overall average across all quarters.

    Args:
        df: cleaned_absenteeism DataFrame with columns Year, Period, AbsenteeismPercentage
        last_n_years: how many recent years to include (default 5)

    Returns:
        str: self-contained HTML fragment
    """
    from db import extract_quarter_number

    max_year = int(df['Year'].max())
    min_year = max_year - last_n_years + 1
    subset = df[df['Year'] >= min_year].copy()
    subset['Q'] = subset['Period'].apply(extract_quarter_number)
    subset = subset[subset['Q'].notna()]
    subset['Q'] = subset['Q'].astype(int)

    avg_per_q = (
        subset.groupby('Q')['AbsenteeismPercentage']
        .mean()
        .reset_index()
        .sort_values('Q')
    )

    overall_avg = avg_per_q['AbsenteeismPercentage'].mean()
    quarter_labels = ['Q1 (jan–mrt)', 'Q2 (apr–jun)', 'Q3 (jul–sep)', 'Q4 (okt–dec)']

    fig = go.Figure()

    labels = [quarter_labels[int(row['Q']) - 1] for _, row in avg_per_q.iterrows()]
    values = [round(row['AbsenteeismPercentage'], 2) for _, row in avg_per_q.iterrows()]
    colors = [_QUARTER_COLORS[int(row['Q']) - 1] for _, row in avg_per_q.iterrows()]

    fig.add_trace(go.Bar(
        x=labels,
        y=values,
        marker_color=colors,
        showlegend=False,
        hovertemplate='<b>%{x}</b><br>Gemiddeld verzuim: %{y:.2f}%<extra></extra>',
    ))

    # Overall average reference line
    fig.add_hline(
        y=overall_avg,
        line_dash='dash',
        line_color='#555',
        annotation_text=f'Gemiddeld {overall_avg:.2f}%',
        annotation_position='top right',
        annotation_font_size=12,
    )

    fig.update_layout(
        title=f'Gemiddeld ziekteverzuim per kwartaal ({min_year}–{max_year}, alle sectoren)',
        xaxis=dict(title=dict(text='Kwartaal', standoff=10)),
        yaxis=dict(title=dict(text='Ziekteverzuim %', standoff=10)),
        showlegend=False,
        hovermode='closest',
        margin=dict(l=70, r=40, t=70, b=60),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        bargap=0.35,
    )

    return fig.to_html(full_html=False, include_plotlyjs=False, div_id='seasonal-chart')


def create_flu_comparison_figure(df, flu_records, last_n_years=5):
    """Dual-axis line chart: avg CBS absenteeism (all sectors) vs WHO FluNet griep positives.

    Args:
        df: cleaned_absenteeism DataFrame with Year, Period, AbsenteeismPercentage
        flu_records: list of dicts from load_flu_data() — keys year, quarter, flu_positives
        last_n_years: how many recent years to include (default 5)

    Returns:
        str: HTML fragment (no plotlyjs, already loaded on page)
    """
    from db import extract_quarter_number
    import pandas as pd

    max_year = int(df['Year'].max())
    min_year = max_year - last_n_years + 1

    # ── Absenteeism: average across all sectors per quarter ──────────────────
    df = df[df['Year'] >= min_year].copy()
    df['Q'] = df['Period'].apply(extract_quarter_number)
    df = df[df['Q'].notna()]
    df['Q'] = df['Q'].astype(int)
    df['period_key'] = df['Year'].astype(str) + '-Q' + df['Q'].astype(str)

    abs_avg = (
        df.groupby('period_key')['AbsenteeismPercentage']
        .mean()
        .reset_index()
        .rename(columns={'period_key': 'period', 'AbsenteeismPercentage': 'abs_pct'})
        .sort_values('period')
    )

    # ── Flu: filter to same year range ───────────────────────────────────────
    flu_df = pd.DataFrame(flu_records)
    if not flu_df.empty:
        flu_df = flu_df[flu_df['year'] >= min_year]
        flu_df['period_key'] = flu_df['year'].astype(str) + '-Q' + flu_df['quarter'].astype(str)
        flu_df = flu_df.sort_values('period_key')

    fig = go.Figure()

    # Primary y-axis: absenteeism
    fig.add_trace(go.Scatter(
        x=abs_avg['period'],
        y=abs_avg['abs_pct'].round(2),
        name='Gem. ziekteverzuim % (CBS)',
        mode='lines+markers',
        line=dict(color='#0d6efd', width=2),
        marker=dict(color='#0d6efd', size=5),
        hoverlabel=dict(bgcolor='#0d6efd', font=dict(color='#ffffff')),
        hovertemplate='<b>Ziekteverzuim</b><br>%{x}<br>%{y:.2f}%<extra></extra>',
    ))

    # Secondary y-axis: flu positives
    if not flu_df.empty:
        fig.add_trace(go.Scatter(
            x=flu_df['period_key'],
            y=flu_df['flu_positives'],
            name='Griepactiviteit (WHO FluNet NL)',
            mode='lines+markers',
            yaxis='y2',
            line=dict(color='#f03e3e', width=2, dash='dot'),
            marker=dict(color='#f03e3e', size=5),
            hoverlabel=dict(bgcolor='#f03e3e', font=dict(color='#ffffff')),
            hovertemplate='<b>Griep</b><br>%{x}<br>Positieven: %{y:.0f}<extra></extra>',
        ))

    fig.update_layout(
        title=f'Ziekteverzuim vs. griepactiviteit ({min_year}–{max_year}, Nederland)',
        xaxis=dict(title=dict(text='Kwartaal', standoff=20), tickangle=-45),
        yaxis=dict(
            title=dict(text='Ziekteverzuim %', standoff=10),
            side='left',
        ),
        yaxis2=dict(
            title=dict(text='Griepactiviteit (positieven)', standoff=10),
            overlaying='y',
            side='right',
            showgrid=False,
            zeroline=False,
        ),
        legend=dict(orientation='h', yanchor='top', y=-0.35, xanchor='center', x=0.5),
        hovermode='x unified',
        margin=dict(l=70, r=80, t=50, b=120),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )

    return fig.to_html(full_html=False, include_plotlyjs=False, div_id='flu-comparison-chart')


def create_hero_preview_figure(df, sector='G Handel', last_n_years=3):
    """Small hero chart: real sector absenteeism + 4-quarter forecast vs a mock 'jouw bedrijf' line.

    Forecast uses the same linear regression + seasonal dummies + residual anchoring as predict.py.
    The mock line covers only the historical period (not extended into the forecast).

    Args:
        df: cleaned_absenteeism DataFrame
        sector: sector name to use as benchmark line
        last_n_years: number of recent years to show for the historical lines

    Returns:
        str: HTML fragment (no plotlyjs)
    """
    from db import extract_quarter_number
    import math
    import numpy as np
    from sklearn.linear_model import LinearRegression

    # ── Build quarterly averages for the sector (all history, for model training) ──
    sector_df = df[df['Sector'] == sector].copy()
    sector_df['Q'] = sector_df['Period'].apply(extract_quarter_number)
    sector_df = sector_df[sector_df['Q'].notna()]
    sector_df['Q'] = sector_df['Q'].astype(int)
    sector_df['TimeIndex'] = sector_df['Year'] + (sector_df['Q'] - 1) * 0.25

    grouped = (
        sector_df.groupby(['Year', 'Q', 'TimeIndex'])['AbsenteeismPercentage']
        .mean()
        .reset_index()
        .sort_values('TimeIndex')
    )

    if len(grouped) < 4:
        return ''

    # ── Train model (same as predict.py) ──────────────────────────────────────
    time_idx = grouped['TimeIndex'].values
    q_vals = grouped['Q'].values
    X = np.column_stack([
        time_idx,
        (q_vals == 2).astype(float),
        (q_vals == 3).astype(float),
        (q_vals == 4).astype(float),
    ])
    y = grouped['AbsenteeismPercentage'].values
    model = LinearRegression().fit(X, y)

    last_row = grouped.iloc[-1]
    last_year = int(last_row['Year'])
    last_q = int(last_row['Q'])
    last_time = float(last_row['TimeIndex'])
    last_actual = float(last_row['AbsenteeismPercentage'])

    # Residual anchoring
    x_last = np.array([[last_time, float(last_q == 2), float(last_q == 3), float(last_q == 4)]])
    residual = last_actual - model.predict(x_last)[0]

    # ── Generate 4 forecast quarters ──────────────────────────────────────────
    forecast_x, forecast_y = [], []
    for i in range(1, 5):
        next_q_abs = last_q + i
        next_year = last_year + (next_q_abs - 1) // 4
        next_q_num = ((next_q_abs - 1) % 4) + 1
        next_time = next_year + (next_q_num - 1) * 0.25
        x_pred = np.array([[next_time, float(next_q_num == 2), float(next_q_num == 3), float(next_q_num == 4)]])
        forecast_x.append(f'{next_year}-Q{next_q_num}')
        forecast_y.append(round(model.predict(x_pred)[0] + residual, 2))

    # ── Slice to last N years for display ─────────────────────────────────────
    max_year = int(grouped['Year'].max())
    min_year = max_year - last_n_years + 1
    display = grouped[grouped['Year'] >= min_year]
    display_keys = (display['Year'].astype(str) + '-Q' + display['Q'].astype(str)).tolist()
    display_vals = display['AbsenteeismPercentage'].round(2).tolist()

    # Mock "jouw bedrijf": historical period only, slightly above sector average
    mock_y = [round(v + 1.2 + 0.3 * math.sin(i * 1.1), 2) for i, v in enumerate(display_vals)]

    fig = go.Figure()

    # Historical benchmark line
    fig.add_trace(go.Scatter(
        x=display_keys, y=display_vals,
        mode='lines+markers',
        name='G Handel (CBS)',
        line=dict(color='#0d6efd', width=2),
        marker=dict(color='#0d6efd', size=5),
        hovertemplate='<b>Sector benchmark</b><br>%{x}: %{y:.2f}%<extra></extra>',
    ))

    # Forecast line (connects from last historical point)
    fig.add_trace(go.Scatter(
        x=[display_keys[-1]] + forecast_x,
        y=[display_vals[-1]] + forecast_y,
        mode='lines+markers',
        name='Prognose (CBS trend)',
        line=dict(color='#0d6efd', width=2, dash='dot'),
        marker=dict(color='#0d6efd', size=5, symbol='circle-open'),
        hovertemplate='<b>Prognose</b><br>%{x}: %{y:.2f}%<extra></extra>',
    ))

    # Mock "jouw bedrijf" — historical only
    fig.add_trace(go.Scatter(
        x=display_keys, y=mock_y,
        mode='lines+markers',
        name='Jouw bedrijf (voorbeeld)',
        line=dict(color='#f59f00', width=2),
        marker=dict(color='#f59f00', size=5),
        hovertemplate='<b>Jouw bedrijf</b><br>%{x}: %{y:.2f}%<extra></extra>',
    ))

    fig.update_layout(
        xaxis=dict(tickangle=-45, showgrid=False, tickfont=dict(size=10)),
        yaxis=dict(title=dict(text='Verzuim %', standoff=5), tickfont=dict(size=10), showgrid=True, gridcolor='#f0f0f0'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=11)),
        hovermode='x unified',
        margin=dict(l=50, r=20, t=40, b=60),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=280,
    )

    return fig.to_html(full_html=False, include_plotlyjs=False, div_id='hero-preview-chart')

