"""Backend i18n: localized strings shared by analysis, geospatial,
equipment and LLM services. Default language is French (fr)."""

VALID_LANGS = ("fr", "en", "de", "es")


def get_lang(lang) -> str:
    if lang in VALID_LANGS:
        return lang
    return "fr"


# --- Site scorer recommendation templates ---
REC_EXCELLENT = {
    "fr": "Excellent site (score : {score:.0f}/100).",
    "en": "Excellent site (score: {score:.0f}/100).",
    "de": "Hervorragender Standort (Wertung: {score:.0f}/100).",
    "es": "Sitio excelente (puntuación: {score:.0f}/100).",
}
REC_GOOD = {
    "fr": "Bon site (score : {score:.0f}/100).",
    "en": "Good site (score: {score:.0f}/100).",
    "de": "Guter Standort (Wertung: {score:.0f}/100).",
    "es": "Buen sitio (puntuación: {score:.0f}/100).",
}
REC_MODERATE = {
    "fr": "Potentiel modéré (score : {score:.0f}/100).",
    "en": "Moderate potential (score: {score:.0f}/100).",
    "de": "Mäßiges Potenzial (Wertung: {score:.0f}/100).",
    "es": "Potencial moderado (puntuación: {score:.0f}/100).",
}
REC_LOW = {
    "fr": "Potentiel faible (score : {score:.0f}/100).",
    "en": "Low potential (score: {score:.0f}/100).",
    "de": "Geringes Potenzial (Wertung: {score:.0f}/100).",
    "es": "Potencial bajo (puntuación: {score:.0f}/100).",
}
REC_DOMINANT = {
    "fr": "Ressource dominante : {resource}.",
    "en": "Dominant resource: {resource}.",
    "de": "Dominante Ressource: {resource}.",
    "es": "Recurso dominante: {resource}.",
}
DOMINANT_LABEL = {
    "solar": {"fr": "solaire", "en": "solar", "de": "Solar", "es": "solar"},
    "wind": {"fr": "éolien", "en": "wind", "de": "Wind", "es": "eólico"},
    "hybrid": {"fr": "hybride", "en": "hybrid", "de": "Hybrid", "es": "híbrido"},
}
REC_SOLAR = {
    "fr": "Ressource solaire : {cls} (GHI : {ghi:.1f} kWh/m²/jour, {sy:.0f} kWh/kWp/an).",
    "en": "Solar resource: {cls} (GHI: {ghi:.1f} kWh/m²/day, {sy:.0f} kWh/kWp/yr).",
    "de": "Solarressource: {cls} (GHI: {ghi:.1f} kWh/m²/Tag, {sy:.0f} kWh/kWp/Jahr).",
    "es": "Recurso solar: {cls} (GHI: {ghi:.1f} kWh/m²/día, {sy:.0f} kWh/kWp/año).",
}
REC_WIND = {
    "fr": "Ressource éolienne : {cls} (vent à la hauteur du moyeu : {ws:.1f} m/s).",
    "en": "Wind resource: {cls} (hub WS: {ws:.1f} m/s).",
    "de": "Windressource: {cls} (WS Nabenhöhe: {ws:.1f} m/s).",
    "es": "Recurso eólico: {cls} (WS a la altura del buje: {ws:.1f} m/s).",
}
REC_HYBRID = {
    "fr": "Complémentarité hybride : {comp:.0f}/100 (P90 : {p90:.0f} MWh/an).",
    "en": "Hybrid complementarity: {comp:.0f}/100 (P90: {p90:.0f} MWh/yr).",
    "de": "Hybrid-Komplementarität: {comp:.0f}/100 (P90: {p90:.0f} MWh/Jahr).",
    "es": "Complementariedad híbrida: {comp:.0f}/100 (P90: {p90:.0f} MWh/año).",
}


# --- LLM chat fallback (agent returned no text, e.g. provider rate limit) ---
LLM_EMPTY_RESPONSE = {
    "fr": "Désolé, je n'ai pas pu formuler de réponse pour le moment. Réessayez dans quelques secondes.",
    "en": "Sorry, I could not formulate a response right now. Please try again in a few seconds.",
    "de": "Entschuldigung, ich konnte gerade keine Antwort formulieren. Bitte versuchen Sie es in ein paar Sekunden erneut.",
    "es": "Lo siento, no he podido formular una respuesta en este momento. Inténtelo de nuevo dentro de unos segundos.",
}
LLM_RETRYING = {
    "fr": "Le service répond lentement, veuillez patienter…",
    "en": "The service is responding slowly, please wait…",
    "de": "Der Dienst antwortet langsam, bitte warten…",
    "es": "El servicio responde con lentitud, espere…",
}


def pick(d: dict, lang) -> str:
    return d.get(get_lang(lang), d["fr"])
