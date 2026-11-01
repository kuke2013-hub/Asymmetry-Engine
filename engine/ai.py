"""Optional LOCAL Ollama-only classifier. The engine never sends paid API calls."""
import json
from urllib.request import Request, urlopen
CATEGORIES=['beauty','kitchen','cleaning','storage','personal_care',
            'gadgets','pet','travel','home','other','not_product']
SCHEMA={'type':'object','additionalProperties':False,
        'properties':{
          'translated_term':{'type':'string'},
          'product_related':{'type':'boolean'},
          'category':{'type':'string','enum':CATEGORIES},
          'demo_potential':{'type':'integer','minimum':0,'maximum':5},
          'impulse_fit':{'type':'integer','minimum':0,'maximum':5},
          'confidence':{'type':'number','minimum':0,'maximum':1},
          'rationale':{'type':'string'},
          'risk_flags':{'type':'array','items':{'type':'string'}}
        },
        'required':['translated_term','product_related','category','demo_potential',
                    'impulse_fit','confidence','rationale','risk_flags']}
def classify(term,market,source,model,host='http://127.0.0.1:11434'):
    prompt=(f'Market={market}; Source={source}; Term={term}. '
       'Translate to English and classify. Many trending terms are news, not products. '
       'Do not invent sales, demand, availability, trend lead/lag or commission. '
       'Return exactly the JSON schema; suitability ratings are speculative, not factual.')
    body={'model':model,'messages':[{'role':'user','content':prompt}],
          'stream':False,'format':SCHEMA,'options':{'temperature':0}}
    req=Request(host.rstrip('/')+'/api/chat',
          data=json.dumps(body).encode(),method='POST',
          headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=120) as resp:
        obj=json.load(resp)
    result=json.loads(obj['message']['content'])
    if set(result)!=set(SCHEMA['required']):raise ValueError('Model returned incomplete schema')
    if result['category'] not in CATEGORIES:raise ValueError('Unexpected category')
    if not isinstance(result['product_related'],bool):raise ValueError('Invalid product flag')
    for key in ('demo_potential','impulse_fit'):
        if type(result[key]) is not int or not 0<=result[key]<=5:
            raise ValueError('Invalid category score')
    if not isinstance(result['confidence'],(int,float)) or not 0<=result['confidence']<=1:
        raise ValueError('Invalid confidence')
    if not isinstance(result['risk_flags'],list):raise ValueError('Invalid risk flags')
    return result
