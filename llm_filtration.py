# llm_analytical_scorer.py
# code wont work as you must insert an API key
import os
import json
import re
import pandas as pd
from datetime import datetime
import requests
from openpyxl.styles import PatternFill
from google import genai
from google.genai import types

# =====================================================================
# PART 1: LLM ANALYTICAL SCORER ENGINE (UNTOUCHED RUBRIC)
# =====================================================================
def evaluate_and_score_tenders(input_json_path="file.json", output_json_path="file.json"):
    """
    Reads semantically filtered tenders matching the scraper layout, runs them
    through the 2-Dimension Technical Fit Rubric via Gemini 2.5, appends
    the LLM_RelevancyScore, and outputs the exact schema structure to disk.
    """
    client = genai.Client(api_key="") # IMPORTANT add your api key here from google ai studio

    if not os.path.exists(input_json_path):
        print(f"Execution Halted: Input file '{input_json_path}' cannot be located.")
        return False

    with open(input_json_path, "r") as f:
        tenders = json.load(f)

    if not tenders:
        print(f"⚠️ Operations halted: Target input JSON file '{input_json_path}' is empty.")
        return False

    print(f" Successfully loaded {len(tenders)} tenders from semantic cache.")
    print(" Commencing Multi-Criteria Architectural Analysis using Gemini 2.5 Engine...\n")

    system_instruction = """
You are a strict, precise technical auditing system. Your sole task is to evaluate an incoming tender JSON object against an uncompromising 10.0-Point scoring rubric, calculate an exact composite float score out of 10.0, and append that calculated score to the JSON object under the key "LLM_RelevancyScore".

CRITICAL CORE DIRECTION:
- Evaluate the tender EXCLUSIVELY based on the structural criteria provided below.
- You are completely open to custom product development, new product lines, and alternative form factors. Do not penalize a tender for proposing a brand-new type of device or hardware as long as it tracks sensor metrics.
- Completely ignore the volume/scale of deployment, the geographical location, or who the buying entity is.
- You must be uncompromisingly strict: do not assume or infer capabilities. Score only what is explicitly stated in the text.

=====================================================================
SCORING MATRIX (MAXIMUM 10.0 POINTS)
=====================================================================

--- DIMENSION 1: CORE TRACKING & SENSOR REQUIREMENT (0.0 to 5.0 Points) ---
This dimension evaluates if the project fundamentally revolves around collecting data via sensor hardware.

* 5.0 Points: Direct Sensor/Tracking Match
  The tender explicitly mandates tracking, measuring, or collecting data using physical hardware, sensors, biometric components, wearables, portable trackers, or data-collection points. This applies across any sector (Health, Defence, Corporate, Pet tracking, or an entirely new tracking domain).

* 0.0 Points: Unrelated Categories / No Sensors
  The project is for a completely unrelated infrastructure, hardware, or services with zero tracking sensor context. Examples include fixed CCTV optical security camera networks, physical perimeter fencing, construction/civil engineering, brick-and-mortar office furniture supply, or general administrative staffing.

--- DIMENSION 2: SENSIO AI LINGUISTIC & TARGET TRACK MATCH (0.0 to 2.5 Points) ---
This dimension utilizes your semantic understanding to evaluate if the descriptive vocabulary matches the core target tracking ecosystems of Sensio AI.

* 2.5 Points: High-Value Target Domain Context
  The text utilizes vocabulary, terminology, or nomenclature that aligns with any of the following four primary semantic tracking tracks. It does not require exact word matching; evaluate based on context, synonyms, and operational intent:

  1. The Physiological/Clinical Track: Language referencing human health status, patient diagnostics, clinical monitoring, vital sign acquisition, medical trials, or biometric data logging.
  2. The Tactical/Operational Track: Language referencing personnel field tracking, soldier readiness, infantry deployment, emergency first responder status, or physical strain monitoring under stressful operations.
  3. The Workforce/Occupational Track: Language referencing everyday corporate employee metrics, corporate wellness programs, desk-bound staff activity tracking, office lifestyle optimization, or personnel movement analytics within a business infrastructure.
  4. The Animal/Veterinary Track: Language referencing canine, feline, livestock, or service animal tracking, biological vitals for animals, or specialized mobile tracking frameworks like smart collars or animal harnesses.

* 0.0 Points: Industrial / Static Asset Context
  The text completely lacks any human, biological, or personal workforce tracking context. It describes tracking inanimate, industrial, or mass logistics objects (e.g., shipping crates, fleet vehicles, factory raw materials) using purely industrial asset management phrasing, without any crossover into Sensio AI's human, employee, or animal tracking tracks.

--- DIMENSION 3: CONNECTIVITY & DATA MOBILITY (0.0 to 2.5 Points) ---
This dimension evaluates the operational freedom of data collection and transmission.

* 2.5 Points: Mobile / Wireless Transmission
  The tender requires data to move wirelessly via any modern broadcasting protocols (e.g., Bluetooth/BLE, Wi-Fi, Cellular LTE/5G, Mesh topologies, or Satellite communication) back to a smartphone application, desktop dashboard, cloud ecosystem, or external API endpoints.

* 0.0 Points: Strictly Hard-Wired / Static Tethering
  The tracking hardware is explicitly restricted to fixed, hard-wired connections (e.g., a desktop device that must remain continuously plugged into a physical PC via a USB cable to operate) with zero mobile capability or wireless data broadcasting networks.

=====================================================================
CRITICAL OUTPUT PROTOCOL (UNCOMPROMISING CONSTRAINT)
=====================================================================
- You must output VALID JSON ONLY.
- Do NOT include markdown blocks like ```json or ``` outside of the object.
- Do NOT provide conversational greetings, text introductions, notes, or concluding remarks.
- Do NOT provide reasoning, explanations, justifications, or a breakdown of how the score was calculated.
- Do NOT modify, alter, delete, or reorder any existing key-value pairs inside the incoming JSON object.
- Your output must consist EXCLUSIVELY of the original input fields, with the single addition of the "LLM_RelevancyScore" key populated with your final float value (e.g., 7.5 or 10.0). Any deviation from this rule will break the automated pipeline parser.
"""

    response_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "Primary Key": types.Schema(type=types.Type.STRING),
            "Adapter": types.Schema(type=types.Type.STRING),
            "Country": types.Schema(type=types.Type.STRING),
            "Sector": types.Schema(type=types.Type.STRING),
            "Health or Defence Category": types.Schema(type=types.Type.STRING),
            "Budget Currency": types.Schema(type=types.Type.STRING),
            "Budget in Local Currency Minimum": types.Schema(type=types.Type.STRING),
            "Budget in Local Currency Maximum": types.Schema(type=types.Type.STRING),
            "Budget in INR Minimum": types.Schema(type=types.Type.STRING),
            "Budget in INR Maximum": types.Schema(type=types.Type.STRING),
            "Order Quantity": types.Schema(type=types.Type.STRING),
            "Expiry Date": types.Schema(type=types.Type.STRING),
            "Opening Date": types.Schema(type=types.Type.STRING),
            "Organisation Name": types.Schema(type=types.Type.STRING),
            "Link to the Tender": types.Schema(type=types.Type.STRING),
            "Tender Title": types.Schema(type=types.Type.STRING),
            "Tender Description": types.Schema(type=types.Type.STRING),
            "Special Observation": types.Schema(type=types.Type.STRING),
            "Award Date": types.Schema(type=types.Type.STRING),
            "Timeline": types.Schema(type=types.Type.STRING),
            "Eligibility": types.Schema(type=types.Type.STRING),
            "Keyword included": types.Schema(type=types.Type.STRING),
            "Application Status": types.Schema(type=types.Type.STRING),
            "Current Applicants": types.Schema(type=types.Type.STRING),
            "LLM_RelevancyScore": types.Schema(
                type=types.Type.NUMBER,
                description="The calculated objective relevancy score as a float locked strictly between 0.0 and 10.0"
            )
        }
    )

    enriched_dataset = []

    for index, tender in enumerate(tenders, start=1):
        tender_title = tender.get("Tender Title", "Unknown Identifier")
        print(f" Processing Record {index}/{len(tenders)}: '{tender_title[:45]}...'")

        for key, value in tender.items():
            if value is None:
                tender[key] = "None"

        structured_prompt = (
            f"Please run our 4-pillar architectural assessment matrix against this incoming tender data record. "
            f"Analyze the text and populate the 'LLM_RelevancyScore' float fields:\n\n"
            f"{json.dumps(tender, indent=2)}"
        )

        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=structured_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=0.0,
                ),
            )

            evaluated_item = json.loads(response.text)
            enriched_dataset.append(evaluated_item)

        except Exception as error:
            print(f"  ⚠️ Error encountered while scoring item {index}. Injecting fallback baseline score. Detail: {error}")
            tender["LLM_RelevancyScore"] = 0.0
            enriched_dataset.append(tender)

    with open(output_json_path, "w") as f:
        json.dump(enriched_dataset, f, indent=2)

    print("\n" + "="*60)
    print(f"  ANALYSIS COMPLETION SUCCESS!")
    print(f" Saved precisely scored dataset out to: '{output_json_path}'")
    print("="*60 + "\n")
    return True

if __name__ == "__main__":
    evaluate_and_score_tenders(
        input_json_path="file.json",
        output_json_path="file.json"
    )
