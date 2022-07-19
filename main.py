from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class StoreInput(BaseModel):
    store_no: str
    sku_no: int
    qty_req: int

class StoreOutput(BaseModel):
    store: str
    type: str

@app.post("/soh/")
async def fetch_stores(input: StoreInput):
    return do_something(input)

def do_something(input):
    soh_list = []
    for i in range(1,10):
        soh_list.append(StoreOutput(store = "dummy_" + str(i), type = "dummy_store"))
    return soh_list