from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from google.cloud import datastore


app = FastAPI()

class StoreInput(BaseModel):
    sku_no: int
    qty_req: int

class StoreInputList(BaseModel):
    store_no: int
    sku_list: List[StoreInput]

class StoreOutput(BaseModel):
    store: int
    type: str

@app.post("/soh/")
async def fetch_stores(input: StoreInputList):
    sku_values = []
    for sku in input.sku_list:
        sku_values.append(sku.sku_no)

    sku_value_chunks = chunks(sku_values, 10)

    #Retrieve values for the requested store from Datastore
    requested_store_soh = get_requested_store_stock(input.store_no, sku_values)

    #hub and route code values are needed in order to do additional checks if the requested store cannot fulfill the order
    hub_code = requested_store_soh[0]['hub_code']
    route_code = requested_store_soh[0]['route_code']

    hub_route_match_list_soh = get_hub_route_match(
        hub_code, route_code, sku_value_chunks)

    hub_match_list_soh = get_hub_match(
         hub_code, sku_value_chunks)

    route_list_soh = get_route_match(
        route_code, sku_value_chunks)

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

    return returned_store_objects + returned_hub_route_stores + returned_hub_stores + returned_route_stores

def get_requested_store_stock(store_no, sku_values):
    client = datastore.Client()

    keys = []

    for sku in sku_values:
        keys.append(client.key(
            "sohval", "{0}-{1}".format(store_no, sku), namespace='soh'))

    results = list(client.get_multi(keys))

    return results

def get_hub_route_match(hub_code, route_code, sku_value_chunks):
    client = datastore.Client()
    
    combined_query_results = []
    for sku_batch in sku_value_chunks:
        query = client.query(kind="sohval", namespace='soh')
        query.add_filter('hub_code', '=', hub_code)
        query.add_filter('route_code', '=', route_code)
        query.add_filter('sku_no', "IN", sku_batch)

        combined_query_results = combined_query_results + list(query.fetch())

    return combined_query_results


def get_hub_match(hub_code, sku_value_chunks):
    client = datastore.Client()

    combined_query_results = []
    for sku_batch in sku_value_chunks:
        query = client.query(kind="sohval", namespace='soh')
        query.add_filter('hub_code', '=', hub_code)
        query.add_filter('sku_no', "IN", sku_batch)

        combined_query_results = combined_query_results + list(query.fetch())

    return combined_query_results


def get_route_match(route_code, sku_value_chunks):
    client = datastore.Client()

    combined_query_results = []
    for sku_batch in sku_value_chunks:
        query = client.query(kind="sohval", namespace='soh')
        query.add_filter('route_code', '=', route_code)
        query.add_filter('sku_no', "IN", sku_batch)

        combined_query_results = combined_query_results + list(query.fetch())

    return combined_query_results

def get_order_fulfilled_stores(api_input, datastore_output, match_type, request_store, processed_so_far = []):
    #TODO understand what I've done here
    prev_store = -1
    store_obj_list = []
    store_list = []
    order_fulfilled = True

    for single_entry in datastore_output:
        if single_entry['store_no'] not in processed_so_far:
            if single_entry['store_no'] != prev_store and prev_store != -1:
                #Previous condition indicates that processing of a store is complete
                if order_fulfilled:
                    if match_type == 'STORE_MATCH' or prev_store != request_store:
                        store_obj_list.append(StoreOutput(store=prev_store, type=match_type))
                        store_list.append(prev_store)
                else:
                    order_fulfilled = True

            for sku_req in api_input:
                if single_entry['sku_no'] == sku_req.sku_no and order_fulfilled:
                    if (single_entry['soh_qty'] < sku_req.qty_req):
                        order_fulfilled = False

            prev_store = single_entry['store_no']

    #Below appends the final store to list if it can fulfill order
    if order_fulfilled:
        if match_type == 'STORE_MATCH' or prev_store != request_store and prev_store != -1:
            store_obj_list.append(StoreOutput(store=prev_store, type=match_type))
            store_list.append(prev_store)

    return store_obj_list,store_list

def chunks(xs, n):
    n = max(1, n)
    return (xs[i:i+n] for i in range(0, len(xs), n))
