"""Multilingual zero-shot similarity categorisation (Japanese/Korean/Chinese/English).

This is a PRETRAINED open-weight embedding model, NOT a fine-tuned LLM.
Categories are proposals for human review. It NEVER invents product sales.
"""
import json,math
from pathlib import Path

MODEL="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
LABELS={
 "beauty":"Skincare product, face tool, massage brush, hair styling accessory, beauty gadget.",
 "kitchen":"Kitchen utensil, cooking tool, vegetable slicer, meal preparation tool.",
 "storage":"Foldable storage container, organiser, household space saving gadget.",
 "cleaning":"Cleaning brush, cleaning gadget, laundry tool, stain remover, pet hair remover.",
 "electronics":"Consumer electronic accessory, portable gadget, charging device.",
 "travel":"Travel accessory, luggage organiser, compact packing gadget.",
 "pets":"Pet care product, animal accessory, dog and cat grooming tool.",
 "other_product":"Physical retail merchandise and shopping item.",
 "sports_news":"Sports game results, match fixtures, athlete news and standings.",
 "celebrity_news":"Celebrity news, TV programme, film, music and entertainment.",
 "general_news":"Politics, breaking news, international affairs, weather and public events.",
 "finance_news":"Financial markets, stocks, cryptocurrency and economic news."
}
POS=set(["beauty","kitchen","storage","cleaning","electronics","travel","pets","other_product"])

def cosine(a,b):
    ab=sum(float(x)*float(y) for x,y in zip(a,b))
    an=math.sqrt(sum(float(x)*float(x) for x in a))
    bn=math.sqrt(sum(float(x)*float(x) for x in b))
    return ab/(an*bn) if an and bn else 0.

def classify_batch(texts, encoder, *, source_is_product=False):
    """Encoder must support .embed(list[str]) -> iterable of vectors."""
    if not texts:return []
    samples=[LABELS[k] for k in LABELS]+list(texts)
    vectors=list(encoder.embed(samples))
    keys=list(LABELS)
    centers=vectors[:len(keys)]
    outcomes=[]
    for title,vec in zip(texts,vectors[len(keys):]):
        sims={k:round(cosine(vec,c),4) for k,c in zip(keys,centers)}
        positives=sorted(((k,v) for k,v in sims.items() if k in POS),
                          key=lambda x:x[1],reverse=True)
        negatives=sorted(((k,v) for k,v in sims.items() if k not in POS),
                          key=lambda x:x[1],reverse=True)
        best=positives[0]; neg=negatives[0]
        margin=round(best[1]-neg[1],4)
        # For an actual marketplace listing, product-ness is supplied by the source.
        related=bool(source_is_product or (margin>=0.045 and best[1]>=0.38))
        certain=bool(source_is_product or (margin>=0.10 and best[1]>=0.50))
        outcomes.append({
          "original":title,"category":best[0] if related else "unconfirmed",
          "product_related":related,
          "needs_review":not certain,
          "product_similarity":best[1],"nonproduct_similarity":neg[1],
          "score_margin":margin,"model":MODEL,
          "warning":"Semantic similarity heuristic, NOT verified demand or sales"})
    return outcomes

def real_encoder():
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=MODEL)

def classify_evidence(snapshot, *, encoder=None, limit=120):
    data=json.loads(Path(snapshot).read_text(encoding="utf-8"))
    rows=data.get("observations") or []
    # Avoid accidentally labelling raw text as product-sales evidence.
    rows=[r for r in rows if r.get("term")][:limit]
    if not rows:return []
    model=encoder if encoder is not None else real_encoder()
    labels=classify_batch([r["term"] for r in rows],model)
    for target,obs in zip(labels,rows):
        target.update(market=obs.get("market"),source=obs.get("source"),
                      source_url=obs.get("source_url"))
    return labels

def main(argv=None):
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--limit",type=int,default=120)
    args=p.parse_args(argv)
    labels=classify_evidence(args.input,limit=args.limit)
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps({"model":MODEL,
       "disclaimer":"Zero-shot predictions require review; this is not a trained sales predictor.",
       "classified":len(labels),"results":labels},ensure_ascii=False,indent=2)+"\n",
       encoding="utf-8")
    print(f"Classified {len(labels)} recorded observations; review uncertain labels.")
    return 0

if __name__=="__main__":raise SystemExit(main())
