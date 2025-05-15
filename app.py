import streamlit as st
import pandas as pd
import io
import altair as alt

from bodenauswertung import (
    humusvorrat,
    berechne_kalkbedarf,
    gesamt_nfk,
    bodentyp_to_bg,
    build_horizonte_list,
    humuskategorie
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
    bodenform = st.text_input("Bodenform", "Braunerde")
    st.markdown("---")
    run       = st.button("Auswerten")

st.title("🌿 Bohrstock-Auswertung")

# — Wenn noch nichts hochgeladen — 
if not uploaded:
    st.info("Bitte lade eine Datei in der Sidebar hoch.")
    st.stop()

# — Daten einlesen — 
if uploaded.name.lower().endswith(("xls","xlsx")):
    df = pd.read_excel(uploaded)
else:
    df = pd.read_csv(uploaded)

# — Auswertung starten — 
if run:
    # Horizonte aufbereiten
    horizonte = build_horizonte_list(df)

    # Tabs anlegen
    tab1, tab2, tab3 = st.tabs(["Rohdaten", "Horizonte", "Ergebnisse"])

    # Tab 1: Rohdaten zeigen
    with tab1:
        st.subheader("📋 Eingelesene Rohdaten")
        st.dataframe(df, use_container_width=True)

    # Tab 2: Verarbeitete Horizonte
    with tab2:
        st.subheader("🔍 Verarbeitete Horizonte")
        horizonte_df = pd.DataFrame(horizonte)
        st.dataframe(horizonte_df, use_container_width=True)

        # Interaktives Profildiagramm
        st.markdown("**Interaktives Profildiagramm**")
        df_plot = horizonte_df.rename(columns={"z_top": "Tiefe [cm]"})
        df_melt = df_plot.melt(
            id_vars="Tiefe [cm]",
            value_vars=["pH", "humus", "bd"],
            var_name="Parameter",
            value_name="Wert"
        )
        chart = (
            alt.Chart(df_melt)
            .mark_line(point=True)
            .encode(
                x=alt.X("Wert:Q", title="Messwert"),
                y=alt.Y("Tiefe [cm]:Q", title="Tiefe (cm)", scale=alt.Scale(reverse=True)),
                color=alt.Color("Parameter:N", title="Parameter"),
                tooltip=["Parameter","Wert","Tiefe [cm]"]
            )
            .properties(height=400)
        )
        st.altair_chart(chart, use_container_width=True)

    # Oberboden-Werte extrahieren
    ober        = min(horizonte, key=lambda h: h["z_top"])
    bodentyp    = ober["Bodenart"].strip()
    bg          = bodentyp_to_bg.get(bodentyp)
    ph_wert     = ober["pH"]
    humus_wert  = ober["humus"]

    # Kalkbedarf berechnen
    df_acker = pd.read_csv("kalkbedarf_acker.csv")
    df_gruen = pd.read_csv("kalkbedarf_gruen.csv")
    kalk, msg = berechne_kalkbedarf(
        bg,
        ph_wert,
        humus_wert,
        nutzungsart=nutzung.lower(),
        df_acker=df_acker,
        df_gruen=df_gruen
    )
    kalk_value = kalk if msg is None else None

    # Humusvorrat und nFK
    _, total_hum = humusvorrat(horizonte, max_tiefe=100)
    nfk          = gesamt_nfk(horizonte, phyto)

    # Tab 3: Ergebnisse
    with tab3:
        st.subheader("✅ Zusammenfassung")
        # Kennzahlen als Metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Humusvorrat 1m (Mg/ha)", f"{total_hum*10:.1f}")
        c2.metric("pH Oberboden", f"{ph_wert:.2f}")
        c3.metric("nFK (mm)", f"{nfk:.0f}")
        c4.metric("Kalkbedarf (dt CaO/ha)", f"{kalk_value:.1f}" if kalk_value is not None else "–")

        st.markdown("---")
        # Ergebnistabelle
        result_df = pd.DataFrame([{
            "Bodentyp":                           bodentyp,
            "Bodenform":                          bodenform,
            "Physiologische Gründigkeit (cm)":    phyto,
            "Humusvorrat bis 1 m (Mg/ha)":        total_hum * 10,
            "pH Oberboden":                       ph_wert,
            "Kalkbedarf (dt CaO/ha)":             kalk_value or "",
            "nFK (mm)":                           nfk
        }])
        st.dataframe(result_df, use_container_width=True)

        # Download-Button
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
