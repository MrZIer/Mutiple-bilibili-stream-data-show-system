from celery import shared_task
import json
from datetime import datetime
from utils.bilibili_client import fetch_live_data
from utils.redis_handler import save_to_redis
from utils.data_processor import process_data

@shared_task
def collect_live_data():
    live_data = fetch_live_data()
    processed_data = process_data(live_data)
    save_to_redis(processed_data)

    # Save data as JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f'live_data_{timestamp}.json', 'w') as json_file:
        json.dump(processed_data, json_file)