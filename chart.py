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
        margin=dict(l=70, r=40, t=70, b=80),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )

    return fig.to_html(full_html=False, include_plotlyjs='cdn', div_id='plotly-chart')
