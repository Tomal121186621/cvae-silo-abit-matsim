#!/usr/bin/env python3
"""Figure: resident share captured by facility, decomposed into accepted non-resident vs resident shortfall."""
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from netval2023_common import ROOT, OUTDIR

OUT=OUTDIR
FIG=OUT/"figures"; FIG.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({"font.family":"serif","font.serif":["Times New Roman","Times","DejaVu Serif"],
    "mathtext.fontset":"stix","font.size":10,"axes.titlesize":12,"axes.labelsize":10,
    "legend.fontsize":8.5,"xtick.labelsize":9.5,"ytick.labelsize":9,"savefig.dpi":600,"figure.dpi":120})

# out-of-scope (non-resident personal/through) band midpoints, matching analyze_resident_validation.py
NONRES_MID={"Interstate/Freeway":0.325,"Principal Arterial":0.17,"Minor Arterial":0.09,"Collector/Local":0.055}
ORDER=["Interstate/Freeway","Principal Arterial","Minor Arterial","Collector/Local"]

def main():
    t=pd.read_csv(OUT/"resident_capture_by_facility.csv").set_index("facility")
    labels=[f.replace(" ","\n").replace("/","/\n") for f in ORDER]
    cap=np.array([t.loc[f,"agg_ratio"] for f in ORDER])
    comm=np.array([ (t.loc[f,"comm_pct"] if pd.notna(t.loc[f,"comm_pct"]) else 4)/100.0 for f in ORDER])
    oos=comm+np.array([NONRES_MID[f] for f in ORDER])       # accepted non-resident+commercial (of total)
    resid=np.clip(1-cap-oos,0,1)                            # residual RESIDENT shortfall (of total)
    x=np.arange(len(ORDER))
    fig,ax=plt.subplots(figsize=(7.4,4.6))
    b1=ax.bar(x,cap,color="#27AE60",edgecolor="white",label="Resident demand captured (model $\\times$10 / AADT)")
    b2=ax.bar(x,oos,bottom=cap,color="#95A5A6",edgecolor="white",
              label="Out-of-scope: non-resident + commercial/freight/through (ACCEPTED)")
    b3=ax.bar(x,resid,bottom=cap+oos,color="#C0392B",alpha=0.85,edgecolor="white",
              label="Residual RESIDENT shortfall (trip-length truncation)")
    for i in range(len(ORDER)):
        ax.text(i,cap[i]/2,f"{cap[i]:.2f}",ha="center",va="center",color="white",fontsize=9,fontweight="bold")
        ax.text(i,cap[i]+oos[i]/2,f"{oos[i]*100:.0f}%",ha="center",va="center",color="white",fontsize=8.5)
        if resid[i]>0.04: ax.text(i,cap[i]+oos[i]+resid[i]/2,f"{resid[i]*100:.0f}%",ha="center",va="center",color="white",fontsize=8.5)
    ax.axhline(1.0,color="k",lw=0.8,ls="--")
    ax.text(len(ORDER)-1,1.015,"observed total (all vehicles)",ha="right",va="bottom",fontsize=8,style="italic",color="#555")
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel("Share of observed AADT 2023"); ax.set_ylim(0,1.13)
    ax.set_title("Resident-only assignment: where the volume gap comes from, by facility", pad=12)
    ax.legend(loc="upper center",bbox_to_anchor=(0.5,-0.10),frameon=True,ncol=1)
    fig.tight_layout(); fig.savefig(FIG/"e_resident_capture_by_facility.png",bbox_inches="tight"); plt.close()
    print("wrote",FIG/"e_resident_capture_by_facility.png")

if __name__=="__main__":
    main()
