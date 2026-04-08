from flask import Flask, render_template_string
import pandas as pd
import sqlite3
import os

app = Flask(__name__)

@app.route('/')
def index():
    # Load data
    conn = sqlite3.connect('data.db')
    df = pd.read_sql('SELECT * FROM cleaned_absenteeism LIMIT 10', conn)
    pred_df = pd.read_sql('SELECT * FROM predictions', conn)
    conn.close()
    
    # Simple HTML template
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Labour Market Analysis</title></head>
    <body>
    <h1>Labour Market Analysis - Absenteeism</h1>
    <h2>Sample Data</h2>
    {{ table|safe }}
    <h2>Predictions</h2>
    {{ pred_table|safe }}
    <h2>Plots</h2>
    {% for file in plots %}
    <img src="/static/{{ file }}" alt="{{ file }}">
    {% endfor %}
    </body>
    </html>
    """
    
    table = df.to_html()
    pred_table = pred_df.to_html()
    plots = [f for f in os.listdir('static') if f.startswith('plot_') and f.endswith('.png')]
    
    return render_template_string(html, table=table, pred_table=pred_table, plots=plots)

if __name__ == "__main__":
    app.run(debug=True)