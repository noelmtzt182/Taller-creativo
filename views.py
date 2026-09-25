"""Todas las vistas de la app: inicio, selector de método, y los 7 flujos guiados."""
import streamlit as st

from data import (
    METHODS, GOALS, SCAMPER_STEPS, DT_LABELS, DD_LABELS, CPS_LABELS, TRIZ_LABELS,
    SIX_HATS, BRAIN_RULES, BRAIN_MODES, TRIZ_PRINCIPLES, method_by_id,
)
from state import compute_progress, reset_session
from export_utils import build_export_text, slugify
from advisor import ask_advisor
from ui import method_header, step_tabs, nav_row, list_capture, timer_widget, badge


# ============================================================
# Inicio
# ============================================================

def render_home():
    st.markdown("##### MÉTODOS DE CREATIVIDAD GUIADOS")
    st.title("Convierte un problema difícil en una lista de ideas")
    st.write("Describe tu reto, elige un método probado, y avanza paso a paso — solo o con tu equipo.")

    cols = st.columns(4)
    steps = ["Cuenta tu reto", "Elige o pide recomendación", "Sigue el proceso guiado", "Exporta tus resultados"]
    for i, (c, s) in enumerate(zip(cols, steps)):
        c.markdown(f"**0{i + 1}**  \n{s}")

    st.divider()
    st.session_state.problem = st.text_area(
        "¿Cuál es el reto o problema que quieres resolver?",
        value=st.session_state.problem,
        placeholder="Ej. Nuestras entregas a domicilio llegan tarde y los clientes se quejan.",
        height=90,
    )
    if st.button("Comenzar →", type="primary"):
        st.session_state.started = True
        st.rerun()


def render_session_bar():
    """Barra compacta con el reto actual y opción de editarlo, mostrada una vez iniciada la sesión."""
    cols = st.columns([8, 2])
    with cols[0]:
        with st.expander(f'📝 "{st.session_state.problem or "(sin problema definido)"}"', expanded=False):
            st.session_state.problem = st.text_area("Editar el reto", value=st.session_state.problem, key="edit_problem_box")
    with cols[1]:
        if st.button("Inicio", use_container_width=True):
            st.session_state.started = False
            st.session_state.method = None
            st.rerun()
    if st.session_state.method:
        pct = compute_progress(st.session_state.method)
        st.caption(f"Progreso: {pct}%")


# ============================================================
# Selector de método / recomendador
# ============================================================

def render_method_select():
    st.markdown("###### PASO 2")
    st.subheader("Elige qué usar para tu reto")
    st.caption(f'"{st.session_state.problem or "(sin problema definido)"}"')

    with st.container(border=True):
        st.markdown("#### 🎯 ¿Qué quieres lograr?")
        st.caption("Elige la opción más parecida a tu objetivo y vas directo a la herramienta indicada.")
        for g in GOALS:
            gm = method_by_id(g["id"])
            c1, c2 = st.columns([1, 11])
            with c1:
                st.markdown(
                    f'<div style="width:14px;height:14px;border-radius:5px;background:{gm["color"]};'
                    f'margin-top:10px;"></div>',
                    unsafe_allow_html=True,
                )
            with c2:
                if st.button(g["label"], key=f"goal_{g['id']}", use_container_width=True):
                    st.session_state.method = g["id"]
                    st.rerun()

        st.markdown("&nbsp;")
        st.markdown("#### 🤖 ¿No estás seguro? Pregúntale al asistente")
        render_advisor()

    st.divider()
    st.markdown("## Métodos")
    st.caption("Procesos completos, varias etapas")
    _render_method_grid([m for m in METHODS if m["category"] == "metodo"])

    st.markdown("## Técnicas y herramientas")
    st.caption("Generadores puntuales de ideas")
    _render_method_grid([m for m in METHODS if m["category"] == "tecnica"])


def _render_method_grid(items):
    cols = st.columns(2)
    for i, m in enumerate(items):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(
                    f'<div style="height:6px;border-radius:99px;background:{m["color"]};margin:-1rem -1rem 0.8rem;"></div>',
                    unsafe_allow_html=True,
                )
                badge(m["code"], m["color"], m.get("text_on", "white"))
                st.markdown(f"**{m['name']}**  \n{m['tagline']}")
                st.caption(f"Ideal para: {m['best_for']} · {m['time']}")
                if st.button("Elegir", key=f"choose_{m['id']}", use_container_width=True):
                    st.session_state.method = m["id"]
                    st.rerun()


def render_advisor():
    adv = st.session_state.advisor
    if not (st.session_state.get("api_key") or _has_secret_or_env_key()):
        st.caption("Configura tu API key de Anthropic en la barra lateral para activar el asistente.")

    text = st.text_area(
        "Cuéntame tu situación",
        value=adv.get("input", ""),
        placeholder="Ej. Tengo que rediseñar el proceso de onboarding, ya existe pero está desordenado...",
        key="advisor_input_box",
        label_visibility="collapsed",
        height=80,
    )
    if st.button("Preguntar", key="ask_advisor_btn"):
        adv["input"] = text
        if not text.strip():
            st.warning("Escribe primero tu situación.")
        else:
            with st.spinner("Pensando en la mejor opción para ti…"):
                result = ask_advisor(text.strip())
            st.session_state.advisor = {**adv, **result}
            st.rerun()

    if adv.get("status") == "unavailable":
        st.warning("El asistente con IA no está disponible: agrega tu API key de Anthropic en la barra lateral.")
    elif adv.get("status") == "error":
        st.error(adv.get("error") or "Algo salió mal. Intenta de nuevo.")
    elif adv.get("status") == "done":
        m = method_by_id(adv["id"])
        if m:
            st.success(f"**Recomendación: {m['name']}**\n\n{adv.get('reason', '')}")
            if st.button(f"Usar {'esta técnica' if m['category'] == 'tecnica' else 'este método'}", key="use_advisor_rec", type="primary"):
                st.session_state.method = m["id"]
                st.session_state.advisor = {"status": "idle", "input": "", "id": None, "reason": None, "error": None}
                st.rerun()


def _has_secret_or_env_key():
    try:
        if "ANTHROPIC_API_KEY" in st.secrets:
            return True
    except Exception:
        pass
    import os
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


# ============================================================
# Export helper (usado en cada resumen)
# ============================================================

def render_export_button(method):
    text = build_export_text(st.session_state.problem, method, st.session_state.data)
    filename = f"taller-ideas-{method}-{slugify(st.session_state.problem)}.md"
    st.download_button("⬇ Exportar sesión (.md)", data=text, file_name=filename, mime="text/markdown",
                        key=f"export_{method}")


def render_change_method_button():
    if st.button("← Cambiar método", key="change_method_top"):
        st.session_state.method = None
        st.rerun()


# ============================================================
# SCAMPER
# ============================================================

def render_scamper():
    m = method_by_id("scamper")
    d = st.session_state.data["scamper"]
    method_header(m)
    render_change_method_button()
    idx = d["step"]
    labels = [s["key"] for s in SCAMPER_STEPS]
    step_tabs(labels, idx, "scamper", ("scamper", "step"))

    if idx < len(SCAMPER_STEPS):
        st_ = SCAMPER_STEPS[idx]
        with st.container(border=True):
            st.markdown(f"#### {st_['key']} — {st_['title']}")
            for p in st_["prompts"]:
                st.markdown(f"— {p}")
            list_capture(d[st_["key"]], f"scamper_{st_['key']}", f'Escribe una idea para "{st_["title"]}"...')
        nav_row(idx, len(SCAMPER_STEPS), "scamper", ("scamper", "step"))
    else:
        _render_scamper_summary(d, m)


def _render_scamper_summary(d, m):
    total = sum(len(d[s["key"]]) for s in SCAMPER_STEPS)
    st.markdown(f"### Resumen SCAMPER — {total} ideas en total")
    for st_ in SCAMPER_STEPS:
        with st.expander(f"{st_['key']} — {st_['title']} ({len(d[st_['key']])})", expanded=bool(d[st_["key"]])):
            if d[st_["key"]]:
                for it in d[st_["key"]]:
                    st.markdown(f"- {it}")
            else:
                st.caption("Sin ideas.")
    render_export_button("scamper")


# ============================================================
# Design Thinking
# ============================================================

def render_design_thinking():
    m = method_by_id("design-thinking")
    d = st.session_state.data["design_thinking"]
    method_header(m)
    render_change_method_button()
    idx = d["step"]
    step_tabs(DT_LABELS, idx, "dt", ("design_thinking", "step"))

    if idx >= len(DT_LABELS):
        _render_dt_summary(d)
        return

    with st.container(border=True):
        if idx == 0:
            st.markdown("#### Empatizar")
            st.markdown("— ¿Quién vive este problema de cerca?  \n— ¿Qué observas, escuchas o sabes de esas personas?  \n— ¿Qué necesidades no dichas podrían tener?")
            list_capture(d["empathize"], "dt_empathize", "Una observación, cita o necesidad detectada...")
        elif idx == 1:
            st.markdown("#### Definir")
            st.caption("Construye tu declaración de punto de vista (POV):")
            d["define"]["user"] = st.text_input("¿Quién es la persona?", value=d["define"]["user"], placeholder="Ej. un repartidor nuevo")
            d["define"]["need"] = st.text_input("¿Qué necesita?", value=d["define"]["need"], placeholder="Ej. conocer la ruta más rápida")
            d["define"]["insight"] = st.text_input("¿Por qué? (insight)", value=d["define"]["insight"], placeholder="Ej. el tráfico cambia cada hora")
            st.info(f"{d['define']['user'] or '[Persona]'} necesita {d['define']['need'] or '[necesidad]'} porque {d['define']['insight'] or '[insight]'}.")
        elif idx == 2:
            st.markdown("#### Idear")
            st.caption("Genera tantas ideas como puedas, sin juzgarlas todavía. Meta sugerida: 15 ideas.")
            st.progress(min(1.0, len(d["ideate"]) / 15))
            list_capture(d["ideate"], "dt_ideate", "Una idea nueva, por alocada que parezca...")
        elif idx == 3:
            st.markdown("#### Prototipar")
            st.caption("Describe un prototipo simple: un boceto, un storyboard, una maqueta de papel, un guion de rol-play.")
            d["prototype"]["description"] = st.text_area("Descripción del prototipo", value=d["prototype"]["description"],
                                                           placeholder="Describe cómo se vería o funcionaría...")
            st.caption("Preguntas abiertas que quieres resolver al probarlo")
            list_capture(d["prototype"]["questions"], "dt_proto_q", "Una pregunta abierta sobre tu prototipo...")
        elif idx == 4:
            st.markdown("#### Testear")
            st.caption("Comparte tu prototipo con alguien real y registra lo que aprendes.")
            st.markdown("**Qué funcionó**")
            list_capture(d["test"]["worked"], "dt_worked", "Algo que funcionó bien...")
            st.markdown("**Qué no funcionó**")
            list_capture(d["test"]["didnt_work"], "dt_notworked", "Algo que no funcionó...")
            st.markdown("**Ajustes o nuevas ideas**")
            list_capture(d["test"]["adjustments"], "dt_adjust", "Un ajuste a partir del feedback...")

    nav_row(idx, len(DT_LABELS), "dt", ("design_thinking", "step"))


def _render_dt_summary(d):
    st.markdown("### Resumen Design Thinking")
    with st.expander("Empatizar", expanded=True):
        for it in d["empathize"] or []:
            st.markdown(f"- {it}")
        if not d["empathize"]:
            st.caption("Sin registros.")
    with st.expander("Definir", expanded=True):
        de = d["define"]
        if de["user"] or de["need"] or de["insight"]:
            st.info(f"{de['user'] or '[Persona]'} necesita {de['need'] or '[necesidad]'} porque {de['insight'] or '[insight]'}.")
        else:
            st.caption("Sin definir.")
    with st.expander(f"Idear ({len(d['ideate'])})"):
        for it in d["ideate"]:
            st.markdown(f"- {it}")
    with st.expander("Prototipar"):
        st.write(d["prototype"]["description"] or "Sin descripción.")
    with st.expander("Testear"):
        st.caption(f"{len(d['test']['worked'])} funcionó · {len(d['test']['didnt_work'])} no funcionó · {len(d['test']['adjustments'])} ajustes")
    render_export_button("design-thinking")


# ============================================================
# Double Diamond
# ============================================================

def render_double_diamond():
    m = method_by_id("double-diamond")
    d = st.session_state.data["double_diamond"]
    method_header(m)
    render_change_method_button()
    idx = d["step"]
    step_tabs(DD_LABELS, idx, "dd", ("double_diamond", "step"))

    if idx >= len(DD_LABELS):
        _render_dd_summary(d)
        return

    with st.container(border=True):
        if idx == 0:
            st.markdown("#### Descubrir")
            st.caption("Explora ampliamente antes de decidir nada. Este es el primer rombo: se abre.")
            list_capture(d["discover"], "dd_discover", "Un hallazgo, observación o pregunta...")
        elif idx == 1:
            st.markdown("#### Definir")
            st.caption("Cierra el primer rombo: sintetiza todo lo descubierto en una definición clara.")
            d["problem_statement"] = st.text_area("Declaración del problema", value=d["problem_statement"],
                                                    placeholder="En una o dos frases, ¿cuál es el problema real?")
            st.caption("Criterios de éxito")
            list_capture(d["success_criteria"], "dd_criteria", "¿Cómo sabrás que lo resolviste?")
        elif idx == 2:
            st.markdown("#### Desarrollar")
            st.caption("Segundo rombo, se abre de nuevo: genera y explora posibles soluciones sin elegir todavía.")
            list_capture(d["develop"], "dd_develop", "Una posible solución a explorar...")
        elif idx == 3:
            st.markdown("#### Entregar")
            st.caption("Cierra el segundo rombo: elige, refina y planea cómo entregarla.")
            d["chosen_solution"] = st.text_area("Solución elegida", value=d["chosen_solution"],
                                                 placeholder="Describe la solución final...")
            st.caption("Próximos pasos para entregarla")
            list_capture(d["next_steps"], "dd_next", "Un paso concreto para entregar la solución...")

    nav_row(idx, len(DD_LABELS), "dd", ("double_diamond", "step"))


def _render_dd_summary(d):
    st.markdown("### Resumen Double Diamond")
    with st.expander("Descubrir", expanded=True):
        for it in d["discover"]:
            st.markdown(f"- {it}")
        if not d["discover"]:
            st.caption("Sin registros.")
    with st.expander("Definir", expanded=True):
        st.write(d["problem_statement"] or "Sin definir.")
        for it in d["success_criteria"]:
            st.markdown(f"- {it}")
    with st.expander(f"Desarrollar ({len(d['develop'])})"):
        for it in d["develop"]:
            st.markdown(f"- {it}")
    with st.expander("Entregar"):
        st.write(d["chosen_solution"] or "Sin definir.")
        for it in d["next_steps"]:
            st.markdown(f"- {it}")
    render_export_button("double-diamond")


# ============================================================
# CPS
# ============================================================

def render_cps():
    m = method_by_id("cps")
    d = st.session_state.data["cps"]
    method_header(m)
    render_change_method_button()
    idx = d["step"]
    step_tabs(CPS_LABELS, idx, "cps", ("cps", "step"))

    if idx >= len(CPS_LABELS):
        _render_cps_summary(d)
        return

    with st.container(border=True):
        if idx == 0:
            st.markdown("#### Clarificar")
            st.caption("Nombra el reto como una pregunta abierta e invitante.")
            d["challenge"] = st.text_input("¿Cómo podríamos...?", value=d["challenge"],
                                            placeholder="¿Cómo podríamos reducir el tiempo de espera sin subir costos?")
            st.caption("Hechos y datos relevantes")
            list_capture(d["facts"], "cps_facts", "¿Qué sabemos con certeza? ¿Qué suposiciones hacemos?")
        elif idx == 1:
            st.markdown("#### Idear")
            st.caption("Genera tantas alternativas como puedas para tu reto, sin filtrarlas todavía.")
            list_capture(d["ideate"], "cps_ideate", "Una alternativa para el reto...")
        elif idx == 2:
            st.markdown("#### Desarrollar")
            st.caption("Elige la idea o ideas más prometedoras y fortalécelas.")
            d["best_idea"] = st.text_area("Idea(s) más prometedora(s)", value=d["best_idea"],
                                           placeholder="¿Cuál idea tiene más potencial?")
            st.caption("Cómo fortalecerla")
            list_capture(d["strengthen"], "cps_strengthen", "¿Qué la haría más viable? ¿Qué obstáculo resolver primero?")
        elif idx == 3:
            st.markdown("#### Implementar")
            st.caption("Convierte la idea fortalecida en un plan de acción concreto.")
            st.caption("Plan de acción")
            list_capture(d["action_plan"], "cps_plan", "Un paso concreto: quién lo hace y para cuándo...")
            d["support"] = st.text_area("Apoyo y recursos necesarios", value=d["support"],
                                         placeholder="¿Qué o quién necesitas para lograrlo?")

    nav_row(idx, len(CPS_LABELS), "cps", ("cps", "step"))


def _render_cps_summary(d):
    st.markdown("### Resumen CPS")
    with st.expander("Clarificar", expanded=True):
        st.write(d["challenge"] or "Sin definir.")
        for it in d["facts"]:
            st.markdown(f"- {it}")
    with st.expander(f"Idear ({len(d['ideate'])})"):
        for it in d["ideate"]:
            st.markdown(f"- {it}")
    with st.expander("Desarrollar"):
        st.write(d["best_idea"] or "Sin definir.")
        for it in d["strengthen"]:
            st.markdown(f"- {it}")
    with st.expander("Implementar"):
        for it in d["action_plan"]:
            st.markdown(f"- {it}")
        st.write(d["support"] or "Sin apoyo/recursos definidos.")
    render_export_button("cps")


# ============================================================
# Seis Sombreros
# ============================================================

def render_six_hats():
    m = method_by_id("six-hats")
    d = st.session_state.data["six_hats"]
    method_header(m)
    render_change_method_button()
    idx = d["step"]
    labels = [h["name"] for h in SIX_HATS]
    step_tabs(labels, idx, "hats", ("six_hats", "step"))

    if idx < len(SIX_HATS):
        h = SIX_HATS[idx]
        with st.container(border=True):
            st.markdown(
                f'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;'
                f'background:{h["color"]};border:1px solid #8886;margin-right:8px;"></span>'
                f'**Sombrero {h["name"]} — {h["label"]}**',
                unsafe_allow_html=True,
            )
            for p in h["prompts"]:
                st.markdown(f"— {p}")
            timer_widget(f"six-hats:{h['key']}", f"hats_{h['key']}")
            list_capture(d["hats"][h["key"]], f"hats_{h['key']}_list", f'Un pensamiento desde el sombrero {h["name"]}...')
        nav_row(idx, len(SIX_HATS), "hats", ("six_hats", "step"))
    else:
        _render_hats_summary(d)


def _render_hats_summary(d):
    st.markdown("### Resumen — Seis Sombreros")
    for h in SIX_HATS:
        items = d["hats"][h["key"]]
        with st.expander(f"{h['name']} — {h['label']} ({len(items)})", expanded=bool(items)):
            for it in items:
                st.markdown(f"- {it}")
            if not items:
                st.caption("Sin registros.")
    render_export_button("six-hats")


# ============================================================
# Brainstorming y variantes
# ============================================================

def render_brainstorming():
    m = method_by_id("brainstorming")
    d = st.session_state.data["brainstorming"]
    method_header(m)
    render_change_method_button()

    if not d["sub_mode"]:
        st.caption("Elige cómo quieres generar ideas:")
        cols = st.columns(3)
        for c, bm in zip(cols, BRAIN_MODES):
            with c:
                with st.container(border=True):
                    st.markdown(f"**{bm['name']}**")
                    st.caption(bm["desc"])
                    if st.button("Elegir", key=f"brain_mode_{bm['id']}", use_container_width=True):
                        d["sub_mode"] = bm["id"]
                        st.rerun()
        return

    if st.button("← Elegir otra variante", key="brain_change_mode"):
        d["sub_mode"] = None
        st.rerun()

    if d["sub_mode"] == "classic":
        _render_brain_classic(d)
    elif d["sub_mode"] == "brainwriting":
        _render_brainwriting(d)
    elif d["sub_mode"] == "mindmap":
        _render_mindmap(d)


def _render_brain_classic(d):
    with st.container(border=True):
        st.markdown("#### Brainstorming clásico")
        for i, r in enumerate(BRAIN_RULES):
            st.markdown(f"**{i + 1}.** {r}")
        timer_widget("classic", "brain_classic")
        list_capture(d["classic"]["ideas"], "brain_classic_list", "Escribe una idea, sin filtrarla...", starable=True)
    render_export_button("brainstorming")


def _render_brainwriting(d):
    bw = d["brainwriting"]
    ri = bw["round"]
    with st.container(border=True):
        st.markdown("#### Brainwriting 6-3-5")
        st.caption("Tradicionalmente: 6 personas, 3 ideas cada una, 5 rondas de 5 minutos, pasando la hoja. "
                   "Aquí puedes simular las rondas tú solo o en equipo usando una sola pantalla.")
        st.markdown(f"**Ronda {ri + 1} de 5**")
        if ri > 0 and bw["rounds"][ri - 1]:
            with st.expander("Ideas de la ronda anterior (para inspirarte o evolucionar)", expanded=True):
                for it in bw["rounds"][ri - 1]:
                    st.markdown(f"- {it}")
        list_capture(bw["rounds"][ri], f"bw_round_{ri}", "Una idea nueva o evolucionada para esta ronda...")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("← Ronda anterior", disabled=ri <= 0, key="bw_prev"):
                bw["round"] = max(0, ri - 1)
                st.rerun()
        with c2:
            if ri < 4:
                if st.button("Siguiente ronda →", type="primary", key="bw_next", use_container_width=True):
                    bw["round"] = min(4, ri + 1)
                    st.rerun()
    render_export_button("brainstorming")


def _render_mindmap(d):
    mm = d["mindmap"]
    with st.container(border=True):
        st.markdown("#### Mapa mental")
        st.info(st.session_state.problem or "Tu problema")
        with st.form("mm_add_branch", clear_on_submit=True):
            name = st.text_input("Nombre de una rama principal (un tema o dirección)...", label_visibility="collapsed")
            if st.form_submit_button("Agregar rama") and name.strip():
                mm["branches"].append({"name": name.strip(), "ideas": []})
                st.rerun()

        if not mm["branches"]:
            st.caption("Agrega tu primera rama para empezar a ramificar el problema.")
        for bi, br in enumerate(mm["branches"]):
            with st.expander(f"🌿 {br['name']}", expanded=True):
                new_name = st.text_input("Nombre de la rama", value=br["name"], key=f"mm_branch_name_{bi}")
                br["name"] = new_name
                list_capture(br["ideas"], f"mm_branch_{bi}", "Una idea bajo esta rama...")
                if st.button("Eliminar rama", key=f"mm_del_branch_{bi}"):
                    mm["branches"].pop(bi)
                    st.rerun()
    render_export_button("brainstorming")


# ============================================================
# TRIZ
# ============================================================

def render_triz():
    m = method_by_id("triz")
    d = st.session_state.data["triz"]
    method_header(m)
    render_change_method_button()
    idx = d["step"]
    step_tabs(TRIZ_LABELS, idx, "triz", ("triz", "step"))

    if idx == 0:
        with st.container(border=True):
            st.markdown("#### ¿Qué es TRIZ?")
            st.write(
                "TRIZ es una metodología desarrollada a partir del análisis de miles de patentes. "
                "Su idea central: la mayoría de los problemas de diseño esconden una **contradicción** "
                "— mejorar algo empeora otra cosa — y esa contradicción ya fue resuelta antes, en otro "
                "contexto, con uno de 40 principios de inventiva reutilizables."
            )
            st.write(
                "Esta versión es un checklist exploratorio y simplificado, no la matriz de contradicciones "
                "completa: te ayuda a nombrar tu contradicción y navegar los 40 principios para encontrar "
                "inspiración aplicable."
            )
        nav_row(idx, len(TRIZ_LABELS), "triz", ("triz", "step"))
    elif idx == 1:
        with st.container(border=True):
            st.markdown("#### Nombra tu contradicción")
            d["improve"] = st.text_input("¿Qué característica quieres mejorar?", value=d["improve"],
                                          placeholder="Ej. la velocidad de entrega")
            d["worsen"] = st.text_input("¿Qué empeora cuando intentas mejorarla?", value=d["worsen"],
                                         placeholder="Ej. el costo de transporte")
            st.info(f"Mejorar {d['improve'] or '[característica]'} empeora {d['worsen'] or '[otra característica]'}.")
        nav_row(idx, len(TRIZ_LABELS), "triz", ("triz", "step"))
    elif idx == 2:
        _render_triz_principles(d)
        nav_row(idx, len(TRIZ_LABELS), "triz", ("triz", "step"))
    else:
        _render_triz_summary(d)


def _render_triz_principles(d):
    with st.container(border=True):
        st.markdown("#### Los 40 principios de inventiva")
        st.caption("Busca y selecciona los que podrían aplicar a tu contradicción; anota cómo lo harías.")
        query = st.text_input("Buscar por palabra clave", placeholder="ej. dividir, flexible, temperatura...",
                               label_visibility="collapsed", key="triz_search")
        q = query.strip().lower()
        cols = st.columns(2)
        i = 0
        for n, name, desc in TRIZ_PRINCIPLES:
            haystack = f"{name} {desc}".lower()
            if q and q not in haystack:
                continue
            sel_dict = d["selected"].setdefault(str(n), {"selected": False, "note": ""})
            with cols[i % 2]:
                with st.container(border=True):
                    st.markdown(f"**#{n} — {name}**")
                    st.caption(desc)
                    checked = st.checkbox("Seleccionar", value=sel_dict["selected"], key=f"triz_sel_{n}")
                    sel_dict["selected"] = checked
                    if checked:
                        sel_dict["note"] = st.text_area("¿Cómo aplicarías esto a tu problema?",
                                                         value=sel_dict["note"], key=f"triz_note_{n}", height=68)
            i += 1
        if i == 0:
            st.caption("Ningún principio coincide con tu búsqueda.")


def _render_triz_summary(d):
    st.markdown("### Resumen TRIZ")
    st.info(f"Mejorar {d['improve'] or '[característica]'} empeora {d['worsen'] or '[otra característica]'}.")
    any_sel = False
    for n, name, desc in TRIZ_PRINCIPLES:
        sel = d["selected"].get(str(n))
        if sel and sel.get("selected"):
            any_sel = True
            with st.expander(f"#{n} — {name}", expanded=True):
                st.write(sel.get("note") or "(sin nota de aplicación)")
    if not any_sel:
        st.caption("Aún no seleccionas principios.")
    render_export_button("triz")


# ============================================================
# Router
# ============================================================

METHOD_RENDERERS = {
    "scamper": render_scamper,
    "design-thinking": render_design_thinking,
    "double-diamond": render_double_diamond,
    "cps": render_cps,
    "six-hats": render_six_hats,
    "brainstorming": render_brainstorming,
    "triz": render_triz,
}
