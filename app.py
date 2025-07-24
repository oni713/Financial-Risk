from flask import Flask, render_template, request, jsonify
from SPARQLWrapper import SPARQLWrapper, JSON
import spacy

app = Flask(__name__)

FUSEKI_URL = "http://localhost:3030/Financial_Risk_Management/sparql"

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except:
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

def query_ontology(search_term):
    sparql = SPARQLWrapper(FUSEKI_URL)
    term = search_term.strip().lower()
    type_map = {
        "bank": "ex:Bank",
        "loan": "ex:Loan",
        "investment": "ex:Investment",
        "insurance": "ex:InsurancePolicy",
        "retirement": "ex:RetirementAccount",
        "risk": "ex:RiskCategory"
    }
    if term in type_map:
        type_uri = type_map[term]
        query = f"""
            PREFIX ex: <http://www.semanticweb.org/financial_risk#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?entity ?name ?type ?property ?value
            WHERE {{
                ?entity rdf:type ?type .
                ?entity ex:hasName ?name .
                ?type rdfs:subClassOf* {type_uri} .
                OPTIONAL {{
                    ?entity ?property ?value .
                    FILTER(isLiteral(?value))
                }}
            }}
        """
    else:
        query = f"""
            PREFIX ex: <http://www.semanticweb.org/financial_risk#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT DISTINCT ?entity ?name ?type ?property ?value
            WHERE {{
                ?entity rdf:type ?type .
                ?entity ex:hasName ?name .
                OPTIONAL {{
                    ?entity ?property ?value .
                    FILTER(isLiteral(?value))
                }}
                FILTER(
                    REGEX(str(?name), "{search_term}", "i") ||
                    REGEX(str(?type), "{search_term}", "i")
                )
                FILTER(?type != owl:NamedIndividual)
            }}
        """
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    output = []
    for row in results["results"]["bindings"]:
        result = {
            'entity': row['entity']['value'],
            'name': row['name']['value'],
            'type': row['type']['value'],
            'properties': []
        }
        if 'property' in row and 'value' in row:
            result['properties'].append({
                'property': row['property']['value'],
                'value': row['value']['value']
            })
        output.append(result)
    return output

def get_recommendations(entity_uri):
    sparql = SPARQLWrapper(FUSEKI_URL)
    query = f"""
        PREFIX ex: <http://www.semanticweb.org/financial_risk#>
        SELECT DISTINCT ?related ?name ?relation
        WHERE {{
            <{entity_uri}> ?relation ?related .
            ?related ex:hasName ?name .
        }}
    """
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    recommendations = []
    for row in results["results"]["bindings"]:
        recommendations.append({
            'name': row['name']['value'],
            'relation': row['relation']['value']
        })
    return recommendations

def exploratory_search(search_term):
    sparql = SPARQLWrapper(FUSEKI_URL)
    query = f"""
        PREFIX ex: <http://www.semanticweb.org/financial_risk#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT DISTINCT ?entity ?name ?type
        WHERE {{
            ?mainEntity ex:hasName ?mainName .
            FILTER(REGEX(str(?mainName), "{search_term}", "i"))
            ?mainEntity ?p1 ?intermediate .
            ?intermediate ?p2 ?entity .
            ?entity ex:hasName ?name .
            ?entity rdf:type ?type .
            FILTER(?entity != ?mainEntity)
            FILTER(?type != owl:NamedIndividual)
        }}
        LIMIT 10
    """
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    output = []
    for row in results["results"]["bindings"]:
        output.append({
            'entity': row['entity']['value'],
            'name': row['name']['value'],
            'type': row['type']['value']
        })
    return output

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search')
def search():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'No search term provided'})
    results = query_ontology(query)
    # Get recommendations for each result
    for result in results:
        result['recommendations'] = get_recommendations(result['entity'])
    return jsonify(results)

@app.route('/explore')
def explore():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'No search term provided'})
    results = exploratory_search(query)
    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True) 