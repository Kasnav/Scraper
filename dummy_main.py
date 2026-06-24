from Scraper.datasetManager import json_to_excel

json_to_excel(
    json_filename="file.json",
    excel_filename="live_tenders_pipeline.xlsx"
)

print("Excel generated")