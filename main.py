from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from google.cloud import datastore
import os
import redis


app = FastAPI()

class StoreInput(BaseModel):
    sku_no: int
    qty_req: int

class StoreInputList(BaseModel):
    store_no: str
    company_id_no: int
    sku_list: List[StoreInput]

class StoreOutput(BaseModel):
    store: str
    type: str

class StoreSOHItem:
    def __init__(self, store, company_id_no, sku_no, soh_qty):
        self.store = store
        self.company_id_no = company_id_no
        self.sku_no = sku_no
        self.soh_qty = soh_qty

redis_host = os.environ.get('REDISHOST', 'localhost')
redis_port = int(os.environ.get('REDISPORT', 6379))
redis_client = redis.StrictRedis(host=redis_host, port=redis_port)

@app.post("/soh/")
async def fetch_stores(input: StoreInputList):
    sku_values = []
    for sku in input.sku_list:
        sku_values.append(sku.sku_no)

    #sku_value_chunks = chunks(sku_values, 10)

    #Retrieve values for the requested store from Datastore
    requested_store_soh = get_requested_store_stock(input.store_no,input.company_id_no,sku_values)

    #hub and route code values are needed in order to do additional checks if the requested store cannot fulfill the order
    #hub and route data is stored in redis with store:metadata as key:value pair
    store_metadata = get_redis_store_metadata(input.store_no,input.company_id_no)

    hub_route_match_stores = store_metadata['HUB_ROUTE_MATCH']['stores']
    hub_match_stores = store_metadata['HUB_MATCH']['stores']
    route_match_stores = store_metadata['ROUTE_MATCH']['stores']

    hub_route_match_list_soh = get_requested_store_list_stock(
        hub_route_match_stores,input.company_id_no, sku_values)

    hub_match_list_soh = get_requested_store_list_stock(
        hub_match_stores,input.company_id_no, sku_values)

    route_list_soh = route_match_stores(
        hub_match_stores,input.company_id_no, sku_values)

    returned_store_objects,processed_so_far = get_order_fulfilled_stores(
        input.sku_list, requested_store_soh, 'STORE_MATCH', input.store_no)

    returned_hub_route_stores,hub_route_stores_processed = get_order_fulfilled_stores(
        input.sku_list, hub_route_match_list_soh, 'HUB_ROUTE_MATCH', input.store_no,processed_so_far)
    
    processed_so_far = processed_so_far + hub_route_stores_processed

    returned_hub_stores,hub_stores_processed  = get_order_fulfilled_stores(
         input.sku_list, hub_match_list_soh, 'HUB_MATCH', input.store_no,processed_so_far)

    processed_so_far = processed_so_far + hub_stores_processed

    returned_route_stores,route_stores_processed = get_order_fulfilled_stores(
        input.sku_list, route_list_soh, 'ROUTE_MATCH', input.store_no,processed_so_far)

    all_returned_stores = returned_store_objects + returned_hub_route_stores + returned_hub_stores + returned_route_stores
    
    if len(all_returned_stores) == 0:
        return StoreOutput(store=9999999,type="Current order cannot be fulfilled")

    return all_returned_stores

def get_requested_store_stock(store_no,company_id_no, sku_values):

    soh_values = []
    for sku in sku_values:
        soh_qty = redis_client.get(store_no+"|"+company_id_no+"|"+sku)
        soh_values.append(StoreSOHItem(company_id_no=company_id_no,sku_no=sku,store=store_no,soh_qty=soh_qty))

    return soh_values

def get_requested_store_list_stock(store_list,company_id_no, sku_values):
    soh_values = []
    for store in store_list:
        for sku in sku_values:
            soh_qty = redis_client.get(store+"|"+company_id_no+"|"+sku)
            soh_values.append(StoreSOHItem(company_id_no=company_id_no,sku_no=sku,store=store,soh_qty=soh_qty))


def get_order_fulfilled_stores(api_input, redis_output, match_type, request_store, processed_so_far = []):
    #TODO understand what I've done here
    prev_store = -1
    store_obj_list = []
    store_list = []
    order_fulfilled = True


    for single_entry in redis_output:
        if single_entry.store not in processed_so_far:
            if single_entry.store != prev_store and prev_store != -1:
                #Previous condition indicates that processing of a store is complete
                if order_fulfilled:
                    if match_type == 'STORE_MATCH' or prev_store != request_store:
                        store_obj_list.append(StoreOutput(store=prev_store, type=match_type))
                        store_list.append(prev_store)
                else:
                    order_fulfilled = True

            for sku_req in api_input:
                if single_entry.sku_no == sku_req.sku_no and order_fulfilled:
                    if (single_entry.soh_qty< sku_req.qty_req):
                        order_fulfilled = False

            prev_store = single_entry.store

    #Below appends the final store to list if it can fulfill order
    if order_fulfilled:
        if match_type == 'STORE_MATCH' or prev_store != request_store and prev_store != -1:
            store_obj_list.append(StoreOutput(store=prev_store, type=match_type))
            store_list.append(prev_store)

    return store_obj_list,store_list

def get_redis_store_metadata(store_no,company_id_no):
    return redis_client.get(str(store_no) +'|'+str(company_id_no))


