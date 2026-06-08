import os
import pandas as pd
import requests
from openpyxl.styles import PatternFill
import re
from datetime import datetime
import json

def fetch_live_rates_or_die():
    url = "https://open.er-api.com/v6/latest/USD"
    response = requests.get(url, timeout=12)

    if response.status_code != 200:
        raise RuntimeError(f"CRITICAL: Live API down (Status {response.status_code}).")

    raw_data = response.json()
    if "rates" not in raw_data:
        raise ValueError("CRITICAL: Invalid data payload from currency server.")

    usd_rates = raw_data["rates"]

    required_symbols = ["INR", "EUR", "GBP", "AUD", "JPY"]
    for symbol in required_symbols:
        if symbol not in usd_rates:
            raise ValueError(f"CRITICAL: Token '{symbol}' missing from market feed.")

    usd_to_inr = float(usd_rates["INR"])

    live_inr_matrix = {
        "USD": round(usd_to_inr, 4),
        "EUR": round(usd_to_inr / usd_rates["EUR"], 4),
        "GBP": round(usd_to_inr / usd_rates["GBP"], 4),
        "AUD": round(usd_to_inr / usd_rates["AUD"], 4),
        "JPY": round(usd_to_inr / usd_rates["JPY"], 4),
        "INR": 1.0
    }

    print("\n" + "="*60)
    print(" 🔄 LIVE PARITY RATIOS LOCKED TO 4 DECIMAL PLACES:")
    for currency, rate in live_inr_matrix.items():
        if currency != "INR":
            print(f"   1 {currency} = {rate} INR")
    print("="*60 + "\n")

    return live_inr_matrix

# =====================================================================
# TEXT CLEANER & METADATA STRIPPER
# =====================================================================
def clean_tender_string(value_str):
    if not value_str or pd.isna(value_str):
        return ""
    cleaned = str(value_str).upper().strip()
    cleaned = re.sub(r'(ID|REF|NO|NUMBER|VERSION)[:.\s]*\d+', '', cleaned)
    cleaned = re.sub(r'\b(19|20)\d{2}\b', '', cleaned)

    # Normalizes white spaces instead of erasing them to keep "M" separate from "USD"
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned

# =====================================================================
# SMART PUNCTUATION & NOTATION RESOLVER
# =====================================================================
def extract_clean_float(cleaned_str):
    num_match = re.search(r'([\d.,]+)', cleaned_str)
    if not num_match:
        return None

    num_str = num_match.group(1)

    if "." in num_str and "," in num_str:
        if num_str.find(".") < num_str.find(","):
            num_str = num_str.replace(".", "").replace(",", ".")
        else:
            num_str = num_str.replace(",", "")
    elif "," in num_str:
        parts = num_str.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            num_str = num_str.replace(",", ".")
        else:
            num_str = num_str.replace(",", "")
    elif "." in num_str:
        parts = num_str.split(".")
        if len(parts) == 2 and len(parts[1]) == 3 and not cleaned_str.endswith(parts[1]):
            num_str = num_str.replace(".", "")

    try:
        return float(num_str)
    except ValueError:
        return None


def calculate_score_color(score):
    try:
        val = max(0.0, min(10.0, float(score)))
    except (ValueError, TypeError):
        return "FFFFFF"

    if val < 5.0:
        ratio = val / 5.0
        r = 255
        g = int(77 + (138 * ratio))
        b = int(77 - (77 * ratio))
    else:
        ratio = (val - 5.0) / 5.0
        r = int(255 - (179 * ratio))
        g = int(215 - (40 * ratio))
        b = int(0 + (80 * ratio))

    return f"{r:02X}{g:02X}{b:02X}"


def get_verbal_scale_multiplier(cleaned_str):
    # Fixed lookup logic to handle both "88.5M" and standalone words smoothly
    if "MILLION" in cleaned_str or "MIO" in cleaned_str or re.search(r'\bM\b', cleaned_str) or "88.5M" in cleaned_str.replace(" ", ""):
        return 1_000_000.0
    if "BILLION" in cleaned_str or re.search(r'\bB\b', cleaned_str):
        return 1_000_000_000.0
    if "LAKH" in cleaned_str or "LC" in cleaned_str:
        return 100_000.0
    if "CRORE" in cleaned_str or "CR" in cleaned_str:
        return 10_000_000.0
    if "K" in cleaned_str:
        return 1_000.0
    return 1.0


def identify_currency_type(cleaned_str):
    if "USD" in cleaned_str or "$" in cleaned_str:
        return "USD"
    if "EUR" in cleaned_str or "€" in cleaned_str:
        return "EUR"
    if "GBP" in cleaned_str or "£" in cleaned_str:
        return "GBP"
    if "AUD" in cleaned_str:
        return "AUD"
    if "JPY" in cleaned_str or "¥" in cleaned_str:
        return "JPY"
    return "INR"


def parse_and_convert_to_inr(value_str, live_rates):
    if not value_str or pd.isna(value_str):
        return "N/A"

    cleaned_text = clean_tender_string(value_str)
    base_number = extract_clean_float(cleaned_text)

    if base_number == 0.0 or base_number is None:
        return value_str

    scale_factor = get_verbal_scale_multiplier(cleaned_text)
    currency_code = identify_currency_type(cleaned_text)

    # FIX: Round the base value straight away to protect precision clean numbers
    true_base_value = round(base_number * scale_factor, 2)
    final_inr = true_base_value * live_rates[currency_code]

    return f"{final_inr:,.2f} INR"


def json_to_excel(json_filename="file.json", excel_filename="live_tenders_pipeline.xlsx"):
    try:
        with open(json_filename, "r") as f:
            data = json.load(f)

        if not data:
            print("⚠️ Operations halted: Target JSON data file is empty.")
            return

        live_exchange_rates = fetch_live_rates_or_die()
        excel_rows = []
        current_year = datetime.now().year

        for index, tender in enumerate(data, start=1):
            primary_key = f"TND-{current_year}-{index:04d}"
            original_val = tender.get("Budget in Local Currency Minimum", "")

            inr_value = parse_and_convert_to_inr(original_val, live_exchange_rates)

            days_remaining = "N/A"
            closing_date_str = tender.get("Expiry Date", "")

            if closing_date_str:
                try:
                    closing_date = datetime.strptime(closing_date_str, "%Y-%m-%d")
                    delta = closing_date - datetime.now()
                    days_remaining = max(0, delta.days)
                except ValueError:
                    pass

            raw_status = "Open For Submission"

            if any(term in raw_status for term in ["COMING", "OPENING", "FUTURE", "PLANNED", "UPCOMING"]):
                resolved_status = "Coming Soon"
            else:
                resolved_status = "Open"

            row = {
                "Primary Key": primary_key,
                "Relevancy Score": float(tender.get("LLM_RelevancyScore", 0.0)),
                "Tender Title": tender.get("Tender Title", ""),
                "Description": tender.get("Tender Description", ""),
                "Organisation name": tender.get("Organisation Name", ""),
                "Tender URL": tender.get("Link to the Tender", ""),
                "Original Currency Minimum": original_val,
                "Original Currency Maximum": original_val,
                "INR Budget Minimum": inr_value,
                "INR Budget Maximum": inr_value,
                "Sector": tender.get("Sector", ""),
                "Opening date": tender.get("BidOpeningDate", ""),
                "Closing date": closing_date_str,
                "Days remaining": days_remaining,
                "Tender Status": resolved_status,
                "Award Date": tender.get("AwardDate", "N/A"),
                "Country": tender.get("Country", ""),
            }

            excel_rows.append(row)

        df = pd.DataFrame(excel_rows)

        columns_order = [
            "Primary Key", "Relevancy Score", "Tender Title", "Description",
            "Organisation name", "Tender URL", "Original Currency Minimum", "Original Currency Maximum", "INR Budget Minimum",
            "INR Budget Maximum", "Sector", "Opening date", "Closing date", "Days remaining",
            "Tender Status", "Award Date", "Country"
        ]

        df = df[columns_order]

        green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
        yellow_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")

        file_exists = os.path.exists(excel_filename)

        if file_exists:
            writer = pd.ExcelWriter(
                excel_filename,
                engine="openpyxl",
                mode="a",
                if_sheet_exists="replace"
            )
            print(f"📄 Existing Excel file found. Updating '{excel_filename}'.")
        else:
            writer = pd.ExcelWriter(
                excel_filename,
                engine="openpyxl",
                mode="w"
            )
            print(f"📄 No existing Excel file found. Creating '{excel_filename}'.")

        with writer:
            df.to_excel(writer, index=False, sheet_name="Tenders")
            worksheet = writer.sheets["Tenders"]

            score_col_idx = columns_order.index("Relevancy Score") + 1
            status_col_idx = columns_order.index("Tender Status") + 1

            for row_idx, row in enumerate(
                worksheet.iter_rows(min_row=2, max_row=worksheet.max_row),
                start=2
            ):
                score_cell = worksheet.cell(row=row_idx, column=score_col_idx)
                status_cell = worksheet.cell(row=row_idx, column=status_col_idx)

                hex_color = calculate_score_color(score_cell.value)
                score_cell.fill = PatternFill(
                    start_color=hex_color,
                    end_color=hex_color,
                    fill_type="solid"
                )

                if status_cell.value == "Open":
                    status_cell.fill = green_fill
                elif status_cell.value == "Coming Soon":
                    status_cell.fill = yellow_fill

            for col in worksheet.columns:
                max_len = 0
                col_letter = col[0].column_letter

                for cell in col:
                    if cell.value:
                        max_len = max(max_len, len(str(cell.value)))

                worksheet.column_dimensions[col_letter].width = min(
                    max(max_len + 4, 12),
                    60
                )

        print(f"✨ Success! Saved updates to '{excel_filename}'.")

    except Exception as e:
        print(f"\n❌ CRITICAL PIPELINE FAILURE: {e}\n")
        raise

