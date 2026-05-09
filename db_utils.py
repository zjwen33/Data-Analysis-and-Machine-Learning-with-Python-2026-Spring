import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def get_db():
    """獲取 MongoDB 資料庫實例"""
    mongo_uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
    client = MongoClient(mongo_uri)
    db = client['google_maps_reviews_db']
    return db

def get_reviews_collection():
    """獲取評論集合"""
    return get_db()['reviews']
