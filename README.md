# Labour Market Analysis Tool

This is a Python web application to analyze Dutch labour market data, focusing on absenteeism (ziekteverzuim) from CBS.

## Setup

1. Install Python 3.8+.
2. Create virtual environment: `python -m venv venv`
3. Activate: `venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`

## Usage

1. Fetch data: `python fetch_data.py`
2. Preprocess: `python preprocess.py`
3. Visualize: `python visualize.py`
4. Analyze: `python ai_analyze.py`
5. Run app: `python app.py`

Open http://127.0.0.1:5000/ in browser.

## Features

- Data fetching from CBS OData API
- Data preprocessing and storage in SQLite
- Static plots of trends per sector
- Basic AI forecasting with linear regression
- Web app to view results

## How the App Works

### Architecture
- **Backend**: Flask web framework serves the application.
- **Data Storage**: SQLite database (`data.db`) stores raw, cleaned, and analyzed data.
- **Visualization**: Matplotlib generates static PNG plots saved in `static/` folder.
- **AI**: Scikit-learn for simple linear regression forecasting.

### Data Flow
1. **fetch_data.py**: Retrieves data from CBS API (currently dummy data) and stores in `absenteeism` table.
2. **preprocess.py**: Cleans data, adds `Year` column, stores in `cleaned_absenteeism` table.
3. **visualize.py**: Groups data by sector and year, plots trends, saves PNGs in `static/`.
4. **ai_analyze.py**: Trains linear regression models per sector, predicts next year, stores in `predictions` table.
5. **app.py**: Flask app loads data from DB, renders HTML with tables and image links.

### Web App
- Single route `/` displays:
  - Sample cleaned data table.
  - AI predictions table.
  - Images of plots for each sector.
- Static files (images) served from `static/` folder.

### Files Overview
- `requirements.txt`: Python dependencies.
- `fetch_data.py`: Data acquisition.
- `preprocess.py`: Data cleaning.
- `visualize.py`: Plot generation.
- `ai_analyze.py`: ML analysis.
- `app.py`: Web application.
- `data.db`: SQLite database.
- `static/`: Folder for images.
- `README.md`: This documentation.

For real CBS data, update the API URL in `fetch_data.py` with the correct table ID.