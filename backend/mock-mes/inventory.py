from database import connect

def check_stock(item_id):
    db = connect()
    return f"Stock for {item_id} is 50"