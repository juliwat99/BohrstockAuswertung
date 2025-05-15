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
if uploaded.name.endswith(("xls", "xlsx")):
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
    ober = min(horizonte, key=lambda h: h["z_top"])
    bg   = bodentyp_to_bg.get(ober["Bodenart"])
    ph_wert    = ober["pH"]
    humus_wert = ober["humus"]
    humus_kat  = humuskategorie(humus_wert)

    # ───── DEBUG-Ausgaben ─────
    st.write("🔍 DEBUG – Suchparameter für Kalkbedarf", {
        "bg": bg,
        "Bodenart": repr(ober["Bodenart"]),
        "pH": ph_wert,
        "humus": humus_wert,
        "humus_kategorie": humus_kat,
        "nutzung": nutzung
    })

    # Tabellen laden und Kopf zeigen
    df_acker = pd.read_csv("kalkbedarf_acker.csv")
    df_gruen = pd.read_csv("kalkbedarf_gruen.csv")
    df_kalk  = df_acker if nutzung.lower()=="acker" else df_gruen
    st.write("🔍 DEBUG – gesamte Kalk-Tabelle (erste 10 Zeilen)", df_kalk.head(10))

    # Filter simulieren und Ergebnisse zeigen
    mask = (
        (df_kalk.bg == bg) &
        (df_kalk.humus_kat == humus_kat) &
        ((df_kalk.pH_lo.isna()) | (df_kalk.pH_lo <= ph_wert)) &
        ((df_kalk.pH_hi.isna()) | (ph_wert <= df_kalk.pH_hi))
    )
    st.write("🔍 DEBUG – gefilterte Zeilen (sollten CaO=17 enthalten)", df_kalk.loc[mask])
    # ────────────────────────────

    # Kalkbedarf tatsächlich berechnen
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
        kalk_text = ""
    else:
        st.success(f"Kalkbedarf: {kalk} dt CaO/ha")
        kalk_text = kalk

    # weitere Auswertungen
    _, total_hum = humusvorrat(horizonte)
    nfk = gesamt_nfk(horizonte, phyto)

    # Ergebnisse zusammenstellen
    res = {
        "Bodenform":                 bodenform,
        "Humusvorrat (Mg/ha)":       total_hum * 10,
        "nFK (mm)":                  nfk,
        "Kalkbedarf (dt CaO/ha)":    kalk_text
    }
    result_df = pd.DataFrame([res])
    st.write("### Ergebnisse", result_df)

    # 5) Download als echte Excel-Datei
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
