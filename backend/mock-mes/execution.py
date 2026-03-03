import database
from inventory import check_stock

def start_production_run(job_id):
    db = database.connect()
    stock = check_stock("raw_material_A")
    return f"Starting job {job_id} with {stock}"