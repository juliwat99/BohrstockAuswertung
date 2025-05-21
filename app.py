import streamlit as st
import pandas as pd
import io
import re

from bodenauswertung import (
    humusvorrat,
    berechne_kalkbedarf,
    gesamt_nfk,
    bodentyp_to_bg,
    build_horizonte_list,
    humuskategorie,
    kapillaraufstiegsrate,
)

# — Seite konfigurieren —
st.set_page_config(
    page_title="Bohrstock-Auswertung",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# — Sidebar für Inputs —
with st.sidebar:
    st.header("Einstellungen")
    uploaded  = st.file_uploader("Excel/CSV hochladen", type=["xlsx","csv"])
    nutzung   = st.selectbox("Nutzungsart", ["Acker", "Gruenland"])
    phyto     = st.number_input("Physio. Gründigkeit (cm)", min_value=10, max_value=500, value=100)
    bodenform = st.text_input("Bodenform")
    st.markdown("---")
    run = st.button("Auswerten")

st.title("🌿 Bohrstock-Auswertung")

if not uploaded:
    st.info("Bitte lade eine Datei in der Sidebar hoch.")
    st.stop()

# — Daten einlesen —
if uploaded.name.lower().endswith(("xls","xlsx")):
    df = pd.read_excel(uploaded)
else:
    df = pd.read_csv(uploaded)

if run:
    # 1) Horizonte verarbeiten
    horizonte = build_horizonte_list(df)

    # 1a) Cleanup: Bodenart ohne "(...)", Skelett <1% → 0.5
    for h in horizonte:
        h["Bodenart"] = re.sub(r"\s*\(.*\)$", "", str(h["Bodenart"])).strip()
        if h.get("skelett", 0) < 1:
            h["skelett"] = 0.5

    # 2) Tabs
    tab1, tab2, tab3 = st.tabs(["Rohdaten", "Horizonte", "Ergebnisse"])
    with tab1:
        st.subheader("📋 Eingelesene Rohdaten")
        st.dataframe(df, use_container_width=True)
    with tab2:
        st.subheader("🔍 Verarbeitete Horizonte")
        st.dataframe(pd.DataFrame(horizonte), use_container_width=True)

    # 3) Oberboden
    ober     = min(horizonte, key=lambda h: h["z_top"])
    bodentyp = ober["Bodenart"]
    bg       = bodentyp_to_bg.get(bodentyp)
    ph_wert  = ober["pH"]
    humus_w  = ober["humus"]

    # 4) Fehler, falls Bodentyp unbekannt
    if bg is None:
        erlaubte = ", ".join(sorted(bodentyp_to_bg.keys()))
        st.error(
            f"🚫 Unbekannte Bodenart „{bodentyp}“!\n\n"
            f"Erlaubte Codes sind: {erlaubte}"
        )
        st.stop()

    # 5) Kalkbedarf
    df_acker = pd.read_csv("kalkbedarf_acker.csv")
    df_gruen = pd.read_csv("kalkbedarf_gruen.csv")
    kalk, msg = berechne_kalkbedarf(
        bg,
        ph_wert,
        humus_w,
        nutzungsart=nutzung.lower(),
        df_acker=df_acker,
        df_gruen=df_gruen
    )
    kalk_value = f"{kalk:.1f}" if kalk is not None else "Kein Bedarf"

    # 6) Kapillar-Aufstiegsrate
    kap_rate = kapillaraufstiegsrate(horizonte, phyto) or ""

    # 7) Humusvorrat und nFK
    _, total_h = humusvorrat(horizonte, max_tiefe=100)
    nfk        = gesamt_nfk(horizonte, phyto)
    nfk_value  = f"{nfk:.0f}" if nfk is not None else ""

    # 8) Ergebnisse
    with tab3:
        st.subheader("✅ Zusammenfassung")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Humusvorrat 1 m (Mg/ha)", f"{total_h*10:.1f}")
        c2.metric("pH Oberboden",           f"{ph_wert:.2f}")
        c3.metric("nFK (mm)",               nfk_value)
        c4.metric("Kalkbedarf (dt CaO/ha)", kalk_value)
        c5.metric("Kap. Aufstiegsrate (mm/d)", f"{kap_rate}")

        st.markdown("---")
        result_df = pd.DataFrame([{
            "Bodentyp":                       bodentyp,
            "Bodenform":                      bodenform,
            "Phys. Gründigkeit (cm)":         phyto,
            "Humusvorrat bis 1 m (Mg/ha)":    total_h * 10,
            "pH Oberboden":                   ph_wert,
            "Kalkbedarf (dt CaO/ha)":         kalk_value,
            "nFK (mm)":                       nfk_value,
            "Kap. Aufstiegsrate (mm/d)":      kap_rate
        }])
        st.dataframe(result_df, use_container_width=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            result_df.to_excel(writer, index=False)
        buffer.seek(0)
        st.download_button(
            "Ergebnis als Excel herunterladen",
            data=buffer,
            file_name="ergebnis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
