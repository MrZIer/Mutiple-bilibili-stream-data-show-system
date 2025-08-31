# bilibili-live-monitor-django

This project is a Django application designed to collect live streaming data from Bilibili, store it in Redis, visualize it, and periodically save the data as JSON.

## Project Structure

```
bilibili-live-monitor-django
├── manage.py                # Command-line utility for interacting with the Django project
├── requirements.txt         # Lists the dependencies required for the project
├── bilibili_monitor          # Main Django application package
│   ├── __init__.py          # Indicates that the directory is a Python package
│   ├── settings.py          # Configuration settings for the Django project
│   ├── urls.py              # URL patterns for the project
│   ├── wsgi.py              # Entry point for WSGI-compatible web servers
│   └── asgi.py              # Entry point for ASGI-compatible web servers
├── live_data                # Application for handling live data
│   ├── __init__.py          # Indicates that the directory is a Python package
│   ├── admin.py             # Registers models with the Django admin site
│   ├── apps.py              # Configuration for the live_data app
│   ├── models.py            # Defines data models for the application
│   ├── views.py             # View functions that handle requests and responses
│   ├── urls.py              # URL patterns specific to the live_data app
│   ├── tasks.py             # Background tasks for collecting live streaming data
│   ├── migrations            # Directory for database migrations
│   │   └── __init__.py      # Indicates that the migrations directory is a Python package
│   └── templates             # HTML templates for rendering views
│       └── live_data
│           ├── dashboard.html # Template for the dashboard view
│           └── visualization.html # Template for the data visualization view
├── static                   # Static files (CSS, JS)
│   ├── css
│   │   └── style.css        # CSS styles for the project
│   └── js
│       └── charts.js        # JavaScript code for rendering charts and visualizations
├── templates                # Base templates for the project
│   └── base.html            # Base template for extending other templates
├── utils                    # Utility functions for the project
│   ├── __init__.py          # Indicates that the directory is a Python package
│   ├── bilibili_client.py    # Functions for interacting with the Bilibili API
│   ├── redis_handler.py      # Functions for handling Redis data storage
│   └── data_processor.py     # Functions for processing collected data
└── README.md                # Documentation for the project
```

## Setup Instructions

1. **Clone the repository:**
   ```
   git clone <repository-url>
   cd bilibili-live-monitor-django
   ```

2. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

3. **Run migrations:**
   ```
   python manage.py migrate
   ```

4. **Start the development server:**
   ```
   python manage.py runserver
   ```

5. **Access the application:**
   Open your web browser and navigate to `http://127.0.0.1:8000/`.

## Usage

- The application collects live streaming data from Bilibili and stores it in Redis.
- You can visualize the collected data on the dashboard.
- Data is periodically saved as JSON for further analysis.

## Contributing

Feel free to submit issues or pull requests for improvements and bug fixes.