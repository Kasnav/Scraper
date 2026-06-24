from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import json, pandas as pd

from Scraper.target_profiles import HealthTargetProfiles, DefenceTargetProfiles, CorporateTargetProfiles, PetsTargetProfiles

model = SentenceTransformer('all-MiniLM-L6-v2')
print("✓ Model loaded")
print("Embedding dim:", model.get_sentence_embedding_dimension())

health_emb  = model.encode(HealthTargetProfiles,  normalize_embeddings=True)
defence_emb = model.encode(DefenceTargetProfiles, normalize_embeddings=True)
corporate_emb = model.encode(CorporateTargetProfiles, normalize_embeddings=True)
pets_emb = model.encode(PetsTargetProfiles, normalize_embeddings=True)

health_vec  = health_emb.mean(axis=0, keepdims=True)
defence_vec = defence_emb.mean(axis=0, keepdims=True)
corporate_vec = corporate_emb.mean(axis=0, keepdims=True)
pets_vec = pets_emb.mean(axis=0, keepdims=True)


def score_tender(tender: dict, threshold=0.35) -> dict:
    text = f"{tender.get('TenderTitle', '')} {tender.get('WorkDescription', '')}"
    vec  = model.encode([text], normalize_embeddings=True)

    h_score = float(cosine_similarity(vec, health_vec)[0][0])
    d_score = float(cosine_similarity(vec, defence_vec)[0][0])
    c_score = float(cosine_similarity(vec, corporate_vec)[0][0])
    p_score = float(cosine_similarity(vec, pets_vec)[0][0])

    scores = {
        "Health"    : h_score,
        "Defence"   : d_score,
        "Corporate" : c_score,
        "Pets"      : p_score,
    }

    passing = {sector: score for sector, score in scores.items() if score >= threshold}
    top_sector = max(passing, key=passing.get) if passing else "None"

    return {
        "health_score"    : round(h_score, 4),
        "defence_score"   : round(d_score, 4),
        "corporate_score" : round(c_score, 4),
        "pet_score"       : round(p_score, 4),
        "health_pass"     : h_score >= threshold,
        "defence_pass"    : d_score >= threshold,
        "corporate_pass"  : c_score >= threshold,
        "pets_pass"       : p_score >= threshold,
        "sector"          : top_sector,
    }

print("✓ score_tender() ready")

def semantic_filter(tenders, threshold=0.35):
    results = [score_tender(t, threshold) for t in tenders]
    df = pd.DataFrame(results)
    print(df[[
        'health_score', 'defence_score', 'corporate_score', 'pet_score',
        'health_pass',  'defence_pass',  'corporate_pass',  'pets_pass',
        'sector'
    ]])

    # filtered = [
    #     {**tender, **result}
    #     for tender, result in zip(tenders, results)
    #     if any([
    #         result["health_pass"],
    #         result["defence_pass"],
    #         result["corporate_pass"],
    #         result["pets_pass"],
    #     ])
    # ]
    filtered = [
        {**tender, **result}
        for tender, result in zip(tenders, results)
    ]
    print(f"Input tenders: {len(tenders)}")
    print(f"Filtered tenders: {len(filtered)}")
    with open("file.json", "w") as f:
        json.dump(filtered, f, indent=2)

    print(f"✓ Exported {len(filtered)} / {len(tenders)} tenders → file.json")