package abm.data.pop;

public enum EconomicStatus {

    //Todo: It seems like MOP doesn't have the definition of economic status. I checked the read.MOP.r, the economic status is classified into 4 levels: 1 for hh.incomeEUR/hh.sizeAdj <= 800, 2 for hh.incomeEUR/hh.sizeAdj <= 1600, 3 for hh.incomeEUR/hh.sizeAdj <= 2400, 4 for hh.incomeEUR/hh.sizeAdj > 2400. The economic status is changed based on the R script. Please make any change if needed

    from0to800,
    from801to1600,
    from1601to2400,
    from2401;

    private static final EconomicStatus[] ENUMS = values();

    public static EconomicStatus assignEconomicStatus(int EurPerAdjPerson) {
        if (EurPerAdjPerson <= 800) {
            return from0to800;
        } else if (EurPerAdjPerson <= 1600) {
            return from801to1600;
        } else if (EurPerAdjPerson <= 2400) {
            return from1601to2400;
        } else {
            return from2401;
        }
    }

    public static EconomicStatus of(int economicStatus) {
        if (economicStatus >= 1 && economicStatus <= 4) {
            return ENUMS[economicStatus - 1];
        } else {
            throw new IllegalArgumentException("Invalid value for economic status: " + economicStatus);
        }
    }

}
