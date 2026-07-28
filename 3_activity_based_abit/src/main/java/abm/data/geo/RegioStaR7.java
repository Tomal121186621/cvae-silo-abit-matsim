package abm.data.geo;

//Todo: ask Joanna for double checking the regio type definition
public enum RegioStaR7 {

    URBAN_METROPOLIS(71),
    URBAN_REGIOPOLIS(72),
    URBAN_MEDIUM_SIZED_CITY(73),
    URBAN_PROVINCIAL(74),
    RURAL_CENTRAL_CITY(75),
    RURAL_URBAN_AREA(76),
    RURAL_PROVICIAL(77);


    private final int code;

    RegioStaR7(int code) {
        this.code = code;
    }

    public static RegioStaR7 valueOf(int code) {
        switch (code) {
            case 71:
                return URBAN_METROPOLIS;
            case 72:
                return URBAN_REGIOPOLIS;
            case 73:
                return URBAN_MEDIUM_SIZED_CITY;
            case 74:
                return URBAN_PROVINCIAL;
            case 75:
                return RURAL_CENTRAL_CITY;
            case 76:
                return RURAL_URBAN_AREA;
            case 77:
                return RURAL_PROVICIAL;
            default:
                throw new RuntimeException("Area Type for code " + code + " not specified in SGtyp classification.");
        }
    }

    public int code() {
        return code;
    }

}
