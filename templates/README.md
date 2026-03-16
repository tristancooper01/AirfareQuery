# Airfare Query

United Airlines fare class availability scraper. Enter a route and date range to see which booking/upgrade classes are open on nonstop flights.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Add your MileagePlus credentials (optional — you can also log in manually when the browser opens):
   ```
   cp .env.example .env
   ```
   Then edit `.env` with your username and password.

3. Run the app:
   ```
   python app.py
   ```

4. Open `http://localhost:5000` in your browser.
