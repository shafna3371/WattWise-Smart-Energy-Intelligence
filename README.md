# ⚡ WattWise — AI Energy Intelligence Platform

WattWise is a sophisticated energy monitoring and prediction dashboard that leverages real-world energy consumption datasets and Machine Learning to provide deep insights into household electricity usage.

## 🚀 Key Features

- **Real-Time Simulation**: Continuous "playback" of 15-minute interval energy data on a dynamic dashboard.
- **Predictive Analytics**: An ML model (`electricity_model.pkl`) predicts next month's bill based on current usage trends, temperature, and historical data.
- **Behavioral Profiling**: Automatically categorizes users (e.g., "Night Owl", "Early Bird") based on their energy consumption patterns.
- **Appliance Breakdown**: Detailed tracking of 18 different appliances, showing daily kWh, cost per day, and percentage of total load.
- **Mobile Responsive Design**: Fully optimized for modern mobile and tablet devices with a premium "glassmorphism" aesthetic.
- **Interactive Visualizations**: High-performance charts (Chart.js) showing 24-hour windows, monthly trends, and peer benchmarks.
- **Smart Suggestions**: Data-driven advice on how to reduce consumption and save on electricity bills.

## 🛠️ Tech Stack

- **Backend**: Python, Flask
- **Data Processing**: Pandas, NumPy
- **Machine Learning**: Scikit-Learn (Model tracking)
- **Frontend**: HTML5, CSS3 (Vanilla), JavaScript (ES6+)
- **Charts**: Chart.js
- **Fonts**: Orbitron, Rajdhani (Google Fonts)

## 📁 Project Structure

```text
Mini_project/
├── app.py                  # Flask server and data processing logic
├── 15min_TOD.csv           # 15-minute interval appliance-level data (70k+ rows)
├── Monthly.csv             # Monthly billing and aggregate usage data
├── electricity_model.pkl   # Pre-trained ML model for bill prediction
├── static/                 # Frontend assets
│   ├── logo.png            # Project Logo
│   ├── manifest.json       # PWA Manifest
│   └── sw.js              # Service Worker for PWA
├── templates/              # HTML templates
│   ├── index.html          # Main Dashboard
│   ├── login.html          # Login Page with interactive loader
│   └── profile.html        # User Behavioral Profile Page
└── README.md               # User guide and documentation
```

## 🚥 Getting Started

### 1. Install Dependencies
Ensure you have Python installed, then install the required packages:
```bash
pip install flask pandas numpy scikit-learn
```

### 2. Run the Application
Start the Flask server:
```bash
python3 app.py
```

### 3. Access the Dashboard
Open your browser and navigate to:
```
http://localhost:5000/login
```
- **Demo User**: `demo_user`
- **Access Code**: `wattwise` (or just click "View Demo")

## 📊 Dataset Metadata

- **Interval Data**: 70,176 rows covering 2 years (2024–2025) of 15-minute intervals.
- **Appliances**: Tracks 18 devices including AC, Refrigerators, Induction Stoves, Water Pumps, etc.
- **Calculations**: Carbon footprint is estimated using an Indian grid factor of **0.82 kg CO₂/kWh**.

---
*Built for the Advanced Energy Monitoring Project.*
