import uuid
from datetime import datetime
from typing import List, Dict

from fastapi import FastAPI
from pydantic import BaseModel


# Part 1: Data Models and Structures
class Property:
    def __init__(self, property_id: str, user_id: str, details: dict):
        self.property_id = property_id
        self.user_id = user_id
        self.details = details
        self.status = 'available'
        self.timestamp = datetime.now()


class PropertyManager:
    def __init__(self):
        self.properties: Dict[str, Property] = {}
        self.user_portfolios: Dict[str, List[str]] = {}
        self.search_index: Dict[str, List[str]] = {}

    # Add Property
    def add_property(self, user_id: str, property_details: dict) -> str:
        property_id = str(uuid.uuid4())
        property_obj = Property(property_id, user_id, property_details)

        # Store property and update user portfolio
        self.properties[property_id] = property_obj
        if user_id not in self.user_portfolios:
            self.user_portfolios[user_id] = []
        self.user_portfolios[user_id].append(property_id)

        # Update search indices
        self._update_index(property_id, property_details)
        return property_id

    # Update Property Status
    def update_property_status(self, property_id: str, status: str, user_id: str) -> bool:
        if property_id not in self.properties:
            return False
        property_obj = self.properties[property_id]
        if property_obj.user_id != user_id:
            return False

        property_obj.status = status
        # Update search index for availability
        if status == 'sold':
            self.search_index['available'].remove(property_id)
        elif status == 'available':
            self.search_index.setdefault('available', []).append(property_id)
        return True

    # Get Properties by User
    def get_user_properties(self, user_id: str) -> List[Property]:
        property_ids = self.user_portfolios.get(user_id, [])
        return sorted(
            [self.properties[pid] for pid in property_ids],
            key=lambda x: x.timestamp,
            reverse=True
        )

    # Update Search Indices
    def _update_index(self, property_id: str, details: dict):
        # Index by price range, location, and type
        price_range = f"{int(details['price'] // 100000)}00k"
        location = details['location']
        property_type = details['property_type']

        for key in [price_range, location, property_type, 'available']:
            if key not in self.search_index:
                self.search_index[key] = []
            self.search_index[key].append(property_id)


class PropertySearch:
    def __init__(self, manager: PropertyManager):
        self.manager = manager

    # Search Properties
    def search_properties(self, criteria: dict) -> List[Property]:
        results = set()
        for key, value in criteria.items():
            if key in self.manager.search_index:
                results.update(self.manager.search_index.get(value, []))

        filtered_properties = [self.manager.properties[pid] for pid in results if
                               self.manager.properties[pid].status == 'available']
        return sorted(filtered_properties, key=lambda x: x.timestamp, reverse=True)

    # Shortlist Property
    def shortlist_property(self, user_id: str, property_id: str) -> bool:
        if property_id not in self.manager.properties:
            return False
        property_obj = self.manager.properties[property_id]
        if property_obj.status == 'sold':
            return False
        if user_id not in self.manager.user_portfolios:
            self.manager.user_portfolios[user_id] = []
        if property_id in self.manager.user_portfolios[user_id]:
            return False
        self.manager.user_portfolios[user_id].append(property_id)
        return True

    # Get Shortlisted Properties
    def get_shortlisted(self, user_id: str) -> List[Property]:
        property_ids = self.manager.user_portfolios.get(user_id, [])
        return sorted(
            [self.manager.properties[pid] for pid in property_ids if
             self.manager.properties[pid].status == 'available'],
            key=lambda x: x.timestamp,
            reverse=True
        )


# Part 2: API Implementation
app = FastAPI()
manager = PropertyManager()
search = PropertySearch(manager)


class PropertyCreate(BaseModel):
    location: str
    price: float
    property_type: str
    description: str
    amenities: List[str]


# Create Property API
@app.post("/api/v1/properties")
async def create_property(property_data: PropertyCreate, user_id: str):
    property_id = manager.add_property(user_id, property_data.dict())
    return {"property_id": property_id}


# Search Properties API
@app.get("/api/v1/properties/search")
async def search_properties(
        min_price: float = None,
        max_price: float = None,
        location: str = None,
        property_type: str = None,
        page: int = 1,
        limit: int = 10
):
    criteria = {}
    if location:
        criteria['location'] = location
    if property_type:
        criteria['property_type'] = property_type
    if min_price and max_price:
        criteria['price'] = f"{int(min_price // 100000)}00k-{int(max_price // 100000)}00k"

    results = search.search_properties(criteria)
    start = (page - 1) * limit
    end = start + limit
    return results[start:end]
