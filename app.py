import streamlit as st
import pandas as pd
from bodenauswertung import humusvorrat, berechne_kalkbedarf, gesamt_nfk, bodentyp_to_bg

st.title("Bohrstock-Auswertung")

# 1) Datei hochladen
uploaded = st.file_uploader("Excel- oder CSV-Datei hochladen", type=["xlsx","csv"])
if not uploaded:
    st.info("Bitte hochladen, um auszuwerten.")
    st.stop()

# 2) Daten einlesen
if uploaded.name.endswith(("xls","xlsx")):
    df = pd.read_excel(uploaded)
else:
    df = pd.read_csv(uploaded)

# 3) Parameter wählen
nutzung = st.selectbox("Nutzungsart", ["acker","gruenland"])
phyto  = st.number_input("Physiologische Gründigkeit (cm)", min_value=10, max_value=500, value=100)

# 4) Auswertung starten
if st.button("Auswerten"):
    # Hier musst du deine Logik auf df anwenden:
    # (Spalten finden, parse_range, Horizon-Liste bauen etc.)
    horizonte = build_horizonte_list(df)  # schreibe dir eine Hilfsfunktion
    # Oberboden-Werte
    ober = min(horizonte, key=lambda h: h["z_top"])
    bg = bodentyp_to_bg.get(ober["Bodenart"])
    kalk, _ = berechne_kalkbedarf(bg, ober["pH"], ober["humus"], nutzung,
                                  pd.read_csv("kalkbedarf_acker.csv"),
                                  pd.read_csv("kalkbedarf_gruen.csv"))
    humus_df, total_hum = humusvorrat(horizonte)
    nfk = gesamt_nfk(horizonte, phyto)

    res = {
      "Humusvorrat (Mg/ha)": total_hum*10,
      "nFK (mm)": nfk,
      "Kalkbedarf (dt CaO/ha)": kalk
    }
    result_df = pd.DataFrame([res])
    st.write("### Ergebnisse", result_df)

    # 5) Download
    towrite = result_df.to_excel(index=False)
    st.download_button("Ergebnis als Excel herunterladen", data=towrite, file_name="ergebnis.xlsx")
