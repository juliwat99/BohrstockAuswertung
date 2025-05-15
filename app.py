import streamlit as st
import pandas as pd
import io

from bodenauswertung import (
    humusvorrat,
    berechne_kalkbedarf,
    gesamt_nfk,
    bodentyp_to_bg,
    build_horizonte_list,
    humuskategorie
)

st.title("Bohrstock-Auswertung")

# 1) Datei hochladen
uploaded = st.file_uploader("Excel- oder CSV-Datei hochladen", type=["xlsx","csv"])
if not uploaded:
    st.info("Bitte hochladen, um auszuwerten.")
    st.stop()

# 2) Daten einlesen
if uploaded.name.lower().endswith(("xls", "xlsx")):
    df = pd.read_excel(uploaded)
else:
    df = pd.read_csv(uploaded)

# 3) Parameter wählen
nutzung   = st.selectbox("Nutzungsart", ["Acker", "Gruenland"])
phyto     = st.number_input("Physiologische Gründigkeit (cm)", min_value=10, max_value=500, value=100)
bodenform = st.text_input("Bodenform (z.B. Braunerde)", value="")

# 4) Auswertung starten
if st.button("Auswerten"):
    horizonte = build_horizonte_list(df)

    # Oberboden-Werte
    ober        = min(horizonte, key=lambda h: h["z_top"])
    bodentyp    = ober["Bodenart"].strip()
    bg          = bodentyp_to_bg.get(bodentyp)
    ph_wert     = ober["pH"]
    humus_wert  = ober["humus"]
    humus_kat   = humuskategorie(humus_wert)

    # Kalkbedarf berechnen
    df_acker = pd.read_csv("kalkbedarf_acker.csv")
    df_gruen = pd.read_csv("kalkbedarf_gruen.csv")
    kalk, msg = berechne_kalkbedarf(
        bg,
        ph_wert,
        humus_wert,
        nutzung.lower(),
        df_acker,
        df_gruen
    )
    if msg:
        st.warning(msg)
        kalk_value = ""
    else:
        kalk_value = kalk

    # weitere Auswertungen
    _, total_hum = humusvorrat(horizonte)
    nfk = gesamt_nfk(horizonte, phyto)

    # 5) Ergebnisse in Tabelle zusammenstellen
    result_df = pd.DataFrame([{
        "Bodentyp":                             bodentyp,
        "Bodenform":                            bodenform,
        "Physiologische Gründigkeit (cm)":      phyto,
        "Humusvorrat bis 1 m (Mg/ha)":          total_hum * 10,
        "pH Oberboden":                         ph_wert,
        "Kalkbedarf (dt CaO/ha)":               kalk_value,
        "nFK (mm)":                             nfk
    }])

    st.write("### Ergebnisse", result_df)

    # 6) Download als echte Excel-Datei
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
