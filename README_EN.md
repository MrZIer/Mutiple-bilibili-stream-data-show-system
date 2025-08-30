# Bilibili Live Data Real-time Monitoring System

A real-time monitoring system for Bilibili live streaming data that supports multi-room simultaneous monitoring, real-time collection of danmaku (comments), gifts, popularity and other data, with dual Y-axis visualization charts.

## Features

- 🎯 **Multi-room Monitoring**: Monitor multiple live rooms simultaneously
- 💬 **Real-time Danmaku Collection**: Real-time acquisition of danmaku content and user information
- 🎁 **Gift Data Statistics**: Statistics of gift quantities and values
- 📊 **Dual Y-axis Visualization**: Independent display of danmaku and gift data trends
- 💾 **JSON Data Storage**: Structured storage of all collected data
- ⚡ **Real-time Updates**: 1-second interval chart and data updates

## Project Structure

```
bilibili_data/
├── spider_live_data/
│   ├── live_data_visualizer.py    # Data visualization module
│   ├── data_storage.py            # Data storage module
│   ├── get_data_with_visualization.py  # Main program entry
│   └── data/                      # Data storage directory
├── live_data/                     # Historical data files
├── README.md                      # Chinese documentation
├── README_EN.md                   # English documentation
└── requirements.txt               # Dependencies
```

## Installation

### Prerequisites

- Python 3.7+
- Required packages listed in requirements.txt

### Install Dependencies

```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install bilibili-api matplotlib numpy asyncio
```

## Usage

1. **Configure Room IDs**
   
   Edit the room ID list in `get_data_with_visualization.py`:
   ```python
   room_ids = [6, 7720242]  # Replace with your target room IDs
   ```

2. **Run the Program**
   ```bash
   cd spider_live_data
   python get_data_with_visualization.py
   ```

3. **View Results**
   - Real-time visualization window will open automatically
   - Data files are saved in the `data/` directory as JSON format

## Data Format

### JSON Storage Structure

```json
{
  "room_info": {
    "room_id": 6,
    "uname": "Streamer Name",
    "title": "Stream Title",
    "created_at": "2025-08-30T18:59:39.598094"
  },
  "data": {
    "timestamps": ["2025-08-30T19:05:59.307459"],
    "popularity": [9999],
    "watched": [181948010],
    "likes": [275274],
    "total_danmaku_at_time": [346],
    "total_gifts_at_time": [0]
  },
  "real_time": {
    "current_popularity": 9999,
    "current_watched": 181948010,
    "current_likes": 275274,
    "total_danmaku": 346,
    "total_gifts": 0,
    "last_update": "2025-08-30T19:06:01.469806"
  },
  "recent_danmaku": [...],
  "recent_gifts": [...]
}
```

### Data Fields Description

- **room_info**: Basic room information
- **data**: Time-series data (popularity, views, likes, cumulative danmaku/gifts)
- **real_time**: Real-time status data
- **recent_danmaku**: Recent danmaku records (last 100)
- **recent_gifts**: Recent gift records (last 50)

## Visualization Features

### Dashboard Layout

- **Left Panel**: Dual Y-axis chart showing cumulative danmaku and gift counts
  - Blue line (Left Y-axis): Cumulative danmaku count
  - Green line (Right Y-axis): Cumulative gift count
- **Middle Panel**: Real-time status information
  - Room ID and data file name
  - Current popularity, viewers, likes
  - Cumulative statistics with growth rates
  - Last update timestamp
- **Right Panel**: Real-time danmaku scrolling display
  - Latest 10 danmaku messages
  - Timestamp and username information

### Key Features

- **Independent Scaling**: Each Y-axis scales independently for optimal data visualization
- **Real-time Updates**: 1-second refresh rate
- **Data Persistence**: All data saved to JSON files for later analysis
- **Multi-room Support**: Monitor multiple streams simultaneously

## API Reference

### Core Classes

#### `LiveDataVisualizer`
Main visualization class handling real-time chart updates.

```python
visualizer = LiveDataVisualizer(room_ids)
visualizer.start()  # Start visualization
```

#### `DataStorage`
Data persistence class managing JSON file operations.

```python
storage = DataStorage(data_dir="data")
await storage.init_room_info(room_ids)
storage.save_data(room_id, data_type, value, extra_data)
```

### Event Handlers

The system automatically handles various live stream events:
- **Danmaku events**: User comments and messages
- **Gift events**: Virtual gift donations
- **Popularity updates**: Real-time viewer metrics

## Configuration

### Customization Options

1. **Data Collection Interval**: Modify the animation interval in `live_data_visualizer.py`
   ```python
   animation.FuncAnimation(self.fig, self.animate, interval=1000)  # 1000ms = 1 second
   ```

2. **Data Retention**: Adjust the maximum number of data points stored in memory
   ```python
   deque(maxlen=30)  # Keep last 30 data points
   ```

3. **Chart Appearance**: Customize colors, fonts, and layout in the visualization module

## Troubleshooting

### Common Issues

1. **Network Connection Errors**
   - Check your internet connection
   - Verify room IDs are valid and streams are live

2. **Missing Dependencies**
   ```bash
   pip install --upgrade bilibili-api matplotlib numpy
   ```

3. **Permission Errors**
   - Ensure write permissions for the data directory
   - Run with appropriate user privileges

4. **Performance Issues**
   - Reduce the number of monitored rooms
   - Increase the update interval
   - Close unnecessary applications

## Future Roadmap

- [ ] **Django Web Interface**: Web-based dashboard for remote monitoring
- [ ] **Redis Caching**: High-performance data caching layer
- [ ] **MySQL Database**: Persistent database storage for historical analysis
- [ ] **ECharts Integration**: Advanced interactive chart library
- [ ] **Data Analysis Features**: Statistical analysis and reporting tools
- [ ] **Room Comparison**: Side-by-side comparison of multiple streams
- [ ] **Alert System**: Notifications for significant events or milestones
- [ ] **Export Functionality**: Data export in various formats (CSV, Excel, etc.)
- [ ] **API Endpoints**: RESTful API for external integrations

## Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Add comments for complex logic
- Include error handling for external API calls
- Test with multiple room IDs before submitting

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [bilibili-api](https://github.com/Nemo2011/bilibili-api) - Python library for Bilibili API
- [matplotlib](https://matplotlib.org/) - Plotting library for Python
- [numpy](https://numpy.org/) - Numerical computing library

## Contact

If you have any questions or suggestions, please:
- Open an issue on GitHub
- Contact the maintainer: [Your Contact Information]

## Disclaimer

This project is for educational and research purposes only. Please respect Bilibili's terms of service and rate limits when using this tool. The authors are not responsible for any misuse of this software.

---

**Note**: This system monitors public live stream data only. No private or sensitive information is collected or stored.