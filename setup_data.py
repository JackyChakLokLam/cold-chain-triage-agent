import pandas as pd

data = [
    {
        "shipment_id": "NCC-1001",
        "carrier": "PolarExpress Freight",
        "carrier_email": "dispatch@polarexpress.example.com",
        "origin": "Concord, ON",
        "destination": "Ottawa, ON",
        "eta_status": "Delayed +3.5 hrs (Hwy 401 accident near Kingston)",
        "temp_c": 2.1,
        "required_temp_range": "0C to 4C",
        "raw_driver_note": "Driver John Smith (416-555-0192) stuck behind multi-vehicle collision, reefer unit holding steady at 2.1C."
    },
    {
        "shipment_id": "NCC-1002",
        "carrier": "MapleCold Logistics",
        "carrier_email": "ops@maplecold.example.com",
        "origin": "Concord, ON",
        "destination": "London, ON",
        "eta_status": "On Time",
        "temp_c": 2.8,
        "required_temp_range": "0C to 4C",
        "raw_driver_note": "Driver Sarah Lee cleared Woodstock checkpoint, normal transit."
    },
    {
        "shipment_id": "NCC-1003",
        "carrier": "FrostLine Transport",
        "carrier_email": "MISSING",
        "origin": "Brampton, ON",
        "destination": "Montreal, QC",
        "eta_status": "Delayed +2.0 hrs",
        "temp_c": 7.4,
        "required_temp_range": "0C to 4C",
        "raw_driver_note": "ALERT: Reefer compressor fault reported by driver Mike Chen (647-555-0881). Box temp rising to 7.4C!"
    }
]

df = pd.DataFrame(data)
df.to_excel("shipments.xlsx", index=False)
print("shipments.xlsx generated with 3 test records.")