"""
Labour Market Analysis Flask Application

A web application for analyzing Dutch labour market data,
specifically absenteeism rates across different sectors.
"""
from flask import Flask, render_template
from utils import load_data_from_db, prepare_context

app = Flask(__name__)


@app.route('/')
def index():
    """Render the main dashboard page."""
    df, pred_df = load_data_from_db()
    context = prepare_context(df, pred_df)
    return render_template('index.html', **context)


if __name__ == '__main__':
    app.run(debug=True)
