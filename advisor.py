"""Asistente de IA que recomienda un método/técnica usando la API de Anthropic.

Requiere que el usuario proporcione su propia API key de Anthropic (barra lateral,
o variable de entorno / st.secrets con el nombre ANTHROPIC_API_KEY).
"""
import json
import re

import streamlit as st

from data import METHODS


def _get_api_key():
    if st.session_state.get("api_key"):
        return st.session_state["api_key"]
    try:
        if "ANTHROPIC_API_KEY" in st.secrets:
            return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
    import os
    return os.environ.get("ANTHROPIC_API_KEY")


def _friendly_error(exc):
    msg = str(exc).lower()
    if "401" in msg or "auth" in msg:
        return "Tu API key no parece válida o no tiene acceso. Revísala en la barra lateral."
    if "429" in msg or "rate" in msg:
        return "Se alcanzó el límite de solicitudes a la API. Intenta de nuevo en un momento."
    if "model" in msg and ("not_found" in msg or "invalid" in msg):
        return ("El modelo configurado no existe o ya no está disponible. Revisa el nombre del "
                "modelo en la barra lateral (ver docs.claude.com/en/docs/about-claude/models).")
    return f"Algo salió mal al consultar al asistente: {exc}"


def ask_advisor(user_text):
    """Devuelve un dict: {status: 'unavailable'|'error'|'done', id?, reason?, error?}."""
    api_key = _get_api_key()
    if not api_key:
        return {"status": "unavailable"}

    try:
        import anthropic
    except ImportError:
        return {"status": "error", "error": "Falta instalar el paquete 'anthropic' (pip install anthropic)."}

    context = "\n".join(
        f'- id:"{m["id"]}" ({m["name"]}): {m["tagline"]} Ideal para: {m["best_for"]}'
        for m in METHODS
    )
    prompt = (
        "Eres un asesor experto en metodologías de creatividad e innovación dentro de la app "
        '"Taller de Ideas". Estos son los ÚNICOS métodos y técnicas disponibles '
        '(usa siempre el "id" exacto entre comillas):\n' + context +
        '\n\nUn usuario describe su situación:\n"' + user_text.replace('"', "'") + '"\n\n'
        "Elige el id de UN solo método o técnica de la lista que mejor se ajuste. "
        'Responde SOLO con JSON válido de la forma {"id":"...","reason":"..."}, donde "reason" '
        "son 2-3 frases en español, tono cercano, explicando por qué ese es el mejor ajuste."
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        model_id = st.session_state.get("model_id") or "claude-3-5-haiku-latest"
        resp = client.messages.create(
            model=model_id,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in resp.content if hasattr(block, "text"))
        match = re.search(r"\{.*\}", text, re.DOTALL)
        payload = json.loads(match.group(0)) if match else json.loads(text)
        valid_ids = {m["id"] for m in METHODS}
        if payload.get("id") in valid_ids:
            return {"status": "done", "id": payload["id"], "reason": payload.get("reason", "")}
        return {"status": "error", "error": "No obtuvimos una recomendación válida. Intenta con más detalle."}
    except Exception as exc:  # noqa: BLE001 - queremos capturar cualquier falla de red/API y mostrarla amable
        return {"status": "error", "error": _friendly_error(exc)}
